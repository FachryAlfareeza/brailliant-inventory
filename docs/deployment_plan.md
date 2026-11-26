# Deployment plan

## Setup

- Region: us-east-1
- Account: my personal AWS account, deployed by an IAM user (root has MFA and isn't used)
- Tools: AWS CLI v2, AWS SAM CLI, Git Bash, Python 3.13, Docker (for local testing)
- Everything is in `template.yaml` and deployed as one CloudFormation stack called `brailliant`.

## What gets created

1. **DynamoDB table** `brailliant-scans`, key `scanId`, on-demand billing.
2. **Lambda layer** `brailliant-pillow`: the Linux build of Pillow (`scripts/build_layer.sh`).
3. **Lambda function** `brailliant-scan-api`: Python 3.13, 512 MB (Pillow needs it for camera photos), 15 s timeout.
4. **IAM role** for the function (made by SAM): CRUD on the table only, `textract:DetectDocumentText`,
   and writing its own logs.
5. **HTTP API** with the 6 routes, `$default` stage, throttled to 10 requests/s (burst 20).
6. **Log group** with 7 day retention.
7. **Budget** of $1/month with an email alert (only if `BUDGET_EMAIL` is set).

`bash scripts/deploy.sh` builds the layer, runs `sam build` and `sam deploy`, and saves the API URL.
Running it again only updates what changed.

On AWS Academy Learner Lab, roles and budgets can't be created. `deploy.sh` notices the
`voclabs` login and passes `LabRoleArn` (the lab's ready-made LabRole) instead, and skips the budget.
If Textract isn't allowed in the lab, deploy with `OCR=false bash scripts/deploy.sh`.

## How I check it works

| Check | How | Expected |
|---|---|---|
| right user | `aws sts get-caller-identity` | my IAM user, not root |
| stack created | CloudFormation console | `brailliant` is CREATE_COMPLETE |
| function works | Lambda console, Test with `{"routeKey": "GET /health"}` | status 200 |
| API reaches the table | `curl <url>/health` | 200, tableStatus ACTIVE |
| CRUD + graph mode | `bash scripts/test_api.sh` | Failed: 0 |
| OCR | `python scripts/device_sim.py data/samples/text.png --mode text --url <url>` | text and braille |
| data stored | DynamoDB, Explore items | the scan jobs |
| logs | CloudWatch, /aws/lambda/brailliant-scan-api | one entry per request |

Locally I can do everything except the OCR check and the console checks (see `evidence/`).

## Cleanup

`bash scripts/teardown.sh` (sam delete) removes the whole stack. Then delete the IAM user's access key.

## Next weeks

- store photos in S3 (presigned upload) instead of base64 in the request
- Grade 2 braille with Liblouis, math mode (Nemeth)
- device login with a Lambda authorizer (no Cognito or IoT Core: they bill per user or per connected minute)
- Polly audio for the speaker
- GitHub Actions to run the unit tests on every push

No CloudWatch alarms on purpose: they bill per alarm per month, and BrAIlliant avoids
anything billed by time. The budget alert covers cost mistakes.
The full plan for the product is in the BrAIlliant cloud masterplan (AAKRUTI project folder).

## What actually runs: the AWS Academy lab version

The lab I was given only allows containers, so `scripts/lab_deploy.sh` deploys the same code differently
(details and reasons in `docs/lab_implementation.docx`):

| Ideal | Lab |
|---|---|
| API Gateway | container serves HTTP on a public IP, port 8080 |
| Lambda | ECS Fargate (0.25 vCPU, 512 MB), image in ECR |
| DynamoDB | S3 bucket `brailliant-scans-<account>`, one JSON file per scan |
| own least-privilege role | the lab's `PipelineRole` |
| Textract | off (no permission in the lab) |
| SAM | AWS CLI + Docker |

Fargate bills per second while running, so `scripts/lab_stop.sh` scales it to 0 when not in use.
