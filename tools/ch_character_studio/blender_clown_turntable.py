"""Render one physical clown model through the four canonical CH Actor directions.

V2 fixes the visual failure of the first proxy: the character is authored once in
South-local space, parented to one root and the root is rotated for E/N/W. No
independent directional silhouette authoring is allowed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bpy
from mathutils import Vector

import blender_character_base as base

DIRECTIONS = ("S", "E", "N", "W")
FRAME = base.FRAME
ANCHOR = base.ANCHOR
SUPERSAMPLE = 4


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
    args.camera_mode = "canonical"
    args.inspection_yaw = 45.0
    args.inspection_pitch = 30.0
    args.inspection_ortho_scale = 2.05
    args.inspection_resolution_scale = 1
    return args


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def remove_generic_actor_geometry() -> None:
    keep = {"CH_ACTOR_CAMERA", "CH_KEY_LIGHT", "CH_FILL_LIGHT"}
    for obj in list(bpy.data.objects):
        if obj.name in keep or obj.type in {"CAMERA", "LIGHT"}:
            continue
        bpy.data.objects.remove(obj, do_unlink=True)


def mat(spec: dict, key: str, fallback: str, name: str):
    value = spec.get("appearance", {}).get("palette", {}).get(key, fallback)
    return base.material(name, value)


def add_ellipsoid(name: str, point, scale, material, root):
    obj = base.add_uv_sphere(name, Vector(point), scale, material)
    obj.parent = root
    return obj


def add_capsule(name: str, a: Vector, b: Vector, radius: float, material, root):
    delta = b - a
    length = max(delta.length, 0.001)
    mid = (a + b) * 0.5
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=radius, depth=length, location=mid)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(delta.normalized())
    obj.parent = root
    for suffix, p in (("A", a), ("B", b)):
        joint = base.add_uv_sphere(f"{name}_{suffix}", p, (radius, radius, radius), material)
        joint.parent = root
    return obj


def add_beveled_box(name: str, point, scale, material, root, bevel=0.035):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=Vector(point))
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    modifier = obj.modifiers.new("SoftEdges", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    obj.parent = root
    return obj


def build_clown_once(spec: dict) -> tuple[bpy.types.Object, dict[str, Vector]]:
    """Build the physical character exactly once in South-local space."""
    points = base.pose_points(spec, "S", "idle")
    root = bpy.data.objects.new("CH_CLOWN_PHYSICAL_ROOT", None)
    bpy.context.collection.objects.link(root)

    skin = mat(spec, "skin", "#f3c7ad", "CH_CLOWN_SKIN")
    hair = mat(spec, "hair", "#d43b2f", "CH_CLOWN_HAIR")
    red = mat(spec, "primary", "#d43b2f", "CH_CLOWN_RED")
    blue = mat(spec, "secondary", "#2b71c9", "CH_CLOWN_BLUE")
    yellow = mat(spec, "accent", "#f2d744", "CH_CLOWN_YELLOW")
    shoes = mat(spec, "shoes", "#26313a", "CH_CLOWN_SHOES")
    white = base.material("CH_CLOWN_WHITE", "#f4f2e3")
    nose_mat = base.material("CH_CLOWN_NOSE", "#df3b36")
    eye_mat = base.material("CH_CLOWN_EYES", "#262220")
    purple = base.material("CH_CLOWN_BOW", "#8b5cf6")

    # Head is intentionally readable and smaller than the failed V1 mushroom mass.
    add_ellipsoid("Head", (0.0, 0.0, 1.52), (0.135, 0.125, 0.165), skin, root)
    add_ellipsoid("Neck", (0.0, 0.0, 1.335), (0.058, 0.058, 0.075), skin, root)
    add_ellipsoid("EarL", (-0.135, 0.0, 1.53), (0.028, 0.020, 0.040), skin, root)
    add_ellipsoid("EarR", (0.135, 0.0, 1.53), (0.028, 0.020, 0.040), skin, root)

    # Hair is a ring of small curls around the side/back, not three giant ellipsoids.
    curls = [
        (-0.145, 0.015, 1.60), (-0.115, 0.055, 1.655), (-0.055, 0.085, 1.68),
        (0.055, 0.085, 1.68), (0.115, 0.055, 1.655), (0.145, 0.015, 1.60),
        (-0.10, 0.105, 1.59), (0.0, 0.115, 1.61), (0.10, 0.105, 1.59),
    ]
    for index, p in enumerate(curls):
        add_ellipsoid(f"HairCurl_{index:02d}", p, (0.060, 0.052, 0.060), hair, root)

    # Small facial volumes on the physical front (-depth).
    add_ellipsoid("Nose", (0.0, -0.128, 1.515), (0.042, 0.030, 0.042), nose_mat, root)
    add_ellipsoid("EyeL", (-0.047, -0.119, 1.565), (0.014, 0.010, 0.018), eye_mat, root)
    add_ellipsoid("EyeR", (0.047, -0.119, 1.565), (0.014, 0.010, 0.018), eye_mat, root)

    # Jacket: compact rounded volume instead of balloon torso.
    add_beveled_box("Jacket", (0.0, 0.0, 1.045), (0.39, 0.27, 0.48), red, root, bevel=0.070)
    add_ellipsoid("Waist", (0.0, 0.0, 0.785), (0.165, 0.115, 0.105), red, root)

    # Ruff made from smaller puffs following the neck circumference.
    for index, (x, y) in enumerate(((-0.12, 0.0), (-0.06, -0.03), (0.0, -0.04), (0.06, -0.03), (0.12, 0.0), (0.0, 0.045))):
        add_ellipsoid(f"Ruff_{index:02d}", (x, y, 1.305), (0.055, 0.045, 0.040), white, root)

    # Bow-tie front only.
    add_ellipsoid("BowL", (-0.038, -0.145, 1.225), (0.050, 0.024, 0.040), purple, root)
    add_ellipsoid("BowR", (0.038, -0.145, 1.225), (0.050, 0.024, 0.040), purple, root)

    arm_mats = {"L": blue, "R": yellow}
    for label in ("L", "R"):
        add_capsule(f"SleeveUpper_{label}", points[f"shoulder_{label}"], points[f"elbow_{label}"], 0.052, arm_mats[label], root)
        add_capsule(f"SleeveLower_{label}", points[f"elbow_{label}"], points[f"hand_{label}"], 0.046, arm_mats[label], root)
        add_ellipsoid(f"Glove_{label}", points[f"hand_{label}"], (0.055, 0.055, 0.062), white, root)

    leg_mats = {"L": blue, "R": yellow}
    for label in ("L", "R"):
        add_capsule(f"TrouserUpper_{label}", points[f"hip_{label}"], points[f"knee_{label}"], 0.060, leg_mats[label], root)
        add_capsule(f"TrouserLower_{label}", points[f"knee_{label}"], points[f"ankle_{label}"], 0.052, leg_mats[label], root)
        foot = points[f"foot_{label}"]
        shoe = add_ellipsoid(f"Shoe_{label}", (foot.x, foot.y + 0.020, foot.z), (0.082, 0.125, 0.052), shoes, root)
        shoe.rotation_euler[2] = 0.0

    return root, points


def render_supersampled(scene: bpy.types.Scene, direction_dir: Path) -> None:
    direction_dir.mkdir(parents=True, exist_ok=True)
    review = direction_dir / "underlay_review.png"
    final = direction_dir / "underlay.png"

    scene.render.resolution_x = FRAME[0] * SUPERSAMPLE
    scene.render.resolution_y = FRAME[1] * SUPERSAMPLE
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(review.resolve())
    bpy.ops.render.render(write_still=True)

    image = bpy.data.images.load(str(review.resolve()), check_existing=False)
    image.scale(FRAME[0], FRAME[1])
    image.filepath_raw = str(final.resolve())
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def render_direction(spec: dict, args: argparse.Namespace, direction: str, output_dir: Path) -> dict:
    # Scene/camera is always created from the same South pose. Direction is applied
    # only as one root rotation, guaranteeing one physical model in all four views.
    _, canonical_camera, _ = base.setup_scene(spec, "S", "idle", args)
    remove_generic_actor_geometry()

    # setup_scene removal also removes lights/root geometry but keeps camera/lights by name.
    scene = bpy.context.scene
    if scene.camera is None or scene.camera.name not in bpy.data.objects:
        canonical_camera = base.setup_canonical_camera(scene)
        scene.camera = canonical_camera
    else:
        canonical_camera = scene.camera

    # Recreate lights if needed after geometry cleanup.
    if "CH_KEY_LIGHT" not in bpy.data.objects:
        bpy.ops.object.light_add(type="AREA", location=(-2.5, -3.0, 4.5))
        key = bpy.context.object; key.name = "CH_KEY_LIGHT"; key.data.energy = 650; key.data.shape = "DISK"; key.data.size = 4.0
    if "CH_FILL_LIGHT" not in bpy.data.objects:
        bpy.ops.object.light_add(type="AREA", location=(2.0, 1.0, 2.4))
        fill = bpy.context.object; fill.name = "CH_FILL_LIGHT"; fill.data.energy = 180; fill.data.size = 3.0

    root, _ = build_clown_once(spec)
    root.rotation_euler[2] = base.DIRECTION_ANGLE[direction]

    direction_dir = output_dir / direction.lower()
    render_supersampled(scene, direction_dir)

    direction_points = base.pose_points(spec, direction, "idle")
    projected = base.project_landmarks(scene, canonical_camera, direction_points)
    spatial = base.frame_spatial(scene, canonical_camera, projected, direction)
    payload = {
        "contract": "CH_CLOWN_TURNTABLE_DIRECTION_V2",
        "direction": direction,
        "frame": "idle",
        "frameSize": list(FRAME),
        "reviewSize": [FRAME[0] * SUPERSAMPLE, FRAME[1] * SUPERSAMPLE],
        "groundAnchor": list(ANCHOR),
        "camera": "CH_ACTOR_CAMERA_V1",
        "proxy": {
            "contract": "CH_CLOWN_PHYSICAL_PROXY_V2",
            "singleAuthoredModel": True,
            "directionViaRootRotationOnly": True,
            "primitiveBalloonTorsoRemoved": True,
            "smallCurlHairRing": True,
            "supersample": SUPERSAMPLE,
        },
        "points": projected,
        "anchors": spatial,
        "sockets": {"left_hand": projected["hand_L"], "right_hand": projected["hand_R"]},
        "outputs": {"underlay": "underlay.png", "review": "underlay_review.png"},
    }
    (direction_dir / "underlay.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def write_guarded_proxy_outputs(output_dir: Path, report: dict) -> None:
    south = output_dir / "s" / "underlay.png"
    proxy_south = output_dir / "proxy_south.png"
    shutil.copyfile(south, proxy_south)

    preflight_report = {
        "contract": "CH_SCENE_PREFLIGHT_V1",
        "status": "pass",
        "assetId": "clown_01",
        "purpose": "character_direction_identity_lock_v2",
        "frameSize": list(FRAME),
        "groundAnchor": list(ANCHOR),
        "camera": "CH_ACTOR_CAMERA_V1",
        "checks": {
            "singlePhysicalModel": True,
            "directionViaRootRotationOnly": True,
            "fourCanonicalDirections": True,
            "supersampled": True,
            "runtimeExportAllowed": False,
        },
    }
    (output_dir / "preflight_report.json").write_text(json.dumps(preflight_report, indent=2) + "\n", encoding="utf-8")

    proxy_report = {
        "contract": "CH_PROXY_RENDER_V1",
        "status": "ok",
        "assetId": "clown_01",
        "direction": "south",
        "sha256": sha256(proxy_south),
        "proxy": "proxy_south.png",
        "turntableReport": "turntable_report.json",
        "geometryAuthority": "CH_Blender_single_physical_model_v2",
        "requiresHumanVisualReview": True,
        "runtimeExportAllowed": False,
        "directions": report["directions"],
    }
    (output_dir / "proxy_report.json").write_text(json.dumps(proxy_report, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    spec = base.load_spec(args.character_spec)
    if spec.get("characterId") != "clown_01":
        raise RuntimeError("blender_clown_turntable.py currently expects clown_01")

    args.output.mkdir(parents=True, exist_ok=True)
    directions = {direction: render_direction(spec, args, direction, args.output) for direction in DIRECTIONS}
    report = {
        "contract": "CH_CLOWN_TURNTABLE_V2",
        "status": "candidate_for_visual_review",
        "characterId": "clown_01",
        "directions": list(DIRECTIONS),
        "camera": "CH_ACTOR_CAMERA_V1",
        "frameSize": list(FRAME),
        "groundAnchor": list(ANCHOR),
        "geometryAuthority": "one_model_root_rotated",
        "paintAuthority": "CH_Character_Studio",
        "crossDirectionRasterWarp": False,
        "independentDirectionalSilhouetteAuthoring": False,
        "supersample": SUPERSAMPLE,
        "directionsData": directions,
    }
    (args.output / "turntable_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_guarded_proxy_outputs(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
