# Tests for the AWS Academy lab version: S3 storage (s3_table.py) and the
# container web server's request -> event mapping (server.py).
# Run: python -m unittest discover -s tests -v
import io
import json
import os
import sys
import unittest

from botocore.exceptions import ClientError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["OCR_ENABLED"] = "false"
import app  # noqa: E402
import server  # noqa: E402
from s3_table import S3Table  # noqa: E402


class FakeS3:
    """Just the S3 calls s3_table.py makes, kept in a dict."""

    def __init__(self):
        self.objects = {}

    def head_bucket(self, Bucket):
        return {}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": ""}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def get_paginator(self, name):
        objects = self.objects

        class Paginator:
            def paginate(self, Bucket, Prefix):
                yield {"Contents": [{"Key": k} for k in sorted(objects) if k.startswith(Prefix)]}

        return Paginator()


def call(route, body=None, scan_id=None, query=None):
    event = {"routeKey": route, "body": json.dumps(body) if body is not None else None,
             "pathParameters": {"scanId": scan_id} if scan_id else None,
             "queryStringParameters": query}
    res = app.lambda_handler(event, None)
    return res["statusCode"], json.loads(res["body"])


class S3StorageTests(unittest.TestCase):
    def setUp(self):
        self.s3 = FakeS3()
        app._table = S3Table(self.s3, "test-bucket")

    def tearDown(self):
        app._table = None

    def test_crud_on_s3(self):
        status, scan = call("POST /scans", {"deviceId": "dev-1", "mode": "text", "text": "Hi"})
        self.assertEqual(status, 201)
        sid = scan["scanId"]
        self.assertIn(f"scans/{sid}.json", self.s3.objects)

        self.assertEqual(call("GET /scans/{scanId}", scan_id=sid)[1]["braille"], "⠠⠓⠊")
        call("POST /scans", {"deviceId": "dev-2", "mode": "text", "text": "x"})
        status, body = call("GET /scans", query={"deviceId": "dev-1"})
        self.assertEqual((status, body["count"]), (200, 1))

        status, body = call("PUT /scans/{scanId}", {"read": True}, scan_id=sid)
        self.assertEqual((status, body["read"]), (200, True))
        self.assertEqual(call("DELETE /scans/{scanId}", scan_id=sid)[0], 200)
        self.assertEqual(call("GET /scans/{scanId}", scan_id=sid)[0], 404)
        self.assertEqual(call("DELETE /scans/{scanId}", scan_id=sid)[0], 404)
        self.assertEqual(call("PUT /scans/{scanId}", {"read": True}, scan_id=sid)[0], 404)

    def test_health(self):
        self.assertEqual(call("GET /health")[0], 200)


class ServerRouteTests(unittest.TestCase):
    def test_routes(self):
        e = server.to_event("GET", "/scans/S-123", None)
        self.assertEqual((e["routeKey"], e["pathParameters"]), ("GET /scans/{scanId}", {"scanId": "S-123"}))
        e = server.to_event("GET", "/scans?deviceId=dev-1", None)
        self.assertEqual((e["routeKey"], e["queryStringParameters"]), ("GET /scans", {"deviceId": "dev-1"}))
        self.assertEqual(server.to_event("POST", "/scans", "{}")["routeKey"], "POST /scans")
        self.assertEqual(server.to_event("PATCH", "/scans", None)["routeKey"], "PATCH /scans")  # -> 404 in app


if __name__ == "__main__":
    unittest.main()
