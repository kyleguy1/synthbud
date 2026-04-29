#!/usr/bin/env bash
#
# Copy a minimal Postgres runtime from a Homebrew installation into
# frontend/src-tauri/postgres/ and rewrite dylib references so the binaries
# resolve their libraries from @executable_path/../lib at runtime.
#
# Only ships what the desktop runtime actually needs (server + client
# binaries, libpq, and the PostgreSQL share/ tree). Skipping the static
# archives, extension dylibs, man pages, and pkgconfig keeps the bundle
# under tauri-build's resource walker limits and shrinks the .app by ~80%.
#
# Idempotent. Re-run after upgrading Homebrew Postgres.
#
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_ROOT="$REPO_ROOT/frontend/src-tauri/postgres"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required to source Postgres binaries for bundling." >&2
  exit 1
fi

PG_KEG="${SYNTHBUD_POSTGRES_KEG:-postgresql@16}"
PG_PREFIX="$(brew --prefix "$PG_KEG" 2>/dev/null || true)"
if [ -z "$PG_PREFIX" ] || [ ! -d "$PG_PREFIX" ]; then
  echo "Homebrew keg $PG_KEG is not installed. Run: brew install $PG_KEG" >&2
  exit 1
fi

PG_BIN_SRC="$PG_PREFIX/bin"
PG_LIB_SRC="$PG_PREFIX/lib"
PG_SHARE_SRC="$PG_PREFIX/share"

if [ ! -x "$PG_BIN_SRC/postgres" ]; then
  echo "Expected $PG_BIN_SRC/postgres to exist." >&2
  exit 1
fi

DEST_BIN="$DEST_ROOT/bin"
DEST_LIB="$DEST_ROOT/lib"
DEST_SHARE="$DEST_ROOT/share"

echo "Bundling minimal Postgres from $PG_PREFIX into $DEST_ROOT..."
rm -rf "$DEST_ROOT"
mkdir -p "$DEST_BIN" "$DEST_LIB" "$DEST_SHARE"

# `cp -X` excludes ACLs and most extended attributes, but macOS still
# attaches `com.apple.provenance` to every newly created file. That xattr
# is benign and isn't what triggered earlier resource-walker failures —
# the actual culprit was bundle file count blowing past tauri-build's
# walker budget. Stay lean and ship only what the runtime needs.

# Server + client binaries we actually invoke from desktop_launcher.py.
for tool in postgres pg_ctl initdb psql; do
  cp -X "$PG_BIN_SRC/$tool" "$DEST_BIN/$tool"
done

# Transitively copy every Homebrew dylib referenced by the bundled binaries.
# Postgres pulls in a lot more than libpq+OpenSSL+ICU at runtime — gettext
# (libintl), krb5 (libgssapi_krb5), zstd, lz4, readline, and their own
# transitive deps. Walking otool -L iteratively is the only reliable way
# to capture them all without hardcoding each Homebrew formula.
copy_homebrew_dylibs() {
  local queue=("$@")
  # macOS ships bash 3.2, no associative arrays. Track 'seen' via a
  # newline-delimited string and grep-with-fixed-string lookups.
  local seen=$'\n'
  while [ ${#queue[@]} -gt 0 ]; do
    local current="${queue[0]}"
    queue=("${queue[@]:1}")

    case "$seen" in
      *$'\n'"$current"$'\n'*) continue ;;
    esac
    seen="$seen$current"$'\n'

    [ -f "$current" ] || continue

    # Where the current binary lives — used to resolve @loader_path
    # references (ICU dylibs use these for their sibling deps).
    local current_dir
    current_dir="$(dirname "$current")"

    # Iterate this binary's direct dylib references and copy any that come
    # from outside the system frameworks.
    while IFS= read -r dep; do
      [ -n "$dep" ] || continue

      # Resolve to an absolute Homebrew path. Three reference styles:
      #   1. Absolute Homebrew path: take it as-is
      #   2. @loader_path/X: resolve relative to current binary's dir
      #   3. @rpath/X or absolute /usr/lib/...: skip (system or unsupported)
      local resolved=""
      case "$dep" in
        /opt/homebrew/*|/usr/local/Cellar/*|/usr/local/opt/*)
          resolved="$dep"
          ;;
        @loader_path/*)
          local rel="${dep#@loader_path/}"
          resolved="$current_dir/$rel"
          ;;
        *)
          continue
          ;;
      esac

      # Resolve symlinks so we always copy the real file, then place the
      # copy at DEST_LIB/<basename> (matching what the dependent binary
      # will look up via @executable_path/../lib/).
      local real_dep
      real_dep="$(readlink -f "$resolved" 2>/dev/null || echo "$resolved")"
      [ -f "$real_dep" ] || continue

      local dest_path="$DEST_LIB/$(basename "$resolved")"
      if [ ! -f "$dest_path" ]; then
        cp -fX "$real_dep" "$dest_path"
      fi
      queue+=("$real_dep")
    done < <(otool -L "$current" 2>/dev/null | awk 'NR>1 {print $1}')
  done
}

# Seed the walker with the four binaries we ship plus libpq itself
# (psycopg2 in the frozen backend will dlopen the bundled libpq).
copy_homebrew_dylibs \
  "$DEST_BIN/postgres" \
  "$DEST_BIN/pg_ctl" \
  "$DEST_BIN/initdb" \
  "$DEST_BIN/psql" \
  "$PG_LIB_SRC/libpq.5.dylib"

# Postgres share/ contains the bootstrap SQL, timezone data, locale files,
# and encoding conversion tables that initdb/postgres need. The Homebrew
# layout puts them under share/<keg>/.
PG_SHARE_DIR_NAME="$(basename "$PG_KEG")"
if [ -d "$PG_SHARE_SRC/$PG_SHARE_DIR_NAME" ]; then
  cp -RX "$PG_SHARE_SRC/$PG_SHARE_DIR_NAME" "$DEST_SHARE/$PG_SHARE_DIR_NAME"
elif [ -d "$PG_SHARE_SRC/postgresql" ]; then
  cp -RX "$PG_SHARE_SRC/postgresql" "$DEST_SHARE/postgresql"
else
  echo "Could not locate postgresql share directory under $PG_SHARE_SRC" >&2
  exit 1
fi

# Patch dylib install names so binaries look in @executable_path/../lib at
# runtime instead of /opt/homebrew/.../lib (which won't exist on a fresh Mac).
patch_binary() {
  local target="$1"
  chmod u+w "$target" 2>/dev/null || true

  # Build the dep list once so a non-matching grep (e.g. libcrypto, which
  # has no Homebrew deps) doesn't abort the function via `set -e | pipefail`
  # before we reach the re-sign step. install_name_tool -id was already
  # called by the caller for dylibs, so the signature is invalid and the
  # final codesign is mandatory — losing it leaves Postgres unable to load
  # the dylib (macOS SIGKILLs any process that loads a dylib whose
  # signature doesn't match its bytes).
  #
  # Capture both Homebrew-absolute deps and @loader_path/ refs so ICU
  # dylibs (which reference each other via @loader_path/libicudata...) get
  # rewritten to the bundle layout.
  local deps
  deps="$(otool -L "$target" 2>/dev/null \
    | awk 'NR>1 {print $1}' \
    | grep -E '^(/opt/homebrew|/usr/local|@loader_path)/' || true)"

  while IFS= read -r dep; do
    [ -n "$dep" ] || continue
    local base
    base="$(basename "$dep")"
    install_name_tool -change "$dep" "@executable_path/../lib/$base" "$target" 2>/dev/null || true
  done <<< "$deps"

  codesign --force --sign - "$target" >/dev/null 2>&1 || true
}

for tool in "$DEST_BIN"/*; do
  [ -f "$tool" ] || continue
  patch_binary "$tool"
done

find "$DEST_LIB" -maxdepth 1 -type f -name '*.dylib' \
  | while read -r dylib; do
      install_name_tool -id "@executable_path/../lib/$(basename "$dylib")" "$dylib" 2>/dev/null || true
      patch_binary "$dylib"
    done

# Many Homebrew dylibs ship with mode 0444 (no owner-write). cargo/tauri-build's
# resource walker stat()s every entry under the resource tree and at least one
# downstream operation needs writability — leaving them read-only manifests as
# `Permission denied (os error 13)` deep inside the build script. Make every
# bundled file owner-writable defensively.
chmod -R u+w "$DEST_ROOT"

echo "Bundled $(find "$DEST_ROOT" -type f | wc -l | xargs) files into $DEST_ROOT"
echo "Verify with: otool -L $DEST_BIN/postgres"
