"""Promote an approved 8-direction character sequence into the canonical asset tree."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

EXPECTED = ("n", "ne", "e", "se", "s", "sw", "w", "nw")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--asset-dir", required=True)
    parser.add_argument("--pack-out", required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def main():
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("contract") == "TYCOON_CHARACTER_SEQUENCE_V1", "Wrong character manifest contract")
    require(tuple(manifest.get("directionOrder", [])) == EXPECTED, "Character directions must be canonical")
    require(manifest.get("directionCount") == 8, "Character needs eight directions")
    require(manifest.get("animation", {}).get("frameCount") == 8, "Character needs eight frames")

    base = manifest_path.parent
    asset_id = manifest["assetId"]
    asset_dir = Path(args.asset_dir).resolve() / asset_id
    pack_out = Path(args.pack_out).resolve()
    if (asset_dir.exists() or pack_out.exists()) and not args.force:
        raise FileExistsError("Target exists; pass --force to replace it")
    asset_dir.mkdir(parents=True, exist_ok=True)

    files = manifest.get("files", {})
    copy_names = [files[key] for key in ("spriteSheet", "atlas", "sequenceReview", "context8Dir")]
    for direction in manifest["directions"]:
        copy_names.extend(frame["file"] for frame in direction["frames"])
    for name in dict.fromkeys(copy_names):
        source = base / name
        require(source.is_file(), f"Missing sequence file: {source}")
        shutil.copy2(source, asset_dir / Path(name).name)

    pack = {
        "packVersion": "CH_ACTOR_CONTENT_PACK_V1",
        "id": asset_id,
        "kind": "actor",
        "assetId": asset_id,
        "sequenceContract": manifest["contract"],
        "bakeStatus": manifest.get("status", "production_candidate"),
        "humanApprovalRequired": manifest.get("humanApprovalRequired", True),
        "cameraContract": manifest["cameraContract"],
        "gridContract": manifest["gridContract"],
        "runtime": manifest.get("runtime", {}),
        "directionOrder": list(EXPECTED),
        "animation": manifest["animation"],
        "pivotPolicy": "shared_projected_world_origin",
        "sourcePath": str(asset_dir),
        "files": files,
    }
    pack_out.parent.mkdir(parents=True, exist_ok=True)
    pack_out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    print("CH_ACTOR_CONTENT_PACK_V1: PASS")
    print(pack_out)


if __name__ == "__main__":
    main()
