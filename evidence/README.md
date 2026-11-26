# Evidence

A = the AWS Academy lab deployment (ECS Fargate + S3). L = the ideal version tested locally
(SAM CLI + DynamoDB Local). They're collected with captions in `evidence.docx`
(`python tools/fill_template.py evidence`) and its PDF export.

| File | What it shows |
|---|---|
| `A1_ecs_service.png` | ECS console: brailliant-cluster / brailliant-scan-service, 1 running task |
| `A2_ecs_task.png` | the running task: task definition, PipelineRole, public IP |
| `A3_ecr_image.png` | ECR repository brailliant-scan with the pushed image |
| `A4_s3_scans.png` | S3 bucket, scans/ folder with the JSON scan files |
| `A5_cloudwatch_logs.png` | CloudWatch log group /ecs/brailliant-scan |
| `A6_live_api_test.png` | `scripts/test_api.sh` against the public IP, Failed: 0 |
| `A7_live_device_sim.png` | `scripts/device_sim.py` against the public IP |
| `test_api_output_aws.txt` | full output of the API test against AWS |
| `L1_docker_containers.png` | DynamoDB Local and the Lambda container running |
| `L2_sam_build_and_start.png` | sam build and the mounted routes |
| `L3_api_test_pass.png` | `scripts/test_api.sh`, Failed: 0 |
| `L4_device_sim_graph.png` | `scripts/device_sim.py` printing the 96 x 64 pins as braille characters |
| `L5_graph_to_pins.png` | the photo next to the pin grid (made by device_sim.py) |
| `L6_dynamodb_scans.png` | scans stored in the table |
| `L7_lambda_logs.png` | Lambda START/END/REPORT logs |
| `L8_aws_suspended_email.pdf` | the AWS suspension email (email, account ID and link blacked out) |
| `test_api_output.txt` | full output of `scripts/test_api.sh` |

`evidence/private/` is in .gitignore and holds the original email. Don't commit it.
