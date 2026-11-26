# BrAIlliant Scan API

Cloud Computing project (Week 12), Track C: API Gateway + Lambda + DynamoDB (+ Textract for OCR).

Muhammad Fachry Alfareeza, 540199

For the AAKRUTI competition I'm building BrAIlliant, a cheap braille display with a camera
and a 96 x 64 pin display. The ESP32 inside is too weak to process photos, so this is the
cloud service it talks to: the device sends a photo and gets back

- **graph mode**: the lines in the picture, scaled down to the 96 x 64 pins (edge detection with Pillow)
- **text mode**: the text in the picture (OCR with Amazon Textract) as Grade 1 braille

Every photo is saved as a scan job in DynamoDB, so the device or an app can list,
label or delete it later. Photos themselves are not stored.

![architecture](docs/architecture.png)

| Photo sent by the device | What the pins show |
|---|---|
| `data/samples/graph.png` | 96 x 64 grid returned by the Lambda (see `evidence/`) |

## Status

- **Deployed on AWS (26 Nov 2026)** in the course's AWS Academy lab. That lab only allows
  containers and S3, so it runs as an ECS Fargate container that stores scans in S3 (see the
  next section and `docs/lab_implementation.docx`). All 9 API tests pass against it, and graph
  mode turns photos into the 96 x 64 pin grid.
- **The ideal version** (Lambda + API Gateway + DynamoDB, `template.yaml`) is tested locally with
  AWS SAM CLI and DynamoDB Local. My personal AWS account was suspended on 24 Nov, and the lab
  doesn't allow those services.
- **OCR (Textract)** isn't shown anywhere yet: the lab blocks it and it can't run locally.
  Text sent directly still becomes braille.

## AWS Academy lab version (what actually runs on AWS)

The course's lab only allows containers (ECS, ECR) and S3, not Lambda, API Gateway or DynamoDB.
So the same `app.py` also runs as an **ECS Fargate container** (`Dockerfile`, `src/server.py`)
that stores scans in **S3** (`src/s3_table.py`). The differences and the reasons are in
`docs/lab_implementation.docx` (and `docs/architecture_lab.png`).

```bash
bash scripts/lab_deploy.sh     # build + push the image, create bucket, cluster, service; prints the URL
bash scripts/test_api.sh       # against the container's public IP
bash scripts/lab_stop.sh       # 0 containers = no Fargate charges (scans stay in S3)
bash scripts/lab_start.sh      # start again (new IP)
bash scripts/lab_teardown.sh   # delete everything
```

## Folders

```
src/app.py          the Lambda function (image processing, braille, CRUD)
src/server.py       runs app.py as a web server in a container (lab version)
src/s3_table.py     S3 storage with the same interface as the DynamoDB table (lab version)
Dockerfile          container image for ECS Fargate (lab version)
tests/              unit tests, use a fake table so they run without AWS
template.yaml       SAM template (table, Pillow layer, function, role, API, budget)
scripts/            deploy / teardown, local run, API test, device simulator
data/samples/       sample photos (a graph and a page of text)
docs/               design brief (Word template + PDF), architecture diagram, deployment plan
evidence/           screenshots and test output
tools/              fills the Word template, exports PDF, makes the submission zip
```

## API

| Method | Path | What it does |
|---|---|---|
| POST | /scans | send a photo: `deviceId`, `mode` (graph/text), `image` (base64), optional `method` (edges/dark), `label` |
| GET | /scans | list scans, `?deviceId=...` to filter |
| GET | /scans/{scanId} | get one scan |
| PUT | /scans/{scanId} | change `label` or `read` |
| DELETE | /scans/{scanId} | delete a scan |
| GET | /health | checks that Lambda can reach the table |

A graph scan returns `dots`: 64 rows of 24 hex characters (96 bits each, 1 = raised pin).

## Running it

Use **Git Bash** on Windows (in PowerShell, `bash` opens WSL, which can't see Docker Desktop).

```bash
python -m unittest discover -s tests -v            # unit tests

bash scripts/local_start.sh                        # terminal 1: API on http://127.0.0.1:3000
bash scripts/test_api.sh http://127.0.0.1:3000     # terminal 2
python scripts/device_sim.py data/samples/graph.png        # like the device would
python scripts/device_sim.py data/samples/text.png --mode text
bash scripts/local_stop.sh
```

Needs Docker Desktop and SAM CLI (I installed it in a venv:
`python -m venv .venv-sam` then `.venv-sam/Scripts/python -m pip install aws-sam-cli`).
`scripts/build_layer.sh` downloads the Linux version of Pillow for the Lambda layer.

On AWS (with an IAM user, not root):
```bash
BUDGET_EMAIL=me@example.com bash scripts/deploy.sh
bash scripts/test_api.sh
bash scripts/teardown.sh      # deletes the whole stack
```
On AWS Academy Learner Lab: paste the lab's CLI credentials into `~/.aws/credentials` and run
`bash scripts/deploy.sh`. It detects the lab and uses `LabRole` (the lab can't create roles).

## Documents

`docs/design_brief.docx` and `evidence/evidence.docx` are made from my Word template
(`docs/template/brief_template.docx`):

```bash
python tools/fill_template.py brief
python tools/fill_template.py evidence
```
Then export to PDF from Word, or in PowerShell: `.\tools\export_pdf.ps1 docs\design_brief.docx`.

## Cost

Everything is pay-per-request, so it costs nothing when no one is scanning. No EC2 or RDS.
The API is throttled to 10 requests/s, logs are kept 7 days, and there's a $1/month budget alert.
