#!/usr/bin/env bash
set -euo pipefail

# Character Forge-only bootstrap for the official MakeHuman system assets pack.
# The full archive is cached by GitHub Actions, but only the small subset needed
# by the current visitor gate is extracted into MPFB's isolated user-data tree.

ASSET_PACK_URL="https://files2.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip"
ASSET_PACK_NAME="makehuman_system_assets_cc0.zip"
ASSET_PACK_LICENSE="CC0-1.0"
CACHE_ROOT="${HOME}/.cache/ch-character-forge/makehuman-system-assets"
ARCHIVE="$CACHE_ROOT/$ASSET_PACK_NAME"

: "${BLENDER_USER_RESOURCES:?BLENDER_USER_RESOURCES must be exported by bootstrap_mpfb.sh}"
: "${CH_CHARACTER_FORGE_MPFB_ROOT:?CH_CHARACTER_FORGE_MPFB_ROOT must be exported by bootstrap_mpfb.sh}"

MPFB_USER_HOME="$BLENDER_USER_RESOURCES/extensions/.user/user_default/mpfb"
USER_DATA="$MPFB_USER_HOME/data"
MANIFEST="$MPFB_USER_HOME/ch_makehuman_system_assets_subset.json"

mkdir -p "$CACHE_ROOT" "$USER_DATA"

if [[ ! -s "$ARCHIVE" ]]; then
  echo "Character Forge: downloading official MakeHuman system assets pack..."
  curl -L --fail --retry 3 --retry-delay 2 "$ASSET_PACK_URL" -o "$ARCHIVE.tmp"
  mv "$ARCHIVE.tmp" "$ARCHIVE"
else
  echo "Character Forge: using cached MakeHuman system assets archive."
fi

python3 - "$ARCHIVE" "$USER_DATA" "$MANIFEST" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

archive = Path(sys.argv[1])
destination = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])

# Gate-only subset. Keep whole directories because MHCLO assets reference
# sibling OBJ/material/texture files by relative path.
required_dirs = {
    "clothes/male_casualsuit01",
    "clothes/shoes01",
    "hair/short01",
    "eyes/low-poly",
    "eyebrows/eyebrow001",
}
required_pack_files = {
    "packs/makehuman_system_assets.json",
}


def normalized_relative(member: str) -> PurePosixPath | None:
    parts = [p for p in PurePosixPath(member).parts if p not in ("", ".")]
    # Asset-pack zips may optionally carry one or more wrapper directories.
    for index in range(len(parts)):
        candidate = PurePosixPath(*parts[index:])
        ctext = candidate.as_posix()
        if any(ctext == root or ctext.startswith(root + "/") for root in required_dirs):
            return candidate
        if ctext in required_pack_files:
            return candidate
    return None

with zipfile.ZipFile(archive) as zf:
    selected: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
    for info in zf.infolist():
        rel = normalized_relative(info.filename)
        if rel is not None and not info.is_dir():
            selected.append((info, rel))

    if not selected:
        raise RuntimeError("No requested MakeHuman system assets were found in the asset pack")

    for info, rel in selected:
        target = destination.joinpath(*rel.parts).resolve()
        root = destination.resolve()
        if root != target and root not in target.parents:
            raise RuntimeError(f"Unsafe asset-pack path: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, target.open("wb") as dst:
            dst.write(src.read())

required = [
    destination / "clothes/male_casualsuit01/male_casualsuit01.mhclo",
    destination / "clothes/shoes01/shoes01.mhclo",
    destination / "hair/short01/short01.mhclo",
    destination / "eyes/low-poly/low-poly.mhclo",
    destination / "eyebrows/eyebrow001/eyebrow001.mhclo",
]
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise RuntimeError(f"MakeHuman asset bootstrap incomplete; missing: {missing}")

sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
manifest = {
    "contract": "CH_CHARACTER_FORGE_MAKEHUMAN_SYSTEM_ASSETS_V1",
    "source": "https://files2.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip",
    "license": "CC0-1.0",
    "archive": str(archive),
    "archiveSha256Observed": sha256,
    "userData": str(destination),
    "subset": [
        "clothes/male_casualsuit01",
        "clothes/shoes01",
        "hair/short01",
        "eyes/low-poly",
        "eyebrows/eyebrow001",
    ],
    "purpose": "Character Forge visitor SOUTH visual gate",
}
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest, indent=2))
PY

echo "CH_CHARACTER_FORGE_MAKEHUMAN_DATA=$USER_DATA" >> "$GITHUB_ENV"
echo "CH_CHARACTER_FORGE_MAKEHUMAN_ARCHIVE=$ARCHIVE" >> "$GITHUB_ENV"
echo "CH_CHARACTER_FORGE_MAKEHUMAN_LICENSE=$ASSET_PACK_LICENSE" >> "$GITHUB_ENV"

echo "Character Forge MakeHuman system-assets subset ready: $USER_DATA"
