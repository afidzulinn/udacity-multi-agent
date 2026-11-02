#!/usr/bin/env bash
# deploy.sh - Tasks 3, 4 and 6 in one command (run after create_kbs.py):
#   1. install the AgentCore CLI toolchain if missing (uv, Node.js 20+, @aws/agentcore@0.30.0)
#      into the user's home - no sudo needed
#   2. python src/agent_orchestrator.py deploy   (guardrail, runtime, memory, observability;
#      writes AGENTCORE_RUNTIME_ARN / GUARDRAIL_ID / GUARDRAIL_VERSION to .env)
#   3. python src/agent_orchestrator.py test     (3 scenarios -> X-Ray traces for the Service Map)
#   4. python tests/test_agent.py all            (the 120-point score)
# Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
NODE_VERSION=v22.12.0
LOCAL="$HOME/.local"
export PATH="$LOCAL/bin:$LOCAL/node/bin:$("$PY" -c 'import sysconfig; print(sysconfig.get_path("scripts"))'):$PATH"

aws sts get-caller-identity >/dev/null || { echo "Not logged in - run: bash aws.sh"; exit 1; }
grep -q '^RETURNS_KB_ID=..*' .env || { echo "Knowledge Base IDs missing in .env - run: python create_kbs.py"; exit 1; }

echo "== 1/4 AgentCore CLI toolchain"
command -v uv >/dev/null || "$PY" -m pip install -q uv
node_major=$(node -v 2>/dev/null | sed 's/^v\([0-9]*\).*/\1/' || true)
if [ "${node_major:-0}" -lt 20 ]; then
  case "$(uname -m)" in x86_64) arch=x64 ;; aarch64|arm64) arch=arm64 ;; *) echo "Unsupported CPU $(uname -m)"; exit 1 ;; esac
  echo "Installing Node.js $NODE_VERSION into $LOCAL/node"
  mkdir -p "$LOCAL/node"
  curl -fsSL "https://nodejs.org/dist/$NODE_VERSION/node-$NODE_VERSION-linux-$arch.tar.gz" \
    | tar -xz -C "$LOCAL/node" --strip-components=1
fi
# The old Python starter toolkit installs a conflicting `agentcore` command
"$PY" -m pip show -q bedrock-agentcore-starter-toolkit >/dev/null 2>&1 \
  && "$PY" -m pip uninstall -y -q bedrock-agentcore-starter-toolkit
if [ "$(agentcore --version 2>/dev/null || true)" != "0.30.0" ]; then
  npm install -g --silent --prefix "$LOCAL" @aws/agentcore@0.30.0
fi
echo "node $(node -v) | uv $(uv --version | cut -d' ' -f2) | agentcore $(agentcore --version)"

echo "== 2/4 Deploy (first run bootstraps CDK - 10-15 minutes)"
"$PY" src/agent_orchestrator.py deploy

echo "== 3/4 Test scenarios (X-Ray traces)"
"$PY" src/agent_orchestrator.py test

echo "== 4/4 Full test suite"
"$PY" tests/test_agent.py all
echo "Next: CloudWatch console -> X-Ray traces -> Service map, take the screenshot."
