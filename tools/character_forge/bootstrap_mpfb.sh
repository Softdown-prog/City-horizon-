#!/usr/bin/env bash
set -euo pipefail

# Character Forge-only bootstrap for MPFB.
# This does not mutate the frozen CH Blender installation. MPFB is built,
# installed and enabled inside a temporary per-run Blender user profile so only
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
PACKAGE_ROOT="$SRC/src/mpfb"
PACKAGE_ZIP="$ROOT/mpfb-${MPFB_VERSION}.zip"
EXT_DIR="$EXT_REPO/mpfb"

mkdir -p "$ROOT" "$EXT_REPO" "$BLENDER_USER_RESOURCES"

if [[ ! -d "$SRC" ]]; then
  curl -L --fail --retry 3 "$MPFB_URL" -o "$ARCHIVE"
  mkdir -p "$SRC"
  tar -xzf "$ARCHIVE" -C "$SRC" --strip-components=1
fi

if [[ ! -f "$PACKAGE_ROOT/blender_manifest.toml" ]]; then
  echo "MPFB bootstrap failed: expected manifest missing at $PACKAGE_ROOT/blender_manifest.toml" >&2
  find "$SRC" -maxdepth 4 -name blender_manifest.toml -print >&2 || true
  exit 31
fi

# Blender 4.2 extensions must be installed/enabled, not merely copied into the
# extensions directory. Use an isolated user profile so this cannot affect the
# canonical CH Blender environment.
export BLENDER_USER_RESOURCES

rm -rf "$EXT_REPO" "$PACKAGE_ZIP"
mkdir -p "$EXT_REPO"

"$CH_BLENDER_EXE" --command extension repo-add user_default \
  --name "CH Character Forge Local" \
  --directory "$EXT_REPO" \
  --clear-all

"$CH_BLENDER_EXE" --command extension build \
  --source-dir "$PACKAGE_ROOT" \
  --output-filepath "$PACKAGE_ZIP"

"$CH_BLENDER_EXE" --command extension install-file \
  -r user_default \
  -e \
  "$PACKAGE_ZIP"

if [[ ! -f "$EXT_DIR/blender_manifest.toml" ]]; then
  echo "MPFB bootstrap failed: extension install completed but manifest is missing at $EXT_DIR/blender_manifest.toml" >&2
  "$CH_BLENDER_EXE" --command extension repo-list >&2 || true
  "$CH_BLENDER_EXE" --command extension list >&2 || true
  exit 32
fi

cat > "$ROOT/mpfb_bootstrap.json" <<JSON
{
  "contract": "CH_CHARACTER_FORGE_MPFB_BOOTSTRAP_V2",
  "version": "${MPFB_VERSION}",
  "tag": "${MPFB_TAG}",
  "commit": "${MPFB_COMMIT}",
  "sourceUrl": "${MPFB_URL}",
  "packageRoot": "${PACKAGE_ROOT}",
  "packageZip": "${PACKAGE_ZIP}",
  "extensionDir": "${EXT_DIR}",
  "blenderUserResources": "${BLENDER_USER_RESOURCES}",
  "installMode": "blender_extension_install_file_enabled",
  "scope": "character_forge_only"
}
JSON

echo "BLENDER_USER_RESOURCES=$BLENDER_USER_RESOURCES" >> "$GITHUB_ENV"
echo "CH_CHARACTER_FORGE_MPFB_ROOT=$EXT_DIR" >> "$GITHUB_ENV"
echo "CH_CHARACTER_FORGE_MPFB_VERSION=$MPFB_VERSION" >> "$GITHUB_ENV"

echo "Character Forge MPFB bootstrap ready and enabled: ${MPFB_VERSION} (${MPFB_COMMIT})"
