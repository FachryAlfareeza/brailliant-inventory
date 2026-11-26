#!/usr/bin/env bash
# Deploys template.yaml to AWS with SAM (CloudFormation stack "brailliant").
# Run it again after changing the code, it only updates what changed.
#
# Normal account:  BUDGET_EMAIL=me@example.com bash scripts/deploy.sh
# Learner Lab:     bash scripts/deploy.sh   (detected automatically, uses LabRole, no budget)
# No OCR:          OCR=false bash scripts/deploy.sh   (if Textract isn't allowed)
set -euo pipefail
source "$(dirname "$0")/config.sh"

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
CALLER=$(aws sts get-caller-identity --query Arn --output text)
if [[ "$CALLER" == *":root" ]]; then
  echo "Don't deploy as the root user, make an IAM user first."
  exit 1
fi

PARAMS=(OcrEnabled="${OCR:-true}")
if [[ "$CALLER" == *"/voclabs/"* || "${LAB_ROLE:-}" == yes ]]; then
  # Learner Lab can't create IAM roles or budgets
  echo "Learner Lab: using LabRole, skipping the budget"
  PARAMS+=(LabRoleArn="arn:aws:iam::$ACCOUNT:role/LabRole")
else
  PARAMS+=(BudgetEmail="${BUDGET_EMAIL:-}")
fi
echo "deploying as $CALLER ($AWS_REGION)"

bash scripts/build_layer.sh
$SAM build
$SAM deploy --stack-name $STACK_NAME --resolve-s3 --capabilities CAPABILITY_IAM \
  --no-confirm-changeset --no-fail-on-empty-changeset \
  --parameter-overrides "${PARAMS[@]}" \
  --tags Project=brailliant

URL=$(aws cloudformation describe-stacks --stack-name $STACK_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
echo "$URL" > $URL_FILE
echo
echo "Done. API URL: $URL"
echo "Test it with: bash scripts/test_api.sh"
