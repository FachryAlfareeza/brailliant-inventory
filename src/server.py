# Small web server that runs app.lambda_handler inside a container (ECS Fargate).
# It turns each HTTP request into the same event API Gateway would send to Lambda,
# so app.py works unchanged in both places. Port 8080.
import json
import re
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

import app

ROUTES = [  # (method, path pattern, route key) - same routes as the API Gateway version
    ("POST", r"^/scans$", "POST /scans"),
    ("GET", r"^/scans$", "GET /scans"),
    ("GET", r"^/scans/(?P<scanId>[^/]+)$", "GET /scans/{scanId}"),
    ("PUT", r"^/scans/(?P<scanId>[^/]+)$", "PUT /scans/{scanId}"),
    ("DELETE", r"^/scans/(?P<scanId>[^/]+)$", "DELETE /scans/{scanId}"),
    ("GET", r"^/health$", "GET /health"),
]
MAX_BODY = 8 * 1024 * 1024


def to_event(method, raw_path, body):
    url = urlsplit(raw_path)
    event = {"routeKey": f"{method} {url.path}", "rawPath": url.path,
             "queryStringParameters": dict(parse_qsl(url.query)) or None,
             "body": body, "isBase64Encoded": False}
    for m, pattern, key in ROUTES:
        match = re.match(pattern, url.path)
        if m == method and match:
            event["routeKey"] = key
            event["pathParameters"] = match.groupdict() or None
            break
    return event


class Handler(BaseHTTPRequestHandler):
    def _handle(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._send(413, json.dumps({"error": "Request too big"}))
            return
        body = self.rfile.read(length).decode() if length else None
        request_id = str(uuid.uuid4())
        start = time.time()
        print(f"START RequestId: {request_id} {method} {self.path}", flush=True)
        try:
            res = app.lambda_handler(to_event(method, self.path, body), None)
        except Exception as e:  # e.g. storage unreachable: answer 500 instead of dropping the connection
            print(f"ERROR RequestId: {request_id} {type(e).__name__}: {e}", flush=True)
            res = {"statusCode": 500, "body": json.dumps({"error": "Server error"})}
        self._send(res["statusCode"], res["body"])
        print(f"END RequestId: {request_id} status {res['statusCode']} "
              f"duration {(time.time() - start) * 1000:.1f} ms", flush=True)

    def _send(self, status, body):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def log_message(self, fmt, *args):  # the START/END lines above are enough
        pass


if __name__ == "__main__":
    print("listening on :8080", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
