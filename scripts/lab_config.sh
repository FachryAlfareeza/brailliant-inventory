# Names used by the lab_*.sh scripts (AWS Academy lab version).
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET="brailliant-scans-$ACCOUNT"     # bucket names must be unique worldwide
REPO=brailliant-scan
CLUSTER=brailliant-cluster
SERVICE=brailliant-scan-service
FAMILY=brailliant-scan
SG_NAME=brailliant-scan-sg
LOG_GROUP=/ecs/brailliant-scan
ROLE_ARN="arn:aws:iam::$ACCOUNT:role/PipelineRole"
mkdir -p build
