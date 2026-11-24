# Deployment plan

## Environment
| Item | Value |
|---|---|
| Account | AWS Academy Learner Lab (temporary `voclabs` credentials, about 4 h session) |
| Region | `us-east-1` |
| Lambda execution role | `LabRole` (pre-made; Learner Lab blocks `iam:CreateRole`) |
| Tooling | AWS CLI v2, bash (Learner Lab terminal or Git Bash), Python 3.13 |
| Tags | `Project=brailliant-inventory` on the table, function and API |

## Resources (created by `infra/deploy.sh`, in order)
1. **DynamoDB** `brailliant-parts`: PK `partId` (S), `PAY_PER_REQUEST`. The script waits until it is `ACTIVE`.
2. **Lambda** `brailliant-parts-api`: zip of `src/app.py`, `python3.13`, `arm64`, 128 MB, 10 s,
   env `TABLE_NAME`, role `LabRole`. Log group retention is set to 7 days.
3. **API Gateway HTTP API** `brailliant-parts-http-api`: one `AWS_PROXY` integration (payload 2.0),
   six routes (`POST/GET /parts`, `GET/PUT/DELETE /parts/{partId}`, `GET /health`), and a `$default` stage
   with auto-deploy and throttling at 10 rps / burst 20. CORS allows `GET, POST, PUT, DELETE`.
4. **Lambda permission** `apigw-invoke`: principal `apigateway.amazonaws.com`, limited to this API's ARN.

The script checks each resource first and reuses it if it exists. Re-running only uploads new code.

## Verification (Week 12 evidence)
| # | Check | How | Expected |
|---|---|---|---|
| 1 | Credentials work | `aws sts get-caller-identity` | ARN `…assumed-role/voclabs/…` |
| 2 | Table active | `aws dynamodb describe-table --table-name brailliant-parts` | `TableStatus: ACTIVE` |
| 3 | Function test | Lambda console → Test with `{"routeKey":"GET /health"}` | `statusCode 200` |
| 4 | API route + storage permission | `curl $URL/health` | 200 with `tableStatus: ACTIVE` |
| 5 | CRUD | `bash infra/smoke_test.sh` | `Result: 0 failure(s)` |
| 6 | Data stored | DynamoDB console → Explore items | the smoke-test or seeded parts |
| 7 | Logs | CloudWatch → `/aws/lambda/brailliant-parts-api` | invocation logs |

## Rollback / cleanup
- Code rollback: `git checkout <commit> -- src/app.py && bash infra/deploy.sh`.
- Full cleanup: `bash infra/teardown.sh`, which deletes the API, the function, the log group and the table.

## Later weeks
- Add authentication (a JWT authorizer, if Cognito is allowed in Learner Lab [to verify]).
- Add `GET /parts/shortage?devices=N` (parts where `qtyInStock < qtyPerDevice × N`).
- Add a CloudWatch alarm on Lambda errors and API 5xx.
- Add a GitHub Actions workflow that runs the unit tests on every push.
