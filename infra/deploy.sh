#!/usr/bin/env bash
# Provision the Track C stack:
#   [IAM role] -> DynamoDB table -> Lambda -> API Gateway HTTP API [-> cost budget]
# Safe to re-run: each step reuses what already exists.
#
# Personal account: configure an IAM user's access key first (aws configure).
#   Optional: BUDGET_EMAIL=you@example.com bash infra/deploy.sh  (adds a $1/month alert)
# Learner Lab: run in the lab terminal or paste the lab's CLI credentials.
set -euo pipefail
source "$(dirname "$0")/config.sh"

log "Checking credentials"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
CALLER_ARN=$(aws sts get-caller-identity --query Arn --output text)
if [[ "$CALLER_ARN" == *":root" ]]; then
  echo "You are using the ROOT user. Create an IAM user with an access key instead (see README)."; exit 1
fi
echo "Account $ACCOUNT_ID, region $AWS_REGION, caller $CALLER_ARN"

TABLE_ARN="arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}"
LOG_GROUP_ARN="arn:aws:logs:${AWS_REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/${FUNCTION_NAME}"
mkdir -p "$BUILD_DIR"

# ---------------------------------------------------------------- IAM role
NEW_ROLE=0
if is_learner_lab; then
  log "Learner Lab detected: using pre-made $LAB_ROLE_NAME"
  ROLE_NAME="$LAB_ROLE_NAME"
else
  ROLE_NAME="$OWN_ROLE_NAME"
  log "IAM execution role $ROLE_NAME (least privilege)"
  cat > "$BUILD_DIR/trust.json" <<EOF
{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
  "Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole",
  "Condition":{"StringEquals":{"aws:SourceAccount":"$ACCOUNT_ID"}}}]}
EOF
  cat > "$BUILD_DIR/policy.json" <<EOF
{"Version":"2012-10-17","Statement":[
  {"Sid":"PartsTableCrud","Effect":"Allow",
   "Action":["dynamodb:PutItem","dynamodb:GetItem","dynamodb:UpdateItem",
             "dynamodb:DeleteItem","dynamodb:Scan","dynamodb:DescribeTable"],
   "Resource":"$TABLE_ARN"},
  {"Sid":"OwnLogsOnly","Effect":"Allow",
   "Action":["logs:CreateLogStream","logs:PutLogEvents"],
   "Resource":"$LOG_GROUP_ARN:*"}]}
EOF
  if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    echo "exists"
  else
    aws iam create-role --role-name "$ROLE_NAME" \
      --assume-role-policy-document "file://$BUILD_DIR/trust.json" \
      --description "Execution role for $FUNCTION_NAME" \
      --tags Key=Project,Value="$PROJECT" >/dev/null
    NEW_ROLE=1
    echo "created"
  fi
  # Always (re)apply the inline policy so it matches this script.
  aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name parts-table-access \
    --policy-document "file://$BUILD_DIR/policy.json"
  echo "inline policy parts-table-access applied"
fi
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

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

# ---------------------------------------------------------------- Lambda
log "Packaging Lambda"
"$PY" - src/app.py "$BUILD_DIR/function.zip" <<'EOF'
import sys, zipfile
with zipfile.ZipFile(sys.argv[2], "w", zipfile.ZIP_DEFLATED) as z:
    z.write(sys.argv[1], "app.py")
EOF
ls -l "$BUILD_DIR/function.zip"

# Create the log group first so retention applies from the first invocation
# (the least-privilege role is not allowed to create it).
aws logs create-log-group --log-group-name "/aws/lambda/$FUNCTION_NAME" \
  --tags Project="$PROJECT" 2>/dev/null || true
aws logs put-retention-policy --log-group-name "/aws/lambda/$FUNCTION_NAME" \
  --retention-in-days "$LOG_RETENTION_DAYS"

log "Lambda function $FUNCTION_NAME"
if aws lambda get-function --function-name "$FUNCTION_NAME" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$BUILD_DIR/function.zip" >/dev/null
  aws lambda wait function-updated-v2 --function-name "$FUNCTION_NAME"
  echo "code updated"
else
  # A brand-new IAM role takes a few seconds to become usable by Lambda.
  [[ $NEW_ROLE == 1 ]] && { echo "waiting for the new role to propagate..."; sleep 10; }
  for attempt in 1 2 3 4 5 6; do
    if aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime python3.13 \
        --architectures arm64 \
        --handler app.lambda_handler \
        --role "$ROLE_ARN" \
        --zip-file "fileb://$BUILD_DIR/function.zip" \
        --timeout 10 --memory-size 128 \
        --environment "Variables={TABLE_NAME=$TABLE_NAME}" \
        --tags Project="$PROJECT" >/dev/null 2>"$BUILD_DIR/create.err"; then
      break
    fi
    if grep -q "cannot be assumed" "$BUILD_DIR/create.err" && [[ $attempt -lt 6 ]]; then
      echo "role not ready yet, retrying in 10 s ($attempt/5)"; sleep 10
    else
      cat "$BUILD_DIR/create.err"; exit 1
    fi
  done
  aws lambda wait function-active-v2 --function-name "$FUNCTION_NAME"
  echo "created"
fi
FUNCTION_ARN=$(aws lambda get-function --function-name "$FUNCTION_NAME" --query Configuration.FunctionArn --output text)

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

# ---------------------------------------------------------------- Budget
if ! is_learner_lab; then
  log "Cost budget $BUDGET_NAME"
  if aws budgets describe-budget --account-id "$ACCOUNT_ID" --budget-name "$BUDGET_NAME" >/dev/null 2>&1; then
    echo "exists"
  elif [[ -z "$BUDGET_EMAIL" ]]; then
    echo "skipped: re-run with BUDGET_EMAIL=you@example.com to get an email at 80% of \$$BUDGET_LIMIT_USD/month"
  else
    cat > "$BUILD_DIR/budget.json" <<EOF
{"BudgetName":"$BUDGET_NAME","BudgetType":"COST","TimeUnit":"MONTHLY",
 "BudgetLimit":{"Amount":"$BUDGET_LIMIT_USD","Unit":"USD"}}
EOF
    cat > "$BUILD_DIR/notify.json" <<EOF
[{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":80,"ThresholdType":"PERCENTAGE"},
  "Subscribers":[{"SubscriptionType":"EMAIL","Address":"$BUDGET_EMAIL"}]},
 {"Notification":{"NotificationType":"FORECASTED","ComparisonOperator":"GREATER_THAN","Threshold":100,"ThresholdType":"PERCENTAGE"},
  "Subscribers":[{"SubscriptionType":"EMAIL","Address":"$BUDGET_EMAIL"}]}]
EOF
    aws budgets create-budget --account-id "$ACCOUNT_ID" \
      --budget "file://$BUILD_DIR/budget.json" \
      --notifications-with-subscribers "file://$BUILD_DIR/notify.json"
    echo "created: \$$BUDGET_LIMIT_USD/month, email at 80% actual and 100% forecast"
  fi
fi

log "Done"
cat <<EOF
Role     : $ROLE_ARN
Table    : $TABLE_ARN
Function : $FUNCTION_ARN
API URL  : $API_URL
Next     : bash infra/smoke_test.sh
EOF
