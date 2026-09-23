"""Create one neutral/male MPFB human for Character Forge evaluation.

Experimental only: no runtime promotion. This script assumes MPFB is already
bootstrapped into Blender user resources for the current worker run.
"""
from __future__ import annotations

import importlib
import json
import math
import sys
from pathlib import Path

import bpy


def dynamic_import(absolute_package_str: str, key: str):
    for amod in list(sys.modules):
        if amod.endswith(absolute_package_str):
            module = importlib.import_module(amod)
            if not hasattr(module, key):
                raise AttributeError(f"Module {amod} missing {key}")
            return getattr(module, key)
    raise RuntimeError(f"MPFB module not loaded: {absolute_package_str}")


def find_mpfb_extension_module() -> str:
    # Import every extension package candidate that visibly contains mpfb.
    for addon_name in bpy.context.preferences.addons.keys():
        if "mpfb" in addon_name.lower():
            try:
                importlib.import_module(addon_name)
                return addon_name
            except Exception:
                pass

    # Blender 4.2 extension namespace. Try known conventional suffixes.
    candidates = [
        "bl_ext.user_default.mpfb",
        "bl_ext.blender_org.mpfb",
    ]
    for name in candidates:
        try:
            importlib.import_module(name)
            return name
        except Exception:
            continue
    raise RuntimeError("MPFB extension could not be imported after bootstrap")


def setup_camera_and_light(human: bpy.types.Object) -> bpy.types.Camera:
    # Character review camera only. This is not the final runtime scale gate.
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
    output_dir = Path(argv[0] if argv else "out/ch_blender_agent/character.forge.mpfb.human.001").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    extension_module = find_mpfb_extension_module()
    # Register extension when imported outside normal interactive startup.
    module = importlib.import_module(extension_module)
    if hasattr(module, "register"):
        try:
            module.register()
        except Exception:
            pass

    HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
    TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")
    HumanObjectProperties = dynamic_import("mpfb.entities.objectproperties", "HumanObjectProperties")

    human = HumanService.create_human(feet_on_ground=True, scale=0.1)
    human.name = "CH_Visitor_Male_MPFB_Probe"

    # MPFB uses 0..1 macro values. Bias toward adult male but not muscular/heavy.
    for key, value in {
        "gender": 0.88,
        "age": 0.50,
        "muscle": 0.42,
        "weight": 0.46,
        "proportions": 0.48,
        "height": 0.48,
    }.items():
        try:
            HumanObjectProperties.set_value(key, value, entity_reference=human)
        except Exception:
            pass
    TargetService.reapply_macro_details(human)

    # Stylized viewport material: intentionally simple, because this is a silhouette test.
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
        "blender": bpy.app.version_string,
        "object": human.name,
        "vertexCount": len(human.data.vertices),
        "output": "mpfb_male_south_idle.png",
        "purpose": "silhouette_and_human_base_mesh_evaluation_only",
    }
    (output_dir / "mpfb_human_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
