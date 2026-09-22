"""CH_COLOR_MASK_V1 bake overlay for the approved agricultural shop v2.

This module does not change the approved geometry or normal color render. It
reuses build_agricultural_shop_guarded_v2 and adds only the packed color-mask
pass required by CH_COLOR_MASK_V1.

Mask scope is intentionally coarse and gameplay-oriented:
  R = large wall surfaces only
  G = large roof/canopy surfaces only
  B = unused

Small trim, roof seams, ridge details, vent/cupola, signs, woodwork, glass,
produce and other authored details remain RGB black in the mask.
"""
from __future__ import annotations

import json

import bpy

import build_agricultural_shop_guarded as base
import build_agricultural_shop_guarded_v2  # noqa: F401  # installs approved v2 build_shop
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

# Deliberately object-level instead of material-level so shared roof/wall
# materials cannot pull micro details into the mask.
WALL_MASK_OBJECTS = {
    "MainBody",
    "SouthGableWall",
    "NorthGableWall",
}
ROOF_MASK_OBJECTS = {
    "MainGableRoof",
    "FrontCanopy",
}

_original_render_final = base.render_final


def _apply_mask_roles(authored):
    by_name = {obj.name: obj for obj in authored}
    required = WALL_MASK_OBJECTS | ROOF_MASK_OBJECTS
    missing = sorted(required - set(by_name))
    if missing:
        raise RuntimeError(
            "Agricultural shop color mask expected approved large-surface objects: "
            + ", ".join(missing)
        )

    for name in sorted(WALL_MASK_OBJECTS):
        color_mask.tag_object(by_name[name], "wall")
    for name in sorted(ROOF_MASK_OBJECTS):
        color_mask.tag_object(by_name[name], "roof")

    spec = color_mask.normalize_spec({"colorMask": COLOR_MASK_DECLARATION})
    return spec, color_mask.assignment_summary(authored, spec)


def render_final(studio, scene, root, ground, authored, out, reference):
    # Preserve the already approved normal four-direction bake byte-for-byte in
    # authoring logic; this overlay adds only the mask source pass/metadata.
    spec, assignment = _apply_mask_roles(authored)
    _original_render_final(studio, scene, root, ground, authored, out, reference)

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

    metadata["assetConfig"] = "tools/tycoon_photo_studio/build_agricultural_shop_color_mask.py"
    metadata["colorMask"] = color_mask.metadata(spec, assignment)
    metadata.setdefault("sourceSummary", {})["colorMaskScope"] = "large_surfaces_only_wall_roof"
    metadata["sourceSummary"]["colorMaskWallObjects"] = sorted(WALL_MASK_OBJECTS)
    metadata["sourceSummary"]["colorMaskRoofObjects"] = sorted(ROOF_MASK_OBJECTS)
    metadata["sourceSummary"]["colorMaskBlueChannel"] = "unused"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    base.bs.set_direction(root, base.bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    print("[CH_COLOR_MASK_V1] agricultural shop v2 wall/roof mask source bake complete")


base.render_final = render_final


if __name__ == "__main__":
    base.main()
