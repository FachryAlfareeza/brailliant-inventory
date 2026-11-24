# Shared settings for the deploy / smoke-test / teardown scripts.
# Works on a personal AWS account (default) and on AWS Academy Learner Lab
# (detected automatically from the caller ARN).
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PAGER=""            # never open a pager for CLI output
export MSYS_NO_PATHCONV=1      # Git Bash on Windows: don't mangle "/parts" args

PROJECT="brailliant-inventory"
TABLE_NAME="brailliant-parts"
FUNCTION_NAME="brailliant-parts-api"
API_NAME="brailliant-parts-http-api"
LOG_RETENTION_DAYS=7

# Personal account: deploy.sh creates this least-privilege execution role.
# Learner Lab: role creation is blocked, so the pre-made LabRole is used instead.
OWN_ROLE_NAME="brailliant-parts-lambda-role"
LAB_ROLE_NAME="LabRole"

# Optional monthly cost alarm (personal account only). Set BUDGET_EMAIL to enable.
BUDGET_NAME="brailliant-inventory-budget"
BUDGET_LIMIT_USD="${BUDGET_LIMIT_USD:-1}"
BUDGET_EMAIL="${BUDGET_EMAIL:-}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Native Windows programs (aws.exe, python.exe) can't read Git Bash paths like
# /d/Coding/..., so every script works from the repo root with relative paths.
cd "$ROOT"
BUILD_DIR="build"
STATE_FILE="infra/.api_url"

# A Python that really runs (on Windows "python3" can be the Store stub).
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break; fi
done

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

# True when running with AWS Academy Learner Lab credentials.
is_learner_lab() { [[ "${CALLER_ARN:-}" == *"/voclabs/"* || "${CALLER_ARN:-}" == *"/vocstartsoft/"* ]]; }
