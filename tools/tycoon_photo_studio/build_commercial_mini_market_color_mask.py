"""CH_COLOR_MASK_V1 overlay for the approved commercial mini market v2.

This module preserves the approved mini-market geometry and normal color bake.
It reuses build_commercial_mini_market_guarded_v2 and adds only the packed
color-mask source pass required by CH_COLOR_MASK_V1.

Mask scope is deliberately coarse and gameplay-oriented:
  R = large wall surface only
  G = large flat-roof surface only
  B = unused

Storefront glass, doors, green branding bands, awnings, sign/emblem, trim,
produce, planters, lamps, parapets, HVAC equipment and microdetail remain RGB
black in the mask while still contributing alpha coverage.
"""
from __future__ import annotations

import json

import bpy

import build_commercial_mini_market_guarded as base
import build_commercial_mini_market_guarded_v2  # noqa: F401  # installs approved v2 build_market
import ch_color_mask as color_mask


COLOR_MASK_DECLARATION = {
    "contract": "CH_COLOR_MASK_V1",
    "enabled": True,
    "channels": {
        "R": "wall",
        "G": "roof",
    },
    "alpha": "coverage",
}

# Object-level roles keep shared materials and small facade/roof details from
# being recolored accidentally.
WALL_MASK_OBJECTS = {
    "MarketBody",
}
ROOF_MASK_OBJECTS = {
    "FlatRoofSlab",
}

_original_render_final = base.render_final


def _apply_mask_roles(authored):
    by_name = {obj.name: obj for obj in authored}
    required = WALL_MASK_OBJECTS | ROOF_MASK_OBJECTS
    missing = sorted(required - set(by_name))
    if missing:
        raise RuntimeError(
            "Mini market color mask expected approved large-surface objects: "
            + ", ".join(missing)
        )

    for name in sorted(WALL_MASK_OBJECTS):
        color_mask.tag_object(by_name[name], "wall")
    for name in sorted(ROOF_MASK_OBJECTS):
        color_mask.tag_object(by_name[name], "roof")

    spec = color_mask.normalize_spec({"colorMask": COLOR_MASK_DECLARATION})
    return spec, color_mask.assignment_summary(authored, spec)


def render_final(context):
    recipe_path, recipe, reference, studio, out, scene, root, ground, authored = context
    spec, assignment = _apply_mask_roles(authored)

    # Preserve approved normal color/shadow authoring exactly; add only masks.
    _original_render_final(context)

    metadata_path = out / "studio_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    direction_meta = {item["id"]: item for item in metadata["directions"]}

    for direction in base.bs.DIRECTIONS:
        base.bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        mask_name = f"{base.ASSET_ID}_{direction['id']}_mask_source.png"
        color_mask.render_mask_pass(
            scene,
            authored,
            ground,
            str(out / mask_name),
            spec,
        )
        direction_meta[direction["id"]]["maskSource"] = mask_name

    metadata["builder"] = "tools/tycoon_photo_studio/build_commercial_mini_market_color_mask.py"
    metadata["assetConfig"] = recipe_path.relative_to(base.ROOT).as_posix()
    metadata["renderResolution"] = [
        int(scene.render.resolution_x),
        int(scene.render.resolution_y),
    ]
    metadata["colorMask"] = color_mask.metadata(spec, assignment)
    metadata.setdefault("sourceSummary", {})["colorMaskScope"] = "large_surfaces_only_wall_roof"
    metadata["sourceSummary"]["colorMaskWallObjects"] = sorted(WALL_MASK_OBJECTS)
    metadata["sourceSummary"]["colorMaskRoofObjects"] = sorted(ROOF_MASK_OBJECTS)
    metadata["sourceSummary"]["colorMaskBlueChannel"] = "unused"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    base.bs.set_direction(root, base.bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    print("[CH_COLOR_MASK_V1] mini market v2 wall/roof mask source bake complete")


base.render_final = render_final


if __name__ == "__main__":
    base.main()
