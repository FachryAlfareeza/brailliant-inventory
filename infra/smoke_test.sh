#!/usr/bin/env bash
# Connectivity + CRUD test against the deployed API. Output is also saved to
# evidence/smoke_test_output.txt for the Week 12 submission.
set -uo pipefail
source "$(dirname "$0")/config.sh"

API_URL="${1:-$(cat "$STATE_FILE" 2>/dev/null)}"
[[ -z "$API_URL" ]] && { echo "No API URL. Run infra/deploy.sh first or pass the URL."; exit 1; }
OUT="${OUT:-$ROOT/evidence/smoke_test_output.txt}"
TARGET="${TARGET:-AWS}"
mkdir -p "$ROOT/evidence"
ID="SMOKE-$(date +%s)"
FAILS=0

req() {  # req <expected-status> <method> <path> [json-body]
  local want=$1 method=$2 path=$3 body=${4:-}
  echo "\$ curl -X $method $API_URL$path ${body:+-d '$body'}"
  local args=(-s -w '\nHTTP %{http_code}  (%{time_total}s)\n' -X "$method" "$API_URL$path")
  [[ -n "$body" ]] && args+=(-H 'Content-Type: application/json' -d "$body")
  local res; res=$(curl "${args[@]}")
  echo "$res"
  local got; got=$(tail -n1 <<<"$res" | awk '{print $2}')
  if [[ "$got" == "$want" ]]; then echo "PASS (expected $want)"; else echo "FAIL (expected $want, got $got)"; FAILS=$((FAILS+1)); fi
  echo
}

{
  echo "BrAIlliant Parts Inventory - smoke test ($TARGET)"
  echo "Date (UTC): $(date -u '+%Y-%m-%d %H:%M:%S')"
  echo "API: $API_URL"
  [[ "$TARGET" == AWS ]] && echo "Caller: $(aws sts get-caller-identity --query Arn --output text 2>/dev/null || echo 'n/a')"
  echo

  echo "## 0. Connectivity: API Gateway -> Lambda -> DynamoDB"
  req 200 GET /health

  echo "## 1. CREATE"
  req 201 POST /parts "{\"partId\":\"$ID\",\"section\":\"Carrier board\",\"reference\":\"U2\",\"description\":\"BQ25895RTWR charger (smoke test)\",\"partNumber\":\"BQ25895RTWR\",\"package\":\"WQFN-24 4x4\",\"qtyPerDevice\":1,\"qtyInStock\":3,\"unitCostLow\":1.06,\"unitCostHigh\":2.23,\"location\":\"Drawer A1\"}"
  req 409 POST /parts "{\"partId\":\"$ID\",\"description\":\"duplicate\",\"qtyInStock\":1}"
  req 400 POST /parts '{"description":"missing qty"}'

  echo "## 2. READ"
  req 200 GET "/parts/$ID"
  req 200 "GET" "/parts?section=Carrier%20board"

  echo "## 3. UPDATE"
  req 200 PUT "/parts/$ID" '{"qtyInStock":10,"location":"Drawer B2"}'

  echo "## 4. DELETE"
  req 200 DELETE "/parts/$ID"
  req 404 GET "/parts/$ID"

  echo "Result: $FAILS failure(s)"
} 2>&1 | tee "$OUT"

echo "Saved to $OUT"
grep -q "Result: 0 failure" "$OUT"
