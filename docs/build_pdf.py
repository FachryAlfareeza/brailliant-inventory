"""Render docs/design_brief.html to PDF with headless Microsoft Edge.

    python docs/build_pdf.py --niu 123456 --name "Full Name"

Writes docs/design_brief.pdf and docs/architecture.png (from architecture.svg).
"""
import argparse
import datetime
import pathlib
import subprocess

DOCS = pathlib.Path(__file__).resolve().parent
EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

ap = argparse.ArgumentParser()
ap.add_argument("--niu", default="540199")
ap.add_argument("--name", default="Muhammad Fachry Alfareeza")
opts = ap.parse_args()

edge = next((p for p in EDGE_CANDIDATES if pathlib.Path(p).exists()), None)
if not edge:
    raise SystemExit("Microsoft Edge not found")

# Diagram PNG (embedded in the brief)
subprocess.run([edge, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--window-size=1200,720", f"--screenshot={DOCS / 'architecture.png'}",
                (DOCS / "architecture.svg").as_uri()], check=True, capture_output=True)

html = (DOCS / "design_brief.html").read_text(encoding="utf-8")
html = (html.replace("{{NAME}}", opts.name).replace("{{NIU}}", opts.niu)
            .replace("{{DATE}}", datetime.date.today().strftime("%d %B %Y")))
tmp = DOCS / "_brief_render.html"
tmp.write_text(html, encoding="utf-8")
try:
    subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={DOCS / 'design_brief.pdf'}", tmp.as_uri()],
                   check=True, capture_output=True)
finally:
    tmp.unlink(missing_ok=True)
print("wrote", DOCS / "design_brief.pdf")
