# Fills my Word template (docs/template/brief_template.docx) with content.
# Keeps the template's header, styles and page setup; only the title in the header
# and the body are replaced.
#   python tools/fill_template.py brief      -> docs/design_brief.docx
#   python tools/fill_template.py evidence   -> evidence/evidence.docx
#   python tools/fill_template.py implementation -> docs/lab_implementation.docx
# Export to PDF from Word afterwards (File > Save As > PDF), or run tools/export_pdf.ps1.
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs" / "template" / "brief_template.docx"
TITLE = " Scan API"   # header reads "Brailliant" + this
TEXT_W = 5731510      # text width in EMU (A4 with 1 inch margins)

RPR = '<w:rFonts w:cstheme="majorBidi"/>{extra}<w:szCs w:val="24"/>'
PPR_RUN = '<w:rPr><w:rFonts w:cstheme="majorBidi"/><w:szCs w:val="24"/></w:rPr>'

media = []   # (zip path, file) of extra images added to the document


def runs(text):
    """**bold** and *italic* -> Word runs with the template's font settings."""
    out = []
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", text):
        if not part:
            continue
        extra = ""
        if part.startswith("**"):
            part, extra = part[2:-2], "<w:b/><w:bCs/>"
        elif part.startswith("*"):
            part, extra = part[1:-1], "<w:i/><w:iCs/>"
        out.append(f'<w:r><w:rPr>{RPR.format(extra=extra)}</w:rPr>'
                   f'<w:t xml:space="preserve">{escape(part)}</w:t></w:r>')
    return "".join(out)


def heading(text):
    return f'<w:p><w:pPr><w:pStyle w:val="Heading1-EJA"/></w:pPr><w:r><w:t>{escape(text)}</w:t></w:r></w:p>'


def para(text, keep_next=False):
    keep = "<w:keepNext/>" if keep_next else ""
    return f"<w:p><w:pPr>{keep}{PPR_RUN}</w:pPr>{runs(text)}</w:p>"


def bullet(text):
    return (f'<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="3"/></w:numPr>{PPR_RUN}</w:pPr>'
            f"{runs(text)}</w:p>")


def page_break():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def table(header, rows, widths):
    border = "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
                     for s in ("top", "left", "bottom", "right"))
    margins = ('<w:tcMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
               '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tcMar>')

    def cell(text, width, head):
        shade = '<w:shd w:val="clear" w:color="auto" w:fill="E7E6E6"/>' if head else ""
        # no space after paragraphs inside cells, otherwise every row gets very tall
        paras = "".join(f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>{PPR_RUN}</w:pPr>'
                        f"{runs(f'**{line}**' if head and line else line)}</w:p>"
                        for line in text.split("\n"))
        return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/><w:tcBorders>{border}</w:tcBorders>'
                f"{shade}{margins}</w:tcPr>{paras}</w:tc>")

    def row(cells, head=False):
        trpr = "<w:trPr><w:cantSplit/>" + ("<w:tblHeader/>" if head else "") + "</w:trPr>"
        return f"<w:tr>{trpr}{''.join(cell(c, w, head) for c, w in zip(cells, widths))}</w:tr>"

    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    return ('<w:tbl><w:tblPr><w:tblW w:w="9026" w:type="dxa"/>'
            '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" '
            f'w:noHBand="0" w:noVBand="1"/></w:tblPr><w:tblGrid>{grid}</w:tblGrid>'
            + row(header, True) + "".join(row(r) for r in rows) + "</w:tbl>")


def picture(path, max_h_cm=11.0, keep_next=True):
    """Adds an image file to the document and returns the paragraph that shows it."""
    n = len(media) + 1
    rid, name = f"rIdPic{n}", f"word/media/pic{n}{path.suffix.lower()}"
    media.append((rid, name, path))
    w, h = Image.open(path).size
    cx = TEXT_W
    cy = round(cx * h / w)
    max_h = int(max_h_cm * 360000)
    if cy > max_h:
        cx, cy = round(cx * max_h / cy), max_h
    keep = "<w:keepNext/>" if keep_next else ""
    return (f'<w:p><w:pPr>{keep}<w:jc w:val="center"/>{PPR_RUN}</w:pPr><w:r><w:rPr>{RPR.format(extra="")}</w:rPr><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="{100 + n}" name="{escape(path.name)}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="0" name="{escape(path.name)}"/>'
            '<pic:cNvPicPr><a:picLocks noChangeAspect="1"/></pic:cNvPicPr></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
            "</wp:inline></w:drawing></w:r></w:p>")


# ---------------- design brief ----------------
def brief():
    return [
        heading("Use case"),
        para("I'm on the team building BrAIlliant, a cheap braille display with a camera and a 96 x 64 pin "
             "display, for the SOLIDWORKS AAKRUTI 2026 competition. Its ESP32 is too weak for image processing "
             "or OCR, so it needs a cloud service. This project is that service: the device sends a photo, and in "
             "**graph** mode the cloud turns the lines in it into the 96 x 64 pins, so a blind student can feel a "
             "textbook chart. In **text** mode it reads the text (OCR) and turns it into braille. Every photo becomes "
             "a *scan job*, like a ticket, that the device or an app can look up, label or delete later."),

        heading("Track and why"),
        para("I chose **Track C: API Gateway (HTTP API) + Lambda + DynamoDB**, with Amazon Textract for OCR."),
        bullet("**Cost.** BrAIlliant is meant to be cheap, so I only use services billed per request, nothing "
               "charged per hour while idle (an EC2 server in Track A/B would be). The API is throttled to "
               "10 requests/s, logs are kept 7 days, and there's a $1/month budget alert."),
        bullet("**Fits the job.** Each scan is short and independent, which is what Lambda is for. The image "
               "library (Pillow) is added as a Lambda layer. No servers to patch and no VPC to set up."),

        heading("Data entity: ScanJob"),
        para("Stored in the DynamoDB table brailliant-scans. The key is scanId."),
        table(["Field", "Type", "Notes", "Example"], [
            ["scanId", "string", "key, made by the server", "S-2df004a818"],
            ["deviceId", "string", "required, which device sent it", "brailliant-01"],
            ["mode, status", "string", "graph or text; done or failed", "graph, done"],
            ["dots, dotCount", "list, number", "graph: 64 rows of 96 bits (hex)", "64 x \"000…f0\", 401"],
            ["text, braille", "string", "text: OCR result and Grade 1 braille", "Hi → ⠠⠓⠊"],
            ["label, read", "string, bool", "can be changed later", "Physics p.12, true"],
            ["createdAt, updatedAt", "string", "set by the server", "2026-11-25T01:02:03Z"],
        ], [2000, 1400, 3226, 2400]),

        heading("CRUD endpoints"),
        table(["", "Endpoint", "Success", "Errors"], [
            ["Create", "POST /scans (deviceId, mode, image)", "201, the processed scan", "400 bad input"],
            ["Read", "GET /scans?deviceId=\nGET /scans/{scanId}", "200, list of scans\n200, one scan", "404 not found"],
            ["Update", "PUT /scans/{scanId} (label, read)", "200, the updated scan", "400, 404"],
            ["Delete", "DELETE /scans/{scanId}", "200", "404 not found"],
            ["Check", "GET /health", "200, table is reachable", "500"],
        ], [1000, 3500, 2526, 2000]),

        heading("Architecture"),
        picture(ROOT / "docs" / "architecture.png", max_h_cm=12),
        para("*Figure 1. Request flow (1 to 6), IAM/security and how the stack is deployed.*"),
        para("**Request flow:** the device sends the photo (base64 JPEG) over HTTPS to API Gateway, which invokes "
             "Lambda. The function processes the image (calling Textract in text mode), saves the scan in "
             "DynamoDB and returns the pins or braille for the display."),
        para("**IAM:** the Lambda role can only do CRUD on this one table, call textract:DetectDocumentText and write its "
             "own logs. Only this API may invoke the function, and I deploy with an IAM user, not root."),
        para("**Network and privacy:** no VPC, HTTPS only, DynamoDB encrypted at rest. Photos may show private "
             "documents, so they are processed in memory and never saved. Device login (a Lambda authorizer) comes later."),

        heading("Environment and status"),
        para("Repo: https://github.com/FachryAlfareeza/brailliant-inventory. The course's AWS Academy lab doesn't "
             "allow Lambda, DynamoDB or API Gateway, so I deployed the same code as an **ECS Fargate container** "
             "storing scans in **S3**; all 9 API tests pass on AWS. The *Ideal plan vs lab implementation* "
             "document explains each difference. **Next:** S3 upload, device login, Polly, Grade 2 braille."),
    ]


# ---------------- ideal plan vs lab implementation ----------------
def implementation():
    return [
        heading("Ideal plan vs lab implementation"),
        para("The design (template.yaml) uses API Gateway, Lambda and DynamoDB. The AWS Academy lab I was given "
             "is set up for a containers exercise, so I checked what it allows with the IAM policy simulator "
             "(aws iam simulate-principal-policy) and used the closest services it permits, as the lecturer asked."),
        picture(ROOT / "docs" / "architecture_lab.png", max_h_cm=9),
        para("*Figure 2. The lab version. Grey notes show what each part replaces in the ideal plan (Figure 1).*"),
        table(["Allowed in the lab", "Not allowed in the lab"], [
            ["ECS (Fargate), ECR, S3 buckets, load balancers, security groups, CloudWatch Logs (through the "
             "container), Rekognition and Polly (my login only), CodeCommit / CodePipeline, Cloud9",
             "Lambda, API Gateway, DynamoDB, Textract, CloudFormation change sets, uploading to S3 from my login, "
             "creating IAM roles, AWS Budgets, SQS / SNS, Secrets Manager, Cognito"],
        ], [4513, 4513]),

        heading("What changed and why"),
        table(["Ideal plan", "In the lab", "Why"], [
            ["API Gateway (HTTP API)", "The container serves HTTP itself on a public IP (port 8080)",
             "API Gateway is blocked. A load balancer is allowed but is billed per hour, a public IP is free. "
             "The cost: the address changes when the container restarts."],
            ["Lambda + Pillow layer", "ECS Fargate container (image in ECR) running the same app.py, with a "
             "small web server (server.py) in front",
             "Lambda is blocked, ECS is what the lab is for. server.py turns each request into the same event "
             "API Gateway would send, so the code is unchanged."],
            ["DynamoDB (on-demand)", "S3 bucket, each scan is one JSON file (s3_table.py)",
             "DynamoDB is blocked. S3 is also billed per request, so the cost rule still holds. Listing all "
             "scans is slower than a DynamoDB scan, fine at this size."],
            ["Own least-privilege role", "The lab's PipelineRole",
             "Creating roles is blocked and PipelineRole is the only role a container may use. It is broader "
             "than I want (full S3 access)."],
            ["Textract OCR", "OCR off, typed text still becomes braille",
             "No role a container can use may call Textract or Rekognition. Graph mode, the main feature, "
             "works fully."],
            ["SAM / CloudFormation", "AWS CLI script (scripts/lab_deploy.sh)",
             "Change sets and S3 uploads from my login are blocked, so sam deploy can't run."],
            ["AWS Budgets", "None", "Blocked. The lab credit limit works as the cap."],
        ], [1900, 3063, 4063]),

        heading("Cost difference"),
        para("The ideal plan bills only per request, nothing while idle. **Fargate is the exception**: it bills "
             "per second while the container runs (smallest size, 0.25 vCPU / 512 MB, roughly $0.01 per hour "
             "[to verify]). To keep that small, scripts/lab_stop.sh sets the service to 0 containers when I'm not "
             "testing (the scans stay in S3), and lab_start.sh starts it again. S3 and CloudWatch Logs are billed "
             "per request / per GB, the same as the ideal plan."),

        heading("What I checked on AWS"),
        bullet("scripts/lab_deploy.sh created the bucket, the ECR image, the security group, the cluster, the "
               "task definition and the service, and the container started with a public IP."),
        bullet("scripts/test_api.sh against the public URL: health check (it reports the S3 bucket), create, bad "
               "input, read, list, update, delete and read-after-delete. All 9 checks pass "
               "(evidence/test_api_output_aws.txt)."),
        bullet("scripts/device_sim.py sent the sample graph photo and got back the 96 x 64 pin grid (401 raised "
               "pins), the same result as locally."),
        bullet("The scans are JSON files under scans/ in the bucket, and every request is logged in CloudWatch "
               "(/ecs/brailliant-scan)."),

        heading("If the full Learner Lab becomes available"),
        para("Nothing in the code has to change: bash scripts/deploy.sh deploys the ideal version from "
             "template.yaml (it uses LabRole automatically on Learner Lab)."),
    ]


# ---------------- evidence ----------------
SHOTS = [
    ("L1_docker_containers.png", "L1. Docker containers",
     "kompaw-dynamodb is DynamoDB Local (port 8010). The other container is the Lambda runtime "
     "(Python 3.13 with the Pillow layer) that SAM starts."),
    ("L2_sam_build_and_start.png", "L2. sam build and sam local start-api",
     "template.yaml is valid and builds, and SAM starts the Lambda runtime with the Pillow layer. The API then runs on http://127.0.0.1:3000 (requests in L7)."),
    ("L3_api_test_pass.png", "L3. API test",
     "scripts/test_api.sh: health check, create (graph photo and text), bad input, read, list, update, delete "
     "and read-after-delete. All 9 checks pass. Full output in evidence/test_api_output.txt."),
    ("L4_device_sim_graph.png", "L4. Device simulator, graph mode",
     "scripts/device_sim.py sends data/samples/graph.png like the device would. The returned 96 x 64 pin grid "
     "is printed with braille characters (each character is 2 x 4 pins)."),
    ("L5_graph_to_pins.png", "L5. Photo and the pins it becomes",
     "Left: the photo that was sent. Right: the 96 x 64 grid from the Lambda, white dots are raised pins."),
    ("L6_dynamodb_scans.png", "L6. Scans stored in DynamoDB",
     "Number of scan jobs saved in the brailliant-scans table after the API test and the simulator run."),
    ("L7_lambda_logs.png", "L7. Lambda logs",
     "START / END / REPORT lines for each request, with duration and memory."),
]

AWS_SHOTS = [
    ("A1_ecs_service.png", "A1. ECS service running",
     "brailliant-cluster / brailliant-scan-service in the ECS console with 1 running task (Fargate)."),
    ("A2_ecs_task.png", "A2. The running container",
     "Task details: brailliant-scan task definition, PipelineRole, and the public IP the API is reached on."),
    ("A3_ecr_image.png", "A3. Container image in ECR",
     "The brailliant-scan repository with the image built and pushed by scripts/lab_deploy.sh."),
    ("A4_s3_scans.png", "A4. Scans stored in S3",
     "The scans/ folder in the bucket, one JSON file per scan job (S3 instead of DynamoDB in the lab)."),
    ("A5_cloudwatch_logs.png", "A5. Container logs in CloudWatch",
     "Log group /ecs/brailliant-scan with a START / END line for each request."),
    ("A6_live_api_test.png", "A6. API test against AWS",
     "scripts/test_api.sh against the container's public IP. All 9 checks pass "
     "(full output in evidence/test_api_output_aws.txt)."),
    ("A7_live_device_sim.png", "A7. Device simulator against AWS",
     "A graph photo sent to the AWS deployment comes back as the 96 x 64 pin grid."),
]


def evidence():
    ev = ROOT / "evidence"
    body = [
        heading("Week 12 evidence"),
        para("**Part A** is the deployment in the AWS Academy lab (ECS Fargate + S3, see the *Ideal plan vs lab "
             "implementation* document for why). **Part L** is the ideal version (Lambda + API Gateway + DynamoDB "
             "from template.yaml) tested locally with AWS SAM CLI and DynamoDB Local, because the lab doesn't "
             "allow those services. OCR (Textract) isn't shown: it's blocked in the lab and can't run locally."),
    ]
    if any((ev / shot[0]).exists() for shot in AWS_SHOTS):
        body.append(heading("Part A: AWS Academy lab (ECS Fargate + S3)"))
    for file, title, text in AWS_SHOTS:
        if not (ev / file).exists():
            print("missing, skipped:", file)
            continue
        body += [heading(title), para(text, keep_next=True), picture(ev / file, max_h_cm=10, keep_next=False)]
    body += [page_break(), heading("Part L: ideal version, tested locally")]
    for file, title, text in SHOTS:
        if not (ev / file).exists():
            print("missing, skipped:", file)
            continue
        # heading + caption stay with the picture, but the picture must not chain to the next block
        body += [heading(title), para(text, keep_next=True), picture(ev / file, max_h_cm=10, keep_next=False)]

    email = ev / "L8_aws_suspended_email.pdf"
    if email.exists():
        import pypdfium2 as pdfium
        body += [page_break(), heading("L8. AWS suspension email (personal account)"),
                 para("My personal AWS account was suspended on 24 Nov for identity verification, which is why I "
                      "first tested everything locally. I blacked out my email, the account ID and the upload link.",
                      keep_next=True)]
        pdf = pdfium.PdfDocument(email)
        for i in range(min(2, len(pdf))):
            png = ROOT / "build" / f"email_{i}.png"
            png.parent.mkdir(exist_ok=True)
            pdf[i].render(scale=1.5).to_pil().save(png)
            body.append(picture(png, max_h_cm=21 if i else 12, keep_next=False))
    return body


# ---------------- write the docx ----------------
def write(out, body):
    with zipfile.ZipFile(TEMPLATE) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            if info.filename.endswith("/") or info.filename == "word/media/image1.png":
                continue   # image1 was the old diagram in the template
            data = zin.read(info.filename)
            if info.filename == "word/document.xml":
                xml = data.decode("utf-8")
                start = xml.index("<w:body>") + len("<w:body>")
                sect = xml.index("<w:sectPr", start)
                data = (xml[:start] + "".join(body) + xml[sect:]).encode("utf-8")
            elif info.filename == "word/_rels/document.xml.rels":
                xml = data.decode("utf-8")
                xml = re.sub(r'<Relationship Id="rId7"[^>]*/>', "", xml)
                rels = "".join(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/'
                               f'2006/relationships/image" Target="{name[5:]}"/>' for rid, name, _ in media)
                data = xml.replace("</Relationships>", rels + "</Relationships>").encode("utf-8")
            elif info.filename == "word/header1.xml":
                data = data.decode("utf-8").replace(
                    '<w:t xml:space="preserve"> Parts Inventory API</w:t>',
                    f'<w:t xml:space="preserve">{TITLE}</w:t>').encode("utf-8")
            zout.writestr(info, data)
        for _, name, path in media:
            zout.write(path, name)
    print("done:", out.relative_to(ROOT))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "brief"
    if which == "brief":
        write(ROOT / "docs" / "design_brief.docx", brief())
    elif which == "evidence":
        write(ROOT / "evidence" / "evidence.docx", evidence())
    elif which == "implementation":
        write(ROOT / "docs" / "lab_implementation.docx", implementation())
    else:
        raise SystemExit("usage: python tools/fill_template.py brief|evidence|implementation")
