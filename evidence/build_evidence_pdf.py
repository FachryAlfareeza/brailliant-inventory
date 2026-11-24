"""Bundle the Week 12 evidence into one captioned PDF: evidence/Week12_Evidence_Local.pdf

    python evidence/build_evidence_pdf.py
Uses headless Microsoft Edge (same as docs/build_pdf.py) and pypdfium2 for the L7 pages.
"""
import html
import pathlib
import subprocess

import pypdfium2 as pdfium

EV = pathlib.Path(__file__).resolve().parent
BUILD = EV.parent / "build" / "evidence"
BUILD.mkdir(parents=True, exist_ok=True)
EDGE = next(p for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
            if pathlib.Path(p).exists())

ITEMS = [
    ("L1_docker_containers.png", "L1. Docker containers",
     "kompaw-dynamodb (DynamoDB Local, host port 8010) and the Lambda runtime container "
     "(public.ecr.aws/lambda/python:3.13) started by SAM CLI."),
    ("L2_sam_build_and_start.png", "L2. sam build and sam local start-api",
     "template.yaml builds successfully. The function runs in the official Lambda Python 3.13 image, "
     "and the API routes /parts, /parts/{partId} and /health are mounted on http://127.0.0.1:3000."),
    ("L3_smoke_test_pass.png", "L3. CRUD smoke test",
     "infra/smoke_test.sh: health, create, duplicate (409), validation (400), read, list, update, delete "
     "and read-after-delete (404). Result: 0 failures (9/9). The full output is in local_smoke_test_output.txt."),
    ("L4_dynamodb_local_count.png", "L4. Data stored in DynamoDB",
     "After infra/seed.py loaded the BrAIlliant BOM through the API (98 x HTTP 201), "
     "a scan of table brailliant-parts returns Count 98."),
    ("L5_get_part_BOM-005.png", "L5. Read one item through the API",
     "GET /parts/BOM-005 returns the stored Part entity as JSON."),
    ("L6_lambda_invocation_logs.png", "L6. Lambda invocation logs",
     "Each request runs app.lambda_handler in the Lambda runtime and logs START / END / REPORT "
     "(duration, 128 MB memory), as CloudWatch Logs would on AWS."),
]

# Render the redacted AWS notice (pages 1-3 hold the content).
notice = pdfium.PdfDocument(EV / "L7_aws_suspension_notice_redacted.pdf")
notice_imgs = []
for i in range(min(2, len(notice))):
    out = BUILD / f"L7_p{i + 1}.png"
    notice[i].render(scale=1).to_pil().save(out)
    notice_imgs.append(out)

parts = []
for fname, title, cap in ITEMS:
    parts.append(f'<section><h2>{html.escape(title)}</h2><p>{html.escape(cap)}</p>'
                 f'<img src="{(EV / fname).as_uri()}"></section>')
l7 = "".join(f'<img class="pg" src="{p.as_uri()}">' for p in notice_imgs)
parts.append('<section class="brk"><h2>L7. Why there is no cloud evidence: AWS account suspension notice (redacted)</h2>'
             '<p>Email from AWS on 24 Nov 2026 suspending my account pending identity verification. The AWS Academy '
             'account is also blocked. Email addresses, the account ID and the private upload link are blacked out.</p>'
             f'<div class="two">{l7}</div></section>')

page = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Week 12 Evidence</title><style>
@page {{ size: A4; margin: 14mm; }}
body {{ font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; color: #111827; margin: 0; }}
h1 {{ font-size: 16pt; margin: 0 0 2px; }}
.meta {{ color: #4b5563; font-size: 9pt; border-bottom: 2px solid #0d9488; padding-bottom: 6px; margin-bottom: 8px; }}
.note {{ background: #fff7ed; border-left: 4px solid #ea580c; padding: 6px 10px; margin: 8px 0 10px; }}
h2 {{ font-size: 11.5pt; color: #0f766e; margin: 12px 0 3px; }}
p {{ margin: 2px 0 6px; }}
section {{ break-inside: avoid; }}
section img {{ max-width: 100%; max-height: 105mm; border: 1px solid #d1d5db; display: block; }}
.brk {{ break-before: page; }}
.two {{ display: flex; gap: 6px; }} .two img.pg {{ width: 50%; max-height: none; }}
</style></head><body>
<h1>BrAIlliant Parts Inventory API: Week 12 Evidence</h1>
<div class="meta">Muhammad Fachry Alfareeza · NIU 540199 · Track C (Serverless) · 24–25 November 2026</div>
<div class="note"><b>Local emulation, not AWS.</b> Both my AWS accounts (personal and AWS Academy) are suspended
(see L7), so the stack in <code>template.yaml</code> was run with AWS's own local tools: SAM CLI
(<code>sam local start-api</code>, official Lambda Python 3.13 image) and DynamoDB Local in Docker.
The same template deploys to AWS with <code>sam deploy</code> once access is restored.</div>
{''.join(parts)}
</body></html>"""

tmp = BUILD / "evidence.html"
tmp.write_text(page, encoding="utf-8")
out = EV / "Week12_Evidence_Local.pdf"
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                "--allow-file-access-from-files", f"--print-to-pdf={out}", tmp.as_uri()],
               check=True, capture_output=True)
print("wrote", out, "pages:", len(pdfium.PdfDocument(out)))
