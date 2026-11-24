# Shared settings for the deploy / smoke-test / teardown scripts.
# AWS Learner Lab only allows us-east-1 and us-west-2; us-east-1 is the default.
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PAGER=""            # never open a pager for CLI output
export MSYS_NO_PATHCONV=1      # Git Bash on Windows: don't mangle "/parts" args

PROJECT="brailliant-inventory"
TABLE_NAME="brailliant-parts"
FUNCTION_NAME="brailliant-parts-api"
API_NAME="brailliant-parts-http-api"
LOG_RETENTION_DAYS=7

# Learner Lab cannot create IAM roles, so the Lambda uses the pre-made LabRole.
ROLE_NAME="${ROLE_NAME:-LabRole}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT/build"
STATE_FILE="$ROOT/infra/.api_url"

# A Python that really runs (on Windows "python3" can be the Store stub).
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break; fi
done

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
