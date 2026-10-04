#!/usr/bin/env python3
"""Promote already-approved articulated steam-train bakes without rebaking art."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
POSTPROCESS = REPO_ROOT / "tools/tycoon_photo_studio/postprocess.py"
STUDIO = REPO_ROOT / "tools/tycoon_photo_studio/render_pipelines/large_asset/studio_1024.json"
DIRECTIONS = ("south", "east", "west", "north")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--locomotive-spec", required=True)
    parser.add_argument("--coach-spec", required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_source(root: Path, name: str) -> Path:
    direct = root / name
    if direct.is_dir():
        return direct
    matches = [path for path in root.rglob(name) if path.is_dir()]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one source directory {name!r}, got {matches}")
    return matches[0]


def normalize_staging_metadata(source: Path) -> None:
    path = source / "studio_metadata.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    existing = data.get("contract")
    if existing not in (None, "TYCOON_ASSET_BAKE_V1"):
        raise RuntimeError(f"Unexpected bake contract {existing!r}")
    data["contract"] = "TYCOON_ASSET_BAKE_V1"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def validate_sprite(path: Path) -> None:
    with Image.open(path) as image:
        if image.mode != "RGBA" or image.size != (1024, 1024):
            raise RuntimeError(f"{path}: expected 1024x1024 RGBA, got {image.size} {image.mode}")
        alpha = image.getchannel("A")
        lo, hi = alpha.getextrema()
        if lo != 0 or hi != 255:
            raise RuntimeError(f"{path}: invalid alpha extrema {(lo, hi)}")
        if alpha.getbbox() is None:
            raise RuntimeError(f"{path}: no visible pixels")
        # Do not require transparent corner pixels here. The canonical studio
        # intentionally permits a soft peripheral shadow/halo after postprocess.


def promote(spec_path: Path, artifact_root: Path, final_root: Path) -> None:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("contract") != "CH_RUNTIME_ASSET_PROMOTION_V1" or spec.get("approved") is not True:
        raise RuntimeError(f"Unapproved promotion spec: {spec_path}")
    if spec.get("promotionRevision") != 3:
        raise RuntimeError(f"V3 promoter requires promotionRevision=3: {spec_path}")
    asset_id = spec["assetId"]
    role = spec["unitRole"]
    if asset_id not in {"vehicle.steam_train.locomotive.01", "vehicle.steam_train.coach.01"}:
        raise RuntimeError(f"Unexpected assetId {asset_id}")
    slug = "locomotive" if role == "locomotive" else "coach"
    source = find_source(artifact_root, spec["sourceDir"])
    normalize_staging_metadata(source)
    output = final_root / slug
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, str(POSTPROCESS),
        "--input", str(source),
        "--output", str(output),
        "--studio-preset", str(STUDIO),
    ], cwd=REPO_ROOT, check=True)

    package_path = output / f"{asset_id}_manifest.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package_views = {view["direction"]: view for view in package["views"]}
    if set(package_views) != set(DIRECTIONS):
        raise RuntimeError(f"Missing directional view in {package_path}")

    destination = REPO_ROOT / spec["destination"]
    destination.mkdir(parents=True, exist_ok=True)
    views = {}
    for direction in DIRECTIONS:
        source_png = output / f"{asset_id}_{direction}.png"
        validate_sprite(source_png)
        target = destination / f"steam_train_{slug}_{direction}.png"
        shutil.copy2(source_png, target)
        views[direction] = {
            "file": target.name,
            "pivot": package_views[direction]["pivot"],
            "sha256": sha256(target),
        }

    runtime_manifest = {
        "contract": "CH_RUNTIME_VEHICLE_TRAIN_UNIT_V1",
        "assetId": asset_id,
        "assetType": "vehicle_train_unit",
        "unitRole": role,
        "visualContract": "CH_STYLIZED_PRERENDER_V1",
        "cameraContract": "CH_CAMERA_V1",
        "runtimeRepresentation": "2D_RGBA_pre_rendered_sprite",
        "format": "PNG_RGBA",
        "frameSize": [1024, 1024],
        "transparentBackground": True,
        "directionOrder": list(DIRECTIONS),
        "logicalDimensionsM": {
            "length": spec["logicalLengthM"],
            "width": spec["logicalWidthM"],
        },
        "views": views,
        "sourceCommit": spec["sourceCommit"],
        "sourceWorkflowRun": spec["sourceWorkflowRun"],
        "sourceArtifactId": spec["sourceArtifactId"],
        "approvedProxySha256": spec["approvedProxySha256"],
        "approvedForRuntime": True,
    }
    runtime_path = destination / "steam_train_unit_runtime.json"
    runtime_path.write_text(json.dumps(runtime_manifest, indent=2) + "\n", encoding="utf-8")

    definition_path = REPO_ROOT / "assets/definitions" / f"steam_train_{slug}_01.json"
    definition = {
        "id": f"steam_train_{slug}_01",
        "name": "Trem a Vapor - Locomotiva" if role == "locomotive" else "Trem a Vapor - Vagao de Passageiros",
        "category": "transport",
        "texture": f"assets/vehicles/steam_train_{slug}_01/steam_train_{slug}_south.png",
        "sprites": {
            "0": f"assets/vehicles/steam_train_{slug}_01/steam_train_{slug}_south.png",
            "1": f"assets/vehicles/steam_train_{slug}_01/steam_train_{slug}_west.png",
            "2": f"assets/vehicles/steam_train_{slug}_01/steam_train_{slug}_north.png",
            "3": f"assets/vehicles/steam_train_{slug}_01/steam_train_{slug}_east.png",
        },
        "rotatable": True,
        "playerBuildable": False,
        "productionStatus": "runtime_vehicle_train_unit_approved",
        "runtimeRole": f"vehicle_train_{role}",
        "runtimeManifest": f"assets/vehicles/steam_train_{slug}_01/steam_train_unit_runtime.json",
        "sourceApprovedProxySha256": spec["approvedProxySha256"],
    }
    definition_path.write_text(json.dumps(definition, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    artifact_root = (REPO_ROOT / args.artifact_root).resolve()
    final_root = REPO_ROOT / "out/runtime_promotion_v3/final"
    specs = [REPO_ROOT / args.locomotive_spec, REPO_ROOT / args.coach_spec]
    for spec in specs:
        promote(spec, artifact_root, final_root)
    print("Articulated steam-train runtime units promoted from approved artifact.")


if __name__ == "__main__":
    main()
