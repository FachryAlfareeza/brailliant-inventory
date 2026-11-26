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
        para("BrAIlliant is a low-cost braille display my team is building for SOLIDWORKS AAKRUTI 2026. It has a "
             "camera and a 96 x 64 grid of pins, but the ESP32 inside can't do image processing or OCR by itself. "
             "This project is the cloud side that does that work for it. The device sends a photo. In **graph** "
             "mode, the cloud picks out the lines and scales them down to the pin grid, so a blind student can feel "
             "a chart from a textbook. In **text** mode, it reads the text with OCR and turns it into braille. Each "
             "photo is saved as a *scan job* that the device (or a phone app later on) can look up, rename or delete."),

        heading("Track and why"),
        para("I went with **Track C: API Gateway (HTTP API) + Lambda + DynamoDB**, plus Amazon Textract for the OCR."),
        bullet("**Cost.** The whole point of BrAIlliant is to be affordable, so I stuck to services that charge per "
               "request. An EC2 server from Track A or B would cost money even when nobody is scanning. I also "
               "limited the API to 10 requests per second, keep logs for 7 days and set a $1/month budget alert."),
        bullet("**It suits the work.** A scan is a short job that doesn't depend on any other scan, which is what "
               "Lambda is good at. Pillow, the image library, goes in as a Lambda layer, and I have no server or "
               "VPC to maintain."),

        heading("Data entity: ScanJob"),
        para("Scan jobs are kept in a DynamoDB table called brailliant-scans, with scanId as the key."),
        table(["Field", "Type", "Notes", "Example"], [
            ["scanId", "string", "key, made by the server", "S-2df004a818"],
            ["deviceId", "string", "required, the device that sent it", "brailliant-01"],
            ["mode, status", "string", "graph or text; done or failed", "graph, done"],
            ["dots, dotCount", "list, number", "graph: 64 rows of 96 bits (hex)", "64 x \"000…f0\", 401"],
            ["text, braille", "string", "text: what OCR read, in Grade 1 braille", "Hi → ⠠⠓⠊"],
            ["label, read", "string, bool", "the user can change these", "Physics p.12, true"],
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
        picture(ROOT / "docs" / "architecture_figma.png", max_h_cm=9),
        para("*Figure 1. Request flow (steps 1 to 6) and how the stack is deployed.*"),
        para("**How a request flows.** The device sends the photo as a base64 JPEG over HTTPS to API Gateway, which "
             "invokes the Lambda function. Lambda processes the image (in text mode it also calls Textract), saves "
             "the scan to DynamoDB and sends the pins or braille back to the display."),
        para("**Permissions.** The Lambda role can only read and write this one table, call "
             "textract:DetectDocumentText and write its own logs. Only this API can invoke the function, and I "
             "deploy with an IAM user, never the root account."),
        para("**Network and privacy.** There's no VPC, everything goes over HTTPS and DynamoDB encrypts data at rest. "
             "Photos can show private documents, so they're processed in memory and never stored. Device login "
             "(a Lambda authorizer) is planned for later."),

        heading("Environment and status"),
        para("The code is at https://github.com/FachryAlfareeza/brailliant-scan. The course's AWS Academy lab "
             "doesn't allow Lambda, DynamoDB or API Gateway, so I ran the same code there as an **ECS Fargate "
             "container** that keeps scans in **S3**. All 9 API tests pass on AWS, and the *Ideal plan vs lab "
             "implementation* document covers each difference. Next: S3 photo upload, device login, Polly and "
             "Grade 2 braille."),
    ]


# ---------------- ideal plan vs lab implementation ----------------
def implementation():
    return [
        heading("Ideal plan vs lab implementation"),
        para("My design (template.yaml) uses API Gateway, Lambda and DynamoDB. The AWS Academy lab I was given is "
             "set up for a containers exercise, so I first checked what it lets me do with the IAM policy simulator "
             "(aws iam simulate-principal-policy). Then, as the lecturer asked, I swapped in the closest services it "
             "does allow. The app code (app.py), the ScanJob entity, the endpoints and the tests didn't change. On "
             "the full Learner Lab, scripts/deploy.sh still deploys the ideal version."),
        picture(ROOT / "docs" / "architecture_figma.png", max_h_cm=7),
        para("*Figure 1. The ideal plan from the design brief. The tables below show what I changed for the lab "
             "and why.*"),
        table(["Allowed in the lab", "Not allowed in the lab"], [
            ["ECS (Fargate), ECR, S3 buckets, load balancers, security groups, CloudWatch Logs (through the "
             "container), Rekognition and Polly (my login only), CodeCommit / CodePipeline, Cloud9",
             "Lambda, API Gateway, DynamoDB, Textract, CloudFormation change sets, uploading to S3 from my login, "
             "creating IAM roles, AWS Budgets, SQS / SNS, Secrets Manager, Cognito"],
        ], [4513, 4513]),

        heading("What changed and why"),
        table(["Ideal plan", "In the lab", "Why"], [
            ["API Gateway (HTTP API)", "The container serves HTTP itself on a public IP (port 8080)",
             "API Gateway is blocked. A load balancer would work, but it costs about $0.0225/hour even when idle. "
             "A public IP is about $0.005/hour and only while the container runs. The downside is that the "
             "address changes every time the container restarts."],
            ["HTTPS, limited to 10 requests/s", "Plain HTTP on port 8080, open to the internet, no limit",
             "HTTPS needs a certificate on a load balancer or API Gateway. Fine for sample photos, not for "
             "real ones."],
            ["Lambda + Pillow layer", "ECS Fargate container (image in ECR) running the same app.py, with a "
             "small web server (server.py) in front",
             "Lambda is blocked; ECS is what the lab is for. server.py builds the same event API Gateway would "
             "send, so app.py is unchanged."],
            ["DynamoDB (on-demand)", "S3 bucket, one JSON file per scan (s3_table.py)",
             "DynamoDB is blocked. S3 also charges per request, so the cost rule holds. Listing scans is "
             "slower, which is fine at this size."],
            ["Own least-privilege role", "The lab's PipelineRole",
             "I can't create roles, and it's the only role a container may use. It allows more than I'd like "
             "(full S3)."],
            ["Textract OCR", "OCR turned off; typed text still becomes braille",
             "None of the roles a container can use may call Textract or Rekognition. Graph mode, the main "
             "feature, works fully."],
            ["SAM / CloudFormation", "AWS CLI script (scripts/lab_deploy.sh)",
             "Change sets and S3 uploads from my login are blocked, so sam deploy can't run."],
            ["AWS Budgets", "None", "Blocked. The lab's credit limit acts as the cap instead."],
        ], [1900, 3063, 4063]),

        heading("Cost difference"),
        para("The ideal plan only charges per request, so it costs nothing while idle. **Fargate is the exception.** "
             "It charges by the second while the container runs. The smallest size (0.25 vCPU / 512 MB) is about "
             "$0.012 an hour, and the public IP adds about $0.005, so leaving it on by mistake would cost around "
             "$0.40 a day (us-east-1 prices). That's why scripts/lab_stop.sh scales the service down to 0 when I'm "
             "not testing (the scans stay in S3) and lab_start.sh brings it back. S3 and CloudWatch Logs are "
             "charged per request and per GB, the same as in the ideal plan."),

        heading("What I checked on AWS"),
        bullet("scripts/lab_deploy.sh created the bucket, pushed the image to ECR, and set up the security group, "
               "cluster, task definition and service. The container started with a public IP."),
        bullet("I ran scripts/test_api.sh against the public URL. It covers the health check (which reports the S3 "
               "bucket), create, bad input, read, list, update, delete and read-after-delete, and all 9 checks "
               "passed (evidence/test_api_output_aws.txt). Scans show up as JSON files in the bucket and requests "
               "in CloudWatch."),
        bullet("scripts/device_sim.py sent the sample graph photo and got the 96 x 64 pin grid back with 401 raised "
               "pins, same as locally."),
    ]


# ---------------- evidence ----------------
SHOTS = [
    ("L1_docker_containers.png", "L1. Docker containers",
     "kompaw-dynamodb is DynamoDB Local on port 8010. The other container is the Lambda runtime "
     "(Python 3.13 with the Pillow layer), which SAM starts on its own."),
    ("L2_sam_build_and_start.png", "L2. sam build and sam local start-api",
     "template.yaml is valid and builds, and SAM starts the Lambda runtime with the Pillow layer. After that the "
     "API runs on http://127.0.0.1:3000 (the requests are in L7)."),
    ("L3_api_test_pass.png", "L3. API test",
     "scripts/test_api.sh runs the health check, creates a graph scan and a text scan, sends bad input, then "
     "reads, lists, updates and deletes, and reads again after deleting. All 9 checks pass. The full output is "
     "in evidence/test_api_output.txt."),
    ("L4_device_sim_graph.png", "L4. Device simulator, graph mode",
     "scripts/device_sim.py sends data/samples/graph.png the way the device would. It prints the 96 x 64 pin "
     "grid it gets back using braille characters, where each character covers 2 x 4 pins."),
    ("L5_graph_to_pins.png", "L5. The photo and the pins it turns into",
     "On the left is the photo that was sent. On the right is the 96 x 64 grid from Lambda, where the white "
     "dots are raised pins."),
    ("L6_dynamodb_scans.png", "L6. Scans stored in DynamoDB",
     "The number of scan jobs in the brailliant-scans table after running the API test and the simulator."),
    ("L7_lambda_logs.png", "L7. Lambda logs",
     "A START, END and REPORT line for each request, showing how long it took and how much memory it used."),
]

AWS_SHOTS = [
    ("A1_ecs_service.png", "A1. ECS service running",
     "brailliant-cluster / brailliant-scan-service in the ECS console, with 1 Fargate task running."),
    ("A2_ecs_task.png", "A2. The running container",
     "The task details: the brailliant-scan task definition, PipelineRole, and the public IP I used to reach "
     "the API."),
    ("A3_ecr_image.png", "A3. Container image in ECR",
     "The brailliant-scan repository, holding the image that scripts/lab_deploy.sh built and pushed."),
    ("A4_s3_scans.png", "A4. Scans stored in S3",
     "The scans/ folder in the bucket, with one JSON file per scan job. In the lab, S3 takes the place of "
     "DynamoDB."),
    ("A5_cloudwatch_logs.png", "A5. Container logs in CloudWatch",
     "The /ecs/brailliant-scan log group, with a START and END line for each request."),
    ("A6_live_api_test.png", "A6. API test against AWS",
     "scripts/test_api.sh run against the container's public IP. All 9 checks pass (the full output is in "
     "evidence/test_api_output_aws.txt)."),
    ("A7_live_device_sim.png", "A7. Device simulator against AWS",
     "A graph photo sent to the AWS deployment comes back as the 96 x 64 pin grid."),
]


def evidence():
    ev = ROOT / "evidence"
    body = [
        heading("Week 12 evidence"),
        para("**Part A** shows the deployment in the AWS Academy lab, which runs on ECS Fargate and S3 (the *Ideal "
             "plan vs lab implementation* document explains why). **Part L** shows the ideal version (Lambda, API "
             "Gateway and DynamoDB from template.yaml) tested on my laptop with AWS SAM CLI and DynamoDB Local, "
             "since the lab doesn't allow those services. OCR with Textract isn't shown, because the lab blocks it "
             "and it can't run locally."),
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
                 para("AWS suspended my personal account on 24 Nov for identity verification, which is why I "
                      "tested everything locally first. My email, the account ID and the upload link are "
                      "blacked out.",
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
