# Lambda handler for the BrAIlliant parts inventory API.
# API Gateway (HTTP API, payload v2) calls lambda_handler, and the data
# is stored in one DynamoDB table with partId as the key.
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
# only used when running locally with DynamoDB Local
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "")

# fields a client is allowed to send, and their types
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
REQUIRED = ["description", "qtyInStock"]

_table = None


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


class BadRequest(Exception):
    pass


def to_json(o):
    # DynamoDB gives numbers back as Decimal
    if isinstance(o, Decimal):
        return int(o) if o % 1 == 0 else float(o)
    raise TypeError(type(o))


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=to_json),
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


def validate(data):
    unknown = set(data) - set(FIELDS) - {"partId"}
    if unknown:
        raise BadRequest("Unknown field(s): " + ", ".join(sorted(unknown)))
    item = {}
    for key, value in data.items():
        if key == "partId":
            continue
        if FIELDS[key] is str:
            if not isinstance(value, str):
                raise BadRequest(f"'{key}' must be a string")
            item[key] = value.strip()
            continue
        # numbers (bool is a subclass of int, so exclude it)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BadRequest(f"'{key}' must be a number")
        if value < 0:
            raise BadRequest(f"'{key}' must not be negative")
        if FIELDS[key] is int:
            if int(value) != value:
                raise BadRequest(f"'{key}' must be an integer")
            item[key] = int(value)
        else:
            item[key] = Decimal(str(value))  # DynamoDB doesn't accept float
    return item


def is_condition_error(e):
    return e.response["Error"]["Code"] == "ConditionalCheckFailedException"


def create_part(event):
    data = read_body(event)
    item = validate(data)
    for f in REQUIRED:
        if f not in item:
            raise BadRequest(f"Missing required field: {f}")
    if not item["description"]:
        raise BadRequest("'description' must not be empty")

    part_id = str(data.get("partId") or "P-" + uuid.uuid4().hex[:8]).strip()
    item["partId"] = part_id
    item["createdAt"] = item["updatedAt"] = now()
    try:
        table().put_item(Item=item, ConditionExpression=Attr("partId").not_exists())
    except ClientError as e:
        if is_condition_error(e):
            return respond(409, {"error": f"Part '{part_id}' already exists"})
        raise
    return respond(201, item)


def list_parts(event):
    params = event.get("queryStringParameters") or {}
    args = {}
    if params.get("section"):
        args["FilterExpression"] = Attr("section").eq(params["section"])

    items = []
    while True:
        page = table().scan(**args)
        items += page.get("Items", [])
        if "LastEvaluatedKey" not in page:
            break
        args["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    items.sort(key=lambda i: i["partId"])
    return respond(200, {"count": len(items), "items": items})


def get_part(part_id):
    item = table().get_item(Key={"partId": part_id}).get("Item")
    if not item:
        return respond(404, {"error": f"Part '{part_id}' not found"})
    return respond(200, item)


def update_part(event, part_id):
    changes = validate(read_body(event))
    if not changes:
        raise BadRequest("Nothing to update")
    if changes.get("description") == "":
        raise BadRequest("'description' must not be empty")
    changes["updatedAt"] = now()

    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in changes)
    try:
        res = table().update_item(
            Key={"partId": part_id},
            UpdateExpression=expr,
            ExpressionAttributeNames={f"#{k}": k for k in changes},
            ExpressionAttributeValues={f":{k}": v for k, v in changes.items()},
            ConditionExpression=Attr("partId").exists(),
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if is_condition_error(e):
            return respond(404, {"error": f"Part '{part_id}' not found"})
        raise
    return respond(200, res["Attributes"])


def delete_part(part_id):
    try:
        table().delete_item(Key={"partId": part_id},
                            ConditionExpression=Attr("partId").exists())
    except ClientError as e:
        if is_condition_error(e):
            return respond(404, {"error": f"Part '{part_id}' not found"})
        raise
    return respond(200, {"deleted": part_id})


def health():
    # checks that the function can actually reach the table
    info = table().meta.client.describe_table(TableName=TABLE_NAME)["Table"]
    return respond(200, {"status": "ok", "table": TABLE_NAME,
                         "tableStatus": info["TableStatus"],
                         "itemCount": info.get("ItemCount", 0), "time": now()})


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
        return respond(404, {"error": f"Unknown route '{route}'"})
    except BadRequest as e:
        return respond(400, {"error": str(e)})
    except ClientError as e:
        print("DynamoDB error:", e)
        return respond(500, {"error": "Database error"})
