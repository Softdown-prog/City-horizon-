"""Final four-direction export for residential_suburban_cottage_3x3_01.

Outputs only the canonical color sprite and packed CH_COLOR_MASK_V1 mask for
south/east/west/north. No activity overlays are authored or exported here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (HERE, ROOT / "tools" / "ch_blender"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_residential_suburban_cottage_detail_v2 as detail_v2  # noqa: E402,F401
import build_residential_suburban_cottage_guarded as base  # noqa: E402
import ch_color_mask as mask_lib  # noqa: E402

ASSET_ID = "residential_suburban_cottage_3x3_01"
DEFAULT_RECIPE = "tools/tycoon_photo_studio/assets/residential_suburban_cottage_3x3_01.house.json"
DEFAULT_MASK = "tools/tycoon_photo_studio/assets/residential_suburban_cottage_3x3_01.color_mask.json"


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--mask-config", default=DEFAULT_MASK)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--approval-proxy-sha", required=True)
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--save-blend", default=None)
    return p.parse_args(argv)


def repo_path(value):
    path = (ROOT / value).resolve()
    path.relative_to(ROOT)
    return path


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_mask_spec(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("assetId") != ASSET_ID:
        raise RuntimeError("CH_COTTAGE_MASK_ASSET_ID")
    spec = mask_lib.normalize_spec(raw)
    if spec is None:
        raise RuntimeError("CH_COTTAGE_MASK_DISABLED")
    return raw, spec


def tag_mask_materials(spec):
    role_map = {
        "house_wall": ("CottageWarmCreamSiding",),
        "house_roof": ("CottageCharcoalRoof", "CottageRoofEdge"),
        "house_trim": ("CottageLightTrim",),
    }
    declared = set(spec["channels"].values())
    for role, names in role_map.items():
        if role not in declared:
            continue
        for name in names:
            material = bpy.data.materials.get(name)
            if material is None:
                raise RuntimeError(f"CH_COTTAGE_MASK_MATERIAL_MISSING: {name}")
            mask_lib.tag_material(material, role)


def main():
    a = parse_args()
    approval = a.approval_proxy_sha.lower().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY_SHA")

    # Reuse the guarded/detailed builder and its frozen camera/studio/preflight.
    class Args:
        pass
    ctx_args = Args()
    ctx_args.recipe = a.recipe
    ctx_args.studio_preset = a.studio_preset
    ctx_args.output = a.output
    ctx_args.preflight_profile = a.preflight_profile
    ctx_args.approval_proxy_sha = approval
    ctx_args.save_blend = a.save_blend

    profile = base.scene_gate.load_profile(a.preflight_profile)
    ctx = base.build_context(ctx_args)
    recipe_path, recipe, ref, studio, out, scene, root, ground, authored = ctx
    report = base.scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=ASSET_ID,
        report_path=out / "preflight_report.json",
    )
    base.scene_gate.require_pass(report)

    raw_mask, mask_spec = load_mask_spec(repo_path(a.mask_config))
    tag_mask_materials(mask_spec)
    assignment = mask_lib.assignment_summary(authored, mask_spec)

    directions = []
    for direction in base.bs.DIRECTIONS:
        base.bs.set_direction(root, direction)
        bpy.context.view_layer.update()

        color_name = f"{ASSET_ID}_{direction['id']}.png"
        mask_name = f"{ASSET_ID}_{direction['id']}_mask.png"
        base.bs.render_color_pass(scene, authored, ground, str(out / color_name))
        mask_lib.render_mask_pass(scene, authored, ground, str(out / mask_name), mask_spec)

        directions.append({
            "id": direction["id"],
            "quarterTurns": direction["quarterTurns"],
            "rotationDegrees": direction["rotationDegrees"],
            "color": color_name,
            "mask": mask_name,
            "groundOriginSourcePx": base.bs.ground_origin_source_px(scene),
        })

    metadata = {
        "contract": "CH_RESIDENTIAL_FINAL_EXPORT_V1",
        "assetId": ASSET_ID,
        "sourceContract": "DIRECT_CH_BLENDER_GUARDED_V1",
        "builder": "tools/tycoon_photo_studio/export_residential_suburban_cottage_final.py",
        "detailPass": "residential_cottage_detail_v2",
        "studioPreset": studio["id"],
        "cameraContract": "CH_CAMERA_V1",
        "gridContract": "CH_GRID_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "footprint": recipe["footprint"],
        "directionOrder": [d["id"] for d in base.bs.DIRECTIONS],
        "approvalProxySha256": approval,
        "recipeSha256": sha256(recipe_path),
        "colorMaskConfig": repo_path(a.mask_config).relative_to(ROOT).as_posix(),
        "colorMask": mask_lib.metadata(mask_spec, assignment),
        "overlays": [],
        "overlayPolicy": "none",
        "outputs": directions,
    }
    (out / "final_export_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    (out / "proxy_approval.json").write_text(
        json.dumps({
            "contract": "CH_PROXY_APPROVAL_V1",
            "assetId": ASSET_ID,
            "proxySha256": approval,
            "reviewed": True,
        }, indent=2),
        encoding="utf-8",
    )
    base.save_blend(a.save_blend)
    print("[CH_FINAL] 4 directions exported: color + mask, overlays=none")


if __name__ == "__main__":
    main()
