#!/usr/bin/env bash
# Deploys the scan API to the AWS Academy lab, which only allows containers:
#   S3 bucket (scan storage) + ECR (image) + ECS Fargate (1 container, public IP)
# The ideal version (Lambda + API Gateway + DynamoDB) is in template.yaml.
# Safe to run again: anything that exists is reused, a new image is rolled out.
#
# Usage: bash scripts/lab_deploy.sh        stop/start: bash scripts/lab_stop.sh / lab_start.sh
set -euo pipefail
source "$(dirname "$0")/lab_config.sh"

echo "== S3 bucket $BUCKET (scan jobs as JSON)"
if ! aws s3api head-bucket --bucket $BUCKET 2>/dev/null; then
  aws s3api create-bucket --bucket $BUCKET >/dev/null
  echo "created"
fi
# no public access (photos and scans can be private documents)
aws s3api put-public-access-block --bucket $BUCKET --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true 2>/dev/null \
  || echo "(couldn't set public access block, new buckets block public access by default anyway)"

echo "== ECR repository $REPO"
aws ecr describe-repositories --repository-names $REPO >/dev/null 2>&1 \
  || { aws ecr create-repository --repository-name $REPO >/dev/null; echo "created"; }
REGISTRY="$ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com"
IMAGE="$REGISTRY/$REPO:$(git rev-parse --short HEAD 2>/dev/null || date +%s)"
aws ecr get-login-password | docker login --username AWS --password-stdin $REGISTRY >/dev/null
docker build --platform linux/amd64 -t $IMAGE .
docker push $IMAGE | tail -1

echo "== network"
VPC=$(aws ec2 describe-vpcs --filters Name=tag:Name,Values=LabVPC --query "Vpcs[0].VpcId" --output text)
SUBNETS=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC Name=map-public-ip-on-launch,Values=true \
  --query "Subnets[].SubnetId" --output text | tr '\t' ',')
SG=$(aws ec2 describe-security-groups --filters Name=vpc-id,Values=$VPC Name=group-name,Values=$SG_NAME \
  --query "SecurityGroups[0].GroupId" --output text)
if [[ "$SG" == "None" ]]; then
  SG=$(aws ec2 create-security-group --group-name $SG_NAME --vpc-id $VPC \
    --description "BrAIlliant scan API, port 8080" --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 8080 --cidr 0.0.0.0/0 >/dev/null
  echo "created security group (port 8080 open)"
fi
echo "VPC $VPC, public subnets $SUBNETS"

echo "== ECS cluster $CLUSTER"
STATUS=$(aws ecs describe-clusters --clusters $CLUSTER --query "clusters[0].status" --output text)
[[ "$STATUS" == "ACTIVE" ]] || { aws ecs create-cluster --cluster-name $CLUSTER >/dev/null; echo "created"; }

echo "== task definition $FAMILY"
# PipelineRole is the only role the lab lets a container use (it can pull from ECR,
# write logs and use S3). Smallest Fargate size: 0.25 vCPU, 512 MB.
cat > build/taskdef.json <<EOF
{
  "family": "$FAMILY",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "$ROLE_ARN",
  "taskRoleArn": "$ROLE_ARN",
  "containerDefinitions": [{
    "name": "scan-api",
    "image": "$IMAGE",
    "essential": true,
    "portMappings": [{"containerPort": 8080, "protocol": "tcp"}],
    "environment": [
      {"name": "STORAGE", "value": "s3"},
      {"name": "BUCKET", "value": "$BUCKET"},
      {"name": "OCR_ENABLED", "value": "false"},
      {"name": "AWS_REGION", "value": "$AWS_REGION"}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "$LOG_GROUP",
        "awslogs-create-group": "true",
        "awslogs-region": "$AWS_REGION",
        "awslogs-stream-prefix": "scan"
      }
    }
  }]
}
EOF
TASKDEF=$(aws ecs register-task-definition --cli-input-json file://build/taskdef.json \
  --query "taskDefinition.taskDefinitionArn" --output text)
echo "${TASKDEF##*/}"

echo "== ECS service $SERVICE"
SVC_STATUS=$(aws ecs describe-services --cluster $CLUSTER --services $SERVICE \
  --query "services[0].status" --output text 2>/dev/null || echo None)
if [[ "$SVC_STATUS" == "ACTIVE" ]]; then
  aws ecs update-service --cluster $CLUSTER --service $SERVICE --task-definition $TASKDEF \
    --desired-count 1 --force-new-deployment >/dev/null
  echo "updated"
else
  aws ecs create-service --cluster $CLUSTER --service-name $SERVICE --task-definition $TASKDEF \
    --desired-count 1 --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG],assignPublicIp=ENABLED}" \
    >/dev/null
  echo "created"
fi

echo "waiting for the container to start (a few minutes)..."
aws ecs wait services-stable --cluster $CLUSTER --services $SERVICE
bash scripts/lab_url.sh
