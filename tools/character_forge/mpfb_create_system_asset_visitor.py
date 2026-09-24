"""Render the first City Horizon visitor using official MPFB/MakeHuman assets.

This is still a SOUTH-only visual gate. Unlike the earlier surface-shell proxy,
clothes, shoes, hair, eyes and eyebrows are real MHCLO assets fitted and rigged
by MPFB. Walk A/B remains blocked until this dressed idle is visually approved.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import mpfb_create_basic_human as base  # noqa: E402


REVIEW_RESOLUTION = 768
GAMEPLAY_RESOLUTION = 256
GAMEPLAY_ORTHO_SCALE = 5.6

ASSET_SPECS = [
    ("eyes", "low-poly.mhclo", "Eyes"),
    ("eyebrows", "eyebrow001.mhclo", "Eyebrows"),
    ("hair", "short01.mhclo", "Hair"),
    ("clothes", "male_casualsuit01.mhclo", "Clothes"),
    ("clothes", "shoes01.mhclo", "Clothes"),
]


def make_skin_material() -> bpy.types.Material:
    mat = bpy.data.materials.new("CHVisitorSkin")
    mat.diffuse_color = (0.56, 0.33, 0.20, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (0.56, 0.33, 0.20, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.91
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def set_skin_material(human: bpy.types.Object) -> None:
    mat = make_skin_material()
    if human.data.materials:
        human.data.materials[0] = mat
    else:
        human.data.materials.append(mat)


def make_materials_matte(obj: bpy.types.Object) -> None:
    """Keep official asset colors/textures while removing shiny/plastic response."""
    if not hasattr(obj.data, "materials"):
        return
    for mat in obj.data.materials:
        if mat is None:
            continue
        mat.diffuse_color[3] = 1.0
        if not mat.use_nodes or mat.node_tree is None:
            continue
        for node in mat.node_tree.nodes:
            if node.type != "BSDF_PRINCIPLED":
                continue
            if "Roughness" in node.inputs:
                node.inputs["Roughness"].default_value = 0.94
            if "Metallic" in node.inputs:
                node.inputs["Metallic"].default_value = 0.0
            if "IOR Level" in node.inputs:
                node.inputs["IOR Level"].default_value = 0.25


def add_system_assets(HumanService, AssetService, human: bpy.types.Object) -> list[dict]:
    added = []
    for subdir, filename, asset_type in ASSET_SPECS:
        path = AssetService.find_asset_absolute_path(filename, asset_subdir=subdir)
        if path is None:
            raise RuntimeError(
                f"Required MakeHuman system asset not found: {subdir}/{filename}; "
                "bootstrap_makehuman_assets.sh must run before this job"
            )
        obj = HumanService.add_mhclo_asset(
            path,
            human,
            asset_type=asset_type,
            material_type="GAMEENGINE",
            set_up_rigging=True,
            interpolate_weights=True,
            import_subrig=True,
            import_weights=True,
        )
        if obj is None:
            raise RuntimeError(f"MPFB returned no object for asset {path}")
        make_materials_matte(obj)
        added.append(
            {
                "subdir": subdir,
                "file": filename,
                "type": asset_type,
                "path": str(path),
                "object": obj.name,
            }
        )
    return added


def configure_render(scene: bpy.types.Scene) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.resolution_percentage = 100


def render(
    scene: bpy.types.Scene,
    camera: bpy.types.Object,
    output: Path,
    resolution: int,
    ortho_scale: float,
) -> None:
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    camera.data.ortho_scale = ortho_scale
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    output_value = argv[0] if argv else os.environ.get(
        "CH_AGENT_OUTPUT_DIR",
        "out/ch_blender_agent/character.forge.mpfb.visitor.system.manual",
    )
    output_dir = Path(output_value).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    extension_module = base.find_mpfb_extension_module()
    base.ensure_mpfb_enabled(extension_module)
    base.clear_scene_objects()

    HumanService = base.import_symbol(extension_module, "services.humanservice", "HumanService")
    TargetService = base.import_symbol(extension_module, "services.targetservice", "TargetService")
    RigService = base.import_symbol(extension_module, "services.rigservice", "RigService")
    AssetService = base.import_symbol(extension_module, "services.assetservice", "AssetService")
    HumanObjectProperties = base.import_symbol(
        extension_module, "entities.objectproperties", "HumanObjectProperties"
    )

    human = HumanService.create_human(feet_on_ground=True, scale=0.1)
    human.name = "CH_Visitor_Male_SystemAssets_Source"
    for key, value in base.MALE_PHENOTYPE.items():
        HumanObjectProperties.set_value(key, value, entity_reference=human)
    TargetService.reapply_macro_details(human)
    bpy.context.view_layer.update()

    phenotype = {
        key: HumanObjectProperties.get_value(key, entity_reference=human)
        for key in base.MALE_PHENOTYPE
    }

    # MPFB's own documented order: rig first, then MHCLO assets. The assets are
    # fitted to the current human and receive rig weights before the idle pose.
    rig = HumanService.add_builtin_rig(human, "default_no_toes")
    assets = add_system_assets(HumanService, AssetService, human)
    base.apply_idle_pose(RigService, rig, base.make_neutral_idle_pose())
    set_skin_material(human)
    bpy.context.view_layer.update()

    camera = base.setup_camera_and_light(human)
    scene = bpy.context.scene
    configure_render(scene)

    review_path = output_dir / "visitor_male_system_assets_south_review.png"
    gameplay_path = output_dir / "visitor_male_system_assets_south_gameplay.png"
    render(
        scene,
        camera,
        review_path,
        REVIEW_RESOLUTION,
        base.CAMERA_CONTRACT["reviewOrthoScale"],
    )
    render(scene, camera, gameplay_path, GAMEPLAY_RESOLUTION, GAMEPLAY_ORTHO_SCALE)

    report = {
        "contract": "CH_CHARACTER_FORGE_SYSTEM_ASSET_VISITOR_V1",
        "status": "ok",
        "blender": bpy.app.version_string,
        "mpfbExtension": extension_module,
        "phenotypeApplied": phenotype,
        "rig": "default_no_toes",
        "pose": "neutral_idle_fk_v1",
        "direction": "south",
        "assetPack": {
            "name": "makehuman_system_assets",
            "license": os.environ.get("CH_CHARACTER_FORGE_MAKEHUMAN_LICENSE", "CC0-1.0"),
            "source": "https://files2.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip",
            "dataRoot": os.environ.get("CH_CHARACTER_FORGE_MAKEHUMAN_DATA"),
        },
        "assets": assets,
        "materialPolicy": "official colors/textures with matte CH roughness pass",
        "review": {
            "resolution": [REVIEW_RESOLUTION, REVIEW_RESOLUTION],
            "orthoScale": base.CAMERA_CONTRACT["reviewOrthoScale"],
            "file": review_path.name,
        },
        "gameplayPreview": {
            "resolution": [GAMEPLAY_RESOLUTION, GAMEPLAY_RESOLUTION],
            "orthoScale": GAMEPLAY_ORTHO_SCALE,
            "studioReference": "CH_TYCOON_STUDIO_V1",
            "file": gameplay_path.name,
        },
        "runtimePromotion": False,
        "walkBlockedUntilApproval": True,
        "purpose": "official_MHCLO_fit_and_visual_quality_gate_before_walk_A_B",
    }
    report_path = output_dir / "visitor_male_system_assets_south.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
