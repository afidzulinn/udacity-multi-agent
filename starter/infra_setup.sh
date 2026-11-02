#!/usr/bin/env bash
# infra_setup.sh - one-time setup after `bash aws.sh` (no copy/paste needed):
#   1. install Python dependencies
#   2. deploy the CloudFormation stack (udacity-agentcore, us-east-1)
#   3. seed DynamoDB + S3 policy documents
#   4. create .env from .env.example (kept if it already exists)
#   5. print the configuration and run the Task 2 tests
# Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"

aws sts get-caller-identity >/dev/null || { echo "Not logged in - run: bash aws.sh"; exit 1; }

echo "== 1/5 Installing Python dependencies"
"$PY" -m pip install -q -r requirements.txt

echo "== 2/5 Deploying CloudFormation stack udacity-agentcore (takes a few minutes)"
aws cloudformation deploy \
  --template-file infrastructure/starter_stack.yaml \
  --stack-name udacity-agentcore \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1 \
  --no-fail-on-empty-changeset

echo "== 3/5 Seeding data"
"$PY" infrastructure/seed_data.py

echo "== 4/5 .env"
[ -f .env ] && echo ".env exists - kept" || { cp .env.example .env; echo ".env created"; }

echo "== 5/5 Configuration + Task 2 tests"
"$PY" config.py
"$PY" tests/test_agent.py task2
