#!/usr/bin/env bash
# Deletes the whole stack (API, function, layer, table with all scans, role, logs, budget).
set -uo pipefail
source "$(dirname "$0")/config.sh"
$SAM delete --stack-name $STACK_NAME
rm -f $URL_FILE
