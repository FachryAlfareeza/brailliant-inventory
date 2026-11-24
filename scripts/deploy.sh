#!/usr/bin/env bash
# Creates the whole stack with the AWS CLI:
#   IAM role -> DynamoDB table -> Lambda -> HTTP API -> (optional) $1 budget
# Can be run again: anything that already exists is reused, and the code is updated.
#
# Usage: BUDGET_EMAIL=me@example.com bash scripts/deploy.sh
set -euo pipefail
source "$(dirname "$0")/config.sh"

echo "== Account"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
CALLER_ARN=$(aws sts get-caller-identity --query Arn --output text)
if [[ "$CALLER_ARN" == *":root" ]]; then
  echo "Don't deploy as the root user, make an IAM user first."
  exit 1
fi
echo "$CALLER_ARN ($AWS_REGION)"

TABLE_ARN="arn:aws:dynamodb:$AWS_REGION:$ACCOUNT_ID:table/$TABLE_NAME"
LOG_GROUP="/aws/lambda/$FUNCTION_NAME"
mkdir -p "$BUILD_DIR"

echo "== IAM role"
NEW_ROLE=no
if is_learner_lab; then
  ROLE_NAME=$ROLE_NAME_LAB
  echo "Learner Lab, using $ROLE_NAME"
else
  ROLE_NAME=$ROLE_NAME_OWN
  cat > $BUILD_DIR/trust.json <<EOF
{"Version": "2012-10-17", "Statement": [{"Effect": "Allow",
  "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole",
  "Condition": {"StringEquals": {"aws:SourceAccount": "$ACCOUNT_ID"}}}]}
EOF
  # the function only gets CRUD on its own table and write access to its own logs
  cat > $BUILD_DIR/policy.json <<EOF
{"Version": "2012-10-17", "Statement": [
  {"Effect": "Allow",
   "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem",
              "dynamodb:DeleteItem", "dynamodb:Scan", "dynamodb:DescribeTable"],
   "Resource": "$TABLE_ARN"},
  {"Effect": "Allow",
   "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
   "Resource": "arn:aws:logs:$AWS_REGION:$ACCOUNT_ID:log-group:$LOG_GROUP:*"}]}
EOF
  if aws iam get-role --role-name $ROLE_NAME >/dev/null 2>&1; then
    echo "$ROLE_NAME already exists"
  else
    aws iam create-role --role-name $ROLE_NAME \
      --assume-role-policy-document file://$BUILD_DIR/trust.json \
      --tags Key=Project,Value=$PROJECT >/dev/null
    NEW_ROLE=yes
    echo "created $ROLE_NAME"
  fi
  aws iam put-role-policy --role-name $ROLE_NAME --policy-name parts-table-access \
    --policy-document file://$BUILD_DIR/policy.json
fi
ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME"

echo "== DynamoDB table"
if aws dynamodb describe-table --table-name $TABLE_NAME >/dev/null 2>&1; then
  echo "$TABLE_NAME already exists"
else
  aws dynamodb create-table --table-name $TABLE_NAME \
    --attribute-definitions AttributeName=partId,AttributeType=S \
    --key-schema AttributeName=partId,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --tags Key=Project,Value=$PROJECT >/dev/null
  echo "created $TABLE_NAME"
fi
aws dynamodb wait table-exists --table-name $TABLE_NAME

echo "== Lambda"
$PY -c "import zipfile; zipfile.ZipFile('$BUILD_DIR/function.zip', 'w').write('src/app.py', 'app.py')"

# make the log group myself so it has 7 day retention (the role can't create it)
aws logs create-log-group --log-group-name $LOG_GROUP 2>/dev/null || true
aws logs put-retention-policy --log-group-name $LOG_GROUP --retention-in-days 7

if aws lambda get-function --function-name $FUNCTION_NAME >/dev/null 2>&1; then
  aws lambda update-function-code --function-name $FUNCTION_NAME \
    --zip-file fileb://$BUILD_DIR/function.zip >/dev/null
  aws lambda wait function-updated-v2 --function-name $FUNCTION_NAME
  echo "updated code"
else
  # a new role takes a few seconds before Lambda can use it, so retry a few times
  [[ $NEW_ROLE == yes ]] && sleep 10
  for try in 1 2 3 4 5 6; do
    if aws lambda create-function --function-name $FUNCTION_NAME \
        --runtime python3.13 --architectures arm64 \
        --handler app.lambda_handler --role $ROLE_ARN \
        --zip-file fileb://$BUILD_DIR/function.zip \
        --timeout 10 --memory-size 128 \
        --environment "Variables={TABLE_NAME=$TABLE_NAME}" \
        --tags Project=$PROJECT >/dev/null 2>$BUILD_DIR/error.txt; then
      break
    fi
    if grep -q "cannot be assumed" $BUILD_DIR/error.txt && [[ $try -lt 6 ]]; then
      echo "role not ready yet, retrying..."
      sleep 10
    else
      cat $BUILD_DIR/error.txt
      exit 1
    fi
  done
  aws lambda wait function-active-v2 --function-name $FUNCTION_NAME
  echo "created $FUNCTION_NAME"
fi
FUNCTION_ARN=$(aws lambda get-function --function-name $FUNCTION_NAME \
  --query Configuration.FunctionArn --output text)

echo "== API Gateway"
API_ID=$(aws apigatewayv2 get-apis --query "Items[?Name=='$API_NAME'].ApiId | [0]" --output text)
if [[ -z "$API_ID" || "$API_ID" == "None" ]]; then
  API_ID=$(aws apigatewayv2 create-api --name $API_NAME --protocol-type HTTP \
    --cors-configuration 'AllowOrigins=*,AllowMethods=GET,POST,PUT,DELETE,AllowHeaders=content-type' \
    --tags Project=$PROJECT --query ApiId --output text)
  echo "created API $API_ID"
fi

INTEGRATION_ID=$(aws apigatewayv2 get-integrations --api-id $API_ID \
  --query "Items[?IntegrationUri=='$FUNCTION_ARN'].IntegrationId | [0]" --output text)
if [[ -z "$INTEGRATION_ID" || "$INTEGRATION_ID" == "None" ]]; then
  INTEGRATION_ID=$(aws apigatewayv2 create-integration --api-id $API_ID \
    --integration-type AWS_PROXY --integration-uri $FUNCTION_ARN \
    --payload-format-version 2.0 --query IntegrationId --output text)
fi

for ROUTE in "POST /parts" "GET /parts" "GET /parts/{partId}" "PUT /parts/{partId}" \
             "DELETE /parts/{partId}" "GET /health"; do
  n=$(aws apigatewayv2 get-routes --api-id $API_ID \
      --query "length(Items[?RouteKey=='$ROUTE'])" --output text)
  if [[ $n == 0 ]]; then
    aws apigatewayv2 create-route --api-id $API_ID --route-key "$ROUTE" \
      --target integrations/$INTEGRATION_ID >/dev/null
    echo "added route $ROUTE"
  fi
done

# throttling keeps the bill small if someone spams the URL
if ! aws apigatewayv2 get-stage --api-id $API_ID --stage-name '$default' >/dev/null 2>&1; then
  aws apigatewayv2 create-stage --api-id $API_ID --stage-name '$default' --auto-deploy \
    --default-route-settings ThrottlingBurstLimit=20,ThrottlingRateLimit=10 >/dev/null
fi

# only this API is allowed to call the function
aws lambda add-permission --function-name $FUNCTION_NAME --statement-id apigw-invoke \
  --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$ACCOUNT_ID:$API_ID/*/*" \
  >/dev/null 2>&1 || true

API_URL="https://$API_ID.execute-api.$AWS_REGION.amazonaws.com"
echo "$API_URL" > $URL_FILE

if ! is_learner_lab; then
  echo "== Budget"
  if aws budgets describe-budget --account-id $ACCOUNT_ID --budget-name $BUDGET_NAME >/dev/null 2>&1; then
    echo "budget already exists"
  elif [[ -z "$BUDGET_EMAIL" ]]; then
    echo "skipped (set BUDGET_EMAIL to get an email alert)"
  else
    cat > $BUILD_DIR/budget.json <<EOF
{"BudgetName": "$BUDGET_NAME", "BudgetType": "COST", "TimeUnit": "MONTHLY",
 "BudgetLimit": {"Amount": "$BUDGET_LIMIT_USD", "Unit": "USD"}}
EOF
    cat > $BUILD_DIR/notify.json <<EOF
[{"Notification": {"NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN",
   "Threshold": 80, "ThresholdType": "PERCENTAGE"},
  "Subscribers": [{"SubscriptionType": "EMAIL", "Address": "$BUDGET_EMAIL"}]}]
EOF
    aws budgets create-budget --account-id $ACCOUNT_ID \
      --budget file://$BUILD_DIR/budget.json \
      --notifications-with-subscribers file://$BUILD_DIR/notify.json
    echo "created \$$BUDGET_LIMIT_USD/month budget"
  fi
fi

echo
echo "Done. API URL: $API_URL"
echo "Test it with: bash scripts/test_api.sh"
