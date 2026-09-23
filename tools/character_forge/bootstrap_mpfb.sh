#!/usr/bin/env bash
set -euo pipefail

# Character Forge-only bootstrap for MPFB.
# This does not mutate the frozen CH Blender installation. It installs the
# extension into a temporary per-run Blender user-resource directory so only
# Character Forge jobs see it.

MPFB_VERSION="2.0.17"
MPFB_TAG="v${MPFB_VERSION}"
MPFB_COMMIT="80919fa4682335c41847f761a4d79dcad4124732"
MPFB_URL="https://github.com/makehumancommunity/mpfb2/archive/${MPFB_COMMIT}.tar.gz"

: "${CH_BLENDER_EXE:?CH_BLENDER_EXE must point at the frozen CH Blender executable}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

ROOT="$RUNNER_TEMP/ch-character-forge"
SRC="$ROOT/mpfb2-${MPFB_COMMIT}"
ARCHIVE="$ROOT/mpfb2-${MPFB_COMMIT}.tar.gz"
BLENDER_USER_RESOURCES="$ROOT/blender_user"
EXT_REPO="$BLENDER_USER_RESOURCES/extensions/user_default"
EXT_DIR="$EXT_REPO/mpfb"

mkdir -p "$ROOT" "$EXT_REPO"

if [[ ! -d "$SRC" ]]; then
  curl -L --fail --retry 3 "$MPFB_URL" -o "$ARCHIVE"
  mkdir -p "$SRC"
  tar -xzf "$ARCHIVE" -C "$SRC" --strip-components=1
fi

# MPFB 2.x is a Blender extension whose package root is src/mpfb/.
PACKAGE_ROOT="$SRC/src/mpfb"
if [[ ! -f "$PACKAGE_ROOT/blender_manifest.toml" ]]; then
  echo "MPFB bootstrap failed: expected manifest missing at $PACKAGE_ROOT/blender_manifest.toml" >&2
  find "$SRC" -maxdepth 4 -name blender_manifest.toml -print >&2 || true
  exit 31
fi

rm -rf "$EXT_DIR"
mkdir -p "$EXT_DIR"
cp -a "$PACKAGE_ROOT/." "$EXT_DIR/"

cat > "$ROOT/mpfb_bootstrap.json" <<JSON
{
  "contract": "CH_CHARACTER_FORGE_MPFB_BOOTSTRAP_V1",
  "version": "${MPFB_VERSION}",
  "tag": "${MPFB_TAG}",
  "commit": "${MPFB_COMMIT}",
  "sourceUrl": "${MPFB_URL}",
  "packageRoot": "${PACKAGE_ROOT}",
  "extensionDir": "${EXT_DIR}",
  "blenderUserResources": "${BLENDER_USER_RESOURCES}",
  "scope": "character_forge_only"
}
JSON

echo "BLENDER_USER_RESOURCES=$BLENDER_USER_RESOURCES" >> "$GITHUB_ENV"
echo "CH_CHARACTER_FORGE_MPFB_ROOT=$EXT_DIR" >> "$GITHUB_ENV"
echo "CH_CHARACTER_FORGE_MPFB_VERSION=$MPFB_VERSION" >> "$GITHUB_ENV"

echo "Character Forge MPFB bootstrap ready: ${MPFB_VERSION} (${MPFB_COMMIT})"
