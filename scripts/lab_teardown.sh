#!/usr/bin/env bash
# Deletes everything lab_deploy.sh made: service, cluster, task definitions,
# image repository, security group, bucket with all scans, logs.
set -uo pipefail
source "$(dirname "$0")/lab_config.sh"

read -r -p "Delete the BrAIlliant lab deployment and all saved scans? [y/N] " ok
[[ "$ok" == y || "$ok" == Y ]] || exit 0

aws ecs update-service --cluster $CLUSTER --service $SERVICE --desired-count 0 >/dev/null 2>&1
aws ecs delete-service --cluster $CLUSTER --service $SERVICE --force >/dev/null 2>&1 && echo "deleted service"
aws ecs wait services-inactive --cluster $CLUSTER --services $SERVICE 2>/dev/null
aws ecs delete-cluster --cluster $CLUSTER >/dev/null 2>&1 && echo "deleted cluster"
for td in $(aws ecs list-task-definitions --family-prefix $FAMILY --query "taskDefinitionArns[]" --output text); do
  aws ecs deregister-task-definition --task-definition $td >/dev/null && echo "deregistered ${td##*/}"
done
aws ecr delete-repository --repository-name $REPO --force >/dev/null 2>&1 && echo "deleted image repository"
VPC=$(aws ec2 describe-vpcs --filters Name=tag:Name,Values=LabVPC --query "Vpcs[0].VpcId" --output text)
SG=$(aws ec2 describe-security-groups --filters Name=vpc-id,Values=$VPC Name=group-name,Values=$SG_NAME \
  --query "SecurityGroups[0].GroupId" --output text)
[[ "$SG" != "None" ]] && aws ec2 delete-security-group --group-id $SG && echo "deleted security group"
aws s3 rb s3://$BUCKET --force >/dev/null 2>&1 && echo "deleted bucket"
aws logs delete-log-group --log-group-name $LOG_GROUP 2>/dev/null && echo "deleted logs"
rm -f $URL_FILE
