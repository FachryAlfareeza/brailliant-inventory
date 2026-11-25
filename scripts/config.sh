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
export MSYS_NO_PATHCONV=1   # stops Git Bash turning "/scans" into a Windows path

STACK_NAME="brailliant"
TABLE_NAME="brailliant-scans"

# run from the repo root with relative paths (aws.exe and python.exe can't read /d/... paths)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
URL_FILE="scripts/.api_url"

PY=python
command -v python >/dev/null 2>&1 || PY=python3
SAM=sam
command -v sam >/dev/null 2>&1 || SAM=.venv-sam/Scripts/sam.exe
