"""
create_kbs.py - create and sync the three Bedrock Knowledge Bases (Task 5).

Same result as the console steps in .env.example:
  - one KB per policy prefix (policies/returns/, shipping/, warranty/)
  - embedding model amazon.titan-embed-text-v2:0 (1024 dimensions)
  - S3 Vectors store: the stack's vector bucket + matching index
  - service role: the stack's agentcore role (trusts bedrock.amazonaws.com,
    can read the policy bucket, invoke the embedding model and use S3 Vectors)
Writes RETURNS_KB_ID / SHIPPING_KB_ID / WARRANTY_KB_ID to .env.

Safe to re-run: existing KBs and data sources are reused and synced again.

Usage:  python create_kbs.py
"""

import os
import sys
import time

import boto3
from dotenv import set_key

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402

ENV_PATH = os.path.join(HERE, '.env')
EMBEDDING_MODEL_ARN = (f"arn:aws:bedrock:{config.AWS_REGION}::foundation-model/"
                       f"amazon.titan-embed-text-v2:0")

# (.env key, knowledge base name, S3 prefix, config attribute holding the vector index name)
KNOWLEDGE_BASES = [
    ('RETURNS_KB_ID',  'novamart-returns-policy-kb',  'policies/returns/',  'RETURNS_VECTOR_INDEX'),
    ('SHIPPING_KB_ID', 'novamart-shipping-policy-kb', 'policies/shipping/', 'SHIPPING_VECTOR_INDEX'),
    ('WARRANTY_KB_ID', 'novamart-warranty-policy-kb', 'policies/warranty/', 'WARRANTY_VECTOR_INDEX'),
]

bedrock_agent = boto3.client('bedrock-agent', region_name=config.AWS_REGION)


def wait_for(get_item, label: str, done: str, failed: tuple, timeout: int = 600) -> dict:
    """Poll get_item() until its status is `done`; raise on a failed status or timeout."""
    deadline = time.time() + timeout
    while True:
        item = get_item()
        status = item.get('status')
        if status == done:
            return item
        if status in failed:
            reasons = item.get('failureReasons') or ''
            raise RuntimeError(f"{label} ended with status {status} {reasons}")
        if time.time() > deadline:
            raise TimeoutError(f"{label} still {status} after {timeout}s")
        time.sleep(5)


def ensure_knowledge_base(name: str, index_name: str) -> str:
    """Return the ID of the KB called `name`, creating it if it does not exist."""
    for page in bedrock_agent.get_paginator('list_knowledge_bases').paginate():
        for kb in page['knowledgeBaseSummaries']:
            if kb['name'] == name:
                print(f"  KB exists      : {name} ({kb['knowledgeBaseId']})")
                return kb['knowledgeBaseId']

    kb_id = bedrock_agent.create_knowledge_base(
        name=name,
        description=f"NovaMart policy documents ({index_name})",
        roleArn=config.AGENTCORE_ROLE_ARN,
        knowledgeBaseConfiguration={
            'type': 'VECTOR',
            'vectorKnowledgeBaseConfiguration': {
                'embeddingModelArn': EMBEDDING_MODEL_ARN,
                'embeddingModelConfiguration': {
                    'bedrockEmbeddingModelConfiguration': {
                        'dimensions': 1024,             # matches the stack's vector indexes
                        'embeddingDataType': 'FLOAT32',
                    },
                },
            },
        },
        storageConfiguration={
            'type': 'S3_VECTORS',
            's3VectorsConfiguration': {
                'vectorBucketArn': config.VECTOR_STORE_BUCKET_ARN,
                'indexName': index_name,
            },
        },
    )['knowledgeBase']['knowledgeBaseId']
    print(f"  KB created     : {name} ({kb_id}) - waiting for ACTIVE")
    wait_for(lambda: bedrock_agent.get_knowledge_base(knowledgeBaseId=kb_id)['knowledgeBase'],
             f"Knowledge base {name}", 'ACTIVE', ('FAILED', 'DELETE_UNSUCCESSFUL'))
    return kb_id


def ensure_data_source(kb_id: str, prefix: str) -> str:
    """Return the KB's S3 data source ID, creating one for `prefix` if there is none."""
    existing = bedrock_agent.list_data_sources(knowledgeBaseId=kb_id)['dataSourceSummaries']
    if existing:
        return existing[0]['dataSourceId']
    ds_id = bedrock_agent.create_data_source(
        knowledgeBaseId=kb_id,
        name=prefix.strip('/').replace('/', '-'),
        dataSourceConfiguration={
            'type': 'S3',
            's3Configuration': {
                'bucketArn': f"arn:aws:s3:::{config.POLICY_BUCKET}",
                'inclusionPrefixes': [prefix],
            },
        },
    )['dataSource']['dataSourceId']
    print(f"  Data source    : s3://{config.POLICY_BUCKET}/{prefix} ({ds_id})")
    return ds_id


def sync(kb_id: str, ds_id: str) -> None:
    """Run an ingestion job (the console's Sync button) and wait for it to finish."""
    job_id = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=kb_id, dataSourceId=ds_id)['ingestionJob']['ingestionJobId']
    job = wait_for(
        lambda: bedrock_agent.get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id)['ingestionJob'],
        f"Sync of {kb_id}", 'COMPLETE', ('FAILED', 'STOPPED'))
    stats = job.get('statistics', {})
    print(f"  Synced         : {stats.get('numberOfNewDocumentsIndexed', 0)} new, "
          f"{stats.get('numberOfModifiedDocumentsIndexed', 0)} modified, "
          f"{stats.get('numberOfDocumentsFailed', 0)} failed")


def main() -> None:
    if not os.path.exists(ENV_PATH):
        sys.exit(".env not found - run: bash infra_setup.sh")
    for env_key, name, prefix, index_attr in KNOWLEDGE_BASES:
        print(f"\n{env_key}")
        kb_id = ensure_knowledge_base(name, getattr(config, index_attr))
        sync(kb_id, ensure_data_source(kb_id, prefix))
        set_key(ENV_PATH, env_key, kb_id, quote_mode='never')
        print(f"  .env           : {env_key}={kb_id}")
    print("\nDone. Next: python tests/test_agent.py task5")


if __name__ == '__main__':
    main()
