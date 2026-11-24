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
OUT="evidence/test_api_output.txt"
ID="TEST-$(date +%s)"
FAILED=0

check() {  # check <expected status> <method> <path> [body]
  local want=$1 method=$2 path=$3 body=${4:-}
  echo "\$ curl -X $method $URL$path ${body:+-d '$body'}"
  local args=(-s -w '\nHTTP %{http_code}\n' -X "$method" "$URL$path")
  [[ -n "$body" ]] && args+=(-H 'Content-Type: application/json' -d "$body")
  local res
  res=$(curl "${args[@]}")
  echo "$res"
  local got
  got=$(tail -n1 <<<"$res" | awk '{print $2}')
  if [[ "$got" == "$want" ]]; then
    echo "PASS"
  else
    echo "FAIL (expected $want)"
    FAILED=$((FAILED + 1))
  fi
  echo
}

{
  echo "API test - $URL - $(date '+%Y-%m-%d %H:%M:%S')"
  echo

  echo "# health check (API -> Lambda -> DynamoDB)"
  check 200 GET /health

  echo "# create"
  check 201 POST /parts "{\"partId\":\"$ID\",\"section\":\"Carrier board\",\"reference\":\"U2\",\"description\":\"BQ25895RTWR charger\",\"partNumber\":\"BQ25895RTWR\",\"package\":\"WQFN-24\",\"qtyPerDevice\":1,\"qtyInStock\":3,\"unitCostLow\":1.06,\"unitCostHigh\":2.23,\"location\":\"Drawer A1\"}"
  check 409 POST /parts "{\"partId\":\"$ID\",\"description\":\"same id again\",\"qtyInStock\":1}"
  check 400 POST /parts '{"description":"no qty"}'

  echo "# read"
  check 200 GET "/parts/$ID"
  check 200 GET "/parts?section=Carrier%20board"

  echo "# update"
  check 200 PUT "/parts/$ID" '{"qtyInStock":10,"location":"Drawer B2"}'

  echo "# delete"
  check 200 DELETE "/parts/$ID"
  check 404 GET "/parts/$ID"

  echo "Failed: $FAILED"
} 2>&1 | tee "$OUT"

grep -q "Failed: 0" "$OUT"
