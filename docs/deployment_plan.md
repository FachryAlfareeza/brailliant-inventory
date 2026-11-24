# Deployment plan

## Setup

- Region: us-east-1
- Account: my personal AWS account. I deploy with an IAM user, not root (root has MFA).
  On Learner Lab the script notices it and uses `LabRole`, because Learner Lab doesn't allow creating roles.
- Tools: AWS CLI v2, Git Bash, Python 3.13, SAM CLI (for local testing)

## What gets created

`scripts/deploy.sh` creates these in order. `template.yaml` describes the same things for SAM.

1. **IAM role** `brailliant-parts-lambda-role`. Only Lambda can use it, and it can only do
   Put/Get/Update/Delete/Scan/DescribeTable on the parts table and write its own logs.
2. **DynamoDB table** `brailliant-parts`, key `partId` (string), on-demand billing.
3. **Lambda function** `brailliant-parts-api`: Python 3.13, arm64, 128 MB, 10 s timeout. Its log group keeps logs for 7 days.
4. **HTTP API** `brailliant-parts-http-api` with the 6 routes, all going to the Lambda.
   The `$default` stage auto-deploys and is limited to 10 requests/s (burst 20).
5. **Permission** that lets only this API invoke the function.
6. **Budget** of $1/month with an email alert (only if `BUDGET_EMAIL` is set).

If something already exists, the script skips it, so running it again just updates the code.

## How I check it works

| Check | How | Expected |
|---|---|---|
| logged in as the right user | `aws sts get-caller-identity` | my IAM user, not root |
| table exists | DynamoDB console | brailliant-parts is Active |
| function works | Lambda console, Test with `{"routeKey": "GET /health"}` | status 200 |
| API reaches the database | `curl <url>/health` | 200, tableStatus ACTIVE |
| CRUD works | `bash scripts/test_api.sh` | Failed: 0 |
| data is stored | DynamoDB, Explore items | the test parts / 98 seeded parts |
| logs | CloudWatch, /aws/lambda/brailliant-parts-api | one entry per request |

Locally I can only do the CRUD, data and log checks (see `evidence/`).

## Cleanup

`bash scripts/teardown.sh` deletes the API, function, logs, table and role. After that, delete the IAM user's access key.

## Next weeks

- authentication (Cognito JWT authorizer or an API key)
- `GET /parts/shortage?devices=N` to show what's missing to build N devices
- CloudWatch alarm for errors
- GitHub Actions to run the unit tests on every push
