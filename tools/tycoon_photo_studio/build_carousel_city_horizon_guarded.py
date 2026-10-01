"""Original City Horizon identity pass for the low/wide carousel.

This builder intentionally reuses the validated classic-carousel geometry/pipeline,
then applies a distinct City Horizon V2 presentation before preflight/proxy review.
It is a proxy-stage authoring wrapper: final animation promotion remains gated on
human approval of the generated SOUTH proxy.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CH_BLENDER = REPO_ROOT / "tools" / "ch_blender"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(CH_BLENDER) not in sys.path:
    sys.path.insert(0, str(CH_BLENDER))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402
import build_carousel_classic_guarded as classic  # noqa: E402


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    return p.parse_args(argv)


def _set_material(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)


def _horse_index(name):
    match = re.search(r"Horse(?:Body|Chest|Neck|Head|Ear|Leg|Tail|Saddle)_(\d+)", name)
    return int(match.group(1)) if match else None


def build_scene(recipe, studio, out):
    scene, root, rotor, ground, authored = classic.build_scene(recipe, studio, out)
    geo = recipe["geometry"]
    mats = {
        key: bpy.data.materials.get(f"Carousel_{key}")
        for key in recipe["materials"]
    }

    burgundy = mats["burgundy"]
    teal = mats["teal"]
    gold = mats["gold"]
    bulb = mats["bulb"]
    horse_palette = [mats["horse"], mats["horse_gray"], mats["horse_chestnut"]]

    # Quiet the copied red/yellow skirt language: V2 uses one burgundy body
    # with smaller brass inset panels instead of alternating full-size blocks.
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        if obj.name == "CarouselFoundation" or obj.name.startswith("Skirt_"):
            _set_material(obj, burgundy)
        elif obj.name == "CenterColumn":
            _set_material(obj, teal)
        elif obj.name in {"CenterColumnLowerBand", "CenterColumnUpperBand"}:
            _set_material(obj, gold)

        idx = _horse_index(obj.name)
        if idx is not None:
            if "Saddle" in obj.name:
                _set_material(obj, burgundy if idx % 2 == 0 else teal)
            elif "Muzzle" not in obj.name and "Pole" not in obj.name:
                _set_material(obj, horse_palette[idx % len(horse_palette)])

    added = []
    base_radius = float(geo["baseRadius"])
    skirt_segments = int(geo.get("skirtSegments", 20))
    for i in range(skirt_segments):
        if i % 2:
            continue
        center = 2.0 * math.pi * (i + 0.5) / skirt_segments
        half_width = math.pi / skirt_segments * 0.48
        accent = classic._annular_sector(
            f"SkirtAccent_{i:02d}",
            root,
            center - half_width,
            center + half_width,
            base_radius - 0.035,
            base_radius + 0.022,
            0.275,
            0.425,
            gold,
        )
        accent["runtimeLayer"] = "static_base"
        added.append(accent)

    canopy_r = float(geo["canopyRadius"])
    outer_z = float(geo["canopyOuterZ"])
    valance_h = float(geo.get("valanceHeight", 0.20))
    valance_depth = float(geo.get("valanceDepth", 0.16))
    valance_segments = int(geo.get("valanceSegments", 20))
    for i in range(valance_segments):
        a0 = 2.0 * math.pi * i / valance_segments
        a1 = 2.0 * math.pi * (i + 1) / valance_segments
        panel = classic._annular_sector(
            f"CanopyValance_{i:02d}",
            rotor,
            a0,
            a1,
            canopy_r - valance_depth,
            canopy_r + 0.018,
            outer_z - valance_h,
            outer_z - 0.035,
            burgundy if i % 2 == 0 else teal,
        )
        panel["runtimeLayer"] = "motion_overlay"
        added.append(panel)

    bulb_count = int(geo.get("bulbCount", 20))
    bulb_radius = float(geo.get("bulbRadius", 0.045))
    bulb_ring_r = canopy_r - valance_depth * 0.52
    bulb_z = outer_z - valance_h - 0.015
    for i in range(bulb_count):
        a = 2.0 * math.pi * (i + 0.5) / bulb_count
        light = classic._sphere(
            f"CanopyBulb_{i:02d}",
            rotor,
            (bulb_ring_r * math.cos(a), bulb_ring_r * math.sin(a), bulb_z),
            (bulb_radius, bulb_radius, bulb_radius),
            bulb,
            segments=12,
            rings=6,
        )
        light["runtimeLayer"] = "motion_overlay"
        added.append(light)

    if bool(geo.get("crownEnabled", True)):
        inner_z = float(geo["canopyInnerZ"])
        crown_specs = [
            ("CarouselCrownLower", inner_z + 0.11, 0.37, 0.11, teal),
            ("CarouselCrownMid", inner_z + 0.21, 0.27, 0.10, burgundy),
            ("CarouselCrownUpper", inner_z + 0.30, 0.18, 0.09, gold),
            ("CarouselFinialStem", inner_z + 0.43, 0.055, 0.22, gold),
        ]
        for name, z, radius, depth, material in crown_specs:
            piece = classic._cylinder(name, rotor, (0.0, 0.0, z), radius, depth, material, vertices=32)
            piece["runtimeLayer"] = "motion_overlay"
            added.append(piece)
        finial = classic._sphere(
            "CarouselFinial",
            rotor,
            (0.0, 0.0, inner_z + 0.57),
            (0.095, 0.095, 0.13),
            gold,
            segments=16,
            rings=8,
        )
        finial["runtimeLayer"] = "motion_overlay"
        added.append(finial)

    authored = list(authored) + added
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    scene.frame_set(int(recipe["animation"].get("frameStart", 1)))
    bpy.context.view_layer.update()
    return scene, root, rotor, ground, authored


def main():
    args = parse_args()
    recipe = json.loads(Path(args.recipe).read_text(encoding="utf-8"))
    if recipe.get("contract") != "CITY_HORIZON_CAROUSEL_V1":
        raise RuntimeError("Expected CITY_HORIZON_CAROUSEL_V1 recipe")

    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    profile = scene_gate.load_profile(args.preflight_profile)
    scene, root, rotor, ground, authored = build_scene(recipe, studio, out)

    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=recipe["assetId"],
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        classic._save_blend(args.save_blend)
        print(f"[CH_GATE] City Horizon carousel V2 preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        scene.frame_set(int(recipe["animation"].get("frameStart", 1)))
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=recipe["assetId"],
            direction="south",
        )
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        classic._save_blend(args.save_blend)
        print(f"[CH_GATE] City Horizon carousel V2 proxy SOUTH ready: {proxy['sha256']}")
        return

    raise RuntimeError(
        "CH_CAROUSEL_V2_FINAL_NOT_APPROVED: review the V2 proxy first; final animation promotion is intentionally gated."
    )


if __name__ == "__main__":
    main()
