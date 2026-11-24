# AWS evidence (Week 12)

## A. Local emulation evidence (submitted, 25 Nov 2026)

**Start with [Week12_Evidence_Local.pdf](Week12_Evidence_Local.pdf)**, which bundles everything below with captions.
Rebuild it with `python evidence/build_evidence_pdf.py`.

| File | Shows |
|---|---|
| `L1_docker_containers.png` | DynamoDB Local container and the SAM Lambda runtime container |
| `L2_sam_build_and_start.png` | `sam build` succeeded, the API routes are mounted on http://127.0.0.1:3000 |
| `L3_smoke_test_pass.png` | CRUD smoke test, `Result: 0 failure(s)` |
| `L4_dynamodb_local_count.png` | 98 BOM parts stored in table `brailliant-parts` |
| `L5_get_part_BOM-005.png` | `GET /parts/BOM-005` returning the item |
| `L6_lambda_invocation_logs.png` | Lambda START/END/REPORT logs per request |
| `L7_aws_suspension_notice_redacted.pdf` | Why there is no cloud evidence: AWS suspension email, with the email, account ID and upload token blacked out |
| `local_smoke_test_output.txt` | full text output of the smoke test |

The unredacted original is kept in `evidence/private/`, which git ignores. Never commit it.

## B. Real AWS evidence (once access is restored)

Put the screenshots in this folder using these file names. Each one should show the account/region bar and the clock where possible.

| File | What to capture |
|---|---|
| `01_iam_user.png` | IAM console: the deploy user (`kompaw-dev`) with MFA on root shown in the IAM dashboard. **Hide the access key ID** |
| `02_sts_identity.png` | terminal: `aws sts get-caller-identity` (blur the account ID if you like) |
| `03_deploy_output.png` | terminal: end of `bash infra/deploy.sh` showing the API URL |
| `04_dynamodb_table.png` | DynamoDB console: `brailliant-parts` ACTIVE, partition key `partId` |
| `05_lambda_function.png` | Lambda console: function overview with the API Gateway trigger, and Configuration → Permissions showing `brailliant-parts-lambda-role` and its policy |
| `06_lambda_test.png` | Lambda console Test with event `{"routeKey":"GET /health"}` and the 200 result |
| `07_api_routes.png` | API Gateway console: the six routes and the integration |
| `08_smoke_test.png` | terminal: `bash infra/smoke_test.sh` ending `Result: 0 failure(s)` |
| `09_dynamodb_items.png` | DynamoDB → Explore items after `python infra/seed.py` |
| `10_cloudwatch_logs.png` | CloudWatch log stream of the function |
| `11_budget_after.png` | Billing → Budgets: `brailliant-inventory-budget` and the actual spend (about $0.00) |

`smoke_test_output.txt` is written automatically by `infra/smoke_test.sh`.

Never put access keys, secret keys or `~/.aws/credentials` in a screenshot or in the repo.
