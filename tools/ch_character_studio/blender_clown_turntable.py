"""Render one physical clown proxy through the four canonical CH Actor directions.

This script exists to solve cross-direction identity drift. The same 3D proxy is
rotated to S/E/N/W; Character Studio may paint over the result, but it must not
invent a different silhouette per direction.

Run through CH Blender / guarded_blender_script. Example Blender invocation:
  blender -b --python tools/ch_character_studio/blender_clown_turntable.py -- \
    --character-spec tools/ch_character_studio/specs/clown_01.character.json \
    --output out/ch_character_studio/clown_01/turntable
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

import blender_character_base as base

DIRECTIONS = ("S", "E", "N", "W")
FRAME = base.FRAME
ANCHOR = base.ANCHOR


def script_args() -> list[str]:
    argv = sys.argv
    return argv[argv.index("--") + 1 :] if "--" in argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--character-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage", default="proxy")
    parser.add_argument("--preflight-profile")
    parser.add_argument("--approval-proxy-sha")
    args, _ = parser.parse_known_args(script_args())
    # Reuse the shape expected by blender_character_base.setup_scene.
    args.camera_mode = "canonical"
    args.inspection_yaw = 45.0
    args.inspection_pitch = 30.0
    args.inspection_ortho_scale = 2.05
    args.inspection_resolution_scale = 1
    return args


def local(direction: str, point: tuple[float, float, float]) -> Vector:
    return base.rotate_local(point, direction)


def add_proxy_ellipsoid(name: str, direction: str, point, scale, mat, root):
    obj = base.add_uv_sphere(
        name,
        local(direction, point),
        scale,
        mat,
        z_rotation=base.DIRECTION_ANGLE[direction],
    )
    obj.parent = root
    return obj


def add_clown_proxy(spec: dict, direction: str, points: dict[str, Vector]) -> dict:
    """Add costume/face volumes shared identically by every direction.

    The geometry is intentionally simple. It is an authoring underlay that owns
    proportion and occlusion, not final art quality.
    """
    palette = spec["appearance"]["palette"]
    skin = base.material("CH_CLOWN_SKIN", palette["skin"])
    hair = base.material("CH_CLOWN_HAIR", palette["hair"])
    red = base.material("CH_CLOWN_RED", palette["primary"])
    blue = base.material("CH_CLOWN_BLUE", palette["secondary"])
    yellow = base.material("CH_CLOWN_YELLOW", palette.get("accent", "#f2d744"))
    shoes = base.material("CH_CLOWN_SHOES", palette["shoes"])
    white = base.material("CH_CLOWN_WHITE", "#f4f2e3")
    nose_mat = base.material("CH_CLOWN_NOSE", "#df3b36")
    eye_mat = base.material("CH_CLOWN_EYE", "#2f2b29")
    purple = base.material("CH_CLOWN_BOW", "#8b5cf6")

    root = bpy.data.objects.new("CH_CLOWN_PROXY_ROOT", None)
    bpy.context.collection.objects.link(root)

    # Shared hair mass: same three lobes rotated with the character.
    add_proxy_ellipsoid("ClownHairCenter", direction, (0.0, 0.025, 1.60), (0.15, 0.12, 0.11), hair, root)
    add_proxy_ellipsoid("ClownHairLeft", direction, (-0.17, 0.01, 1.57), (0.14, 0.12, 0.15), hair, root)
    add_proxy_ellipsoid("ClownHairRight", direction, (0.17, 0.01, 1.57), (0.14, 0.12, 0.15), hair, root)

    # Ruff collar. Four overlapping volumes avoid a paper-thin disk from side/back.
    for index, x in enumerate((-0.14, -0.05, 0.05, 0.14)):
        add_proxy_ellipsoid(f"ClownRuff_{index}", direction, (x, -0.005, 1.31), (0.095, 0.075, 0.06), white, root)

    # Costume torso overlay. Existing generic red torso remains underneath; this
    # locks the clown-specific width/volume across all views.
    add_proxy_ellipsoid("ClownTorso", direction, (0.0, 0.0, 1.02), (0.245, 0.17, 0.31), red, root)

    # Colored sleeves follow the exact rig arms. Blue is anatomical left, yellow right.
    arm_mats = {"L": blue, "R": yellow}
    for label in ("L", "R"):
        base.add_capsule(
            f"ClownSleeve_{label}",
            points[f"shoulder_{label}"],
            points[f"elbow_{label}"],
            0.07,
            arm_mats[label],
        ).parent = root
        base.add_uv_sphere(
            f"ClownGlove_{label}",
            points[f"hand_{label}"],
            (0.065, 0.065, 0.075),
            white,
        ).parent = root

    # Split trousers use the same articulated legs, therefore E/W/N cannot invent
    # a different leg length or hip width.
    leg_mats = {"L": blue, "R": yellow}
    for label in ("L", "R"):
        base.add_capsule(
            f"ClownTrouserUpper_{label}",
            points[f"hip_{label}"],
            points[f"knee_{label}"],
            0.073,
            leg_mats[label],
        ).parent = root
        base.add_capsule(
            f"ClownTrouserLower_{label}",
            points[f"knee_{label}"],
            points[f"ankle_{label}"],
            0.068,
            leg_mats[label],
        ).parent = root
        # Oversized rigid-looking clown shoe volume. One physical size for every view.
        shoe = base.add_uv_sphere(
            f"ClownShoe_{label}",
            points[f"foot_{label}"],
            (0.10, 0.155, 0.065),
            shoes,
            z_rotation=base.DIRECTION_ANGLE[direction],
        )
        shoe.parent = root

    # Bow is a real front-side volume. It disappears naturally when the character
    # turns away instead of needing a hand-authored north exception.
    add_proxy_ellipsoid("ClownBowLeft", direction, (-0.045, -0.175, 1.20), (0.065, 0.035, 0.055), purple, root)
    add_proxy_ellipsoid("ClownBowRight", direction, (0.045, -0.175, 1.20), (0.065, 0.035, 0.055), purple, root)

    # Face volumes are positioned on the same head. Rotation controls visibility;
    # there is no separate E/W face design.
    add_proxy_ellipsoid("ClownNose", direction, (0.0, -0.145, 1.52), (0.055, 0.04, 0.055), nose_mat, root)
    add_proxy_ellipsoid("ClownEyeL", direction, (-0.055, -0.135, 1.575), (0.022, 0.015, 0.025), eye_mat, root)
    add_proxy_ellipsoid("ClownEyeR", direction, (0.055, -0.135, 1.575), (0.022, 0.015, 0.025), eye_mat, root)

    return {
        "contract": "CH_CLOWN_PROXY_V1",
        "direction": direction,
        "sharedGeometry": True,
        "headVolumeLocked": True,
        "hairVolumeLocked": True,
        "torsoVolumeLocked": True,
        "shoeVolumeLocked": True,
    }


def render_direction(spec: dict, args: argparse.Namespace, direction: str, output_dir: Path) -> dict:
    _, canonical_camera, points = base.setup_scene(spec, direction, "idle", args)
    proxy = add_clown_proxy(spec, direction, points)

    direction_dir = output_dir / direction.lower()
    direction_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str((direction_dir / "underlay.png").resolve())
    bpy.ops.render.render(write_still=True)

    projected = base.project_landmarks(scene, canonical_camera, points)
    spatial = base.frame_spatial(scene, canonical_camera, projected, direction)
    payload = {
        "contract": "CH_CLOWN_TURNTABLE_DIRECTION_V1",
        "direction": direction,
        "frame": "idle",
        "frameSize": list(FRAME),
        "groundAnchor": list(ANCHOR),
        "camera": "CH_ACTOR_CAMERA_V1",
        "proxy": proxy,
        "points": projected,
        "anchors": spatial,
        "sockets": {"left_hand": projected["hand_L"], "right_hand": projected["hand_R"]},
        "outputs": {"underlay": "underlay.png"},
    }
    (direction_dir / "underlay.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    args = parse_args()
    spec = base.load_spec(args.character_spec)
    if spec.get("characterId") != "clown_01":
        raise RuntimeError("blender_clown_turntable.py currently expects clown_01")

    args.output.mkdir(parents=True, exist_ok=True)
    directions = {}
    for direction in DIRECTIONS:
        directions[direction] = render_direction(spec, args, direction, args.output)

    report = {
        "contract": "CH_CLOWN_TURNTABLE_V1",
        "status": "candidate_for_visual_review",
        "characterId": "clown_01",
        "directions": list(DIRECTIONS),
        "camera": "CH_ACTOR_CAMERA_V1",
        "frameSize": list(FRAME),
        "groundAnchor": list(ANCHOR),
        "geometryAuthority": "CH_Blender_single_proxy",
        "paintAuthority": "CH_Character_Studio",
        "crossDirectionRasterWarp": False,
        "independentDirectionalSilhouetteAuthoring": False,
        "directionsData": directions,
    }
    (args.output / "turntable_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
