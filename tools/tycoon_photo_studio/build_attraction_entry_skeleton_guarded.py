"""Guarded mathematical blockout for the shared City Horizon attraction entrance.

This file intentionally builds only the structural skeleton. It is not the final
art pass. The objective is to validate proportions against the approved Ferris
wheel before decorative details are authored.

Pipeline:
    preflight -> SOUTH proxy -> human proportion review -> later final asset
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
import build_ferris_wheel as fw  # noqa: E402
import scene_gate  # noqa: E402


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


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


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


def build_skeleton(root, recipe, mats):
    g = recipe["geometry"]
    authored = []

    def box(name, location, dimensions, mat, bevel=0.035, role="attraction.entry_structure", contact=False):
        obj = fw.box(name, location, dimensions, mat, bevel, root)
        scene_gate.tag(obj, role, ground_contact=contact)
        authored.append(obj)
        return obj

    base_h = float(g["baseHeight"])
    overall_w = float(g["overallWidth"])
    overall_d = float(g["overallDepth"])

    # One physical datum for the whole entrance module. Width intentionally
    # equals the Ferris wheel's approved loading-platform width (5.20).
    box(
        "EntranceBase",
        (0.0, 0.0, base_h * 0.5),
        (overall_w, overall_d, base_h),
        mats["skeletonBase"],
        0.055,
        "attraction.entry_base",
        True,
    )

    # Ticket kiosk volume. This is deliberately a blockout, not facade art.
    kw = float(g["kioskWidth"])
    kd = float(g["kioskDepth"])
    kh = float(g["kioskHeight"])
    kx = float(g["kioskCenterX"])
    ky = float(g["kioskCenterY"])
    box(
        "TicketKioskMass",
        (kx, ky, base_h + kh * 0.5),
        (kw, kd, kh),
        mats["skeletonKiosk"],
        0.07,
        "attraction.ticket_kiosk",
        False,
    )
    canopy = float(g["canopyOverhang"])
    box(
        "TicketKioskCanopy",
        (kx, ky - canopy * 0.35, base_h + kh + 0.11),
        (kw + canopy * 2.0, kd + canopy, 0.22),
        mats["skeletonStructure"],
        0.06,
        "attraction.ticket_kiosk_canopy",
        False,
    )
    counter_h = float(g["counterHeight"])
    box(
        "TicketCounterDatum",
        (kx + kw * 0.18, ky - kd * 0.51, base_h + counter_h),
        (kw * 0.58, 0.12, 0.12),
        mats["skeletonGate"],
        0.025,
        "attraction.ticket_counter",
        False,
    )

    # Entrance portal: the clear opening width is exactly the Ferris stair width
    # (1.42), making the queue/boarding handoff mathematically compatible.
    gx = float(g["gateCenterX"])
    gy = float(g["gateCenterY"])
    clear_w = float(g["gateClearWidth"])
    col_w = float(g["gateColumnWidth"])
    col_d = float(g["gateColumnDepth"])
    col_h = float(g["gateColumnHeight"])
    arch_top = float(g["archTopZ"])
    beam_h = float(g["archBeamHeight"])
    for side, sign in (("Left", -1.0), ("Right", 1.0)):
        x = gx + sign * (clear_w * 0.5 + col_w * 0.5)
        box(
            f"GateColumn{side}",
            (x, gy, base_h + col_h * 0.5),
            (col_w, col_d, col_h),
            mats["skeletonStructure"],
            0.045,
            "attraction.entry_portal",
            False,
        )

    portal_span = clear_w + col_w * 2.0
    box(
        "GateArchDatum",
        (gx, gy, arch_top - beam_h * 0.5),
        (portal_span, col_d, beam_h),
        mats["skeletonGate"],
        0.06,
        "attraction.entry_portal",
        False,
    )
    sign_w = float(g["archSignWidth"])
    sign_h = float(g["archSignHeight"])
    box(
        "GateSignDatum",
        (gx, gy, arch_top + sign_h * 0.30),
        (sign_w, col_d * 1.08, sign_h),
        mats["skeletonKiosk"],
        0.08,
        "attraction.entry_sign",
        False,
    )

    # Two turnstile masses establish throughput and walking clearance only.
    turn_count = max(1, int(g["turnstileCount"]))
    tw = float(g["turnstileWidth"])
    td = float(g["turnstileDepth"])
    th = float(g["turnstileHeight"])
    usable = clear_w - 0.14
    for i in range(turn_count):
        t = (i + 0.5) / turn_count - 0.5
        x = gx + t * usable
        box(
            f"TurnstileDatum_{i:02d}",
            (x, gy - 0.40, base_h + th * 0.5),
            (tw * 0.52, td, th),
            mats["skeletonGate"],
            0.035,
            "attraction.entry_turnstile",
            False,
        )

    # Queue skeleton. Same rail height/radius as Ferris loading platform.
    rail_h = float(g["railingHeight"])
    rail_r = float(g["railingRadius"])
    q_right = float(g["queueRightX"])
    q_div = float(g["queueDividerX"])
    q_depth = float(g["queueDepth"])
    q_front = gy - 0.12
    q_back = min(float(g["backY"]) - 0.12, q_front + q_depth)
    q_left = gx + clear_w * 0.5 + col_w + 0.15

    rails = [
        ("QueueOuterRight", (q_right, q_front), (q_right, q_back), 4),
        ("QueueBack", (q_left, q_back), (q_right, q_back), 3),
        ("QueueDivider", (q_div, q_front + 0.30), (q_div, q_back - 0.18), 3),
        ("QueueInnerLeft", (q_left, q_front + 0.35), (q_left, q_back), 3),
    ]
    for name, start, end, posts in rails:
        before = set(bpy.context.scene.objects)
        fw.build_railing(root, name, start, end, base_h, rail_h, rail_r, mats["skeletonRail"], posts)
        for obj in bpy.context.scene.objects:
            if obj not in before and obj.type == "MESH":
                scene_gate.tag(obj, "attraction.queue_railing", ground_contact=False)
                authored.append(obj)

    # Entry steps inherit the Ferris 1.42 width and remain centered on portal.
    stair_w = float(g["stairWidth"])
    stair_d = float(g["stairDepth"])
    stair_steps = max(2, int(g["stairSteps"]))
    step_d = stair_d / stair_steps
    for i in range(stair_steps):
        h = base_h * (i + 1) / stair_steps
        y = float(g["frontY"]) - stair_d + step_d * (i + 0.5)
        box(
            f"EntryStep_{i:02d}",
            (gx, y, h * 0.5),
            (stair_w, step_d * 1.04, h),
            mats["skeletonBase"],
            0.03,
            "attraction.entry_step",
            True,
        )

    return authored


def main():
    args = parse_args()
    recipe = load_json(args.recipe)
    if recipe.get("contract") != "CITY_HORIZON_ATTRACTION_ENTRANCE_V1":
        raise RuntimeError("Expected CITY_HORIZON_ATTRACTION_ENTRANCE_V1 recipe")

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
    root = fw.empty("AssetRoot")
    root["assetId"] = recipe["assetId"]
    root["assetType"] = recipe["assetType"]
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["groundIncludedInAsset"] = False
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_sprite"
    root["proceduralContract"] = recipe["contract"]
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["designStage"] = "mathematical_blockout_v1"

    authored = build_skeleton(root, recipe, mats)

    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material(
        "ShadowReceiver",
        receiver["materialColor"],
        float(receiver.get("roughness", 1.0)),
    )
    ground = bs.add_box(
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
        print(f"[CH_GATE] attraction entrance skeleton preflight PASS: {preflight_path}")
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
    print(f"[CH_GATE] attraction entrance skeleton SOUTH proxy ready: {proxy['sha256']}")


if __name__ == "__main__":
    main()
