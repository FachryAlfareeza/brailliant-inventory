#!/usr/bin/env bash
# Provision the Track C stack: DynamoDB table -> Lambda (LabRole) -> API Gateway HTTP API.
# Safe to re-run: each step reuses what already exists.
#
# Run it from the Learner Lab terminal, or locally after pasting the lab's
# "AWS CLI" credentials into ~/.aws/credentials.
set -euo pipefail
source "$(dirname "$0")/config.sh"

log "Checking credentials"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo "Account $ACCOUNT_ID, region $AWS_REGION, role $ROLE_ARN"

# ---------------------------------------------------------------- DynamoDB
log "DynamoDB table $TABLE_NAME"
if aws dynamodb describe-table --table-name "$TABLE_NAME" >/dev/null 2>&1; then
  echo "exists"
else
  aws dynamodb create-table \
    --table-name "$TABLE_NAME" \
    --attribute-definitions AttributeName=partId,AttributeType=S \
    --key-schema AttributeName=partId,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --tags Key=Project,Value="$PROJECT" >/dev/null
  echo "created, waiting until ACTIVE..."
fi
aws dynamodb wait table-exists --table-name "$TABLE_NAME"
TABLE_ARN=$(aws dynamodb describe-table --table-name "$TABLE_NAME" --query Table.TableArn --output text)

# ---------------------------------------------------------------- Lambda
log "Packaging Lambda"
mkdir -p "$BUILD_DIR"
"$PY" - "$ROOT/src/app.py" "$BUILD_DIR/function.zip" <<'EOF'
import sys, zipfile
with zipfile.ZipFile(sys.argv[2], "w", zipfile.ZIP_DEFLATED) as z:
    z.write(sys.argv[1], "app.py")
EOF
ls -l "$BUILD_DIR/function.zip"

log "Lambda function $FUNCTION_NAME"
if aws lambda get-function --function-name "$FUNCTION_NAME" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$BUILD_DIR/function.zip" >/dev/null
  aws lambda wait function-updated-v2 --function-name "$FUNCTION_NAME"
  echo "code updated"
else
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.13 \
    --architectures arm64 \
    --handler app.lambda_handler \
    --role "$ROLE_ARN" \
    --zip-file "fileb://$BUILD_DIR/function.zip" \
    --timeout 10 --memory-size 128 \
    --environment "Variables={TABLE_NAME=$TABLE_NAME}" \
    --tags Project="$PROJECT" >/dev/null
  aws lambda wait function-active-v2 --function-name "$FUNCTION_NAME"
  echo "created"
fi
FUNCTION_ARN=$(aws lambda get-function --function-name "$FUNCTION_NAME" --query Configuration.FunctionArn --output text)

# Keep logs from piling up (and costing) after the course.
aws logs create-log-group --log-group-name "/aws/lambda/$FUNCTION_NAME" 2>/dev/null || true
aws logs put-retention-policy --log-group-name "/aws/lambda/$FUNCTION_NAME" \
  --retention-in-days "$LOG_RETENTION_DAYS"

# ---------------------------------------------------------------- API Gateway
log "HTTP API $API_NAME"
API_ID=$(aws apigatewayv2 get-apis --query "Items[?Name=='$API_NAME'].ApiId | [0]" --output text)
if [[ -z "$API_ID" || "$API_ID" == "None" ]]; then
  API_ID=$(aws apigatewayv2 create-api --name "$API_NAME" --protocol-type HTTP \
    --cors-configuration AllowOrigins="*",AllowMethods="GET,POST,PUT,DELETE",AllowHeaders="content-type" \
    --tags Project="$PROJECT" --query ApiId --output text)
  echo "created $API_ID"
else
  echo "exists $API_ID"
fi

INTEGRATION_ID=$(aws apigatewayv2 get-integrations --api-id "$API_ID" \
  --query "Items[?IntegrationUri=='$FUNCTION_ARN'].IntegrationId | [0]" --output text)
if [[ -z "$INTEGRATION_ID" || "$INTEGRATION_ID" == "None" ]]; then
  INTEGRATION_ID=$(aws apigatewayv2 create-integration --api-id "$API_ID" \
    --integration-type AWS_PROXY --integration-uri "$FUNCTION_ARN" \
    --payload-format-version 2.0 --query IntegrationId --output text)
fi
echo "integration $INTEGRATION_ID"

for ROUTE in "POST /parts" "GET /parts" "GET /parts/{partId}" "PUT /parts/{partId}" \
             "DELETE /parts/{partId}" "GET /health"; do
  if [[ $(aws apigatewayv2 get-routes --api-id "$API_ID" \
          --query "length(Items[?RouteKey=='$ROUTE'])" --output text) != "0" ]]; then
    echo "route exists: $ROUTE"
  else
    aws apigatewayv2 create-route --api-id "$API_ID" --route-key "$ROUTE" \
      --target "integrations/$INTEGRATION_ID" >/dev/null
    echo "route created: $ROUTE"
  fi
done

if ! aws apigatewayv2 get-stage --api-id "$API_ID" --stage-name '$default' >/dev/null 2>&1; then
  aws apigatewayv2 create-stage --api-id "$API_ID" --stage-name '$default' --auto-deploy \
    --default-route-settings ThrottlingBurstLimit=20,ThrottlingRateLimit=10 >/dev/null
  echo "stage \$default created (auto-deploy, throttled 10 rps / burst 20)"
fi

# Resource-based policy: only this API may invoke the function.
aws lambda add-permission --function-name "$FUNCTION_NAME" \
  --statement-id apigw-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*/*" \
  >/dev/null 2>&1 && echo "invoke permission added" || echo "invoke permission already present"

API_URL="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com"
echo "$API_URL" > "$STATE_FILE"

log "Done"
cat <<EOF
Table    : $TABLE_ARN
Function : $FUNCTION_ARN
API URL  : $API_URL
Next     : bash infra/smoke_test.sh
EOF
