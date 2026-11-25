# Pretends to be the BrAIlliant device: sends a photo to the API and shows the result.
#   python scripts/device_sim.py IMAGE [--mode graph|text] [--method edges|dark] [--url URL]
# For graph mode it prints the 96 x 64 pin grid using Unicode braille cells
# (each cell = 2 x 4 pins, so 48 x 16 characters) and saves a preview PNG.
import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")  # Windows console defaults to cp1252, no braille

ap = argparse.ArgumentParser()
ap.add_argument("image")
ap.add_argument("--mode", default="graph", choices=["graph", "text"])
ap.add_argument("--method", default="dark", choices=["edges", "dark"])
ap.add_argument("--url", default="http://127.0.0.1:3000")
ap.add_argument("--device", default="brailliant-01")
args = ap.parse_args()

body = {"deviceId": args.device, "mode": args.mode,
        "image": base64.b64encode(Path(args.image).read_bytes()).decode(),
        "label": Path(args.image).name}
if args.mode == "graph":
    body["method"] = args.method

req = urllib.request.Request(args.url.rstrip("/") + "/scans", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=60) as res:
        status, scan = res.status, json.loads(res.read())
except urllib.error.HTTPError as e:
    status, scan = e.code, json.loads(e.read() or b"{}")

print(f"POST /scans -> HTTP {status}")
if status != 201:
    print(scan)
    raise SystemExit(1)
print(f"scanId {scan['scanId']}, mode {scan['mode']}, status {scan['status']}")

if scan["mode"] == "text":
    print("text:   ", scan.get("text", ""))
    print("braille:", scan.get("braille", scan.get("error", "")))
    raise SystemExit(0)

# 96 x 64 grid -> list of rows of 0/1
grid = [[(int(row, 16) >> (95 - x)) & 1 for x in range(96)] for row in scan["dots"]]
print(f"source {scan['sourceSize']} -> {scan['width']} x {scan['height']} pins, "
      f"{scan['dotCount']} raised ({args.method})\n")

# braille cell dot numbering: 1 2 3 7 down the left, 4 5 6 8 down the right
bits = [(0, 0, 0x01), (0, 1, 0x02), (0, 2, 0x04), (1, 0, 0x08),
        (1, 1, 0x10), (1, 2, 0x20), (0, 3, 0x40), (1, 3, 0x80)]
for cy in range(0, 64, 4):
    line = ""
    for cx in range(0, 96, 2):
        code = sum(b for dx, dy, b in bits if grid[cy + dy][cx + dx])
        line += chr(0x2800 + code)
    print(line)

# preview: original photo next to the pin grid
src = Image.open(args.image).convert("RGB")
src.thumbnail((480, 320))
pins = Image.new("RGB", (96 * 5, 64 * 5), (40, 40, 40))
d = ImageDraw.Draw(pins)
for y in range(64):
    for x in range(96):
        c = (255, 255, 255) if grid[y][x] else (80, 80, 80)
        d.ellipse([x * 5 + 1, y * 5 + 1, x * 5 + 4, y * 5 + 4], fill=c)
out = Image.new("RGB", (src.width + pins.width + 20, max(src.height, pins.height)), "white")
out.paste(src, (0, 0))
out.paste(pins, (src.width + 20, 0))
preview = ROOT / "build" / f"preview_{scan['scanId']}.png"
preview.parent.mkdir(exist_ok=True)
out.save(preview)
print(f"\npreview saved: {preview.relative_to(ROOT)}")
