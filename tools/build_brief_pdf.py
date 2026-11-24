# Makes docs/design_brief.pdf from docs/design_brief.html (and the diagram PNG
# from docs/architecture.svg) using Edge in headless mode.
# Usage: python tools/build_brief_pdf.py
import datetime
import subprocess
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
NAME = "Muhammad Fachry Alfareeza"
NIU = "540199"

subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--window-size=1200,720", f"--screenshot={DOCS / 'architecture.png'}",
                (DOCS / "architecture.svg").as_uri()], check=True, capture_output=True)

html = (DOCS / "design_brief.html").read_text(encoding="utf-8")
html = html.replace("{{NAME}}", NAME).replace("{{NIU}}", NIU)
html = html.replace("{{DATE}}", datetime.date.today().strftime("%d %B %Y"))
tmp = DOCS / "_tmp_brief.html"
tmp.write_text(html, encoding="utf-8")
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={DOCS / 'design_brief.pdf'}", tmp.as_uri()],
               check=True, capture_output=True)
tmp.unlink()
print("done:", DOCS / "design_brief.pdf")
