#!/usr/bin/env python3
"""Promote the reviewed occupied Flame V2 bake into runtime atomically.

The source PNGs come only from the approved CH Blender Actions artifact. Text
runtime changes are staged in-repository and are copied into their live paths in
the same commit as the packed atlas and generated runtime manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[3]
PAYLOAD = REPO / "tools/animation_preview/coaster_flame_v2_text_payload.json"
EXPECTED_CONTRACT = "CH_COASTER_CAR_ATLAS_RUNTIME_V2"
EXPECTED_ORIENTATION = "CH_COASTER_CAR_ORIENTATION_V2"
FRAME_W = 256
FRAME_H = 256
COLUMNS = 16
ROWS = 12
FRAME_COUNT = 192


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_one(root: Path, name: str) -> Path:
    found = list(root.rglob(name))
    if len(found) != 1:
        raise RuntimeError(f"expected exactly one {name}, found {len(found)}")
    return found[0]


def patch_shared_runtime_comments_and_direct_renderer() -> None:
    train = REPO / "src/coaster_train_runtime.h"
    text = train.read_text(encoding="utf-8")
    old = (
        "// inversions to be represented without pretending that heading+pitch alone are\n"
        "// sufficient. The current 40-frame atlas remains a compatibility fallback until\n"
        "// CH_COASTER_CAR_ATLAS_RUNTIME_V2 is baked."
    )
    new = (
        "// inversions to be represented without pretending that heading+pitch alone are\n"
        "// sufficient. Moving Flame cars consume the promoted occupied\n"
        "// CH_COASTER_CAR_ATLAS_RUNTIME_V2; unsupported combined pitch+roll poses are\n"
        "// reported explicitly instead of silently falling back to V1."
    )
    if old not in text:
        raise RuntimeError("coaster_train_runtime.h legacy V1 comment anchor changed")
    train.write_text(text.replace(old, new), encoding="utf-8")

    renderer = REPO / "C++/MapForge2/src/coaster_project_video_main.cpp"
    text = renderer.read_text(encoding="utf-8")
    old = '''    QImage atlas(atlasPath);\n    if (atlas.isNull() || atlas.width() != 2048 || atlas.height() != 1280) {\n        std::fprintf(stderr, "invalid Flame car pose atlas\\n");\n        return 3;\n    }'''
    new = '''    QImage atlas(atlasPath);\n    const QSize expectedAtlasSize(\n        ch::coaster::kCarPoseAtlasColumns * ch::coaster::kCarPoseFrameWidth,\n        ch::coaster::kCarPoseAtlasRows * ch::coaster::kCarPoseFrameHeight);\n    if (atlas.isNull() || atlas.size() != expectedAtlasSize) {\n        std::fprintf(stderr, "invalid Flame V2 car pose atlas: got %dx%d expected %dx%d\\n",\n                     atlas.width(), atlas.height(), expectedAtlasSize.width(), expectedAtlasSize.height());\n        return 3;\n    }'''
    if old not in text:
        raise RuntimeError("coaster_project_video_main.cpp atlas-size anchor changed")
    renderer.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-root", required=True)
    ap.add_argument("--trigger", required=True)
    args = ap.parse_args()
    artifact_root = Path(args.artifact_root).resolve()
    trigger = load_json((REPO / args.trigger).resolve())

    if trigger.get("contract") != "CH_COASTER_ATLAS_PROMOTION_V1":
        raise RuntimeError("unexpected promotion trigger contract")

    source_manifest_path = find_one(artifact_root, "occupied_pose_manifest_v2.json")
    report_path = find_one(artifact_root, "coaster.car_flame_occupied_atlas_v2.final.002.report.json")
    source_dir = source_manifest_path.parent
    manifest = load_json(source_manifest_path)
    report = load_json(report_path)
    quality = report.get("qualityGate", {})

    required = {
        "sourceRunId": 37127887004,
        "sourceArtifactId": 11275786461,
        "sourceJobId": "coaster.car_flame_occupied_atlas_v2.final.002",
        "approvedProxySha256": "70461e8fa0a2435e98fc22f47154381909d78f84fcec45fa1fb3e4d286c2ba58",
        "sourceFingerprint": "b7fc3f6c56d782bdb1ac0ee074a8ccc674c86dfe13b76504b4ab9c9491b00cc7",
    }
    for key, value in required.items():
        if trigger.get(key) != value:
            raise RuntimeError(f"promotion trigger {key} mismatch")
    if report.get("status") != "ok" or report.get("jobId") != required["sourceJobId"]:
        raise RuntimeError("source worker report is not the approved final bake")
    if quality.get("stage") != "final" or quality.get("proxyReviewed") is not True:
        raise RuntimeError("source worker report is not a reviewed final stage")
    if quality.get("approvedProxySha256") != required["approvedProxySha256"]:
        raise RuntimeError("approved proxy SHA mismatch")
    if quality.get("sourceFingerprint") != required["sourceFingerprint"]:
        raise RuntimeError("reviewed source fingerprint mismatch")
    if manifest.get("contract") != EXPECTED_CONTRACT or manifest.get("orientationContract") != EXPECTED_ORIENTATION:
        raise RuntimeError("source V2 contracts mismatch")
    if manifest.get("frameCount") != FRAME_COUNT or len(manifest.get("frames", [])) != FRAME_COUNT:
        raise RuntimeError("source V2 frame count mismatch")

    outputs = {Path(item["path"]).name: item["sha256"] for item in report.get("outputs", [])}
    atlas_path = REPO / "assets/vehicles/coaster_flame_01/car_pose_atlas_v2.png"
    atlas_path.parent.mkdir(parents=True, exist_ok=True)
    atlas = Image.new("RGBA", (COLUMNS * FRAME_W, ROWS * FRAME_H), (0, 0, 0, 0))
    frames = []
    for frame in sorted(manifest["frames"], key=lambda f: f["frameIndex"]):
        index = int(frame["frameIndex"])
        if not 0 <= index < FRAME_COUNT:
            raise RuntimeError(f"invalid frame index {index}")
        source = source_dir / frame["file"]
        if not source.is_file() or sha256(source) != outputs.get(source.name):
            raise RuntimeError(f"source frame missing or hash mismatch: {source.name}")
        with Image.open(source) as image:
            rgba = image.convert("RGBA")
            if rgba.size != (FRAME_W, FRAME_H):
                raise RuntimeError(f"wrong source frame size: {source.name} {rgba.size}")
            x = (index % COLUMNS) * FRAME_W
            y = (index // COLUMNS) * FRAME_H
            atlas.paste(rgba, (x, y))
        out_frame = dict(frame)
        out_frame["sha256"] = outputs[source.name]
        out_frame["sourceRect"] = [x, y, FRAME_W, FRAME_H]
        frames.append(out_frame)
    atlas.save(atlas_path, "PNG", optimize=True)
    atlas_sha = sha256(atlas_path)

    runtime_manifest = {
        "contract": EXPECTED_CONTRACT,
        "assetId": "vehicle.coaster.flame_01.pose_atlas_v2",
        "sourceAssetId": manifest["assetId"],
        "styleId": manifest["styleId"],
        "trackContract": manifest["trackContract"],
        "cameraContract": manifest["cameraContract"],
        "poseContract": manifest["orientationContract"],
        "spriteSheet": atlas_path.name,
        "spriteSheetSha256": atlas_sha,
        "frameWidth": FRAME_W,
        "frameHeight": FRAME_H,
        "columns": COLUMNS,
        "rows": ROWS,
        "frameCount": FRAME_COUNT,
        "headingCount": manifest["headingCount"],
        "headingStepDegrees": manifest["headingStepDegrees"],
        "pitchBins": manifest["pitchBins"],
        "verticalPitchBins": manifest["verticalPitchBins"],
        "bankRollBins": manifest["bankRollBins"],
        "invertedRollDegrees": manifest["invertedRollDegrees"],
        "selectionPolicy": manifest["selectionPolicy"],
        "occupancy": manifest["occupancy"],
        "approval": {
            "contract": "CH_PROXY_APPROVAL_V1",
            "proxyReviewed": True,
            "approvedProxySha256": required["approvedProxySha256"],
            "sourceFingerprint": required["sourceFingerprint"],
        },
        "sourceBake": {
            "jobId": required["sourceJobId"],
            "runId": required["sourceRunId"],
            "artifactId": required["sourceArtifactId"],
            "artifactDigest": "sha256:45920799651444e62b8300594dc98fc48ebbe0996f1d3bd9ab3e77f11a4888c3",
        },
        "frames": frames,
    }
    runtime_manifest_path = atlas_path.parent / "car_pose_atlas_runtime_v2.json"
    runtime_manifest_path.write_text(json.dumps(runtime_manifest, indent=2) + "\n", encoding="utf-8")

    payload = load_json(PAYLOAD)
    if payload.get("contract") != "CH_COASTER_V2_TEXT_PROMOTION_PAYLOAD_V1":
        raise RuntimeError("unexpected text promotion payload contract")
    for relative, content in payload.get("files", {}).items():
        live_path = (REPO / relative).resolve()
        if not live_path.is_relative_to(REPO) or not isinstance(content, str):
            raise RuntimeError(f"invalid staged text destination: {relative}")
        live_path.parent.mkdir(parents=True, exist_ok=True)
        live_path.write_text(content, encoding="utf-8")

    runtime_catalog_path = REPO / "assets/vehicles/coaster_flame_01/coaster_flame_01_runtime.json"
    runtime_catalog = load_json(runtime_catalog_path)
    runtime_catalog["poseAtlasSource"]["occupiedCompositeSpriteSheetSha256"] = atlas_sha
    runtime_catalog_path.write_text(json.dumps(runtime_catalog, indent=2) + "\n", encoding="utf-8")

    patch_shared_runtime_comments_and_direct_renderer()

    promoted = load_json(runtime_manifest_path)
    if promoted["spriteSheetSha256"] != sha256(atlas_path) or promoted["frameCount"] != FRAME_COUNT:
        raise RuntimeError("promoted atlas/manifest final validation failed")
    print(json.dumps({
        "status": "ok",
        "contract": EXPECTED_CONTRACT,
        "atlas": str(atlas_path.relative_to(REPO)),
        "atlasSha256": atlas_sha,
        "frameCount": FRAME_COUNT,
        "approvedProxySha256": required["approvedProxySha256"],
        "sourceFingerprint": required["sourceFingerprint"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
