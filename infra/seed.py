"""Load the BrAIlliant BOM (data/parts_seed.json, 98 parts) through the API.

Uses only the standard library, so it runs in the Learner Lab terminal too.
    python infra/seed.py [API_URL] [--limit N]
Existing parts (HTTP 409) are skipped, so it is safe to re-run.
"""
import argparse
import json
import pathlib
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("url", nargs="?")
ap.add_argument("--limit", type=int)
opts = ap.parse_args()
url = (opts.url or (ROOT / "infra" / ".api_url").read_text().strip()).rstrip("/")

parts = json.loads((ROOT / "data" / "parts_seed.json").read_text())[:opts.limit]
counts = {}
for p in parts:
    req = urllib.request.Request(f"{url}/parts", data=json.dumps(p).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
        if code not in (409,):
            print(p["partId"], code, e.read().decode())
    counts[code] = counts.get(code, 0) + 1
print(f"Seeded {len(parts)} parts -> status counts {counts}")
