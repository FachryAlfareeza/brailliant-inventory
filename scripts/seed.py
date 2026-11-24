# Loads data/parts.json (the 98 parts from the BrAIlliant BOM) through the API.
# Usage: python scripts/seed.py [API_URL]
# Parts that already exist come back as 409 and are skipped.
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if len(sys.argv) > 1:
    url = sys.argv[1]
else:
    url = (root / "scripts" / ".api_url").read_text().strip()
url = url.rstrip("/")

parts = json.loads((root / "data" / "parts.json").read_text())
results = {}
for part in parts:
    req = urllib.request.Request(url + "/parts", data=json.dumps(part).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            status = res.status
    except urllib.error.HTTPError as e:
        status = e.code
        if status != 409:
            print(part["partId"], status, e.read().decode())
    results[status] = results.get(status, 0) + 1

print(f"{len(parts)} parts sent, status codes: {results}")
