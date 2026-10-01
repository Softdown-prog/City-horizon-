"""City Horizon carousel revision 5: central horse totem pass.

V5 builds on the approved V4 carousel and adds a real procedural horse ornament
on the roof-center mast. The topper is authored geometry, parented to CarouselRotor,
so it participates in the same 48-frame rotation contract and all four direction bakes.
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
import build_carousel_city_horizon_v4_guarded as v4  # noqa: E402


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


def _motion(obj):
    obj["runtimeLayer"] = "motion_overlay"
    return obj


def _build_horse_topper(rotor, geo):
    spec = geo.get("horseTopper", {})
    if not bool(spec.get("enabled", False)):
        return []

    s = float(spec.get("scale", 0.72))
    body_z = float(spec.get("bodyCenterZ", 3.66))
    mast_top_z = float(spec.get("mastTopZ", 4.12))
    facing = math.radians(float(spec.get("facingDegrees", -35.0)))

    ivory = _mat(str(spec.get("material", "horse")))
    gold = _mat(str(spec.get("maneMaterial", "gold")))
    burgundy = _mat(str(spec.get("saddleMaterial", "burgundy")))
    teal = _mat(str(spec.get("blanketMaterial", "teal")))
    dark = _mat("dark")

    topper = classic._empty("CarouselHorseTopper", rotor)
    topper.rotation_euler[2] = facing
    topper["runtimeLayer"] = "motion_overlay"
    added = []

    # Central mast continues through the horse, making the ornament structurally
    # readable at game scale instead of looking like it floats above the canopy.
    mast_base_z = float(geo["canopyInnerZ"]) + 0.32
    mast = classic._cylinder(
        "HorseTopperMast", topper, (0.0, 0.0, (mast_base_z + mast_top_z) * 0.5),
        0.040 * s, mast_top_z - mast_base_z, gold, vertices=16
    )
    added.append(_motion(mast))

    # Main horse masses. The proportions deliberately echo the carousel mounts
    # without duplicating them exactly; this is a heraldic topper, not a rider seat.
    body = classic._sphere(
        "HorseTopperBody", topper, (0.0, 0.0, body_z),
        (0.40*s, 0.16*s, 0.22*s), ivory, segments=24, rings=14
    )
    chest = classic._sphere(
        "HorseTopperChest", topper, (0.26*s, 0.0, body_z + 0.10*s),
        (0.19*s, 0.14*s, 0.24*s), ivory, segments=22, rings=12
    )
    neck = classic._sphere(
        "HorseTopperNeck", topper, (0.34*s, 0.0, body_z + 0.28*s),
        (0.12*s, 0.11*s, 0.30*s), ivory, segments=20, rings=12
    )
    neck.rotation_euler[1] = math.radians(-24.0)
    head = classic._sphere(
        "HorseTopperHead", topper, (0.49*s, 0.0, body_z + 0.43*s),
        (0.20*s, 0.12*s, 0.13*s), ivory, segments=22, rings=12
    )
    head.rotation_euler[1] = math.radians(-10.0)
    muzzle = classic._sphere(
        "HorseTopperMuzzle", topper, (0.64*s, 0.0, body_z + 0.40*s),
        (0.10*s, 0.085*s, 0.075*s), ivory, segments=18, rings=10
    )
    for obj in (body, chest, neck, head, muzzle):
        added.append(_motion(obj))

    # Ears.
    for n, y in enumerate((-0.060*s, 0.060*s)):
        ear = classic._cube(
            f"HorseTopperEar_{n}", topper,
            (0.44*s, y, body_z + 0.58*s),
            (0.030*s, 0.022*s, 0.075*s), ivory, bevel=0.010*s
        )
        ear.rotation_euler[1] = math.radians(-18.0)
        added.append(_motion(ear))

    # Four energetic legs for a raised/galloping silhouette.
    leg_specs = [
        ((0.22*s, -0.10*s, body_z - 0.08*s), (0.43*s, -0.10*s, body_z - 0.36*s)),
        ((0.17*s,  0.10*s, body_z - 0.08*s), (0.01*s,  0.10*s, body_z - 0.39*s)),
        ((-0.21*s,-0.10*s, body_z - 0.07*s), (-0.43*s,-0.10*s, body_z - 0.32*s)),
        ((-0.18*s, 0.10*s, body_z - 0.07*s), (-0.02*s, 0.10*s, body_z - 0.39*s)),
    ]
    for i, (start, end) in enumerate(leg_specs):
        leg = classic._cylinder_between(
            f"HorseTopperLeg_{i}", topper, start, end, 0.042*s, ivory, vertices=10
        )
        hoof = classic._sphere(
            f"HorseTopperHoof_{i}", topper, end,
            (0.060*s, 0.050*s, 0.045*s), dark, segments=12, rings=7
        )
        added.extend((_motion(leg), _motion(hoof)))

    # Tail with two linked segments and gold mane beads for a readable decorative
    # silhouette after downsampling to the runtime sprite resolution.
    tail_a = classic._cylinder_between(
        "HorseTopperTailA", topper,
        (-0.36*s, 0.0, body_z + 0.02*s), (-0.56*s, 0.0, body_z + 0.10*s),
        0.055*s, gold, vertices=12
    )
    tail_b = classic._cylinder_between(
        "HorseTopperTailB", topper,
        (-0.56*s, 0.0, body_z + 0.10*s), (-0.68*s, 0.0, body_z - 0.07*s),
        0.065*s, gold, vertices=12
    )
    added.extend((_motion(tail_a), _motion(tail_b)))

    for i in range(5):
        mane = classic._sphere(
            f"HorseTopperMane_{i}", topper,
            ((0.25 + i*0.045)*s, 0.0, body_z + (0.28 + i*0.055)*s),
            (0.060*s, 0.050*s, 0.065*s), gold, segments=12, rings=7
        )
        added.append(_motion(mane))

    blanket = classic._cube(
        "HorseTopperBlanket", topper, (-0.02*s, 0.0, body_z + 0.16*s),
        (0.25*s, 0.19*s, 0.030*s), teal, bevel=0.020*s
    )
    saddle = classic._cube(
        "HorseTopperSaddle", topper, (0.0, 0.0, body_z + 0.22*s),
        (0.19*s, 0.17*s, 0.045*s), burgundy, bevel=0.028*s
    )
    bridle = classic._cube(
        "HorseTopperBridle", topper, (0.52*s, 0.0, body_z + 0.43*s),
        (0.065*s, 0.13*s, 0.022*s), burgundy, bevel=0.010*s
    )
    added.extend((_motion(blanket), _motion(saddle), _motion(bridle)))

    # Gold medallion and top finial complete the crown hierarchy.
    medallion = classic._sphere(
        "HorseTopperMedallion", topper, (0.05*s, -0.18*s, body_z + 0.16*s),
        (0.045*s, 0.022*s, 0.045*s), gold, segments=12, rings=7
    )
    finial = classic._sphere(
        "HorseTopperFinial", topper, (0.0, 0.0, mast_top_z),
        (0.075*s, 0.075*s, 0.090*s), gold, segments=16, rings=8
    )
    added.extend((_motion(medallion), _motion(finial)))

    return added


def build_scene(recipe, studio, out):
    scene, root, rotor, ground, authored = v4.build_scene(recipe, studio, out)
    geo = recipe["geometry"]
    added = _build_horse_topper(rotor, geo)
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
    if int(recipe.get("designRevision", 0)) < 5:
        raise RuntimeError("Carousel V5 builder requires designRevision >= 5")

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
        print(f"[CH_GATE] City Horizon carousel V5 preflight PASS: {preflight_path}")
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
    print(f"[CH_GATE] City Horizon carousel V5 horse-topper proxy SOUTH ready: {proxy['sha256']}")


if __name__ == "__main__":
    main()
