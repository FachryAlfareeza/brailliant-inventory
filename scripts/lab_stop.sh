#!/usr/bin/env bash
# Stops the container (0 running), so Fargate stops charging. The scans stay in S3.
set -euo pipefail
source "$(dirname "$0")/lab_config.sh"
aws ecs update-service --cluster $CLUSTER --service $SERVICE --desired-count 0 >/dev/null
rm -f $URL_FILE
echo "stopped (start again with: bash scripts/lab_start.sh)"
