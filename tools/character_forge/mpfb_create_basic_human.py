"""Create one neutral male MPFB human for Character Forge evaluation.

Experimental only: no runtime promotion. MPFB is installed into an isolated
Blender user profile by ``bootstrap_mpfb.sh`` before this script is executed.

This stage intentionally validates only the foundation:
    male phenotype -> neutral idle pose -> canonical City Horizon SOUTH view

Clothes, hair and walk animation remain out of scope until this body proxy is
visually approved.
"""
from __future__ import annotations

import importlib
import json
import math
import os
import sys
from pathlib import Path

import bpy


CAMERA_CONTRACT = {
    "projection": "orthographic_dimetric_2_to_1",
    "yawDegrees": 45.0,
    "elevationDegrees": 30.0,
    "target": [0.0, 0.0, 1.25],
    "horizontalDistance": 8.0,
    # Close review framing only. Runtime/gameplay scale comes later.
    "reviewOrthoScale": 2.35,
}

MALE_PHENOTYPE = {
    # MPFB documents gender 0=female, 1=male. Use the endpoint here rather
    # than a blend so the first Character Forge gate is unambiguously male.
    "gender": 1.0,
    "age": 0.50,
    "muscle": 0.56,
    "weight": 0.45,
    # Bias toward broader shoulders / narrower hips without body-builder shape.
    "proportions": 0.72,
    "height": 0.50,
    # Avoid carrying the neutral basemesh breast morph into the male proxy.
    "cupsize": 0.0,
    "firmness": 0.50,
}


def import_symbol(extension_module: str, relative_module: str, key: str):
    """Import one MPFB symbol from Blender's extension namespace."""
    candidates = [
        f"{extension_module}.{relative_module}",
        f"mpfb.{relative_module}",
    ]
    errors = []
    for name in candidates:
        try:
            module = importlib.import_module(name)
            if hasattr(module, key):
                return getattr(module, key)
            errors.append(f"{name}: missing {key}")
        except Exception as exc:
            errors.append(f"{name}: {exc!r}")

    wanted_suffix = f"mpfb.{relative_module}"
    for loaded_name in list(sys.modules):
        if loaded_name.endswith(wanted_suffix):
            module = importlib.import_module(loaded_name)
            if hasattr(module, key):
                return getattr(module, key)

    raise RuntimeError(
        f"Could not import MPFB symbol {key} from {relative_module}; attempts={errors}"
    )


def find_mpfb_extension_module() -> str:
    for addon_name in bpy.context.preferences.addons.keys():
        if "mpfb" in addon_name.lower():
            return addon_name

    candidates = [
        "bl_ext.user_default.mpfb",
        "bl_ext.blender_org.mpfb",
    ]
    errors = []
    for name in candidates:
        try:
            importlib.import_module(name)
            return name
        except Exception as exc:
            errors.append(f"{name}: {exc!r}")
    raise RuntimeError(f"MPFB extension could not be imported after bootstrap: {errors}")


def ensure_mpfb_enabled(extension_module: str) -> None:
    """Enable MPFB in the current Blender process when factory-startup hid prefs."""
    if extension_module in bpy.context.preferences.addons:
        return

    try:
        bpy.ops.preferences.addon_enable(module=extension_module)
    except Exception as exc:
        raise RuntimeError(
            f"MPFB package exists but could not be enabled in this Blender process: {exc!r}"
        ) from exc

    if extension_module not in bpy.context.preferences.addons:
        raise RuntimeError(
            f"MPFB enable returned without registering preferences: {extension_module}"
        )


def clear_scene_objects() -> None:
    """Clear scene content without resetting Blender preferences/extensions."""
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for datablocks in (bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def point_at(obj: bpy.types.Object, target) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_camera_and_light(human: bpy.types.Object) -> bpy.types.Camera:
    """Use the frozen CH camera direction while keeping close review framing."""
    target = human.location.copy()
    target.x = CAMERA_CONTRACT["target"][0]
    target.y = CAMERA_CONTRACT["target"][1]
    target.z = CAMERA_CONTRACT["target"][2]

    yaw = math.radians(CAMERA_CONTRACT["yawDegrees"])
    elevation = math.radians(CAMERA_CONTRACT["elevationDegrees"])
    horizontal = CAMERA_CONTRACT["horizontalDistance"]

    camera_data = bpy.data.cameras.new("CHCharacterForgeCamera")
    camera = bpy.data.objects.new("CHCharacterForgeCamera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = CAMERA_CONTRACT["reviewOrthoScale"]
    camera.location = (
        math.sin(yaw) * horizontal,
        -math.cos(yaw) * horizontal,
        target.z + math.tan(elevation) * horizontal,
    )
    point_at(camera, target)

    key_data = bpy.data.lights.new("CHCharacterForgeKey", type="AREA")
    key_data.energy = 980
    key_data.color = (1.0, 0.79, 0.60)
    key_data.shape = "DISK"
    key_data.size = 4.1
    key = bpy.data.objects.new("CHCharacterForgeKey", key_data)
    bpy.context.scene.collection.objects.link(key)
    key.location = (-5.6, -6.2, 8.5)
    point_at(key, target)

    fill_data = bpy.data.lights.new("CHCharacterForgeFill", type="AREA")
    fill_data.energy = 315
    fill_data.color = (0.52, 0.68, 1.0)
    fill_data.size = 5.5
    fill = bpy.data.objects.new("CHCharacterForgeFill", fill_data)
    bpy.context.scene.collection.objects.link(fill)
    fill.location = (5.0, 4.5, 5.2)
    point_at(fill, target)

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.13, 0.16, 0.20)
    return camera


def make_neutral_idle_pose() -> dict:
    """Small FK correction from MakeHuman's A-pose toward a relaxed idle."""
    deg = math.radians
    rotations = {
        "clavicle.L": [0.0, 0.0, deg(-4.0)],
        "upperarm01.L": [0.0, 0.0, deg(-22.0)],
        "lowerarm01.L": [deg(-6.0), 0.0, 0.0],
        "clavicle.R": [0.0, 0.0, deg(4.0)],
        "upperarm01.R": [0.0, 0.0, deg(22.0)],
        "lowerarm01.R": [deg(-6.0), 0.0, 0.0],
    }
    return {
        "skeleton_type": "default_no_toes",
        "bone_rotations": rotations,
        "bone_rotation_modes": {name: "XYZ" for name in rotations},
        "bone_translations": {},
        "has_ik_bones": False,
        "original_spine_length": 0.0,
        "original_shoulder_width": 0.0,
    }


def apply_idle_pose(RigService, rig: bpy.types.Object, idle_pose: dict) -> None:
    """Apply MPFB FK pose with the armature active in POSE mode.

    RigService uses bpy.ops.pose internally, so headless Blender needs an
    explicit active-object/mode context before calling it.
    """
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    try:
        RigService.set_pose_from_dict(rig, idle_pose, from_rest_pose=True)
    finally:
        if bpy.context.object is not None and bpy.context.object.mode == "POSE":
            bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()


def main() -> None:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    output_value = (
        argv[0]
        if argv
        else os.environ.get(
            "CH_AGENT_OUTPUT_DIR",
            "out/ch_blender_agent/character.forge.mpfb.human.manual",
        )
    )
    output_dir = Path(output_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    extension_module = find_mpfb_extension_module()
    ensure_mpfb_enabled(extension_module)
    clear_scene_objects()

    HumanService = import_symbol(extension_module, "services.humanservice", "HumanService")
    TargetService = import_symbol(extension_module, "services.targetservice", "TargetService")
    RigService = import_symbol(extension_module, "services.rigservice", "RigService")
    HumanObjectProperties = import_symbol(
        extension_module, "entities.objectproperties", "HumanObjectProperties"
    )

    human = HumanService.create_human(feet_on_ground=True, scale=0.1)
    human.name = "CH_Visitor_Male_MPFB_Probe"

    for key, value in MALE_PHENOTYPE.items():
        HumanObjectProperties.set_value(key, value, entity_reference=human)
    TargetService.reapply_macro_details(human)
    bpy.context.view_layer.update()

    actual_phenotype = {
        key: HumanObjectProperties.get_value(key, entity_reference=human)
        for key in MALE_PHENOTYPE
    }

    # Add the canonical MakeHuman FK rig and use MPFB's own pose loader instead
    # of hand-editing mesh vertices. This becomes the foundation for walking.
    rig = HumanService.add_builtin_rig(human, "default_no_toes")
    idle_pose = make_neutral_idle_pose()
    apply_idle_pose(RigService, rig, idle_pose)

    mat = bpy.data.materials.new("CHVisitorSkinProbe")
    mat.diffuse_color = (0.56, 0.33, 0.20, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (0.56, 0.33, 0.20, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.88
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
    if human.data.materials:
        human.data.materials[0] = mat
    else:
        human.data.materials.append(mat)

    setup_camera_and_light(human)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 768
    scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.filepath = str(output_dir / "mpfb_male_south_idle.png")
    bpy.ops.render.render(write_still=True)

    report = {
        "contract": "CH_CHARACTER_FORGE_MPFB_HUMAN_V2",
        "status": "ok",
        "extensionModule": extension_module,
        "addonEnabled": extension_module in bpy.context.preferences.addons,
        "blender": bpy.app.version_string,
        "object": human.name,
        "vertexCount": len(human.data.vertices),
        "phenotypeRequested": MALE_PHENOTYPE,
        "phenotypeApplied": actual_phenotype,
        "rig": "default_no_toes",
        "pose": "neutral_idle_fk_v1",
        "camera": CAMERA_CONTRACT,
        "direction": "south",
        "output": "mpfb_male_south_idle.png",
        "purpose": "male_body_idle_and_canonical_south_evaluation_only",
    }
    (output_dir / "mpfb_male_south_idle.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
