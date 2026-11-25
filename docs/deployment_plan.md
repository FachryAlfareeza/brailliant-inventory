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
4. **IAM role** for the function (made by SAM): CRUD on the table only, `rekognition:DetectText`,
   and writing its own logs.
5. **HTTP API** with the 6 routes, `$default` stage, throttled to 10 requests/s (burst 20).
6. **Log group** with 7 day retention.
7. **Budget** of $1/month with an email alert (only if `BUDGET_EMAIL` is set).

`bash scripts/deploy.sh` builds the layer, runs `sam build` and `sam deploy`, and saves the API URL.
Running it again only updates what changed.

On AWS Academy Learner Lab, SAM can't create the role, so the function would need
`Role: arn:aws:iam::<account>:role/LabRole` instead of `Policies`.

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

- store photos in S3 and use Textract for full pages (better than Rekognition for documents)
- Grade 2 braille with Liblouis, math mode (Nemeth)
- device login (API key per device or Cognito)
- CloudWatch alarm for errors, GitHub Actions for the unit tests
