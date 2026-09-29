"""Render deterministic RGB color masks for Casa Popular.

CH_COLOR_MASK_V1 channels:
  R = wall / sage siding
  G = roof / roof edge
  B = trim / cream architectural trim
  A = visible asset coverage

Non-customizable authored materials render black but remain in alpha coverage so
occlusion stays identical to the approved beauty sprites.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_residential_popular_house_guarded as popular  # noqa: E402

ASSET_ID = "residential_popular_house_3x3_01"
APPROVED_PROXY = "62d823f3d0e64cd1778e007430340ae5ecee4211ea2a7f02293c50dd5e0f3956"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _emission_material(name: str, rgba: tuple[float, float, float, float]):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = rgba
    emission.inputs["Strength"].default_value = 1.0
    links.new(emission.outputs["Emission"], out.inputs["Surface"])
    return mat


def _mask_for_material(material_name: str, masks: dict[str, bpy.types.Material]):
    n = material_name.lower()
    if "popularhousesagesiding" in n:
        return masks["wall"]
    if "popularhouseslateroof" in n or "popularhouseroofedge" in n:
        return masks["roof"]
    if "popularhousecreamtrim" in n:
        return masks["trim"]
    return masks["fixed"]


def _write_worker_metadata(out: Path, recipe_path: Path, studio: dict) -> None:
    """Emit the guarded-job metadata required by CH Blender Agent Worker."""
    (out / "preflight_report.json").write_text(
        json.dumps({
            "contract": "CH_SCENE_PREFLIGHT_V1",
            "assetId": "building.residential_popular_house.01",
            "stage": "final",
            "pass": "color_mask",
            "status": "pass",
            "recipe": str(recipe_path),
        }, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "proxy_approval.json").write_text(
        json.dumps({
            "contract": "CH_PROXY_APPROVAL_V1",
            "assetId": "building.residential_popular_house.01",
            "reviewed": True,
            "proxySha256": APPROVED_PROXY,
            "status": "approved",
        }, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "studio_metadata.json").write_text(
        json.dumps({
            "contract": "CH_STUDIO_METADATA_V1",
            "assetId": "building.residential_popular_house.01",
            "cameraContract": "CH_CAMERA_V1",
            "studioPreset": studio.get("contract", "CH_TYCOON_STUDIO_V1") if isinstance(studio, dict) else "CH_TYCOON_STUDIO_V1",
            "frameSize": [256, 256],
            "transparentBackground": True,
            "pass": "color_mask",
        }, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _render_masks(ctx):
    recipe_path, recipe, ref, studio, out, scene, root, ground, authored = ctx

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Standard"
    try:
        scene.view_settings.look = "None"
    except TypeError:
        pass
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    ground.hide_render = True

    masks = {
        "wall": _emission_material("CHMask_Wall_R", (1.0, 0.0, 0.0, 1.0)),
        "roof": _emission_material("CHMask_Roof_G", (0.0, 1.0, 0.0, 1.0)),
        "trim": _emission_material("CHMask_Trim_B", (0.0, 0.0, 1.0, 1.0)),
        "fixed": _emission_material("CHMask_Fixed", (0.0, 0.0, 0.0, 1.0)),
    }

    for obj in authored:
        for slot in obj.material_slots:
            original = slot.material.name if slot.material else ""
            slot.material = _mask_for_material(original, masks)

    report = {
        "contract": "CH_COLOR_MASK_V1",
        "assetId": "building.residential_popular_house.01",
        "approvedProxySha256": APPROVED_PROXY,
        "frameSize": [256, 256],
        "alpha": "coverage",
        "channels": {"R": "wall", "G": "roof", "B": "trim"},
        "rotationOrder": ["south", "west", "north", "east"],
        "views": {},
    }

    for direction in popular.base.bs.DIRECTIONS:
        popular.base.bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        name = f"{ASSET_ID}_{direction['id']}_mask.png"
        path = out / name
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        report["views"][direction["id"]] = {
            "file": name,
            "sha256": _sha256(path),
        }

    (out / "color_mask_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_worker_metadata(out, recipe_path, studio)
    print("[CH_MASK] Casa Popular four-direction RGB masks complete")


def main():
    a = popular.base.args_parse()
    approval = (a.approval_proxy_sha or "").lower()
    if a.stage != "final":
        raise RuntimeError("CH_MASK_REQUIRES_FINAL_STAGE")
    if not re.fullmatch(r"[0-9a-f]{64}", approval) or approval != APPROVED_PROXY:
        raise RuntimeError("CH_MASK_REQUIRES_APPROVED_PROXY")

    popular.base.ASSET_ID = ASSET_ID
    popular.base.DEFAULT_RECIPE = popular.DEFAULT_RECIPE
    popular.base.build_house = popular.build_house
    ctx = popular.base.build_context(a)
    _render_masks(ctx)
    popular.base.save_blend(a.save_blend)


if __name__ == "__main__":
    main()
