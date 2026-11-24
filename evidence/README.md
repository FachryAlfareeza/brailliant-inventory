# AWS evidence (Week 12)

Put the screenshots in this folder using these file names. Each one should show the account/region bar and the clock where possible.

| File | What to capture |
|---|---|
| `01_learner_lab_started.png` | Learner Lab page with the green dot and the remaining budget |
| `02_sts_identity.png` | terminal: `aws sts get-caller-identity` |
| `03_deploy_output.png` | terminal: end of `bash infra/deploy.sh` showing the API URL |
| `04_dynamodb_table.png` | DynamoDB console: `brailliant-parts` ACTIVE, partition key `partId` |
| `05_lambda_function.png` | Lambda console: function overview with the API Gateway trigger, and Configuration → Permissions showing LabRole |
| `06_lambda_test.png` | Lambda console Test with event `{"routeKey":"GET /health"}` and the 200 result |
| `07_api_routes.png` | API Gateway console: the six routes and the integration |
| `08_smoke_test.png` | terminal: `bash infra/smoke_test.sh` ending `Result: 0 failure(s)` |
| `09_dynamodb_items.png` | DynamoDB → Explore items after `python infra/seed.py` |
| `10_cloudwatch_logs.png` | CloudWatch log stream of the function |
| `11_budget_after.png` | Learner Lab budget after the work (shows the low spend) |

`smoke_test_output.txt` is written automatically by `infra/smoke_test.sh`.
