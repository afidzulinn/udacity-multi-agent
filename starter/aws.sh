#!/usr/bin/env bash
# aws.sh - log the AWS CLI / boto3 in with the credentials saved in aws.txt.
#
# Usage:  bash aws.sh            (reads aws.txt next to this script)
#         bash aws.sh other.txt  (reads another file)
#
# aws.txt may use either format (paste it straight from the Udacity Cloud Lab page):
#   [default]                                export AWS_ACCESS_KEY_ID=ASIA...
#   aws_access_key_id = ASIA...              export AWS_SECRET_ACCESS_KEY=...
#   aws_secret_access_key = ...              export AWS_SESSION_TOKEN=...
#   aws_session_token = ...
#
# aws.txt holds secrets: it is in .gitignore - never commit or share it.
set -euo pipefail

FILE="${1:-$(dirname "$0")/aws.txt}"
REGION="${AWS_REGION:-us-east-1}"   # the project runs in us-east-1

command -v aws >/dev/null || { echo "AWS CLI not found - install it first: https://aws.amazon.com/cli/"; exit 1; }
[ -f "$FILE" ] || { echo "File not found: $FILE"; exit 1; }

KEY_ID=""; SECRET=""; TOKEN=""
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%$'\r'}"                     # Windows line endings
  line="${line#"${line%%[![:space:]]*}"}"  # leading spaces
  line="${line#export }"
  [[ "$line" =~ ^([A-Za-z_]+)[[:space:]]*=[[:space:]]*(.*)$ ]] || continue
  key=$(printf '%s' "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]')
  val="${BASH_REMATCH[2]}"
  val="${val%"${val##*[![:space:]]}"}"     # trailing spaces
  val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
  case "$key" in
    aws_access_key_id)     KEY_ID="$val" ;;
    aws_secret_access_key) SECRET="$val" ;;
    aws_session_token)     TOKEN="$val" ;;
  esac
done < "$FILE"

missing=""
[ -n "$KEY_ID" ] || missing="$missing aws_access_key_id"
[ -n "$SECRET" ] || missing="$missing aws_secret_access_key"
if [ -n "$missing" ]; then
  echo "Missing in $FILE:$missing"
  echo "Copy all credential lines from the Cloud Lab page (not only the session token)."
  exit 1
fi

aws configure set aws_access_key_id     "$KEY_ID"
aws configure set aws_secret_access_key "$SECRET"
aws configure set aws_session_token     "$TOKEN"   # empty clears a stale token from an old lab
aws configure set region "$REGION"
aws configure set output json
unset KEY_ID SECRET TOKEN

echo "Checking credentials..."
if aws sts get-caller-identity --output table; then
  echo "Logged in. Region: $REGION. Next: python config.py"
else
  echo "Login failed - the keys are wrong or the lab session expired. Update $FILE and run again."
  exit 1
fi
