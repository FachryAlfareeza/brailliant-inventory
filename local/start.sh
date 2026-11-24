#!/usr/bin/env bash
# Local emulation of the Track C stack (no AWS account needed):
#   SAM CLI "sam local start-api"  ->  Lambda container (python3.13)  ->  DynamoDB Local container
# The API listens on http://127.0.0.1:3000. Press Ctrl+C to stop it; run local/stop.sh to remove the DB.
set -euo pipefail
# Under PowerShell, plain "bash" starts WSL, which can't see Docker Desktop or the Windows tools.
if [[ "$(uname -s)" == Linux* ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  echo "This is WSL bash. Run the script with Git Bash instead, e.g. from PowerShell:"
  echo '  & "C:\Program Files\Git\bin\bash.exe" '"$0"
  exit 1
fi
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1 AWS_PAGER=""

NET=kompaw-local
DB=kompaw-dynamodb
PORT=${PORT:-3000}
DB_PORT=${DB_PORT:-8010}   # host port; 8000 is often taken
# DynamoDB Local accepts any credentials; these never leave the PC.
DDB_ENV=(env AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local AWS_DEFAULT_REGION=us-east-1)

SAM=sam
command -v sam >/dev/null 2>&1 || SAM=".venv-sam/Scripts/sam.exe"
[[ -x "$SAM" ]] || command -v "$SAM" >/dev/null || { echo "SAM CLI not found (see README: local emulation)"; exit 1; }

echo "==> Docker"
docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop and retry."; exit 1; }
docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET" >/dev/null

echo "==> DynamoDB Local ($DB on localhost:$DB_PORT)"
if [[ -z "$(docker ps -q -f name=^${DB}$)" ]]; then
  docker rm -f "$DB" >/dev/null 2>&1 || true
  docker run -d --name "$DB" --network "$NET" -p "$DB_PORT":8000 \
    amazon/dynamodb-local:latest -jar DynamoDBLocal.jar -sharedDb -inMemory >/dev/null
fi
for i in $(seq 1 30); do
  "${DDB_ENV[@]}" aws dynamodb list-tables --endpoint-url "http://localhost:$DB_PORT" >/dev/null 2>&1 && break
  sleep 1
done
if "${DDB_ENV[@]}" aws dynamodb describe-table --table-name brailliant-parts \
     --endpoint-url "http://localhost:$DB_PORT" >/dev/null 2>&1; then
  echo "table brailliant-parts exists"
else
  "${DDB_ENV[@]}" aws dynamodb create-table --endpoint-url "http://localhost:$DB_PORT" \
    --table-name brailliant-parts \
    --attribute-definitions AttributeName=partId,AttributeType=S \
    --key-schema AttributeName=partId,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  echo "table brailliant-parts created"
fi

echo "==> sam validate + build"
"$SAM" validate --lint
"$SAM" build

echo "==> sam local start-api on http://127.0.0.1:$PORT  (Ctrl+C to stop)"
exec "$SAM" local start-api \
  --port "$PORT" \
  --docker-network "$NET" \
  --env-vars local/env.json \
  --parameter-overrides Architecture=x86_64 \
  --warm-containers EAGER
