#!/usr/bin/env bash
# Starts the container again (1 running) and prints the new URL.
set -euo pipefail
source "$(dirname "$0")/lab_config.sh"
aws ecs update-service --cluster $CLUSTER --service $SERVICE --desired-count 1 >/dev/null
echo "starting (a few minutes)..."
aws ecs wait services-stable --cluster $CLUSTER --services $SERVICE
bash scripts/lab_url.sh
