#!/usr/bin/env bash
# Delete everything deploy.sh created, to stop any further spend.
# The cost budget is kept (budgets are free); delete it in the console if you want.
set -uo pipefail
source "$(dirname "$0")/config.sh"

read -r -p "Delete API '$API_NAME', function '$FUNCTION_NAME', role '$OWN_ROLE_NAME' and table '$TABLE_NAME' (all data)? [y/N] " ok
[[ "$ok" == "y" || "$ok" == "Y" ]] || { echo "Cancelled."; exit 0; }

for API_ID in $(aws apigatewayv2 get-apis --query "Items[?Name=='$API_NAME'].ApiId" --output text); do
  aws apigatewayv2 delete-api --api-id "$API_ID" && echo "deleted API $API_ID"
done
aws lambda delete-function --function-name "$FUNCTION_NAME" && echo "deleted function"
aws logs delete-log-group --log-group-name "/aws/lambda/$FUNCTION_NAME" 2>/dev/null && echo "deleted log group"
aws dynamodb delete-table --table-name "$TABLE_NAME" >/dev/null && echo "deleted table"

# Only the role this project created; never LabRole.
if aws iam get-role --role-name "$OWN_ROLE_NAME" >/dev/null 2>&1; then
  aws iam delete-role-policy --role-name "$OWN_ROLE_NAME" --policy-name parts-table-access 2>/dev/null
  aws iam delete-role --role-name "$OWN_ROLE_NAME" && echo "deleted role $OWN_ROLE_NAME"
fi
rm -f "$STATE_FILE"
