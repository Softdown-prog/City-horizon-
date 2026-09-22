"""Guarded animation-review stage for the raspadinha vendor.

This is intentionally cheap. It exists to validate the authored IDLE + GREET
poses before the expensive four-direction Cycles bake.

Quality flow:
  preflight -> all 4 directions x 5 authored review poses (20 structural checks)
  proxy     -> SOUTH IDLE + GREET frames 5/6/7/8 in Eevee, plus one sheet

The final production bake remains owned by
build_raspadinha_vendor_animated_guarded.py after explicit human review of the
sheet SHA emitted here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from array import array
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CH_BLENDER = REPO_ROOT / "tools" / "ch_blender"
for p in (str(HERE), str(CH_BLENDER)):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_scene as bs  # noqa: E402
import build_raspadinha_vendor_animated_guarded as anim  # noqa: E402
import raspadinha_vendor_greet_v1 as greet  # noqa: E402
import scene_gate  # noqa: E402

ASSET_ID = anim.ASSET_ID
REVIEW_FRAMES = (("idle", 1), ("greet", 5), ("greet", 6), ("greet", 7), ("greet", 8))


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(description="Raspadinha vendor animation review gate")
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    return p.parse_args(argv)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run_animation_preflight(scene, root, authored, profile, out: Path) -> dict:
    samples = []
    violations = []
    baseline = None

    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        for state, frame in REVIEW_FRAMES:
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            report = scene_gate.run_preflight(
                scene=scene,
                authored=authored,
                footprint={"widthTiles": 1, "depthTiles": 1},
                profile=profile,
                asset_id=ASSET_ID,
            )
            if baseline is None:
                baseline = report
            sample_violations = []
            for violation in report.get("violations", []):
                enriched = dict(violation)
                enriched["direction"] = direction["id"]
                enriched["state"] = state
                enriched["frame"] = frame
                violations.append(enriched)
                sample_violations.append(enriched)
            samples.append({
                "direction": direction["id"],
                "state": state,
                "frame": frame,
                "status": report.get("status"),
                "violations": sample_violations,
            })

    bs.set_direction(root, bs.DIRECTIONS[0])
    scene.frame_set(1)
    bpy.context.view_layer.update()

    aggregate = dict(baseline or {})
    aggregate.update({
        "contract": scene_gate.PREFLIGHT_CONTRACT,
        "status": "pass" if not violations else "fail",
        "assetId": ASSET_ID,
        "animationReview": True,
        "samplesChecked": len(samples),
        "directionsChecked": [d["id"] for d in bs.DIRECTIONS],
        "reviewFrames": [{"state": state, "frame": frame} for state, frame in REVIEW_FRAMES],
        "animationSamples": samples,
        "violations": violations,
    })
    target = out / "preflight_report.json"
    target.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    return aggregate


def compose_horizontal_sheet(paths: list[Path], output: Path) -> None:
    images = [bpy.data.images.load(str(path), check_existing=False) for path in paths]
    try:
        width = int(images[0].size[0])
        height = int(images[0].size[1])
        if any(int(img.size[0]) != width or int(img.size[1]) != height for img in images):
            raise RuntimeError("CH_PROXY_SHEET_SIZE_MISMATCH")

        channels = 4
        sheet_width = width * len(images)
        sheet_pixels = array("f", [0.0]) * (sheet_width * height * channels)
        row_values = width * channels
        sheet_row_values = sheet_width * channels

        for index, image in enumerate(images):
            source = array("f", [0.0]) * (width * height * channels)
            image.pixels.foreach_get(source)
            x_offset = index * row_values
            for y in range(height):
                src_start = y * row_values
                dst_start = y * sheet_row_values + x_offset
                sheet_pixels[dst_start:dst_start + row_values] = source[src_start:src_start + row_values]

        sheet = bpy.data.images.new(
            "RaspadinhaVendorAnimationProxySheet",
            width=sheet_width,
            height=height,
            alpha=True,
            float_buffer=False,
        )
        try:
            sheet.pixels.foreach_set(sheet_pixels)
            sheet.file_format = "PNG"
            sheet.filepath_raw = str(output)
            sheet.save()
        finally:
            bpy.data.images.remove(sheet)
    finally:
        for image in images:
            bpy.data.images.remove(image)


def render_proxy_sheet(scene, root, authored, profile, out: Path) -> dict:
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    frame_records = []
    rendered_paths = []
    for state, frame in REVIEW_FRAMES:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        path = out / f"proxy_south_{state}_f{frame:02d}.png"
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=path,
            profile=profile,
            asset_id=ASSET_ID,
            direction="south",
        )
        frame_records.append({
            "state": state,
            "frame": frame,
            "file": path.name,
            "sha256": proxy["sha256"],
        })
        rendered_paths.append(path)

    sheet_path = out / "proxy_south.png"
    compose_horizontal_sheet(rendered_paths, sheet_path)

    scene.frame_set(1)
    bpy.context.view_layer.update()

    resolution = int(profile.get("proxy", {}).get("resolution", 256))
    report = {
        "contract": scene_gate.PROXY_CONTRACT,
        "status": "ok",
        "assetId": ASSET_ID,
        "direction": "south",
        "reviewType": "animation_pose_sheet",
        "frameOrder": [f"{state}:{frame}" for state, frame in REVIEW_FRAMES],
        "frames": frame_records,
        "resolution": [resolution * len(REVIEW_FRAMES), resolution],
        "path": str(sheet_path),
        "bytes": sheet_path.stat().st_size,
        "sha256": sha256(sheet_path),
    }
    (out / "proxy_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    studio, scene, root, ground, authored, out = anim.build_scene_for_gate(args)

    # Override only the GREET key poses. The static/idle baseline and all other
    # authored states remain untouched.
    greet.apply()

    preflight = run_animation_preflight(scene, root, authored, profile, out)
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        print(f"[CH_GATE] animation review preflight PASS: {preflight['samplesChecked']} samples")
        return

    if args.stage != "proxy":
        raise RuntimeError(
            "CH_ANIMATION_REVIEW_ONLY: use build_raspadinha_vendor_animated_guarded.py for final bake"
        )

    proxy = render_proxy_sheet(scene, root, authored, profile, out)
    if args.save_blend:
        Path(args.save_blend).parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.save_blend).resolve()))
    print(f"[CH_GATE] SOUTH animation proxy sheet ready: {proxy['sha256']}")


if __name__ == "__main__":
    main()
