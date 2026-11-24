# BrAIlliant Parts Inventory API — AWS Cloud Computing Project (Week 12)

A serverless REST API, **Track C: API Gateway (HTTP API) + Lambda + DynamoDB**, that tracks the parts
inventory for **BrAIlliant**, a low-cost multiline refreshable braille display with AI (an
AAKRUTI / IDC 2026 entry). The prototype's real bill of materials (98 lines, Rev. F) is the seed data.

| Deliverable (Week 12) | Where |
|---|---|
| 1. Architecture diagram | [docs/architecture.svg](docs/architecture.svg) / [.png](docs/architecture.png) |
| 2. Design brief (2 pages) | [docs/design_brief.pdf](docs/design_brief.pdf) (source: [design_brief.html](docs/design_brief.html)) |
| 3. Git repo: README, starter code, deployment plan | this repo, [src/app.py](src/app.py), [docs/deployment_plan.md](docs/deployment_plan.md) |
| 4. AWS evidence | [evidence/](evidence/README.md). AWS access is currently blocked, so this is **local emulation** evidence (`local_smoke_test_output.txt`) |
| Infrastructure as code | [template.yaml](template.yaml) (AWS SAM): the same stack, deployable with `sam deploy` |

## Architecture

![architecture](docs/architecture.png)

```
Client --HTTPS--> API Gateway HTTP API ($default, throttled)
                    --AWS_PROXY v2.0--> Lambda brailliant-parts-api (Python 3.13, own least-privilege role)
                                          --SDK (SigV4)--> DynamoDB brailliant-parts (PK partId, on-demand)
                                          --logs--> CloudWatch Logs (7-day retention)
```

## Entity and endpoints

`Part`: `partId` (PK), `description`*, `qtyInStock`*, `qtyPerDevice`, `section`, `reference`,
`partNumber`, `package`, `location`, `unitCostLow`, `unitCostHigh`, `createdAt`, `updatedAt` (* = required on create).

| CRUD | Method & path | Success | Errors |
|---|---|---|---|
| Create | `POST /parts` | 201 | 400, 409 |
| Read | `GET /parts` (`?section=`) · `GET /parts/{partId}` | 200 | 404 |
| Update | `PUT /parts/{partId}` | 200 | 400, 404 |
| Delete | `DELETE /parts/{partId}` | 200 | 404 |
| (check) | `GET /health`: Lambda reaches DynamoDB | 200 | 500 |

## Repository layout

```
src/app.py            Lambda handler (routing, validation, DynamoDB CRUD)
tests/test_app.py     6 unit tests with an in-memory fake table (no AWS needed)
infra/config.sh       names, region, role and budget settings
infra/deploy.sh       idempotent provisioning with the AWS CLI
infra/smoke_test.sh   connectivity + CRUD test, writes evidence/smoke_test_output.txt
infra/seed.py         loads data/parts_seed.json (98 BOM parts) through the API
infra/teardown.sh     deletes everything deploy.sh created
template.yaml         the same stack as AWS SAM infrastructure as code
local/                start.sh / stop.sh / env.json for local emulation
data/parts_seed.json  BrAIlliant BOM Rev. F exported to JSON
docs/                 diagram, design brief, deployment plan, PDF build script
evidence/             AWS screenshots and test outputs
```

## Local emulation (no AWS account needed)

Status, 24 Nov 2026: both of my AWS accounts are blocked, so the stack is verified locally with AWS's own tools.
- `sam local start-api` runs `template.yaml`: API routes, then the Lambda handler in the official `public.ecr.aws/lambda/python:3.13` image.
- **DynamoDB Local** (`amazon/dynamodb-local`) runs in Docker on the same network.

Result: `/health` and the CRUD smoke test pass 9/9, and all 98 BOM parts load (see `evidence/local_smoke_test_output.txt`).

Requirements: Docker Desktop running, AWS CLI v2, and SAM CLI. **On Windows, run the scripts in Git Bash.**
In PowerShell, plain `bash` starts WSL, which can't see Docker Desktop, so use
`& "C:\Program Files\Git\bin\bash.exe" local/start.sh` there. Without admin rights you can install SAM CLI into a venv:
`python -m venv .venv-sam && .venv-sam/Scripts/python -m pip install aws-sam-cli`.

```bash
bash local/start.sh                 # terminal 1: DynamoDB Local + sam validate/build + API on http://127.0.0.1:3000
TARGET="LOCAL emulation" OUT="$PWD/evidence/local_smoke_test_output.txt"   bash infra/smoke_test.sh http://127.0.0.1:3000   # terminal 2
python infra/seed.py http://127.0.0.1:3000          # load the 98 parts
bash local/stop.sh                  # remove the DynamoDB Local container (data is in-memory)
```
DynamoDB Local listens on host port 8010 (`DB_PORT=...` to change). `local/env.json` points the function at it.

Once AWS access works, deploy the same template with `sam build && sam deploy --guided`, or use `infra/deploy.sh`.

## Quick start

### 0. One-time AWS account setup (personal account)
1. Sign up at aws.amazon.com and **turn on MFA for the root user** (account menu → Security credentials).
2. IAM console → Users → **Create user** (e.g. `kompaw-dev`) → *Attach policies directly* → `AdministratorAccess`.
   Use this user, not root, for everything below. Delete it after grading.
3. Open that user → Security credentials → **Create access key** → *Command Line Interface (CLI)*.
4. On your PC run `aws configure` and enter the key, the secret, region `us-east-1` and output `json`.
   Check it with `aws sts get-caller-identity`. The ARN must end in `:user/kompaw-dev`, not `:root`.
   Never commit the key. It lives only in `~/.aws/credentials`.

### 1. Test locally (Python 3.10+ with boto3)
```bash
python -m unittest discover -s tests -v
```

### 2. Deploy and test (Git Bash on Windows, or any bash)
```bash
BUDGET_EMAIL=you@example.com bash infra/deploy.sh   # role, table, function, API, $1/month budget alert
bash infra/smoke_test.sh                            # health + CRUD, saved to evidence/smoke_test_output.txt
python infra/seed.py                                # optional: load the 98 BOM parts
```
AWS emails you once to confirm the budget alert. Accept it.

### 3. When finished (after grading)
```bash
bash infra/teardown.sh      # deletes the API, function, logs, table and role
```
Then delete the `kompaw-dev` user's access key (or the whole user) in IAM.

The same scripts also run on **AWS Academy Learner Lab**. They detect the `voclabs` role, use the pre-made
`LabRole` instead of creating one, and skip the budget.

Example call:

```bash
URL=$(cat infra/.api_url)
curl -X POST "$URL/parts" -H 'Content-Type: application/json'   -d '{"partId":"BOM-005","description":"BQ25895RTWR charger","qtyInStock":3,"section":"Carrier board"}'
curl "$URL/parts/BOM-005"
```

## Budget notes

This runs on a personal account, so it costs real money, but the design keeps the expected spend under $0.01.
- Every service is pay-per-request, so idle cost is about $0. There is no EC2, RDS, NAT gateway or VPC endpoint.
- The stage is throttled to 10 req/s (burst 20), so a leaked URL can't run up a large bill.
- Lambda uses 128 MB on arm64, and logs are kept 7 days.
- An AWS Budgets alert emails you at 80% of $1 (actual) and 100% (forecast).
- Every resource is tagged `Project=brailliant-inventory`, and `teardown.sh` removes all of it.
