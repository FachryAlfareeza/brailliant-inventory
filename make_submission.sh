#!/usr/bin/env bash
# Build the Week 12 submission: submission/540199_MuhammadFachryAlfareeza_CC.zip
# Contents: the committed repo (git archive of HEAD) + the design brief PDF at the top level.
# Commit your evidence screenshots first, then re-run this script.
set -euo pipefail
cd "$(dirname "$0")"
BASE="540199_MuhammadFachryAlfareeza_CC"
mkdir -p submission
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Warning: uncommitted changes are NOT included in the zip:"; git status --short
fi
git archive --format=zip --prefix="$BASE/" -o "submission/$BASE.zip" HEAD
cp docs/design_brief.pdf "submission/${BASE}_DesignBrief.pdf"
python - "submission/$BASE.zip" "docs/design_brief.pdf" "$BASE" <<'EOF'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1], "a") as z:
    z.write(sys.argv[2], f"{sys.argv[3]}/{sys.argv[3]}_DesignBrief.pdf")
    print(len(z.namelist()), "files in", sys.argv[1])
EOF
