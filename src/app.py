# Lambda handler for the BrAIlliant scan API.
#
# The BrAIlliant device takes a photo and POSTs it here. Depending on the mode:
#   graph -> edge detection, scaled down to the 96 x 64 pin display (1 = raised pin)
#   text  -> OCR (Amazon Textract, only on AWS) and then Grade 1 braille
# Every scan is saved as a "scan job" in DynamoDB so the device (or an app)
# can fetch, label or delete it later.
import base64
import binascii
import io
import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

TABLE_NAME = os.environ.get("TABLE_NAME", "brailliant-scans")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "")    # only for local testing
OCR_ENABLED = os.environ.get("OCR_ENABLED", "true") == "true"  # Textract can't run locally

GRID_W, GRID_H = 96, 64          # the BrAIlliant pin display
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_TEXT = 5000

_table = None
_textract = None


def table():
    global _table
    if _table is None:
        if DYNAMODB_ENDPOINT:
            db = boto3.resource("dynamodb", endpoint_url=DYNAMODB_ENDPOINT,
                                region_name=os.environ.get("AWS_REGION", "us-east-1"),
                                aws_access_key_id="local", aws_secret_access_key="local")
        else:
            db = boto3.resource("dynamodb")
        _table = db.Table(TABLE_NAME)
    return _table


def textract():
    global _textract
    if _textract is None:
        _textract = boto3.client("textract")
    return _textract


class BadRequest(Exception):
    pass


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=lambda o: int(o) if o % 1 == 0 else float(o)),
    }


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_body(event):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    if not raw:
        raise BadRequest("Request body is required")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise BadRequest("Body must be valid JSON")
    if not isinstance(data, dict):
        raise BadRequest("Body must be a JSON object")
    return data


# ---------- image processing ----------

def load_image(b64):
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise BadRequest("'image' must be base64")
    if len(raw) > MAX_IMAGE_BYTES:
        raise BadRequest("Image is too big (max 4 MB)")
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)  # phone/camera rotation
        img.load()
    except (UnidentifiedImageError, OSError):
        raise BadRequest("'image' is not a JPEG/PNG image")
    return raw, img


def image_to_dots(img, method="edges"):
    """Turns a photo into a 96 x 64 grid of raised (1) / flat (0) pins."""
    gray = ImageOps.grayscale(img)
    gray.thumbnail((GRID_W * 4, GRID_H * 4))          # small enough to be fast
    gray = ImageOps.autocontrast(gray, cutoff=2)

    if method == "edges":
        # outlines of shapes, good for photos of objects or filled charts
        work = gray.filter(ImageFilter.GaussianBlur(1)).filter(ImageFilter.FIND_EDGES)
    else:
        # dark ink on light paper, good for line graphs and drawings
        work = ImageOps.invert(gray)

    # fit into 96 x 64 without stretching, empty space stays flat
    work.thumbnail((GRID_W, GRID_H), Image.Resampling.BOX)
    canvas = Image.new("L", (GRID_W, GRID_H), 0)
    canvas.paste(work, ((GRID_W - work.width) // 2, (GRID_H - work.height) // 2))

    # threshold: raise roughly the strongest 15% of pixels, but never faint noise
    hist = canvas.histogram()
    total, count, level = GRID_W * GRID_H, 0, 255
    while level > 0 and count + hist[level] <= total * 0.15:
        count += hist[level]
        level -= 1
    cutoff = max(level, 40)

    px = canvas.load()
    rows = []
    for y in range(GRID_H):
        bits = "".join("1" if px[x, y] > cutoff else "0" for x in range(GRID_W))
        rows.append(f"{int(bits, 2):024x}")   # 96 bits -> 24 hex chars
    return rows


def ocr(raw):
    # Textract is made for document pages (Rekognition is more for signs and labels)
    res = textract().detect_document_text(Document={"Bytes": raw})
    return "\n".join(b["Text"] for b in res["Blocks"] if b["BlockType"] == "LINE")


# Simplified Grade 1 (uncontracted) braille, Unicode braille cells.
LETTERS = "⠁⠃⠉⠙⠑⠋⠛⠓⠊⠚⠅⠇⠍⠝⠕⠏⠟⠗⠎⠞⠥⠧⠺⠭⠽⠵"
PUNCT = {" ": " ", ",": "⠂", ";": "⠆", ":": "⠒", ".": "⠲", "!": "⠖", "?": "⠦",
         "'": "⠄", "-": "⠤", "(": "⠐⠣", ")": "⠐⠜", '"': "⠦", "\n": "\n"}
NUMBER_SIGN, CAPITAL_SIGN = "⠼", "⠠"


def to_braille(text):
    out, in_number = [], False
    for ch in text:
        if ch.isdigit():
            if not in_number:
                out.append(NUMBER_SIGN)
                in_number = True
            out.append(LETTERS[(int(ch) - 1) % 10])  # 1-9 = a-i, 0 = j
            continue
        if in_number and ch not in ".,":
            in_number = False
        low = ch.lower()
        if "a" <= low <= "z":
            if ch.isupper():
                out.append(CAPITAL_SIGN)
            out.append(LETTERS[ord(low) - ord("a")])
        else:
            out.append(PUNCT.get(ch, "⠿"))  # unknown symbol
    return "".join(out)


# ---------- CRUD ----------

def create_scan(event):
    data = read_body(event)
    unknown = set(data) - {"deviceId", "mode", "image", "text", "method", "label"}
    if unknown:
        raise BadRequest("Unknown field(s): " + ", ".join(sorted(unknown)))

    device = data.get("deviceId")
    if not isinstance(device, str) or not device.strip() or len(device) > 64:
        raise BadRequest("'deviceId' is required (max 64 characters)")
    mode = data.get("mode")
    if mode not in ("graph", "text"):
        raise BadRequest("'mode' must be 'graph' or 'text'")
    label = data.get("label", "")
    if not isinstance(label, str) or len(label) > 100:
        raise BadRequest("'label' must be a string (max 100 characters)")

    item = {"scanId": "S-" + uuid.uuid4().hex[:10], "deviceId": device.strip(),
            "mode": mode, "label": label, "read": False, "createdAt": now()}

    if mode == "graph":
        method = data.get("method", "edges")
        if method not in ("edges", "dark"):
            raise BadRequest("'method' must be 'edges' or 'dark'")
        if not isinstance(data.get("image"), str):
            raise BadRequest("'image' (base64 JPEG/PNG) is required for graph mode")
        _, img = load_image(data["image"])
        item.update(method=method, sourceSize=f"{img.width}x{img.height}",
                    width=GRID_W, height=GRID_H, dots=image_to_dots(img, method))
        item["dotCount"] = sum(bin(int(r, 16)).count("1") for r in item["dots"])
        item["status"] = "done"
    else:
        if isinstance(data.get("text"), str):
            # text sent directly (lets me test braille without OCR)
            text = data["text"]
        elif isinstance(data.get("image"), str):
            raw, img = load_image(data["image"])
            item["sourceSize"] = f"{img.width}x{img.height}"
            if not OCR_ENABLED:
                item.update(status="failed", error="OCR only runs on AWS (Textract)")
                item["updatedAt"] = item["createdAt"]
                table().put_item(Item=item)
                return respond(201, item)
            text = ocr(raw)
        else:
            raise BadRequest("Text mode needs 'image' or 'text'")
        text = text[:MAX_TEXT]
        item.update(text=text, braille=to_braille(text), status="done")

    item["updatedAt"] = item["createdAt"]
    table().put_item(Item=item)
    return respond(201, item)


def list_scans(event):
    params = event.get("queryStringParameters") or {}
    args = {}
    if params.get("deviceId"):
        args["FilterExpression"] = Attr("deviceId").eq(params["deviceId"])
    items = []
    while True:
        page = table().scan(**args)
        items += page.get("Items", [])
        if "LastEvaluatedKey" not in page:
            break
        args["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    items.sort(key=lambda i: i["createdAt"], reverse=True)
    return respond(200, {"count": len(items), "items": items})


def get_scan(scan_id):
    item = table().get_item(Key={"scanId": scan_id}).get("Item")
    if not item:
        return respond(404, {"error": f"Scan '{scan_id}' not found"})
    return respond(200, item)


def update_scan(event, scan_id):
    data = read_body(event)
    unknown = set(data) - {"label", "read"}
    if unknown or not data:
        raise BadRequest("Only 'label' and 'read' can be changed")
    if "label" in data and (not isinstance(data["label"], str) or len(data["label"]) > 100):
        raise BadRequest("'label' must be a string (max 100 characters)")
    if "read" in data and not isinstance(data["read"], bool):
        raise BadRequest("'read' must be true or false")
    data["updatedAt"] = now()
    try:
        res = table().update_item(
            Key={"scanId": scan_id},
            UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in data),
            ExpressionAttributeNames={f"#{k}": k for k in data},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()},
            ConditionExpression=Attr("scanId").exists(),
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return respond(404, {"error": f"Scan '{scan_id}' not found"})
        raise
    return respond(200, res["Attributes"])


def delete_scan(scan_id):
    try:
        table().delete_item(Key={"scanId": scan_id}, ConditionExpression=Attr("scanId").exists())
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return respond(404, {"error": f"Scan '{scan_id}' not found"})
        raise
    return respond(200, {"deleted": scan_id})


def health():
    info = table().meta.client.describe_table(TableName=TABLE_NAME)["Table"]
    return respond(200, {"status": "ok", "table": TABLE_NAME, "tableStatus": info["TableStatus"],
                         "ocr": OCR_ENABLED, "time": now()})


def lambda_handler(event, context):
    route = event.get("routeKey", "")
    scan_id = (event.get("pathParameters") or {}).get("scanId")
    try:
        if route == "POST /scans":
            return create_scan(event)
        if route == "GET /scans":
            return list_scans(event)
        if route == "GET /scans/{scanId}":
            return get_scan(scan_id)
        if route == "PUT /scans/{scanId}":
            return update_scan(event, scan_id)
        if route == "DELETE /scans/{scanId}":
            return delete_scan(scan_id)
        if route == "GET /health":
            return health()
        return respond(404, {"error": f"Unknown route '{route}'"})
    except BadRequest as e:
        return respond(400, {"error": str(e)})
    except ClientError as e:
        print("AWS error:", e)
        return respond(500, {"error": "Server error"})
