# Deployment plan

## Environment
| Item | Value |
|---|---|
| Account | Personal AWS account. Root has MFA and is not used for deploying |
| Operator | IAM user (e.g. `kompaw-dev`) with an access key configured through `aws configure` |
| Region | `us-east-1` |
| Lambda execution role | `brailliant-parts-lambda-role`, created by the script (least privilege). On Learner Lab the script uses `LabRole` |
| Cost guard | AWS Budgets `brailliant-inventory-budget`, $1/month, email at 80% actual and 100% forecast |
| Tooling | AWS CLI v2, bash (Git Bash on Windows), Python 3.13 |
| Tags | `Project=brailliant-inventory` on the table, function and API |

## Resources (created by `infra/deploy.sh`, in order)
0. **IAM role** `brailliant-parts-lambda-role`: the trust policy allows only `lambda.amazonaws.com` (same account).
   Its inline policy `parts-table-access` allows only Put/Get/Update/Delete/Scan/DescribeTable on the table ARN,
   plus CreateLogStream/PutLogEvents on the function's own log group.
1. **DynamoDB** `brailliant-parts`: PK `partId` (S), `PAY_PER_REQUEST`. The script waits until it is `ACTIVE`.
2. **Lambda** `brailliant-parts-api`: zip of `src/app.py`, `python3.13`, `arm64`, 128 MB, 10 s,
   env `TABLE_NAME`, the role above. The log group is created first with 7-day retention.
   The script retries while a new role propagates.
3. **API Gateway HTTP API** `brailliant-parts-http-api`: one `AWS_PROXY` integration (payload 2.0),
   six routes (`POST/GET /parts`, `GET/PUT/DELETE /parts/{partId}`, `GET /health`), and a `$default` stage
   with auto-deploy and throttling at 10 rps / burst 20. CORS allows `GET, POST, PUT, DELETE`.
4. **Lambda permission** `apigw-invoke`: principal `apigateway.amazonaws.com`, limited to this API's ARN.
5. **Budget**: only if `BUDGET_EMAIL` is set and the account is not Learner Lab.

The script checks each resource first and reuses it if it exists. Re-running only uploads new code.

## Verification (Week 12 evidence)
| # | Check | How | Expected |
|---|---|---|---|
| 1 | Credentials work | `aws sts get-caller-identity` | ARN `…:user/kompaw-dev` (not root) |
| 1b | Role is least-privilege | IAM console → Roles → `brailliant-parts-lambda-role` | one inline policy scoped to the table ARN |
| 2 | Table active | `aws dynamodb describe-table --table-name brailliant-parts` | `TableStatus: ACTIVE` |
| 3 | Function test | Lambda console → Test with `{"routeKey":"GET /health"}` | `statusCode 200` |
| 4 | API route + storage permission | `curl $URL/health` | 200 with `tableStatus: ACTIVE` |
| 5 | CRUD | `bash infra/smoke_test.sh` | `Result: 0 failure(s)` |
| 6 | Data stored | DynamoDB console → Explore items | the smoke-test or seeded parts |
| 7 | Logs | CloudWatch → `/aws/lambda/brailliant-parts-api` | invocation logs |

## Rollback / cleanup
- Code rollback: `git checkout <commit> -- src/app.py && bash infra/deploy.sh`.
- Full cleanup: `bash infra/teardown.sh`, which deletes the API, the function, the log group, the table and the role.
  Then deactivate or delete the IAM user's access key. The budget is free and can stay.

## Later weeks
- Add authentication (a JWT authorizer backed by a Cognito user pool, or an API key with a usage plan).
- Add `GET /parts/shortage?devices=N` (parts where `qtyInStock < qtyPerDevice × N`).
- Add a CloudWatch alarm on Lambda errors and API 5xx.
- Add a GitHub Actions workflow that runs the unit tests on every push.
