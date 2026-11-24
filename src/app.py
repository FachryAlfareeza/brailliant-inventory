"""BrAIlliant Parts Inventory API - AWS Lambda handler (Track C: Serverless).

Invoked by an API Gateway HTTP API (payload format 2.0). Stores one entity,
`Part`, in a DynamoDB table whose partition key is `partId`.

Routes
  POST   /parts            create a part
  GET    /parts            list parts (optional ?section=...)
  GET    /parts/{partId}   read one part
  PUT    /parts/{partId}   update a part
  DELETE /parts/{partId}   delete a part
  GET    /health           connectivity check (Lambda -> DynamoDB)
"""
import base64
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get("TABLE_NAME", "brailliant-parts")

# Field name -> type. Only these fields are accepted from clients.
FIELDS = {
    "section": str,
    "reference": str,
    "description": str,
    "partNumber": str,
    "package": str,
    "location": str,
    "qtyPerDevice": int,
    "qtyInStock": int,
    "unitCostLow": float,
    "unitCostHigh": float,
}
REQUIRED_ON_CREATE = ("description", "qtyInStock")

_table = None


def table():
    """Lazily create the table resource so unit tests can swap it out."""
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


# ---------- helpers ----------

def _json_default(o):
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    raise TypeError(f"Not serialisable: {type(o)}")


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_json_default),
    }


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BadRequest(Exception):
    pass


def parse_body(event):
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    if not raw:
        raise BadRequest("Request body is required")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise BadRequest("Body must be valid JSON")
    if not isinstance(data, dict):
        raise BadRequest("Body must be a JSON object")
    return data


def clean(data):
    """Validate client fields and convert numbers to DynamoDB-safe types."""
    unknown = set(data) - set(FIELDS) - {"partId"}
    if unknown:
        raise BadRequest(f"Unknown field(s): {', '.join(sorted(unknown))}")
    out = {}
    for key, value in data.items():
        if key == "partId":
            continue
        kind = FIELDS[key]
        if kind is str:
            if not isinstance(value, str):
                raise BadRequest(f"'{key}' must be a string")
            out[key] = value.strip()
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise BadRequest(f"'{key}' must be a number")
            if kind is int and int(value) != value:
                raise BadRequest(f"'{key}' must be an integer")
            if value < 0:
                raise BadRequest(f"'{key}' must not be negative")
            out[key] = int(value) if kind is int else Decimal(str(value))
    return out


# ---------- CRUD ----------

def create_part(event):
    data = parse_body(event)
    item = clean(data)
    missing = [f for f in REQUIRED_ON_CREATE if f not in item]
    if missing:
        raise BadRequest(f"Missing required field(s): {', '.join(missing)}")
    if not item["description"]:
        raise BadRequest("'description' must not be empty")
    part_id = str(data.get("partId") or f"P-{uuid.uuid4().hex[:8]}").strip()
    item["partId"] = part_id
    item["createdAt"] = item["updatedAt"] = now_iso()
    try:
        table().put_item(Item=item, ConditionExpression=Attr("partId").not_exists())
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return respond(409, {"error": f"Part '{part_id}' already exists"})
        raise
    return respond(201, item)


def list_parts(event):
    params = event.get("queryStringParameters") or {}
    kwargs = {}
    if params.get("section"):
        kwargs["FilterExpression"] = Attr("section").eq(params["section"])
    items, start = [], None
    while True:
        if start:
            kwargs["ExclusiveStartKey"] = start
        page = table().scan(**kwargs)
        items.extend(page.get("Items", []))
        start = page.get("LastEvaluatedKey")
        if not start:
            break
    items.sort(key=lambda i: i["partId"])
    return respond(200, {"count": len(items), "items": items})


def get_part(part_id):
    item = table().get_item(Key={"partId": part_id}).get("Item")
    if not item:
        return respond(404, {"error": f"Part '{part_id}' not found"})
    return respond(200, item)


def update_part(event, part_id):
    changes = clean(parse_body(event))
    if not changes:
        raise BadRequest("No updatable fields given")
    if "description" in changes and not changes["description"]:
        raise BadRequest("'description' must not be empty")
    changes["updatedAt"] = now_iso()
    names = {f"#{k}": k for k in changes}
    values = {f":{k}": v for k, v in changes.items()}
    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in changes)
    try:
        res = table().update_item(
            Key={"partId": part_id},
            UpdateExpression=expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression=Attr("partId").exists(),
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return respond(404, {"error": f"Part '{part_id}' not found"})
        raise
    return respond(200, res["Attributes"])


def delete_part(part_id):
    try:
        table().delete_item(
            Key={"partId": part_id}, ConditionExpression=Attr("partId").exists()
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return respond(404, {"error": f"Part '{part_id}' not found"})
        raise
    return respond(200, {"deleted": part_id})


def health():
    # DescribeTable proves the Lambda role can reach the table.
    info = table().meta.client.describe_table(TableName=TABLE_NAME)["Table"]
    return respond(200, {
        "status": "ok",
        "table": TABLE_NAME,
        "tableStatus": info["TableStatus"],
        "itemCount": info.get("ItemCount", 0),
        "time": now_iso(),
    })


# ---------- entry point ----------

def lambda_handler(event, context):
    route = event.get("routeKey", "")
    part_id = (event.get("pathParameters") or {}).get("partId")
    try:
        if route == "POST /parts":
            return create_part(event)
        if route == "GET /parts":
            return list_parts(event)
        if route == "GET /parts/{partId}":
            return get_part(part_id)
        if route == "PUT /parts/{partId}":
            return update_part(event, part_id)
        if route == "DELETE /parts/{partId}":
            return delete_part(part_id)
        if route == "GET /health":
            return health()
        return respond(404, {"error": f"No route for '{route}'"})
    except BadRequest as e:
        return respond(400, {"error": str(e)})
    except ClientError as e:
        print("AWS error:", e)
        return respond(500, {"error": "Storage error", "code": e.response["Error"]["Code"]})
