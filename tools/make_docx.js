// Makes editable Word versions of the submission documents:
//   docs/design_brief.docx   and   evidence/evidence.docx
// Needs the "docx" npm package: npm install docx
// Run tools/build_evidence_pdf.py first (it renders the email pages into build/).
// Usage: node tools/make_docx.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, WidthType, BorderStyle, ShadingType, LevelFormat, PageBreak,
} = require("docx");

const ROOT = path.join(__dirname, "..");
const NAME = "Muhammad Fachry Alfareeza";
const NIU = "540199";
const DATE = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

const PAGE_W = 11906, MARGIN = 1134, CONTENT = PAGE_W - 2 * MARGIN; // A4, 2 cm margins
const CONTENT_PX = Math.floor(CONTENT / 15); // image width in px (96 dpi)

// "text with `code` and **bold**" -> TextRuns
function runs(text, base = {}) {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/).filter(Boolean).map((t) => {
    if (t.startsWith("`")) return new TextRun({ ...base, text: t.slice(1, -1), font: "Consolas", size: 20 });
    if (t.startsWith("**")) return new TextRun({ ...base, text: t.slice(2, -2), bold: true });
    return new TextRun({ ...base, text: t });
  });
}
const p = (text, opts = {}) => new Paragraph({ children: runs(text), spacing: { after: 120 }, ...opts });
const h1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
const bullet = (text) => new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: runs(text), spacing: { after: 60 } });

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), data: b };
}
function image(file, maxHeightPx = 400) {
  const { w, h, data } = pngSize(file);
  let width = Math.min(w, CONTENT_PX);
  let height = Math.round((h * width) / w);
  if (height > maxHeightPx) { width = Math.round((width * maxHeightPx) / height); height = maxHeightPx; }
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new ImageRun({ type: "png", data, transformation: { width, height } })] });
}
const caption = (text) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text, italics: true, size: 20 })] });

function table(header, rows, widths) {
  const border = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (text, i, head) => new TableCell({
    borders, width: { size: widths[i], type: WidthType.DXA },
    shading: head ? { fill: "E7E6E6", type: ShadingType.CLEAR } : undefined,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: text.split("\n").map((line) => new Paragraph({ children: runs(line, { size: 20, bold: head }) })),
  });
  return new Table({
    width: { size: CONTENT, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: header.map((t, i) => cell(t, i, true)) }),
           ...rows.map((r) => new TableRow({ children: r.map((t, i) => cell(t, i, false)) }))],
  });
}

function doc(children) {
  return new Document({
    creator: NAME,
    styles: {
      default: { document: { run: { font: "Calibri", size: 22 } } },
      paragraphStyles: [
        { id: "Title", name: "Title", basedOn: "Normal", next: "Normal",
          run: { font: "Calibri", size: 32, bold: true }, paragraph: { spacing: { before: 0, after: 60 } } },
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: "Calibri", size: 26, bold: true }, paragraph: { spacing: { before: 240, after: 80 }, keepNext: true, outlineLevel: 0 } },
      ],
    },
    numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
      alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
    sections: [{ properties: { page: { size: { width: PAGE_W, height: 16838 },
      margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } }, children }],
  });
}

// ---------------- design brief ----------------
const brief = doc([
  new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun("Design Brief: BrAIlliant Parts Inventory API")] }),
  p(`${NAME} (${NIU})  |  Cloud Computing, Week 12  |  Track C (Serverless)  |  ${DATE}`, { spacing: { after: 200 } }),

  h1("1. Use case"),
  p("I'm part of a team building BrAIlliant, a cheap multiline refreshable braille display, for the SOLIDWORKS AAKRUTI 2026 competition. One prototype needs 98 different parts (PCB components, actuators, modules, case parts and so on). We currently track them in an Excel BOM, so it's hard to know what's already in stock, where it's stored, and what we still need to buy before building."),
  p("So my use case is **inventory**: a small REST API where the team can add parts, look them up, update the stock count and location, and delete parts. I exported our real BOM (98 rows) to `data/parts.json` and use it as the starting data."),

  h1("2. Track and why"),
  p("I chose **Track C: API Gateway (HTTP API) + Lambda + DynamoDB**."),
  bullet("**Cost.** All three are charged per request, so they cost almost nothing when nobody is using them. With Track A or B, an EC2 instance (and RDS) is charged every hour unless I remember to stop it."),
  bullet("**It fits the data.** It's one entity that I always look up by its ID, which is exactly what a DynamoDB table with a partition key is for. The traffic is a few people before a build, not constant load."),
  bullet("**Less to manage.** No servers to patch and no VPC or NAT gateway to set up."),
  p("To keep the bill safe: the table is on-demand, the API is throttled to 10 requests/s, Lambda uses 128 MB, logs are deleted after 7 days, and there's a $1/month budget alert."),

  h1("3. Data entity: Part"),
  p("Stored in the DynamoDB table `brailliant-parts`. The key is `partId`."),
  table(["Field", "Type", "Notes", "Example"], [
    ["partId", "string", "key, auto-generated if not given", "BOM-005"],
    ["description", "string", "required", "BQ25895 charger"],
    ["qtyInStock", "integer", "required, can't be negative", "3"],
    ["qtyPerDevice", "integer", "how many one prototype needs", "1"],
    ["section, reference", "string", "BOM section and board reference", "Carrier board, U2"],
    ["partNumber, package", "string", "", "BQ25895RTWR, WQFN-24"],
    ["location", "string", "where it's stored", "Drawer A1"],
    ["unitCostLow, unitCostHigh", "number", "price range in USD", "1.06, 2.23"],
    ["createdAt, updatedAt", "string", "set by the server", "2026-11-24T14:51:29+00:00"],
  ], [2500, 1100, 3138, 2900]),

  h1("4. CRUD endpoints"),
  table(["", "Endpoint", "Success", "Errors"], [
    ["Create", "`POST /parts`", "201, returns the new part", "400 bad input, 409 id already exists"],
    ["Read", "`GET /parts` (optional `?section=`)\n`GET /parts/{partId}`", "200, list with count\n200, one part", "404 not found"],
    ["Update", "`PUT /parts/{partId}`", "200, the updated part", "400 bad input, 404 not found"],
    ["Delete", "`DELETE /parts/{partId}`", "200", "404 not found"],
  ], [1000, 3600, 2338, 2700]),
  p("There's also `GET /health`, which checks that the Lambda can actually reach the table. I use it to test connectivity. The function rejects unknown fields, wrong types and negative numbers. Create, update and delete use conditional writes, so 409 and 404 don't need an extra read.", { spacing: { before: 120, after: 120 } }),

  h1("5. Architecture"),
  image(path.join(ROOT, "docs", "architecture.png"), 420),
  caption("Figure 1. Request flow (1 to 6), IAM/security and how the stack is deployed."),
  p("**Request flow:** the client sends an HTTPS request to API Gateway, which invokes the Lambda function. The function checks the input, reads or writes DynamoDB, and returns JSON. Logs go to CloudWatch."),
  p("**IAM:**", { spacing: { after: 60 } }),
  bullet("The Lambda has its own role, `brailliant-parts-lambda-role`. It can only do PutItem, GetItem, UpdateItem, DeleteItem, Scan and DescribeTable on this one table, and write its own logs."),
  bullet("A resource policy on the function lets only this API invoke it."),
  bullet("I deploy with an IAM user, not the root account."),
  p("**Network:** everything is managed by AWS, so there's no VPC. Traffic is HTTPS, and DynamoDB encrypts data at rest by default. The API has no login yet. I plan to add a Cognito JWT authorizer or an API key later.", { spacing: { before: 60, after: 120 } }),

  h1("6. Environment and status"),
  p("The repo has the Lambda code (`src/app.py`), unit tests, a SAM template (`template.yaml`), AWS CLI scripts to deploy and tear down, a script that tests every endpoint, and the BOM data. Repository: https://github.com/FachryAlfareeza/brailliant-inventory"),
  p("**Status:** both my AWS accounts (personal and AWS Academy) were suspended on 24 Nov for identity verification, so I couldn't create the resources on AWS yet. To still test the design, I ran the same template locally with AWS SAM CLI (Lambda in the official Python 3.13 container) and DynamoDB Local in Docker. The health check and all 9 API tests pass, and the 98 parts load (see the evidence document). Once my account is back I'll deploy with `sam deploy` and add the AWS console screenshots."),
  p("**Next:** deploy to AWS, add login, add a \"what's missing to build N devices\" endpoint, and add a CloudWatch alarm for errors."),
]);

// ---------------- evidence ----------------
const EV = path.join(ROOT, "evidence");
const shots = [
  ["L1_docker_containers.png", "L1. Docker containers", "kompaw-dynamodb is DynamoDB Local (port 8010). The other container is the Lambda runtime (Python 3.13) that SAM starts."],
  ["L2_sam_build_and_start.png", "L2. sam build + sam local start-api", "template.yaml builds, and the routes are served on http://127.0.0.1:3000."],
  ["L3_api_test_pass.png", "L3. API test", "scripts/test_api.sh calls every endpoint (create, read, update, delete and the error cases). All 9 checks pass. Full output: evidence/test_api_output.txt."],
  ["L4_dynamodb_local_count.png", "L4. Data in DynamoDB", "After loading the BOM with scripts/seed.py, the table has 98 items."],
  ["L5_get_part_BOM-005.png", "L5. GET /parts/BOM-005", "One part read back through the API."],
  ["L6_lambda_invocation_logs.png", "L6. Lambda logs", "START / END / REPORT lines for each request."],
];
const evChildren = [
  new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun("Week 12 Evidence")] }),
  p(`${NAME} (${NIU})  |  Track C (Serverless)  |  ${DATE}`, { spacing: { after: 160 } }),
  p("**Note:** these screenshots are from running the project locally, not on AWS, because my AWS accounts are suspended (see L7). I used AWS SAM CLI to run the Lambda function and API, and DynamoDB Local for the database. The same `template.yaml` can be deployed with `sam deploy` once my account works again."),
];
for (const [file, title, text] of shots) {
  evChildren.push(h1(title), p(text, { keepNext: true }), image(path.join(EV, file), 330));
}
evChildren.push(
  new Paragraph({ children: [new PageBreak()] }),
  h1("L7. AWS suspension email"),
  p("This is why there are no screenshots from the AWS console. My personal AWS account was suspended on 24 Nov for identity verification, and my AWS Academy account is blocked too. I blacked out my email, the account ID and the upload link."),
);
for (const i of [0, 1]) {
  const f = path.join(ROOT, "build", `email_${i}.png`);
  if (!fs.existsSync(f)) throw new Error(`${f} missing: run python tools/build_evidence_pdf.py first`);
  evChildren.push(image(f, 560));
}
const evidence = doc(evChildren);

(async () => {
  fs.writeFileSync(path.join(ROOT, "docs", "design_brief.docx"), await Packer.toBuffer(brief));
  fs.writeFileSync(path.join(EV, "evidence.docx"), await Packer.toBuffer(evidence));
  console.log("done: docs/design_brief.docx, evidence/evidence.docx");
})();
