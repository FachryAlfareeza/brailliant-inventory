#!/usr/bin/env bash
# Delete everything deploy.sh created, to stop any further Learner Lab spend.
set -uo pipefail
source "$(dirname "$0")/config.sh"

read -r -p "Delete API '$API_NAME', function '$FUNCTION_NAME' and table '$TABLE_NAME' (all data)? [y/N] " ok
[[ "$ok" == "y" || "$ok" == "Y" ]] || { echo "Cancelled."; exit 0; }

for API_ID in $(aws apigatewayv2 get-apis --query "Items[?Name=='$API_NAME'].ApiId" --output text); do
  aws apigatewayv2 delete-api --api-id "$API_ID" && echo "deleted API $API_ID"
done
aws lambda delete-function --function-name "$FUNCTION_NAME" && echo "deleted function"
aws logs delete-log-group --log-group-name "/aws/lambda/$FUNCTION_NAME" 2>/dev/null && echo "deleted log group"
aws dynamodb delete-table --table-name "$TABLE_NAME" >/dev/null && echo "deleted table"
rm -f "$STATE_FILE"
