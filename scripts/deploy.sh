#!/usr/bin/env bash
# Deploys template.yaml to AWS with SAM (CloudFormation stack "brailliant").
# Run it again after changing the code, it only updates what changed.
#
# Usage: BUDGET_EMAIL=me@example.com bash scripts/deploy.sh
set -euo pipefail
source "$(dirname "$0")/config.sh"

CALLER=$(aws sts get-caller-identity --query Arn --output text)
if [[ "$CALLER" == *":root" ]]; then
  echo "Don't deploy as the root user, make an IAM user first."
  exit 1
fi
echo "deploying as $CALLER ($AWS_REGION)"

bash scripts/build_layer.sh
$SAM build
$SAM deploy --stack-name $STACK_NAME --resolve-s3 --capabilities CAPABILITY_IAM \
  --no-confirm-changeset --no-fail-on-empty-changeset \
  --parameter-overrides BudgetEmail="${BUDGET_EMAIL:-}" OcrEnabled=true \
  --tags Project=brailliant

URL=$(aws cloudformation describe-stacks --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
echo "$URL" > $URL_FILE
echo
echo "Done. API URL: $URL"
echo "Test it with: bash scripts/test_api.sh"
