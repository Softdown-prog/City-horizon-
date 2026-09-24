"""Guarded Blender blockout for City Horizon hydroelectric plant.

Pipeline:
    preflight -> SOUTH proxy -> human visual review -> later final four-direction bake

This script authors the first structural pass only. Water remains map terrain and
is intentionally not baked into the asset.
"""
from __future__ import annotations

import argparse
import json
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


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--save-blend", default=None)
    parser.add_argument("--stage", choices=("preflight", "proxy"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    return parser.parse_args(argv)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def make_empty(name):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    return obj


def make_materials(recipe):
    return {
        key: bs.make_material(
            spec.get("name", key),
            spec["rgba"],
            float(spec.get("roughness", 0.72)),
            float(spec.get("metallic", 0.0)),
        )
        for key, spec in recipe["materials"].items()
    }


def build_hydroelectric(root, recipe, mats):
    g = recipe["geometry"]
    authored = []

    def box(name, location, dimensions, material, bevel=0.04, role="hydro.structure", contact=False):
        obj = bs.add_box(name, location, dimensions, material, bevel)
        obj.parent = root
        scene_gate.tag(obj, role, ground_contact=contact)
        authored.append(obj)
        return obj

    dam_w = float(g["damWidth"])
    dam_d = float(g["damDepth"])
    dam_h = float(g["damHeight"])
    dam_z = float(g["damBaseZ"])

    # Main gravity-dam mass. This is deliberately a clean, readable blockout.
    box(
        "DamMainMass",
        (0.0, 0.0, dam_z + dam_h * 0.5),
        (dam_w, dam_d, dam_h),
        mats["concrete"],
        0.10,
        "hydro.dam_mass",
        True,
    )

    deck_h = float(g["crestDeckHeight"])
    deck_over = float(g["crestDeckOverhang"])
    box(
        "DamCrestDeck",
        (0.0, 0.0, dam_z + dam_h + deck_h * 0.5),
        (dam_w + deck_over * 2.0, dam_d + deck_over * 2.0, deck_h),
        mats["concreteLight"],
        0.055,
        "hydro.crest_deck",
        False,
    )

    # Four downstream-facing spillway gates. For the blockout they read as
    # recessed gate plates against the dam face; detailed chutes come later.
    bay_count = max(1, int(g["spillwayBayCount"]))
    opening_w = float(g["spillwayOpeningWidth"])
    opening_h = float(g["spillwayOpeningHeight"])
    gate_d = float(g["spillwayGateDepth"])
    pier_w = float(g["spillwayPierWidth"])
    sill_z = float(g["spillwaySillZ"])
    total_bay_span = bay_count * opening_w + (bay_count + 1) * pier_w
    start_x = -total_bay_span * 0.5
    downstream_y = -(dam_d * 0.5 + gate_d * 0.46)

    for i in range(bay_count):
        x0 = start_x + pier_w + i * (opening_w + pier_w)
        center_x = x0 + opening_w * 0.5
        box(
            f"SpillwayGate_{i:02d}",
            (center_x, downstream_y, sill_z + opening_h * 0.5),
            (opening_w, gate_d, opening_h),
            mats["gateSteel"],
            0.025,
            "hydro.spillway_gate",
            False,
        )

    # Piers extend above each gate and create unmistakable spillway rhythm.
    for i in range(bay_count + 1):
        center_x = start_x + pier_w * 0.5 + i * (opening_w + pier_w)
        box(
            f"SpillwayPier_{i:02d}",
            (center_x, downstream_y - 0.04, dam_z + dam_h * 0.58),
            (pier_w, gate_d * 1.45, dam_h * 0.86),
            mats["concreteLight"],
            0.025,
            "hydro.spillway_pier",
            False,
        )

    # Attached powerhouse/turbine hall on the downstream side.
    pw_w = float(g["powerhouseWidth"])
    pw_d = float(g["powerhouseDepth"])
    pw_h = float(g["powerhouseHeight"])
    pw_x = float(g["powerhouseOffsetX"])
    pw_y = float(g["powerhouseOffsetY"])
    box(
        "PowerhouseMain",
        (pw_x, pw_y, pw_h * 0.5),
        (pw_w, pw_d, pw_h),
        mats["concreteLight"],
        0.09,
        "hydro.powerhouse",
        True,
    )
    roof_h = float(g["powerhouseRoofHeight"])
    box(
        "PowerhouseRoof",
        (pw_x, pw_y, pw_h + roof_h * 0.5),
        (pw_w + 0.18, pw_d + 0.18, roof_h),
        mats["roof"],
        0.055,
        "hydro.powerhouse_roof",
        False,
    )

    # Large industrial windows communicate a turbine hall without requiring
    # tiny facade detail during this first geometry gate.
    rows = max(1, int(g["powerhouseWindowRows"]))
    cols = max(1, int(g["powerhouseWindowColumns"]))
    window_w = min(0.62, pw_w / (cols + 1.2))
    window_h = min(0.48, pw_h / (rows + 1.6))
    face_y = pw_y - pw_d * 0.5 - 0.025
    for row in range(rows):
        z = 0.58 + row * (window_h + 0.36)
        for col in range(cols):
            t = (col + 0.5) / cols - 0.5
            x = pw_x + t * (pw_w - 0.52)
            box(
                f"PowerhouseWindow_{row:02d}_{col:02d}",
                (x, face_y, z),
                (window_w, 0.055, window_h),
                mats["glass"],
                0.015,
                "hydro.powerhouse_window",
                False,
            )

    deck_w = float(g["serviceDeckWidth"])
    deck_d = float(g["serviceDeckDepth"])
    service_h = float(g["serviceDeckHeight"])
    box(
        "PowerhouseServiceDeck",
        (pw_x, pw_y - pw_d * 0.5 - deck_d * 0.48, service_h * 0.5),
        (deck_w, deck_d, service_h),
        mats["concrete"],
        0.04,
        "hydro.service_deck",
        True,
    )

    # Compact outdoor substation. The pad + transformers + simple gantry are
    # enough to communicate power generation from gameplay distance.
    ss_w = float(g["substationPadWidth"])
    ss_d = float(g["substationPadDepth"])
    ss_x = float(g["substationOffsetX"])
    ss_y = float(g["substationOffsetY"])
    ss_h = float(g["substationPadHeight"])
    box(
        "SubstationPad",
        (ss_x, ss_y, ss_h * 0.5),
        (ss_w, ss_d, ss_h),
        mats["concrete"],
        0.035,
        "hydro.substation_pad",
        True,
    )

    transformer_count = max(1, int(g["transformerCount"]))
    tw = float(g["transformerWidth"])
    td = float(g["transformerDepth"])
    th = float(g["transformerHeight"])
    for i in range(transformer_count):
        t = (i + 0.5) / transformer_count - 0.5
        x = ss_x + t * (ss_w - tw * 1.25)
        box(
            f"Transformer_{i:02d}",
            (x, ss_y + 0.15, ss_h + th * 0.5),
            (tw, td, th),
            mats["transformer"],
            0.045,
            "hydro.transformer",
            False,
        )
        box(
            f"TransformerCap_{i:02d}",
            (x, ss_y + 0.15, ss_h + th + 0.08),
            (tw * 0.78, td * 0.78, 0.16),
            mats["electricalSteel"],
            0.025,
            "hydro.transformer_detail",
            False,
        )

    gantry_h = float(g["gantryHeight"])
    post_w = float(g["gantryPostWidth"])
    beam_h = float(g["gantryBeamHeight"])
    gantry_y = ss_y - ss_d * 0.26
    for sign in (-1.0, 1.0):
        x = ss_x + sign * (ss_w * 0.5 - 0.22)
        box(
            f"SubstationGantryPost_{'L' if sign < 0 else 'R'}",
            (x, gantry_y, ss_h + gantry_h * 0.5),
            (post_w, post_w, gantry_h),
            mats["electricalSteel"],
            0.012,
            "hydro.substation_gantry",
            False,
        )
    box(
        "SubstationGantryBeam",
        (ss_x, gantry_y, ss_h + gantry_h - beam_h * 0.5),
        (ss_w - 0.35, post_w, beam_h),
        mats["electricalSteel"],
        0.012,
        "hydro.substation_gantry",
        False,
    )

    # Crest safety rails are chunky enough to survive gameplay scale.
    rail_h = float(g["railingHeight"])
    rail_w = float(g["railingPostWidth"])
    for side_y in (-1.0, 1.0):
        y = side_y * (dam_d * 0.5 + deck_over * 0.52)
        box(
            f"CrestRail_{'Front' if side_y < 0 else 'Back'}",
            (0.0, y, dam_z + dam_h + deck_h + rail_h),
            (dam_w - 0.35, rail_w, rail_w),
            mats["safety"],
            0.012,
            "hydro.crest_railing",
            False,
        )
        for x in (-dam_w * 0.46, -dam_w * 0.23, 0.0, dam_w * 0.23, dam_w * 0.46):
            box(
                f"CrestRailPost_{side_y:+.0f}_{x:+.2f}",
                (x, y, dam_z + dam_h + deck_h + rail_h * 0.5),
                (rail_w, rail_w, rail_h),
                mats["safety"],
                0.010,
                "hydro.crest_railing",
                False,
            )

    return authored


def main():
    args = parse_args()
    recipe = load_json(args.recipe)
    if recipe.get("contract") != "CITY_HORIZON_HYDROELECTRIC_DAM_V1":
        raise RuntimeError("Expected CITY_HORIZON_HYDROELECTRIC_DAM_V1 recipe")

    studio = bs.load_json(args.studio_preset)
    profile = scene_gate.load_profile(args.preflight_profile)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    mats = make_materials(recipe)
    root = make_empty("AssetRoot")
    root["assetId"] = recipe["assetId"]
    root["assetType"] = recipe["assetType"]
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["groundIncludedInAsset"] = False
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_sprite"
    root["proceduralContract"] = recipe["contract"]
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["designStage"] = "hydroelectric_structural_blockout_v1"

    authored = build_hydroelectric(root, recipe, mats)

    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material(
        "ShadowReceiver",
        receiver["materialColor"],
        float(receiver.get("roughness", 1.0)),
    )
    bs.add_box(
        "ShadowReceiverPlane",
        receiver["location"],
        receiver["dimensions"],
        receiver_mat,
        0.0,
    )

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

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
        save_blend(args.save_blend)
        print(f"[CH_GATE] hydroelectric preflight PASS: {preflight_path}")
        return

    proxy = scene_gate.render_proxy(
        scene=scene,
        authored=authored,
        output_path=out / "proxy_south.png",
        profile=profile,
        asset_id=recipe["assetId"],
        direction="south",
    )
    (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
    save_blend(args.save_blend)
    print(f"[CH_GATE] hydroelectric SOUTH proxy ready: {proxy['sha256']}")


if __name__ == "__main__":
    main()
