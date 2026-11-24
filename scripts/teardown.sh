#!/usr/bin/env bash
# Deletes everything deploy.sh made (the budget is free so it stays).
set -uo pipefail
source "$(dirname "$0")/config.sh"

read -r -p "Delete the API, function, table (with all data) and role? [y/N] " ok
[[ "$ok" == y || "$ok" == Y ]] || exit 0

for id in $(aws apigatewayv2 get-apis --query "Items[?Name=='$API_NAME'].ApiId" --output text); do
  aws apigatewayv2 delete-api --api-id $id && echo "deleted API $id"
done
aws lambda delete-function --function-name $FUNCTION_NAME && echo "deleted function"
aws logs delete-log-group --log-group-name /aws/lambda/$FUNCTION_NAME 2>/dev/null && echo "deleted logs"
aws dynamodb delete-table --table-name $TABLE_NAME >/dev/null && echo "deleted table"

# never touch LabRole, only the role this project created
if aws iam get-role --role-name $ROLE_NAME_OWN >/dev/null 2>&1; then
  aws iam delete-role-policy --role-name $ROLE_NAME_OWN --policy-name parts-table-access
  aws iam delete-role --role-name $ROLE_NAME_OWN && echo "deleted role"
fi
rm -f $URL_FILE
