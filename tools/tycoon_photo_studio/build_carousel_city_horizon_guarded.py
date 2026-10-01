"""Original City Horizon identity pass for the low/wide carousel.

Revision 3 keeps the approved low/wide/open silhouette, but adds readable detail at
gameplay scale: layered canopy trim, subtle radial ribs, decorative frieze medallions,
a mirrored center drum, horse saddle blankets, platform rings and a second bulb band.

Pipeline:
    preflight -> SOUTH proxy -> human approval -> final four-direction animation

The runtime remains 2D RGBA sprites; Blender is offline authoring/render only.
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


def _roof_z_for_radius(geo, radius):
    r0 = float(geo.get("canopyInnerRadius", 0.46))
    r1 = float(geo["canopyRadius"])
    z0 = float(geo["canopyInnerZ"])
    z1 = float(geo["canopyOuterZ"])
    t = 0.0 if abs(r1 - r0) < 1e-6 else (radius - r0) / (r1 - r0)
    t = max(0.0, min(1.0, t))
    return z0 + (z1 - z0) * t


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
    mirror = mats["mirror"]
    horse_palette = [mats["horse"], mats["horse_gray"], mats["horse_chestnut"]]

    # Replace the borrowed red/yellow skirt language with City Horizon's own
    # burgundy body, brass insets and quieter teal/gold trim hierarchy.
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
    platform_z = float(geo["platformTopZ"])
    skirt_segments = int(geo.get("skirtSegments", 20))

    # Brass inset plaques around the base.
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

    # Layered platform rings strengthen the lower silhouette without adding noise.
    ring_a = classic._torus(
        "PlatformTealRing",
        rotor,
        (0.0, 0.0, platform_z + 0.025),
        base_radius - 0.34,
        0.028,
        teal,
    )
    ring_b = classic._torus(
        "PlatformInnerGoldRing",
        rotor,
        (0.0, 0.0, platform_z + 0.028),
        base_radius - 0.58,
        0.022,
        gold,
    )
    for ring in (ring_a, ring_b):
        ring["runtimeLayer"] = "motion_overlay"
        added.append(ring)

    canopy_r = float(geo["canopyRadius"])
    canopy_inner = float(geo.get("canopyInnerRadius", 0.46))
    outer_z = float(geo["canopyOuterZ"])
    inner_z = float(geo["canopyInnerZ"])
    valance_h = float(geo.get("valanceHeight", 0.20))
    valance_depth = float(geo.get("valanceDepth", 0.16))
    valance_segments = int(geo.get("valanceSegments", 20))

    # Alternating hanging frieze panels.
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

    # Two restrained circular roof trims. They give the roof its own visual identity
    # while preserving the radial yellow/cream canopy field.
    for name, radius, material, minor in (
        ("CanopyTealAccentRing", 2.38, teal, 0.026),
        ("CanopyGoldAccentRing", 2.72, gold, 0.020),
    ):
        z = _roof_z_for_radius(geo, radius) + 0.020
        ring = classic._torus(name, rotor, (0.0, 0.0, z), radius, minor, material)
        ring["runtimeLayer"] = "motion_overlay"
        added.append(ring)

    # Under-canopy radial ribs: visible mostly at the front edge, where the proxy
    # previously looked empty. These are deliberately thin and low-frequency.
    rib_count = int(geo.get("canopyRibCount", 12))
    rib_radius = float(geo.get("canopyRibRadius", 0.022))
    for i in range(rib_count):
        a = 2.0 * math.pi * i / rib_count
        start_r = canopy_inner + 0.18
        end_r = canopy_r - 0.10
        start = (
            start_r * math.cos(a),
            start_r * math.sin(a),
            _roof_z_for_radius(geo, start_r) - 0.075,
        )
        end = (
            end_r * math.cos(a),
            end_r * math.sin(a),
            _roof_z_for_radius(geo, end_r) - 0.075,
        )
        rib = classic._cylinder_between(
            f"CanopyRib_{i:02d}", rotor, start, end, rib_radius, gold, vertices=10
        )
        rib["runtimeLayer"] = "motion_overlay"
        added.append(rib)

    # Warm bulbs under the canopy edge.
    bulb_count = int(geo.get("bulbCount", 32))
    bulb_radius = float(geo.get("bulbRadius", 0.040))
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

    # Decorative double medallions on the frieze. A short radial cylinder becomes
    # a readable outward-facing plaque without requiring a texture decal.
    medallion_count = int(geo.get("friezeMedallionCount", 8))
    medallion_radius = float(geo.get("friezeMedallionRadius", 0.135))
    medallion_z = outer_z - valance_h * 0.55
    for i in range(medallion_count):
        a = 2.0 * math.pi * (i + 0.5) / medallion_count
        ux, uy = math.cos(a), math.sin(a)
        r0 = canopy_r - 0.015
        r1 = canopy_r + 0.070
        base = classic._cylinder_between(
            f"FriezeMedallionGold_{i:02d}",
            rotor,
            (r0 * ux, r0 * uy, medallion_z),
            (r1 * ux, r1 * uy, medallion_z),
            medallion_radius,
            gold,
            vertices=20,
        )
        face = classic._cylinder_between(
            f"FriezeMedallionFace_{i:02d}",
            rotor,
            ((r1 - 0.005) * ux, (r1 - 0.005) * uy, medallion_z),
            ((r1 + 0.025) * ux, (r1 + 0.025) * uy, medallion_z),
            medallion_radius * 0.64,
            teal if i % 2 == 0 else burgundy,
            vertices=20,
        )
        for piece in (base, face):
            piece["runtimeLayer"] = "motion_overlay"
            added.append(piece)

    # Lower bulb band on the static skirt to keep the ride readable at night and
    # make the front edge more interesting in daylight proxies.
    skirt_bulb_count = int(geo.get("skirtBulbCount", 20))
    for i in range(skirt_bulb_count):
        a = 2.0 * math.pi * (i + 0.5) / skirt_bulb_count
        r = base_radius + 0.025
        light = classic._sphere(
            f"SkirtBulb_{i:02d}",
            root,
            (r * math.cos(a), r * math.sin(a), 0.47),
            (0.032, 0.032, 0.032),
            bulb,
            segments=10,
            rings=6,
        )
        light["runtimeLayer"] = "static_base"
        added.append(light)

    # Central decorative drum with cool mirror-like panels and gold rings.
    drum_radius = float(geo.get("centerDrumRadius", 0.42))
    drum_height = float(geo.get("centerDrumHeight", 0.62))
    drum_z = 1.37
    drum = classic._cylinder(
        "CarouselCenterDrum",
        rotor,
        (0.0, 0.0, drum_z),
        drum_radius,
        drum_height,
        burgundy,
        vertices=48,
    )
    drum["runtimeLayer"] = "motion_overlay"
    added.append(drum)

    panel_count = int(geo.get("centerPanelCount", 8))
    for i in range(panel_count):
        a = 2.0 * math.pi * i / panel_count
        r = drum_radius + 0.018
        panel = classic._cube(
            f"CenterMirrorPanel_{i:02d}",
            rotor,
            (r * math.cos(a), r * math.sin(a), drum_z),
            (0.025, 0.115, drum_height * 0.33),
            mirror,
            bevel=0.018,
        )
        panel.rotation_euler[2] = a
        panel["runtimeLayer"] = "motion_overlay"
        added.append(panel)

    for name, z in (
        ("CenterDrumGoldLower", drum_z - drum_height * 0.5),
        ("CenterDrumGoldUpper", drum_z + drum_height * 0.5),
    ):
        ring = classic._torus(name, rotor, (0.0, 0.0, z), drum_radius, 0.028, gold)
        ring["runtimeLayer"] = "motion_overlay"
        added.append(ring)

    # Saddle blankets add color separation to the horses without changing their
    # validated body geometry or animation.
    if bool(geo.get("saddleBlankets", True)):
        horse_count = int(geo.get("horseCount", 14))
        z_body = float(geo.get("horseBodyZ", 1.08))
        for i in range(horse_count):
            horse = bpy.data.objects.get(f"Horse_{i:02d}")
            if horse is None:
                continue
            blanket = classic._cube(
                f"HorseBlanket_{i:02d}",
                horse,
                (-0.025, 0.0, z_body + 0.155),
                (0.285, 0.225, 0.026),
                teal if i % 2 == 0 else burgundy,
                bevel=0.028,
            )
            blanket["runtimeLayer"] = "motion_overlay"
            added.append(blanket)

    # Low crown remains intentionally compact so the attraction does not become
    # a tall ornate carousel and lose the approved low/wide silhouette.
    if bool(geo.get("crownEnabled", True)):
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
        print(f"[CH_GATE] City Horizon carousel V3 preflight PASS: {preflight_path}")
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
        print(f"[CH_GATE] City Horizon carousel V3 proxy SOUTH ready: {proxy['sha256']}")
        return

    raise RuntimeError(
        "CH_CAROUSEL_V3_FINAL_NOT_APPROVED: review the V3 proxy first; final animation promotion is intentionally gated."
    )


if __name__ == "__main__":
    main()
