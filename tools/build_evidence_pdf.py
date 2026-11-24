# Puts all the screenshots in evidence/ into one PDF with captions: evidence/evidence.pdf
# Usage: python tools/build_evidence_pdf.py
import subprocess
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "evidence"
TMP = ROOT / "build"
TMP.mkdir(exist_ok=True)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

shots = [
    ("L1_docker_containers.png", "L1. Docker containers",
     "kompaw-dynamodb is DynamoDB Local (port 8010). The other container is the Lambda "
     "runtime (python 3.13) that SAM starts."),
    ("L2_sam_build_and_start.png", "L2. sam build + sam local start-api",
     "template.yaml builds, and the routes are served on http://127.0.0.1:3000."),
    ("L3_api_test_pass.png", "L3. API test",
     "scripts/test_api.sh calls every endpoint (create, read, update, delete and the error cases). "
     "All 9 checks pass. Full output: test_api_output.txt."),
    ("L4_dynamodb_local_count.png", "L4. Data in DynamoDB",
     "After loading the BOM with scripts/seed.py, the table has 98 items."),
    ("L5_get_part_BOM-005.png", "L5. GET /parts/BOM-005",
     "One part read back through the API."),
    ("L6_lambda_invocation_logs.png", "L6. Lambda logs",
     "START / END / REPORT lines for each request."),
]

# first two pages of the (already redacted) AWS email as images
email = pdfium.PdfDocument(EV / "L7_aws_suspended_email.pdf")
email_pages = []
for i in range(2):
    p = TMP / f"email_{i}.png"
    email[i].render(scale=1).to_pil().save(p)
    email_pages.append(p)

body = ""
for file, title, caption in shots:
    body += f'<div class="shot"><h2>{title}</h2><p>{caption}</p><img src="{(EV / file).as_uri()}"></div>'
body += ('<div class="shot newpage"><h2>L7. AWS suspension email</h2>'
         '<p>This is why there are no screenshots from the AWS console. My personal AWS account was '
         'suspended on 24 Nov for identity verification, and my AWS Academy account is blocked too. '
         'I blacked out my email, the account ID and the upload link.</p><div class="row">'
         + "".join(f'<img src="{p.as_uri()}">' for p in email_pages) + "</div></div>")

page = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 14mm; }}
body {{ font-family: Calibri, Arial, sans-serif; font-size: 11pt; margin: 0; }}
h1 {{ font-size: 16pt; margin: 0; }}
h2 {{ font-size: 12pt; margin: 14px 0 2px; }}
p {{ margin: 0 0 6px; }}
.shot {{ break-inside: avoid; }}
.shot img {{ max-width: 100%; max-height: 105mm; border: 1px solid #ccc; }}
.newpage {{ break-before: page; }}
.row {{ display: flex; gap: 6px; }} .row img {{ width: 50%; max-height: none; }}
</style></head><body>
<h1>Week 12 evidence</h1>
<p>Muhammad Fachry Alfareeza (540199), Track C</p>
<p><b>Note:</b> these screenshots are from running the project locally, not on AWS, because my AWS
accounts are suspended (see L7). I used AWS SAM CLI to run the Lambda function and API, and DynamoDB
Local for the database. The same template.yaml can be deployed with <code>sam deploy</code> once my
account works again.</p>
{body}
</body></html>"""

html_file = TMP / "evidence.html"
html_file.write_text(page, encoding="utf-8")
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                "--allow-file-access-from-files", f"--print-to-pdf={EV / 'evidence.pdf'}",
                html_file.as_uri()], check=True, capture_output=True)
print("done:", EV / "evidence.pdf")
