#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse command line arguments
DEV_MODE=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --dev-mode)
      DEV_MODE=true
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --dev-mode    Enable development mode (allows software timestamps for webcams)"
      echo "  --help, -h    Show this help message"
      echo ""
      echo "Development Mode:"
      echo "  When enabled, allows using consumer webcams without hardware timestamps."
      echo "  Sets system.development_mode = true in parameters."
      echo "  NOT suitable for publication data - development and testing only."
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Use --help for usage information" >&2
      exit 1
      ;;
  esac
done

function require_command() {
  local binary="$1"
  if ! command -v "$binary" >/dev/null 2>&1; then
    echo "Required command not found: $binary" >&2
    exit 1
  fi
}

require_command poetry
require_command npm
require_command node

# Enable development mode if requested
if [ "$DEV_MODE" = true ]; then
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "⚠️  DEVELOPMENT MODE ENABLED"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "  Software timestamps allowed for webcams"
  echo "  NOT suitable for publication data"
  echo "  Use for development and testing only"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  export ISI_DEV_MODE=true
fi

echo "Cleaning backend artifacts"
pushd "$ROOT_DIR/apps/backend" >/dev/null
find "$PWD" -name '__pycache__' -type d -print0 | xargs -0 rm -rf 2>/dev/null || true
find "$PWD" -name '*.pyc' -print0 | xargs -0 rm -f 2>/dev/null || true
rm -rf .mypy_cache .pytest_cache
rm -f logs/*.log

echo "Installing backend dependencies with Poetry"
poetry install --no-interaction --sync
popd >/dev/null

echo "Cleaning desktop workspace"
pushd "$ROOT_DIR/apps/desktop" >/dev/null
rm -rf node_modules dist .vite .turbo

echo "Installing desktop dependencies with npm"
npm install

export ISI_POETRY_PATH="$(command -v poetry)"
echo "Using Poetry executable: $ISI_POETRY_PATH"

echo "Starting Electron development environment"
exec npm run dev

