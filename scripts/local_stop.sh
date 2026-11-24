#!/usr/bin/env bash
# Removes the DynamoDB Local container (the data is in memory, so it's gone after this).
docker rm -f kompaw-dynamodb >/dev/null 2>&1 && echo "removed kompaw-dynamodb"
docker network rm kompaw-local >/dev/null 2>&1 && echo "removed network"
true
