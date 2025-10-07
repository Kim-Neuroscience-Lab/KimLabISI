#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
npm ci

export ISI_POETRY_PATH="$(command -v poetry)"
echo "Using Poetry executable: $ISI_POETRY_PATH"

echo "Starting Electron development environment"
exec npm run dev

