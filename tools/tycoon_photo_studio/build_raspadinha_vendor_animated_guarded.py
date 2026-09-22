"""Fail-fast guarded builder for the raspadinha vendor IDLE + GREET animation bake.

Renders two animation states per direction using the existing rig keyframes:
  IDLE  : frame 1  (canonical resting pose)
  GREET : frames 5, 6, 7  (greeting key-poses; frame 8 is return-to-idle)

The pipeline follows the mandatory CH Blender fail-fast sequence:
  preflight  -> validate scene/rig structure
  proxy      -> cheap SOUTH render of IDLE frame for quick visual review
  final      -> full 4-dir x 5-frame bake (IDLE f1 + GREET f5/f6/f7 + return f8)

Usage (via agent worker):
  blender --background --python build_raspadinha_vendor_animated_guarded.py -- \\
      --studio-preset tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json \\
      --output out/ch_blender_agent/prop.raspadinha_vendor.anim \\
      --stage preflight

The agent worker injects --stage, --preflight-profile and --approval-proxy-sha.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CH_BLENDER = REPO_ROOT / "tools" / "ch_blender"
for p in (str(HERE), str(CH_BLENDER)):
    if p not in sys.path:
        sys.path.insert(0, p)

import build_scene as bs                            # noqa: E402
import build_raspadinha_vendor_blender as rv        # noqa: E402
import scene_gate                                   # noqa: E402

# ---------------------------------------------------------------------------
# Animation state definition (matches the authored rig)
# ---------------------------------------------------------------------------

ANIM_STATES = {
    "idle":  [1],           # canonical resting pose
    "greet": [5, 6, 7, 8],  # greeting: raise arm → peak → lower → return-to-idle
}

# Frame 8 is the return-to-idle frame; rendering it gives a clean loop boundary.
# The plan says "1–2 additional key poses" — we bake 4 frames (5–8) so the
# postprocessor can drop frame 8 if the game engine interpolates back to IDLE.

ASSET_ID = rv.ASSET_ID
ANIMATION_CONTRACT = "CH_ANIMATED_SPRITE_V1"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(
        description="Raspadinha Vendor IDLE+GREET animation guarded baker"
    )
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Scene construction (reused from guarded static builder)
# ---------------------------------------------------------------------------

def _parent_keep_world_fixed(obj, parent):
    """Preserve world transform when reparenting under an animation pivot."""
    world = obj.matrix_world.copy()
    bpy.context.view_layer.update()
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = world
    bpy.context.view_layer.update()


def _tag_semantics():
    mapping = {
        "Torso":        ("character.torso",       False),
        "Head":         ("character.head",         False),
        "Shoe_L":       ("character.foot_left",    True),
        "Shoe_R":       ("character.foot_right",   True),
        "Arm_L_Hand":   ("character.hand_left",    False),
        "Arm_R_Hand":   ("character.hand_right",   False),
        "CartBody":     ("vendor.cart",            False),
        "UmbrellaPole": ("vendor.umbrella_pole",   False),
    }
    for name, (role, contact) in mapping.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError(
                f"CH_PREFLIGHT_AUTHORING_ERROR: missing authored object {name}"
            )
        scene_gate.tag(obj, role, ground_contact=contact)


def build_scene_for_gate(args):
    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    src_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, src_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    root = rv.empty("AssetRoot")
    root["assetId"] = ASSET_ID
    root["groundIncludedInAsset"] = False
    root["animationStates"] = "idle:1,greet:5-8"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["animationContract"] = ANIMATION_CONTRACT

    rv.parent_keep_world = _parent_keep_world_fixed

    mats = rv.materials()
    rv.build_cart(root, mats)
    rig = rv.build_vendor(root, mats)
    rv.animate_vendor(rig)
    scene.frame_set(1)
    bpy.context.view_layer.update()
    _tag_semantics()

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
    authored = [
        obj for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj != ground
    ]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.12)
    bs.set_direction(root, bs.DIRECTIONS[0])
    scene.frame_set(1)
    bpy.context.view_layer.update()
    return studio, scene, root, ground, authored, out


# ---------------------------------------------------------------------------
# Final bake: 4 directions × (IDLE frame 1 + GREET frames 5–8)
# ---------------------------------------------------------------------------

def _render_state_frames(scene, root, ground, authored, out, direction, state, frames):
    """Render color+shadow for each frame of a named animation state.

    Returns a list of frame-record dicts for the metadata manifest.
    """
    records = []
    dir_id = direction["id"]
    bs.set_direction(root, direction)
    bpy.context.view_layer.update()

    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()

        color_name = f"{ASSET_ID}_{dir_id}_{state}_f{frame:02d}_color_source.png"
        shadow_name = f"{ASSET_ID}_{dir_id}_{state}_f{frame:02d}_shadow_source.png"

        bs.render_color_pass(scene, authored, ground, str(out / color_name))
        origin_px = bs.ground_origin_source_px(scene)
        bs.render_shadow_pass(scene, authored, ground, str(out / shadow_name))

        records.append({
            "frame": frame,
            "state": state,
            "direction": dir_id,
            "colorSource": color_name,
            "shadowSource": shadow_name,
            "groundOriginSourcePx": origin_px,
        })
        print(f"  [{dir_id}] {state} frame {frame} — rendered")

    return records


def run_final_bake(studio, scene, root, ground, authored, out):
    directions_meta = []
    src_res = (scene.render.resolution_x, scene.render.resolution_y)
    final_res = tuple(map(int, studio["render"]["finalResolution"]))

    for direction in bs.DIRECTIONS:
        dir_records = []
        for state, frames in ANIM_STATES.items():
            dir_records.extend(
                _render_state_frames(
                    scene, root, ground, authored, out,
                    direction, state, frames,
                )
            )
        directions_meta.append({
            "id": direction["id"],
            "quarterTurns": direction["quarterTurns"],
            "rotationDegrees": direction["rotationDegrees"],
            "frames": dir_records,
        })

    # Reset to south / idle before finishing
    bs.set_direction(root, bs.DIRECTIONS[0])
    scene.frame_set(1)
    bpy.context.view_layer.update()

    # Count totals
    total_frames_rendered = sum(
        len(frames) for frames in ANIM_STATES.values()
    ) * len(bs.DIRECTIONS)

    metadata = {
        "contract": ANIMATION_CONTRACT,
        "sourceObject": ASSET_ID,
        "assetType": "animated_prop",
        "sourceContract": "CH_GUARDED_BLENDER_SCRIPT_V1",
        "assetConfig": "tools/tycoon_photo_studio/build_raspadinha_vendor_animated_guarded.py",
        "studioPreset": studio["id"],
        "cameraContract": "CH_CAMERA_V1",
        "gridContract": "CH_GRID_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "tileWidth": 128,
        "tileHeight": 64,
        "footprint": {"widthTiles": 1, "depthTiles": 1},
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "renderResolution": list(src_res),
        "finalResolution": list(final_res),
        "rotationPolicy": {
            "assetRootRotates": True,
            "cameraRemainsFixed": True,
            "lightsRemainWorldFixed": True,
        },
        "animationStates": {state: frames for state, frames in ANIM_STATES.items()},
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "directions": directions_meta,
        "totalFramesRendered": total_frames_rendered,
        "humanApprovalRequired": True,
        "note": (
            "IDLE+GREET animation bake. "
            "Postprocess/palette/shadow compositing required before runtime promotion. "
            "SERVE state is not authored — implement only after gameplay NPC interaction exists."
        ),
    }
    (out / "studio_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(
        f"[anim_bake] Done: {total_frames_rendered} renders "
        f"({len(bs.DIRECTIONS)} directions × "
        f"{sum(len(f) for f in ANIM_STATES.values())} frames)"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    studio, scene, root, ground, authored, out = build_scene_for_gate(args)

    # ── Preflight ────────────────────────────────────────────────────────
    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint={"widthTiles": 1, "depthTiles": 1},
        profile=profile,
        asset_id=ASSET_ID,
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        if args.save_blend:
            Path(args.save_blend).parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.save_blend).resolve()))
        print(f"[CH_GATE] animation preflight PASS: {preflight_path}")
        return

    # ── Proxy — SOUTH, IDLE frame 1 ─────────────────────────────────────
    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        scene.frame_set(1)
        bpy.context.view_layer.update()

        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south_idle.png",
            profile=profile,
            asset_id=ASSET_ID,
            direction="south",
        )
        proxy_path = out / "proxy_report.json"
        proxy_path.write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        if args.save_blend:
            Path(args.save_blend).parent.mkdir(parents=True, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.save_blend).resolve()))
        print(f"[CH_GATE] animation proxy SOUTH/IDLE ready: {proxy['sha256']}")
        return

    # ── Final — validate approved proxy SHA then bake all frames ─────────
    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError(
            "CH_FINAL_REQUIRES_APPROVED_PROXY: "
            "pass --approval-proxy-sha from the reviewed proxy_report.json"
        )

    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": ASSET_ID,
        "animationStates": list(ANIM_STATES.keys()),
        "proxySha256": approval,
        "reviewed": True,
    }
    (out / "proxy_approval.json").write_text(
        json.dumps(approval_record, indent=2), encoding="utf-8"
    )

    run_final_bake(studio, scene, root, ground, authored, out)
    print("[CH_GATE] animation final bake completed after explicit proxy approval")


if __name__ == "__main__":
    main()
