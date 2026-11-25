#!/usr/bin/env bash
# Makes submission/540199_MuhammadFachryAlfareeza_CC.zip from the last commit,
# plus a copy of the design brief PDF. Commit first, uncommitted files aren't included.
set -euo pipefail
cd "$(dirname "$0")/.."
NAME=540199_MuhammadFachryAlfareeza_CC
mkdir -p submission
[[ -z "$(git status --porcelain)" ]] || echo "warning: you have uncommitted changes"
git archive --format=zip --prefix=$NAME/ -o submission/$NAME.zip HEAD
cp docs/design_brief.pdf submission/${NAME}_DesignBrief.pdf
cp docs/design_brief.docx submission/${NAME}_DesignBrief.docx
[[ -f evidence/evidence.docx ]] && cp evidence/evidence.docx submission/${NAME}_Evidence.docx
[[ -f evidence/evidence.pdf ]] && cp evidence/evidence.pdf submission/${NAME}_Evidence.pdf
true
echo "made submission/$NAME.zip"
