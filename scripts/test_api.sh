#!/usr/bin/env bash
# Calls every endpoint and checks the status codes.
# Usage: bash scripts/test_api.sh [API_URL]
#   (without a URL it uses the one saved by deploy.sh)
# The output is also saved to evidence/test_api_output.txt.
set -uo pipefail
source "$(dirname "$0")/config.sh"

URL="${1:-$(cat $URL_FILE 2>/dev/null)}"
if [[ -z "$URL" ]]; then
  echo "No URL given and no deploy found. Run scripts/deploy.sh or pass the URL."
  exit 1
fi
OUT="${OUT:-evidence/test_api_output.txt}"   # OUT=... saves it somewhere else
FAILED=0
mkdir -p build

# request body with the sample graph photo (too big to type on the command line)
$PY -c "
import base64, json
img = base64.b64encode(open('data/samples/graph.png', 'rb').read()).decode()
json.dump({'deviceId': 'brailliant-01', 'mode': 'graph', 'method': 'dark', 'image': img,
           'label': 'sample graph'}, open('build/graph_request.json', 'w'))
"

check() {  # check <expected status> <method> <path> [body or @file]
  local want=$1 method=$2 path=$3 body=${4:-}
  echo "\$ curl -X $method $URL$path ${body:+-d '${body:0:80}'}"
  local args=(-s -w '\nHTTP %{http_code}\n' -X "$method" "$URL$path")
  [[ -n "$body" ]] && args+=(-H 'Content-Type: application/json' -d "$body")
  RES=$(curl "${args[@]}")
  # long results (the dot grid) are shortened so the output stays readable
  local shown
  shown=$(head -n1 <<<"$RES" | cut -c1-300)
  echo "$shown$([[ ${#RES} -gt 320 ]] && echo ' ...')"
  local got
  got=$(tail -n1 <<<"$RES" | awk '{print $2}')
  if [[ "$got" == "$want" ]]; then
    echo "PASS"
  else
    echo "FAIL (expected $want)"
    FAILED=$((FAILED + 1))
  fi
  echo
}
scan_id() { head -n1 <<<"$RES" | $PY -c "import json,sys; print(json.load(sys.stdin)['scanId'])"; }

{
  echo "API test - $URL - $(date '+%Y-%m-%d %H:%M:%S')"
  echo

  echo "# health check (API -> code -> storage)"
  check 200 GET /health

  echo "# create: graph photo -> 96 x 64 pins"
  check 201 POST /scans @build/graph_request.json
  GRAPH_ID=$(scan_id)
  echo "# create: text -> Grade 1 braille"
  check 201 POST /scans '{"deviceId":"brailliant-01","mode":"text","text":"F = m x a"}'
  TEXT_ID=$(scan_id)
  echo "# create: bad input"
  check 400 POST /scans '{"deviceId":"brailliant-01","mode":"music"}'

  echo "# read"
  check 200 GET "/scans/$GRAPH_ID"
  check 200 GET "/scans?deviceId=brailliant-01"

  echo "# update"
  check 200 PUT "/scans/$TEXT_ID" '{"label":"Physics p.12","read":true}'

  echo "# delete"
  check 200 DELETE "/scans/$TEXT_ID"
  check 404 GET "/scans/$TEXT_ID"

  echo "Failed: $FAILED"
} 2>&1 | tee "$OUT"

grep -q "Failed: 0" "$OUT"
