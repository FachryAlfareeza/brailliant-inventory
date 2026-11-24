# BrAIlliant Parts Inventory API — AWS Cloud Computing Project (Week 12)

A serverless REST API, **Track C: API Gateway (HTTP API) + Lambda + DynamoDB**, that tracks the parts
inventory for **BrAIlliant**, a low-cost multiline refreshable braille display with AI (an
AAKRUTI / IDC 2026 entry). The prototype's real bill of materials (98 lines, Rev. F) is the seed data.

| Deliverable (Week 12) | Where |
|---|---|
| 1. Architecture diagram | [docs/architecture.svg](docs/architecture.svg) / [.png](docs/architecture.png) |
| 2. Design brief (2 pages) | [docs/design_brief.pdf](docs/design_brief.pdf) (source: [design_brief.html](docs/design_brief.html)) |
| 3. Git repo: README, starter code, deployment plan | this repo, [src/app.py](src/app.py), [docs/deployment_plan.md](docs/deployment_plan.md) |
| 4. AWS evidence | [evidence/](evidence/README.md) (screenshots and `smoke_test_output.txt`) |

## Architecture

![architecture](docs/architecture.png)

```
Client --HTTPS--> API Gateway HTTP API ($default, throttled)
                    --AWS_PROXY v2.0--> Lambda brailliant-parts-api (Python 3.13, LabRole)
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
infra/config.sh       names, region, LabRole
infra/deploy.sh       idempotent provisioning with the AWS CLI
infra/smoke_test.sh   connectivity + CRUD test, writes evidence/smoke_test_output.txt
infra/seed.py         loads data/parts_seed.json (98 BOM parts) through the API
infra/teardown.sh     deletes everything (protects the Learner Lab budget)
data/parts_seed.json  BrAIlliant BOM Rev. F exported to JSON
docs/                 diagram, design brief, deployment plan, PDF build script
evidence/             AWS screenshots and test outputs
```

## Quick start

```bash
# 1. Local tests (Python 3.10+ with boto3)
python -m unittest discover -s tests -v

# 2. AWS Learner Lab: Start Lab -> wait for the green dot.
#    Either open the lab's terminal and clone this repo there, or copy
#    "AWS Details -> AWS CLI" into ~/.aws/credentials on your own machine.
bash infra/deploy.sh          # creates the table, function, API and routes; prints the API URL
bash infra/smoke_test.sh      # health + CRUD, saved to evidence/smoke_test_output.txt
python infra/seed.py          # optional: load the 98 BOM parts

# 3. When finished (after grading)
bash infra/teardown.sh
```

Example call:

```bash
URL=$(cat infra/.api_url)
curl -X POST "$URL/parts" -H 'Content-Type: application/json' \
  -d '{"partId":"BOM-005","description":"BQ25895RTWR charger","qtyInStock":3,"section":"Carrier board"}'
curl "$URL/parts/BOM-005"
```

## Budget notes

All services are pay-per-request, so idle cost is about $0. There is no EC2, RDS, NAT gateway or VPC endpoint.
The stage is throttled to 10 req/s (burst 20). Lambda uses 128 MB on arm64, logs are kept 7 days,
and every resource is tagged `Project=brailliant-inventory`. Learner Lab sessions end after about 4 h,
but serverless resources persist without spending.
