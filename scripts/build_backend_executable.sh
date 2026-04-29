#!/usr/bin/env bash
#
# Build the synthbud backend as a standalone Mach-O executable using PyInstaller.
# The output replaces frontend/src-tauri/bin/synthbud-backend so the Tauri shell
# can spawn it as a sidecar without requiring the user to have Python installed.
#
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
SPEC_FILE="$BACKEND_DIR/pyinstaller/synthbud-backend.spec"
DIST_DIR="$BACKEND_DIR/pyinstaller/dist"
BUILD_DIR="$BACKEND_DIR/pyinstaller/build"
SIDECAR_DEST="$REPO_ROOT/frontend/src-tauri/bin/synthbud-backend"

if [ ! -d "$BACKEND_DIR/.venv" ]; then
  echo "Backend virtualenv not found at $BACKEND_DIR/.venv" >&2
  echo "Create it first: python -m venv $BACKEND_DIR/.venv" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$BACKEND_DIR/.venv/bin/activate"

if ! python -c "import PyInstaller" >/dev/null 2>&1; then
  echo "Installing build dependencies (PyInstaller + runtime requirements)..."
  pip install -r "$BACKEND_DIR/requirements-build.txt"
fi

echo "Freezing backend with PyInstaller..."
rm -rf "$DIST_DIR" "$BUILD_DIR"
( cd "$BACKEND_DIR" && pyinstaller \
    --noconfirm \
    --clean \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    "$SPEC_FILE" )

FROZEN_BIN="$DIST_DIR/synthbud-backend"
if [ ! -x "$FROZEN_BIN" ]; then
  echo "Expected frozen executable not found at $FROZEN_BIN" >&2
  exit 1
fi

mkdir -p "$(dirname "$SIDECAR_DEST")"
cp "$FROZEN_BIN" "$SIDECAR_DEST"
chmod +x "$SIDECAR_DEST"

echo "Frozen backend installed at $SIDECAR_DEST"
