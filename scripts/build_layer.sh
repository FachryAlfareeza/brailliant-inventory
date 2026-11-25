#!/usr/bin/env bash
# Downloads the Linux version of Pillow into build/layer/python, which the template
# uses as a Lambda layer. (pip on Windows would otherwise install the Windows version,
# which doesn't work inside Lambda.)
set -euo pipefail
source "$(dirname "$0")/config.sh"

if [[ -d build/layer/python/PIL ]]; then
  echo "Pillow layer already built"
  exit 0
fi
rm -rf build/layer
$PY -m pip install pillow --quiet \
  --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
  --implementation cp --python-version 3.13 --only-binary=:all: \
  --target build/layer/python
echo "built build/layer/python ($(ls build/layer/python | tr '\n' ' '))"
