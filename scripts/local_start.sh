#!/usr/bin/env bash
# Runs the API on this PC without AWS:
#   sam local start-api (Lambda in Docker) + DynamoDB Local (also Docker)
# API: http://127.0.0.1:3000   Stop: Ctrl+C, then scripts/local_stop.sh
# OCR (Textract) is switched off locally, everything else works.
set -euo pipefail
source "$(dirname "$0")/config.sh"

NETWORK=kompaw-local
DB_CONTAINER=kompaw-dynamodb
DB_PORT=${DB_PORT:-8010}   # 8000 is already used by another project on my PC
local_aws() {  # DynamoDB Local accepts any credentials
  AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local aws "$@" --endpoint-url http://localhost:$DB_PORT
}

docker info >/dev/null 2>&1 || { echo "Docker isn't running, start Docker Desktop first."; exit 1; }
docker network inspect $NETWORK >/dev/null 2>&1 || docker network create $NETWORK >/dev/null

bash scripts/build_layer.sh

echo "== DynamoDB Local on port $DB_PORT"
if [[ -z "$(docker ps -q -f name=^$DB_CONTAINER$)" ]]; then
  docker rm -f $DB_CONTAINER >/dev/null 2>&1 || true
  docker run -d --name $DB_CONTAINER --network $NETWORK -p $DB_PORT:8000 \
    amazon/dynamodb-local -jar DynamoDBLocal.jar -sharedDb -inMemory >/dev/null
fi
for i in $(seq 30); do
  local_aws dynamodb list-tables >/dev/null 2>&1 && break
  sleep 1
done
if ! local_aws dynamodb describe-table --table-name $TABLE_NAME >/dev/null 2>&1; then
  local_aws dynamodb create-table --table-name $TABLE_NAME \
    --attribute-definitions AttributeName=scanId,AttributeType=S \
    --key-schema AttributeName=scanId,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  echo "created table $TABLE_NAME"
fi

echo "== sam build"
$SAM validate --lint
$SAM build

echo "== sam local start-api"
exec $SAM local start-api --port 3000 \
  --docker-network $NETWORK \
  --env-vars scripts/local_env.json \
  --warm-containers EAGER
