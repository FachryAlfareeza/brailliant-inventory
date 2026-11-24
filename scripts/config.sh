# Settings shared by the scripts in this folder.

# plain "bash" in PowerShell opens WSL, which can't use Docker Desktop or the Windows AWS CLI
if [[ "$(uname -s)" == Linux* ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  echo "This is WSL bash. Use Git Bash instead, e.g. from PowerShell:"
  echo '  & "C:\Program Files\Git\bin\bash.exe" '"$0"
  exit 1
fi

export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PAGER=""
export MSYS_NO_PATHCONV=1   # stops Git Bash turning "/parts" into a Windows path

PROJECT="brailliant-inventory"
TABLE_NAME="brailliant-parts"
FUNCTION_NAME="brailliant-parts-api"
API_NAME="brailliant-parts-http-api"
ROLE_NAME_OWN="brailliant-parts-lambda-role"   # created on a normal account
ROLE_NAME_LAB="LabRole"                        # Learner Lab can't create roles

BUDGET_NAME="brailliant-inventory-budget"
BUDGET_LIMIT_USD="${BUDGET_LIMIT_USD:-1}"
BUDGET_EMAIL="${BUDGET_EMAIL:-}"

# run from the repo root and use relative paths, because aws.exe and
# python.exe on Windows can't read Git Bash paths like /d/Coding/...
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BUILD_DIR="build"
URL_FILE="scripts/.api_url"

PY=python
command -v python >/dev/null 2>&1 || PY=python3

is_learner_lab() { [[ "${CALLER_ARN:-}" == *"/voclabs/"* ]]; }
