#!/usr/bin/env bash
#
# End-to-end build of the synthbud macOS desktop app.
#
# Produces:
#   frontend/src-tauri/target/release/bundle/macos/synthbud.app
#   frontend/src-tauri/target/release/bundle/dmg/synthbud_<version>_<arch>.dmg
#
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"
ICON_DIR="$FRONTEND_DIR/src-tauri/icons"
POSTGRES_BUNDLE="$FRONTEND_DIR/src-tauri/postgres/bin/postgres"

# ---------------------------------------------------------------------------
# 0. Prerequisite checks
# ---------------------------------------------------------------------------
fail() { echo "ERROR: $*" >&2; exit 1; }

[ -d "$REPO_ROOT/backend/.venv" ] \
  || fail "backend/.venv not found. Create it first: python -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt"

command -v cargo >/dev/null 2>&1 \
  || fail "Rust toolchain (cargo) not found. Install via https://rustup.rs/"

command -v brew >/dev/null 2>&1 \
  || fail "Homebrew not found. Install via https://brew.sh/"

PG_KEG="${SYNTHBUD_POSTGRES_KEG:-postgresql@16}"
brew --prefix "$PG_KEG" >/dev/null 2>&1 \
  || fail "Homebrew keg $PG_KEG not installed. Run: brew install $PG_KEG"

# ---------------------------------------------------------------------------
# 1. Icons — regenerate the Tauri icon set if missing, from any 1024x1024 PNG
#    in icons/ that isn't itself one of the known generated outputs.
# ---------------------------------------------------------------------------
if [ ! -f "$ICON_DIR/icon.icns" ] || [ ! -f "$ICON_DIR/icon.png" ]; then
  echo "[icons] Generated icon set missing — locating a source PNG..."
  SOURCE_ICON=""
  for candidate in "$ICON_DIR"/*.png; do
    [ -f "$candidate" ] || continue
    base="$(basename "$candidate")"
    case "$base" in
      icon.png|32x32.png|64x64.png|128x128.png|128x128@2x.png|Square*Logo.png|StoreLogo.png)
        continue
        ;;
    esac
    # Require at least 1024x1024 for the Tauri icon CLI.
    width="$(sips -g pixelWidth "$candidate" 2>/dev/null | awk '/pixelWidth/ {print $2}')"
    height="$(sips -g pixelHeight "$candidate" 2>/dev/null | awk '/pixelHeight/ {print $2}')"
    if [ -n "$width" ] && [ "$width" -ge 1024 ] && [ "$height" -ge 1024 ]; then
      SOURCE_ICON="$candidate"
      break
    fi
  done

  if [ -z "$SOURCE_ICON" ]; then
    fail "No 1024x1024+ source PNG found in $ICON_DIR/. Drop one and rerun."
  fi

  echo "[icons] Generating Tauri icon set from $SOURCE_ICON"
  ( cd "$FRONTEND_DIR/src-tauri" && npx --yes @tauri-apps/cli icon "$SOURCE_ICON" )
fi

# ---------------------------------------------------------------------------
# 2. Freeze the Python backend into a Mach-O binary
# ---------------------------------------------------------------------------
echo "[1/4] Freezing backend with PyInstaller..."
bash "$REPO_ROOT/scripts/build_backend_executable.sh"

# ---------------------------------------------------------------------------
# 3. Bundle Postgres (idempotent) — re-run when missing or when explicitly
#    requested via SYNTHBUD_REBUNDLE_POSTGRES=1.
# ---------------------------------------------------------------------------
if [ ! -x "$POSTGRES_BUNDLE" ] || [ "${SYNTHBUD_REBUNDLE_POSTGRES:-0}" = "1" ]; then
  echo "[2/4] Bundling Postgres binaries..."
  bash "$REPO_ROOT/scripts/bundle_postgres_macos.sh"
else
  echo "[2/4] Postgres bundle already present at $POSTGRES_BUNDLE — skipping."
  echo "      Set SYNTHBUD_REBUNDLE_POSTGRES=1 to refresh."
fi

# ---------------------------------------------------------------------------
# 4. Frontend deps + Tauri bundle
# ---------------------------------------------------------------------------
echo "[3/4] Installing frontend dependencies..."
( cd "$FRONTEND_DIR" && npm install )

# Wipe cargo's staged copy of resource files from any earlier (possibly
# failed) builds. Homebrew dylibs come in as 0444 and get cached read-only
# by cargo's incremental build, so when bundle_postgres_macos.sh rewrites
# them tauri-build later trips on `Permission denied (os error 13)` while
# refreshing its staging area.
rm -rf "$FRONTEND_DIR/src-tauri/target/release/postgres" \
       "$FRONTEND_DIR/src-tauri/target/release/bundle"

echo "[4/4] Building Tauri bundle..."
( cd "$FRONTEND_DIR" && npm run desktop:build )

echo ""
echo "Build complete. Outputs:"
find "$FRONTEND_DIR/src-tauri/target/release/bundle" -maxdepth 3 \
  \( -name "*.app" -o -name "*.dmg" \) -print 2>/dev/null || true
echo ""
echo "Launch with: open $FRONTEND_DIR/src-tauri/target/release/bundle/macos/synthbud.app"
