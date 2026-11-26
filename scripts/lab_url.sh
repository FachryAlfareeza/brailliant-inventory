#!/usr/bin/env bash
# Finds the public IP of the running container and saves the API URL.
# (Without a load balancer the IP changes every time the container restarts.)
set -euo pipefail
source "$(dirname "$0")/lab_config.sh"

TASK=$(aws ecs list-tasks --cluster $CLUSTER --service-name $SERVICE --desired-status RUNNING \
  --query "taskArns[0]" --output text)
if [[ "$TASK" == "None" ]]; then
  echo "No running container. Start it with: bash scripts/lab_start.sh"
  exit 1
fi
ENI=$(aws ecs describe-tasks --cluster $CLUSTER --tasks $TASK \
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value | [0]" --output text)
IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI \
  --query "NetworkInterfaces[0].Association.PublicIp" --output text)
echo "http://$IP:8080" > $URL_FILE
echo "API URL: http://$IP:8080"
echo "Test it with: bash scripts/test_api.sh"
