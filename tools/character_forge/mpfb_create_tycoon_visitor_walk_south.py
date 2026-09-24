"""Render a strongly stylized SOUTH visitor from the MPFB anatomical base.

This is a visual pivot, not a new human model. MPFB remains responsible for
anatomy, rigging and fitted MHCLO assets, while this pass deliberately pushes
silhouette/readability toward City Horizon's classic-tycoon target.

Gate remains SOUTH only: idle + Walk A + Walk B.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mpfb_create_basic_human as base  # noqa: E402
import mpfb_create_system_asset_visitor as visitor  # noqa: E402
import mpfb_create_system_asset_visitor_walk_south as walk  # noqa: E402


FRAME_RESOLUTION = 128
GAMEPLAY_ORTHO_SCALE = 4.45
HEAD_SCALE = 1.13
LIMB_THICKNESS = 1.09
TORSO_THICKNESS = 1.055


def _principled_nodes(obj: bpy.types.Object):
    if not hasattr(obj.data, "materials"):
        return
    for mat in obj.data.materials:
        if mat is None:
            continue
        mat.diffuse_color[3] = 1.0
        if not mat.use_nodes or mat.node_tree is None:
            continue
        for node in mat.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                yield mat, node


def apply_clean_material_response(human: bpy.types.Object, assets: list[dict]) -> None:
    """Reduce plastic/photoreal response while keeping outfit identity.

    We intentionally keep the approved MakeHuman textures for this first gate,
    but flatten the shader response: high roughness, almost no specular and
    slightly brighter base values. This preserves shirt/jeans separation while
    removing much of the realistic shine that collapsed at gameplay size.
    """
    objects = [human]
    for item in assets:
        obj = bpy.data.objects.get(item["object"])
        if obj is not None:
            objects.append(obj)

    for obj in objects:
        for _mat, node in _principled_nodes(obj):
            if "Roughness" in node.inputs:
                node.inputs["Roughness"].default_value = 1.0
            if "Metallic" in node.inputs:
                node.inputs["Metallic"].default_value = 0.0
            if "IOR Level" in node.inputs:
                node.inputs["IOR Level"].default_value = 0.12
            if "Coat Weight" in node.inputs:
                node.inputs["Coat Weight"].default_value = 0.0

    # Skin is intentionally a clean warm midtone, not a photographic shader.
    visitor.set_skin_material(human)
    for _mat, node in _principled_nodes(human):
        node.inputs["Base Color"].default_value = (0.64, 0.40, 0.25, 1.0)
        node.inputs["Roughness"].default_value = 1.0


def apply_tycoon_proportions(rig: bpy.types.Object) -> list[str]:
    """Stylize with pose-bone scale, preserving the MPFB mesh and skinning.

    Blender bones use local Y as their length axis. Scaling only X/Z thickens
    limbs without lengthening the stride. Head is enlarged uniformly for small
    sprite readability. Missing optional bones are simply ignored and reported.
    """
    changed: list[str] = []

    def scale_bone(name: str, sx: float, sy: float, sz: float) -> None:
        bone = rig.pose.bones.get(name)
        if bone is None:
            return
        bone.scale = (sx, sy, sz)
        changed.append(name)

    scale_bone("head", HEAD_SCALE, HEAD_SCALE, HEAD_SCALE)

    for name in ("spine01", "spine02"):
        scale_bone(name, TORSO_THICKNESS, 1.0, TORSO_THICKNESS)

    for side in ("L", "R"):
        for name in (
            f"upperarm01.{side}",
            f"upperarm02.{side}",
            f"lowerarm01.{side}",
            f"lowerarm02.{side}",
            f"upperleg01.{side}",
            f"upperleg02.{side}",
            f"lowerleg01.{side}",
            f"lowerleg02.{side}",
        ):
            scale_bone(name, LIMB_THICKNESS, 1.0, LIMB_THICKNESS)

    bpy.context.view_layer.update()
    return changed


def tune_tycoon_lighting(scene: bpy.types.Scene) -> None:
    """Broad, readable lighting with less fashion-render contrast."""
    key = bpy.data.objects.get("CHCharacterForgeKey")
    fill = bpy.data.objects.get("CHCharacterForgeFill")
    if key is not None and getattr(key, "data", None) is not None:
        key.data.energy = 650
        key.data.size = 5.5
        key.data.color = (1.0, 0.91, 0.78)
    if fill is not None and getattr(fill, "data", None) is not None:
        fill.data.energy = 520
        fill.data.size = 6.5
        fill.data.color = (0.72, 0.82, 1.0)

    rim_data = bpy.data.lights.new("CHTycoonVisitorSoftFill", type="AREA")
    rim_data.energy = 220
    rim_data.size = 6.0
    rim_data.color = (1.0, 0.95, 0.88)
    rim = bpy.data.objects.new("CHTycoonVisitorSoftFill", rim_data)
    scene.collection.objects.link(rim)
    rim.location = (0.0, 5.0, 6.0)

    target = bpy.context.scene.camera.location.copy()
    target.x = 0.0
    target.y = 0.0
    target.z = 1.05
    base.point_at(rim, target)


def make_tycoon_walk_pose(phase: int) -> dict:
    """Short readable walk, slightly clearer than the previous realistic gate."""
    deg = math.radians
    stride = 9.0 * phase
    arm = 4.0 * phase
    idle = base.make_neutral_idle_pose()
    rotations = dict(idle["bone_rotations"])
    rotations.update(
        {
            "upperleg01.L": [deg(-stride), 0.0, 0.0],
            "upperleg01.R": [deg(stride), 0.0, 0.0],
            "lowerleg01.L": [deg(6.0 if phase < 0 else 2.5), 0.0, 0.0],
            "lowerleg01.R": [deg(6.0 if phase > 0 else 2.5), 0.0, 0.0],
            "upperarm01.L": [deg(arm), 0.0, deg(-22.0)],
            "upperarm01.R": [deg(-arm), 0.0, deg(22.0)],
            "lowerarm01.L": [deg(-5.0), 0.0, 0.0],
            "lowerarm01.R": [deg(-5.0), 0.0, 0.0],
        }
    )
    return {
        "skeleton_type": "default_no_toes",
        "bone_rotations": rotations,
        "bone_rotation_modes": {name: "XYZ" for name in rotations},
        "bone_translations": {},
        "has_ik_bones": False,
        "original_spine_length": 0.0,
        "original_shoulder_width": 0.0,
    }


def render_frame(scene: bpy.types.Scene, camera: bpy.types.Object, output: Path) -> None:
    scene.render.resolution_x = FRAME_RESOLUTION
    scene.render.resolution_y = FRAME_RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True
    camera.data.ortho_scale = GAMEPLAY_ORTHO_SCALE
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    output_value = argv[0] if argv else os.environ.get(
        "CH_AGENT_OUTPUT_DIR",
        "out/ch_blender_agent/character.forge.mpfb.visitor.tycoon.south.manual",
    )
    output_dir = Path(output_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    (
        extension_module,
        human,
        rig,
        RigService,
        assets,
        phenotype,
        camera,
        scene,
    ) = walk.build_character()

    apply_clean_material_response(human, assets)
    tune_tycoon_lighting(scene)

    frames = [
        ("idle", base.make_neutral_idle_pose()),
        ("walk_a", make_tycoon_walk_pose(+1)),
        ("walk_b", make_tycoon_walk_pose(-1)),
    ]

    outputs: dict[str, str] = {}
    proportion_bones: list[str] = []
    for frame_name, pose in frames:
        base.apply_idle_pose(RigService, rig, pose)
        proportion_bones = apply_tycoon_proportions(rig)
        path = output_dir / f"visitor_male_tycoon_south_{frame_name}.png"
        render_frame(scene, camera, path)
        outputs[frame_name] = path.name

    report = {
        "contract": "CH_CHARACTER_FORGE_TYCOON_VISITOR_SOUTH_V1",
        "status": "ok",
        "direction": "south",
        "source": "MPFB anatomical base + official MakeHuman fitted assets",
        "visualTarget": "City Horizon classic-tycoon readability; not photoreal human",
        "phenotypeApplied": phenotype,
        "rig": "default_no_toes",
        "assets": assets,
        "stylization": {
            "headScale": HEAD_SCALE,
            "limbThickness": LIMB_THICKNESS,
            "torsoThickness": TORSO_THICKNESS,
            "scaledBones": proportion_bones,
            "shader": "high-roughness low-specular clean response",
            "lighting": "broad low-contrast tycoon readability",
            "texturePolicy": "keep fitted outfit identity for V1; no global palette reduction",
        },
        "gameplayFrame": {
            "resolution": [FRAME_RESOLUTION, FRAME_RESOLUTION],
            "orthoScale": GAMEPLAY_ORTHO_SCALE,
            "transparent": True,
        },
        "animation": {
            "idleFrames": 1,
            "walkFrames": 2,
            "recommendedFrameDurationMs": 220,
            "loop": "A-B-A-B",
            "strideDegrees": 9.0,
            "armSwingDegrees": 4.0,
            "verticalBob": False,
        },
        "outputs": outputs,
        "runtimePromotion": False,
        "nextGate": "visual approval against City Horizon world before other directions",
    }
    (output_dir / "visitor_male_tycoon_south.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
