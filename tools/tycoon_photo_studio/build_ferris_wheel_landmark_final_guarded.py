"""Final guarded entrypoint for the approved landmark Ferris wheel.

Uses the landmark dual-rim geometry while preserving the existing guarded
Ferris animation/final packaging contract. Runtime remains 2D RGBA PNG.
"""
from __future__ import annotations

import json
from pathlib import Path

import build_ferris_wheel as fw
import build_ferris_wheel_guarded as guarded
import ferris_wheel_landmark_geometry as landmark


def _landmark_build_wheel(root, geometry, materials):
    return landmark.build_wheel(root, geometry, materials, fw)


# The guarded builder imports the same module object, so this targeted swap
# preserves all existing gates/animation packaging and changes only geometry.
fw.build_wheel = _landmark_build_wheel


def _write_top_level_metadata(args) -> None:
    if args.stage != "final":
        return

    out = Path(args.output).resolve()
    frame_metadata_path = out / "final_source" / "frame_001" / "studio_metadata.json"
    runtime_manifest_path = out / "runtime" / "attraction.park_ferris_wheel.01_runtime_manifest.json"
    final_report_path = out / "final_bake_report.json"

    if not frame_metadata_path.is_file():
        raise RuntimeError("CH_FERRIS_FINAL_METADATA_MISSING: frame_001 studio metadata was not produced")
    if not runtime_manifest_path.is_file():
        raise RuntimeError("CH_FERRIS_FINAL_RUNTIME_MANIFEST_MISSING: animated runtime manifest was not produced")
    if not final_report_path.is_file():
        raise RuntimeError("CH_FERRIS_FINAL_REPORT_MISSING: final bake report was not produced")

    metadata = json.loads(frame_metadata_path.read_text(encoding="utf-8"))
    runtime_manifest = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
    final_report = json.loads(final_report_path.read_text(encoding="utf-8"))

    metadata["sourceContract"] = "DIRECT_CH_BLENDER_GUARDED_LANDMARK_ANIMATED_FINAL_V1"
    metadata["assetConfig"] = "tools/tycoon_photo_studio/build_ferris_wheel_landmark_final_guarded.py"
    metadata["renderClass"] = "large_asset_1024"
    metadata["finalPackage"] = {
        "contract": runtime_manifest.get("contract"),
        "runtimeManifest": "runtime/attraction.park_ferris_wheel.01_runtime_manifest.json",
        "runtimeRepresentation": runtime_manifest.get("runtimeRepresentation"),
        "transparentCanvas": bool(runtime_manifest.get("transparentCanvas", False)),
        "backgroundIncluded": bool(runtime_manifest.get("backgroundIncluded", True)),
        "directionOrder": runtime_manifest.get("directionOrder", []),
        "frameCount": runtime_manifest.get("frameCount"),
        "fps": runtime_manifest.get("fps"),
        "frameResolution": runtime_manifest.get("frameResolution"),
        "combinedSheet": runtime_manifest.get("combinedSheet", {}),
        "finalBakeStatus": final_report.get("status"),
        "approvedProxySha256": final_report.get("approvedProxySha256"),
    }
    (out / "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print("[CH_GATE] Landmark Ferris wheel top-level final studio metadata written")


def main() -> None:
    args = guarded.parse_args()
    guarded.main()
    _write_top_level_metadata(args)


if __name__ == "__main__":
    main()
