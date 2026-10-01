"""City Horizon carousel revision 4 finishing pass.

V4 preserves the approved low/wide/open carousel silhouette from revision 3 and
focuses on believable, gameplay-readable construction detail: one restrained roof
accent ring, stronger valance trim, support collars, improved horse tack/mane/hooves,
and a small authored boarding step with rails.

Pipeline remains preflight -> SOUTH proxy -> human review. Runtime is still 2D RGBA.
"""
from __future__ import annotations

import argparse
import json
import math
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
import build_carousel_city_horizon_guarded as v3  # noqa: E402


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    return p.parse_args(argv)


def _mat(name):
    material = bpy.data.materials.get(f"Carousel_{name}")
    if material is None:
        raise RuntimeError(f"Missing carousel material: {name}")
    return material


def _remove_object(name):
    obj = bpy.data.objects.get(name)
    if obj is not None:
        bpy.data.objects.remove(obj, do_unlink=True)


def _tag_static(obj):
    obj["runtimeLayer"] = "static_base"
    return obj


def _tag_motion(obj):
    obj["runtimeLayer"] = "motion_overlay"
    return obj


def build_scene(recipe, studio, out):
    scene, root, rotor, ground, _ = v3.build_scene(recipe, studio, out)
    geo = recipe["geometry"]

    gold = _mat("gold")
    burgundy = _mat("burgundy")
    teal = _mat("teal")
    dark = _mat("dark")
    bulb = _mat("bulb")

    # Revision 3's concentric teal/gold lines were too visually dominant in the
    # SOUTH proxy. Replace them with one fine brass ring close to the outer roof.
    _remove_object("CanopyTealAccentRing")
    _remove_object("CanopyGoldAccentRing")
    roof_r = 2.72
    roof_z = v3._roof_z_for_radius(geo, roof_r) + 0.018
    _tag_motion(classic._torus(
        "CanopyGoldAccentRingV4", rotor, (0.0, 0.0, roof_z), roof_r, 0.013, gold
    ))

    canopy_r = float(geo["canopyRadius"])
    outer_z = float(geo["canopyOuterZ"])
    valance_h = float(geo.get("valanceHeight", 0.22))

    # Gold lower edge makes the hanging valance read as an authored fascia rather
    # than a flat colored strip.
    _tag_motion(classic._torus(
        "CanopyValanceLowerGold", rotor,
        (0.0, 0.0, outer_z - valance_h + 0.008),
        canopy_r - 0.075, 0.020, gold
    ))

    # Small rosettes between the larger medallions add rhythm without crowding the
    # canopy. They are intentionally tiny enough to survive only as highlight dots.
    rosette_count = int(geo.get("friezeRosetteCount", 20))
    for i in range(rosette_count):
        a = 2.0 * math.pi * (i + 0.5) / rosette_count
        r = canopy_r + 0.035
        z = outer_z - valance_h * 0.55
        rosette = classic._sphere(
            f"FriezeRosette_{i:02d}", rotor,
            (r * math.cos(a), r * math.sin(a), z),
            (0.050, 0.050, 0.050), gold, segments=10, rings=6
        )
        _tag_motion(rosette)

    # Give each outer support a visible base shoe and upper capital. These details
    # strengthen the sense that the roof is physically supported rather than floating.
    if bool(geo.get("supportCollars", True)):
        support_count = int(geo.get("supportCount", 10))
        support_r = float(geo.get("supportRadius", 2.58))
        platform_z = float(geo["platformTopZ"])
        for i in range(support_count):
            a = 2.0 * math.pi * i / support_count
            x, y = support_r * math.cos(a), support_r * math.sin(a)
            lower = classic._cylinder(
                f"SupportFoot_{i:02d}", rotor,
                (x, y, platform_z + 0.065), 0.072, 0.13, gold, vertices=14
            )
            upper = classic._cylinder(
                f"SupportCapital_{i:02d}", rotor,
                (x, y, outer_z - 0.10), 0.075, 0.11, teal if i % 2 else burgundy,
                vertices=14
            )
            _tag_motion(lower)
            _tag_motion(upper)

    # Horse finishing pass: readable dark mane/bridle/hooves and a tiny brass chest
    # badge. Geometry stays deliberately simple so the animation remains robust.
    if bool(geo.get("horseDetailPass", True)):
        horse_count = int(geo.get("horseCount", 14))
        z_body = float(geo.get("horseBodyZ", 1.08))
        for i in range(horse_count):
            horse = bpy.data.objects.get(f"Horse_{i:02d}")
            if horse is None:
                continue

            mane_positions = [
                (0.33, 0.0, z_body + 0.33, 0.10),
                (0.40, 0.0, z_body + 0.43, 0.09),
                (0.47, 0.0, z_body + 0.53, 0.075),
            ]
            for j, (x, y, z, s) in enumerate(mane_positions):
                _tag_motion(classic._sphere(
                    f"HorseMane_{i:02d}_{j}", horse,
                    (x, y, z), (s, 0.055, s * 0.80), dark,
                    segments=10, rings=6
                ))

            bridle = classic._cube(
                f"HorseBridle_{i:02d}", horse,
                (0.57, 0.0, z_body + 0.47),
                (0.075, 0.155, 0.028), dark, bevel=0.012
            )
            noseband = classic._cube(
                f"HorseNoseband_{i:02d}", horse,
                (0.675, 0.0, z_body + 0.435),
                (0.14, 0.026, 0.026), burgundy if i % 2 == 0 else teal,
                bevel=0.010
            )
            _tag_motion(bridle)
            _tag_motion(noseband)

            pose = 1.0 if i % 2 == 0 else -1.0
            hoof_points = [
                (0.47, -0.11, z_body - 0.47 - 0.05 * pose),
                (0.01,  0.11, z_body - 0.50 + 0.05 * pose),
                (-0.47,-0.11, z_body - 0.42 + 0.05 * pose),
                (-0.04, 0.11, z_body - 0.50 - 0.05 * pose),
            ]
            for j, point in enumerate(hoof_points):
                _tag_motion(classic._cube(
                    f"HorseHoof_{i:02d}_{j}", horse, point,
                    (0.090, 0.075, 0.055), dark, bevel=0.018
                ))

            _tag_motion(classic._sphere(
                f"HorseChestBadge_{i:02d}", horse,
                (0.32, -0.155, z_body + 0.12),
                (0.050, 0.026, 0.050), gold, segments=10, rings=6
            ))

    # Small functional-looking boarding point on the static base. It stays compact
    # enough not to change the 3x3 footprint or the approved overall silhouette.
    if bool(geo.get("boardingStep", True)):
        base_r = float(geo["baseRadius"])
        lower = classic._cube(
            "BoardingStepLower", root,
            (0.0, -base_r + 0.05, 0.15),
            (0.92, 0.38, 0.18), burgundy, bevel=0.045
        )
        upper = classic._cube(
            "BoardingStepUpper", root,
            (0.0, -base_r + 0.23, 0.36),
            (0.82, 0.34, 0.24), _mat("wood"), bevel=0.040
        )
        _tag_static(lower)
        _tag_static(upper)

        for side in (-1.0, 1.0):
            x = 0.49 * side
            post = classic._cylinder(
                f"BoardingRailPost_{'L' if side < 0 else 'R'}", root,
                (x, -base_r + 0.18, 0.71), 0.035, 0.70, gold, vertices=12
            )
            rail = classic._cylinder_between(
                f"BoardingRail_{'L' if side < 0 else 'R'}", root,
                (x, -base_r + 0.36, 0.82),
                (x, -base_r + 0.02, 0.72),
                0.030, gold, vertices=12
            )
            _tag_static(post)
            _tag_static(rail)

    # Rebuild authored list after deleting/replacing revision-3 roof objects.
    authored = [obj for obj in scene.objects if obj.type == "MESH" and obj != ground]
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
    if int(recipe.get("designRevision", 0)) < 4:
        raise RuntimeError("Carousel V4 builder requires designRevision >= 4")

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
        print(f"[CH_GATE] City Horizon carousel V4 preflight PASS: {preflight_path}")
        return

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
    print(f"[CH_GATE] City Horizon carousel V4 proxy SOUTH ready: {proxy['sha256']}")


if __name__ == "__main__":
    main()
