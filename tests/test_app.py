# Unit tests for src/app.py with a fake table, so no AWS account is needed.
# Run: python -m unittest discover -s tests -v
import base64
import io
import json
import os
import sys
import unittest

from botocore.exceptions import ClientError
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["OCR_ENABLED"] = "false"
import app  # noqa: E402


def condition_failed():
    return ClientError({"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}}, "op")


# only implements the Table methods that app.py uses
class FakeTable:
    def __init__(self):
        self.items = {}
        outer = self

        class Client:
            def describe_table(self, TableName):
                return {"Table": {"TableStatus": "ACTIVE", "ItemCount": len(outer.items)}}

        class Meta:
            client = Client()

        self.meta = Meta()

    def put_item(self, Item, ConditionExpression=None):
        self.items[Item["scanId"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["scanId"])
        return {"Item": dict(item)} if item else {}

    def scan(self, FilterExpression=None, ExclusiveStartKey=None):
        items = list(self.items.values())
        if FilterExpression is not None:
            attr, value = FilterExpression._values
            items = [i for i in items if i.get(attr.name) == value]
        return {"Items": items}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames,
                    ExpressionAttributeValues, ConditionExpression, ReturnValues):
        if Key["scanId"] not in self.items:
            raise condition_failed()
        item = self.items[Key["scanId"]]
        for name, field in ExpressionAttributeNames.items():
            item[field] = ExpressionAttributeValues[":" + name[1:]]
        return {"Attributes": dict(item)}

    def delete_item(self, Key, ConditionExpression=None):
        if Key["scanId"] not in self.items:
            raise condition_failed()
        del self.items[Key["scanId"]]


def call(route, body=None, scan_id=None, query=None):
    event = {"routeKey": route}
    if body is not None:
        event["body"] = json.dumps(body)
    if scan_id:
        event["pathParameters"] = {"scanId": scan_id}
    if query:
        event["queryStringParameters"] = query
    res = app.lambda_handler(event, None)
    return res["statusCode"], json.loads(res["body"])


def png_b64(draw_fn, size=(400, 300)):
    img = Image.new("RGB", size, "white")
    draw_fn(ImageDraw.Draw(img))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def raised(dots, x, y):
    return (int(dots[y], 16) >> (95 - x)) & 1


class ScanTests(unittest.TestCase):
    def setUp(self):
        app._table = FakeTable()

    def test_graph_mode_makes_96x64_grid(self):
        # a black vertical line down the middle of the picture
        image = png_b64(lambda d: d.line([(200, 0), (200, 300)], fill="black", width=8))
        status, scan = call("POST /scans", {"deviceId": "dev-1", "mode": "graph",
                                            "method": "dark", "image": image})
        self.assertEqual(status, 201)
        self.assertEqual((scan["width"], scan["height"], len(scan["dots"])), (96, 64, 64))
        self.assertTrue(all(len(r) == 24 for r in scan["dots"]))
        self.assertTrue(raised(scan["dots"], 48, 32) or raised(scan["dots"], 47, 32))
        self.assertFalse(raised(scan["dots"], 5, 32))   # far from the line stays flat

    def test_edges_method(self):
        image = png_b64(lambda d: d.rectangle([100, 80, 300, 220], fill="black"))
        status, scan = call("POST /scans", {"deviceId": "dev-1", "mode": "graph", "image": image})
        self.assertEqual(status, 201)
        self.assertGreater(scan["dotCount"], 0)

    def test_text_mode_braille(self):
        status, scan = call("POST /scans", {"deviceId": "dev-1", "mode": "text", "text": "Hi 12"})
        self.assertEqual(status, 201)
        self.assertEqual(scan["braille"], "⠠⠓⠊ ⠼⠁⠃")

    def test_text_image_without_ocr(self):
        image = png_b64(lambda d: d.text((10, 10), "hello", fill="black"))
        status, scan = call("POST /scans", {"deviceId": "dev-1", "mode": "text", "image": image})
        self.assertEqual((status, scan["status"]), (201, "failed"))

    def test_crud_cycle(self):
        _, scan = call("POST /scans", {"deviceId": "dev-1", "mode": "text", "text": "abc"})
        sid = scan["scanId"]
        self.assertEqual(call("GET /scans/{scanId}", scan_id=sid)[0], 200)
        status, body = call("GET /scans", query={"deviceId": "dev-1"})
        self.assertEqual((status, body["count"]), (200, 1))
        status, body = call("PUT /scans/{scanId}", {"label": "Physics p.3", "read": True}, scan_id=sid)
        self.assertEqual((status, body["label"], body["read"]), (200, "Physics p.3", True))
        self.assertEqual(call("DELETE /scans/{scanId}", scan_id=sid)[0], 200)
        self.assertEqual(call("GET /scans/{scanId}", scan_id=sid)[0], 404)

    def test_bad_requests(self):
        cases = [
            {"mode": "graph", "image": "x"},                       # no deviceId
            {"deviceId": "d", "mode": "music"},                    # bad mode
            {"deviceId": "d", "mode": "graph"},                    # no image
            {"deviceId": "d", "mode": "graph", "image": "%%%"},    # not base64
            {"deviceId": "d", "mode": "graph", "image": base64.b64encode(b"hello").decode()},  # not an image
            {"deviceId": "d", "mode": "text"},                     # no image or text
            {"deviceId": "d", "mode": "text", "text": "a", "x": 1},  # unknown field
        ]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(call("POST /scans", body)[0], 400)
        self.assertEqual(call("PUT /scans/{scanId}", {"read": "yes"}, scan_id="S-1")[0], 400)
        self.assertEqual(call("PUT /scans/{scanId}", {"read": True}, scan_id="nope")[0], 404)
        self.assertEqual(call("DELETE /scans/{scanId}", scan_id="nope")[0], 404)

    def test_health_and_unknown_route(self):
        self.assertEqual(call("GET /health")[0], 200)
        self.assertEqual(call("PATCH /scans")[0], 404)


if __name__ == "__main__":
    unittest.main()
