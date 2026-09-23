"""Create one neutral/male MPFB human for Character Forge evaluation.

Experimental only: no runtime promotion. MPFB is installed into an isolated
Blender user profile by ``bootstrap_mpfb.sh`` before this script is executed.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import bpy


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
    """Enable MPFB in the current Blender process if --factory-startup hid prefs.

    CH Blender jobs traditionally launch with --factory-startup. The Character
    Forge bootstrap installs and enables MPFB in an isolated user profile, but a
    factory-startup process can begin with an empty add-on preference set. The
    extension package is still discoverable, so explicitly enable it before any
    MPFB service asks for add-on preferences.
    """
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

    # Remove orphan scene-level render data only. Do not touch preferences,
    # extensions, MPFB data, or the isolated Character Forge user profile.
    for datablocks in (bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def setup_camera_and_light(human: bpy.types.Object) -> bpy.types.Camera:
    camera_data = bpy.data.cameras.new("CHCharacterForgeCamera")
    camera = bpy.data.objects.new("CHCharacterForgeCamera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.35
    camera.location = (4.2, -4.2, 3.3)

    target = human.location.copy()
    target.z += 0.9
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    key_data = bpy.data.lights.new("CHCharacterForgeKey", type="AREA")
    key_data.energy = 800
    key_data.shape = "DISK"
    key_data.size = 4.0
    key = bpy.data.objects.new("CHCharacterForgeKey", key_data)
    bpy.context.scene.collection.objects.link(key)
    key.location = (-3.0, -4.0, 6.0)

    fill_data = bpy.data.lights.new("CHCharacterForgeFill", type="AREA")
    fill_data.energy = 300
    fill_data.size = 5.0
    fill = bpy.data.objects.new("CHCharacterForgeFill", fill_data)
    bpy.context.scene.collection.objects.link(fill)
    fill.location = (4.0, 1.5, 4.0)

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.035, 0.035, 0.035)
    return camera


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

    # Never call bpy.ops.wm.read_factory_settings() here. That would erase the
    # extension preference state the Character Forge bootstrap just prepared.
    extension_module = find_mpfb_extension_module()
    ensure_mpfb_enabled(extension_module)
    clear_scene_objects()

    HumanService = import_symbol(extension_module, "services.humanservice", "HumanService")
    TargetService = import_symbol(extension_module, "services.targetservice", "TargetService")
    HumanObjectProperties = import_symbol(
        extension_module, "entities.objectproperties", "HumanObjectProperties"
    )

    human = HumanService.create_human(feet_on_ground=True, scale=0.1)
    human.name = "CH_Visitor_Male_MPFB_Probe"

    # Deliberately ordinary adult male. This first gate is about human silhouette,
    # not final clothes, hair, face detail, rigging or gameplay scale.
    for key, value in {
        "gender": 0.88,
        "age": 0.50,
        "muscle": 0.42,
        "weight": 0.46,
        "proportions": 0.48,
        "height": 0.48,
    }.items():
        HumanObjectProperties.set_value(key, value, entity_reference=human)
    TargetService.reapply_macro_details(human)

    mat = bpy.data.materials.new("CHVisitorSkinProbe")
    mat.diffuse_color = (0.56, 0.33, 0.20, 1.0)
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
        "contract": "CH_CHARACTER_FORGE_MPFB_HUMAN_V1",
        "status": "ok",
        "extensionModule": extension_module,
        "addonEnabled": extension_module in bpy.context.preferences.addons,
        "blender": bpy.app.version_string,
        "object": human.name,
        "vertexCount": len(human.data.vertices),
        "output": "mpfb_male_south_idle.png",
        "purpose": "silhouette_and_human_base_mesh_evaluation_only",
    }
    (output_dir / "mpfb_male_south_idle.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
