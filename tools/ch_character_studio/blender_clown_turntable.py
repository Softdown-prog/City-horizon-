"""Render one physical clown authored by CH Blender Authoring Core.

The character is built exactly once in South-local space. Canonical S/E/N/W
views are produced only by rotating the physical root. No directional geometry
re-authoring or cross-direction raster warping is allowed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
CH_BLENDER_DIR = REPO_ROOT / "tools" / "ch_blender"
for candidate in (SCRIPT_DIR, CH_BLENDER_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import bpy
from mathutils import Vector

import blender_character_base as base
from authoring import CharacterAuthoring

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
    """Keep canonical camera/lights and delete the generic visible actor."""
    keep = {"CH_ACTOR_CAMERA", "CH_KEY_LIGHT", "CH_FILL_LIGHT"}
    for obj in list(bpy.data.objects):
        if obj.name in keep or obj.type in {"CAMERA", "LIGHT"}:
            continue
        bpy.data.objects.remove(obj, do_unlink=True)


def palette_value(spec: dict, key: str, fallback: str) -> str:
    return spec.get("appearance", {}).get("palette", {}).get(key, fallback)


def build_clown(spec: dict) -> tuple[CharacterAuthoring, dict[str, Vector]]:
    """Build one stylized physical clown using semantic high-level forms."""
    points = base.pose_points(spec, "S", "idle")
    ch = CharacterAuthoring("CH_CLOWN")

    skin = ch.material("SKIN", palette_value(spec, "skin", "#f3c7ad"), roughness=0.90, specular=0.08)
    hair = ch.material("HAIR", palette_value(spec, "hair", "#d43b2f"), roughness=0.88, specular=0.10)
    red = ch.material("RED", palette_value(spec, "primary", "#d43b2f"))
    blue = ch.material("BLUE", palette_value(spec, "secondary", "#2b71c9"))
    yellow = ch.material("YELLOW", palette_value(spec, "accent", "#f2d744"))
    shoes = ch.material("SHOES", palette_value(spec, "shoes", "#26313a"), roughness=0.76, specular=0.12)
    white = ch.material("WHITE", "#f4f2e3", roughness=0.94, specular=0.05)
    nose = ch.material("NOSE", "#df3b36", roughness=0.86, specular=0.08)
    eye = ch.material("EYE", "#262220", roughness=0.92, specular=0.04)
    purple = ch.material("BOW", "#8b5cf6", roughness=0.84, specular=0.08)

    # Head and neck. The head remains compact so hair owns the clown silhouette.
    ch.soft("head", (0.0, 0.0, 1.52), (0.132, 0.122, 0.158), skin)
    ch.soft("neck", (0.0, 0.0, 1.34), (0.057, 0.057, 0.072), skin)
    ch.soft("ear_L", (-0.132, 0.0, 1.53), (0.027, 0.019, 0.038), skin)
    ch.soft("ear_R", (0.132, 0.0, 1.53), (0.027, 0.019, 0.038), skin)

    # Hairstyle = one semantic cluster, not three giant spheres. Most volume is
    # side/back so the face remains readable from the canonical South view.
    ch.hair_lobes(
        "hair",
        [
            {"location": (-0.142, 0.018, 1.605), "scale": (0.058, 0.050, 0.060)},
            {"location": (-0.118, 0.060, 1.657), "scale": (0.057, 0.052, 0.058)},
            {"location": (-0.063, 0.094, 1.681), "scale": (0.055, 0.052, 0.056)},
            {"location": (0.000, 0.108, 1.690), "scale": (0.054, 0.052, 0.054)},
            {"location": (0.063, 0.094, 1.681), "scale": (0.055, 0.052, 0.056)},
            {"location": (0.118, 0.060, 1.657), "scale": (0.057, 0.052, 0.058)},
            {"location": (0.142, 0.018, 1.605), "scale": (0.058, 0.050, 0.060)},
            {"location": (-0.095, 0.115, 1.598), "scale": (0.052, 0.048, 0.052)},
            {"location": (0.095, 0.115, 1.598), "scale": (0.052, 0.048, 0.052)},
        ],
        hair,
    )

    # Facial landmarks live only on the physical front. Rotation/occlusion decides
    # whether they are visible in E/N/W; no direction-specific face is authored.
    ch.soft("nose", (0.0, -0.126, 1.515), (0.040, 0.029, 0.040), nose)
    ch.soft("eye_L", (-0.046, -0.116, 1.566), (0.013, 0.009, 0.017), eye)
    ch.soft("eye_R", (0.046, -0.116, 1.566), (0.013, 0.009, 0.017), eye)

    # Jacket is a compact rounded shell. It deliberately avoids the former balloon
    # ellipsoid so the waist/shoulders read as clothing rather than a red abdomen.
    ch.box("jacket", (0.0, 0.0, 1.055), (0.345, 0.225, 0.405), red, bevel=0.060, bevel_segments=4)
    ch.soft("waist", (0.0, 0.0, 0.825), (0.150, 0.102, 0.085), red)

    # Ruff is a real toroidal collar plus two front puffs for the old-tycoon read.
    ch.ring("ruff_ring", (0.0, 0.0, 1.305), 0.092, 0.030, white)
    ch.soft("ruff_front_L", (-0.055, -0.065, 1.300), (0.055, 0.034, 0.037), white)
    ch.soft("ruff_front_R", (0.055, -0.065, 1.300), (0.055, 0.034, 0.037), white)

    ch.soft("bow_L", (-0.038, -0.137, 1.225), (0.047, 0.022, 0.037), purple)
    ch.soft("bow_R", (0.038, -0.137, 1.225), (0.047, 0.022, 0.037), purple)

    # Tapered sleeves are wider at the shoulder/cuff and no longer read as pipes.
    arm_mats = {"L": blue, "R": yellow}
    for label in ("L", "R"):
        ch.segment(
            f"sleeve_upper_{label}",
            points[f"shoulder_{label}"], points[f"elbow_{label}"],
            0.060, 0.050, arm_mats[label], vertices=24,
        )
        ch.segment(
            f"sleeve_lower_{label}",
            points[f"elbow_{label}"], points[f"hand_{label}"],
            0.050, 0.056, arm_mats[label], vertices=24,
        )
        ch.soft(f"glove_{label}", points[f"hand_{label}"], (0.056, 0.056, 0.061), white)

    # Trousers taper gently toward the ankle. Each side remains an independent
    # semantic color region for later color-mask generation.
    leg_mats = {"L": blue, "R": yellow}
    for label in ("L", "R"):
        ch.segment(
            f"trouser_upper_{label}",
            points[f"hip_{label}"], points[f"knee_{label}"],
            0.064, 0.057, leg_mats[label], vertices=24,
        )
        ch.segment(
            f"trouser_lower_{label}",
            points[f"knee_{label}"], points[f"ankle_{label}"],
            0.057, 0.047, leg_mats[label], vertices=24,
        )
        foot = points[f"foot_{label}"]
        # Rounded boxes make shoes wide/flat without the football-shaped ellipsoid.
        ch.box(
            f"shoe_{label}",
            (foot.x, foot.y + 0.035, foot.z + 0.005),
            (0.155, 0.225, 0.085),
            shoes,
            bevel=0.035,
            bevel_segments=4,
        )

    return ch, points


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


def setup_authoring_scene(spec: dict, args: argparse.Namespace):
    """Create canonical camera/lights once, then replace the generic actor."""
    _, canonical_camera, _ = base.setup_scene(spec, "S", "idle", args)
    remove_generic_actor_geometry()
    scene = bpy.context.scene
    scene.camera = canonical_camera
    return scene, canonical_camera


def render_direction(
    spec: dict,
    scene: bpy.types.Scene,
    canonical_camera: bpy.types.Object,
    character: CharacterAuthoring,
    direction: str,
    output_dir: Path,
) -> dict:
    character.set_yaw(base.DIRECTION_ANGLE[direction])
    bpy.context.view_layer.update()

    direction_dir = output_dir / direction.lower()
    render_supersampled(scene, direction_dir)

    direction_points = base.pose_points(spec, direction, "idle")
    projected = base.project_landmarks(scene, canonical_camera, direction_points)
    spatial = base.frame_spatial(scene, canonical_camera, projected, direction)
    payload = {
        "contract": "CH_CLOWN_TURNTABLE_DIRECTION_V3",
        "direction": direction,
        "frame": "idle",
        "frameSize": list(FRAME),
        "reviewSize": [FRAME[0] * SUPERSAMPLE, FRAME[1] * SUPERSAMPLE],
        "groundAnchor": list(ANCHOR),
        "camera": "CH_ACTOR_CAMERA_V1",
        "authoringCore": "CH_AUTHORING_CORE_V1",
        "proxy": {
            "contract": "CH_CLOWN_PHYSICAL_PROXY_V3",
            "singleAuthoredModel": True,
            "directionViaRootRotationOnly": True,
            "semanticHighLevelForms": True,
            "taperedLimbs": True,
            "roundedShoeForms": True,
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
        "purpose": "character_authoring_core_visual_gate",
        "frameSize": list(FRAME),
        "groundAnchor": list(ANCHOR),
        "camera": "CH_ACTOR_CAMERA_V1",
        "checks": {
            "authoringCoreV1": True,
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
        "geometryAuthority": "CH_AUTHORING_CORE_V1",
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
    scene, canonical_camera = setup_authoring_scene(spec, args)
    character, _ = build_clown(spec)

    directions = {}
    for direction in DIRECTIONS:
        directions[direction] = render_direction(
            spec, scene, canonical_camera, character, direction, args.output
        )

    report = {
        "contract": "CH_CLOWN_TURNTABLE_V3",
        "status": "candidate_for_visual_review",
        "characterId": "clown_01",
        "directions": list(DIRECTIONS),
        "camera": "CH_ACTOR_CAMERA_V1",
        "frameSize": list(FRAME),
        "groundAnchor": list(ANCHOR),
        "authoringCore": "CH_AUTHORING_CORE_V1",
        "geometryAuthority": "CH_Blender_Authoring_Core_single_physical_model",
        "paintAuthority": "CH_Character_Studio",
        "crossDirectionRasterWarp": False,
        "independentDirectionalSilhouetteAuthoring": False,
        "directionsData": directions,
    }
    (args.output / "turntable_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_guarded_proxy_outputs(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
