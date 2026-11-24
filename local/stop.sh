#!/usr/bin/env bash
# Remove the DynamoDB Local container and the Docker network (data is in-memory, so it is lost).
docker rm -f kompaw-dynamodb >/dev/null 2>&1 && echo "removed kompaw-dynamodb"
docker network rm kompaw-local >/dev/null 2>&1 && echo "removed network kompaw-local"
true
