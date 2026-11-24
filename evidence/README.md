# Evidence

All screenshots with captions are in **[evidence.pdf](evidence.pdf)** (rebuild with `python tools/build_evidence_pdf.py`).

These are from running the project locally (SAM CLI + DynamoDB Local), because my AWS accounts are suspended.

- `L1_docker_containers.png`: DynamoDB Local and the Lambda container running
- `L2_sam_build_and_start.png`: sam build and the API routes
- `L3_api_test_pass.png`: API test, all checks pass
- `L4_dynamodb_local_count.png`: 98 parts in the table
- `L5_get_part_BOM-005.png`: reading one part
- `L6_lambda_invocation_logs.png`: Lambda logs
- `L7_aws_suspended_email.pdf`: the AWS suspension email (email, account ID and link blacked out)
- `test_api_output.txt`: full output of `scripts/test_api.sh`

When my account works again I'll add the same checks from the AWS console
(table, function, API routes, CloudWatch logs, budget).

`evidence/private/` is in .gitignore and holds the original email. Don't commit it.
