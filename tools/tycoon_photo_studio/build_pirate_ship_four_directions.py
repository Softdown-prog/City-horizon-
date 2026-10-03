#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import bpy

import build_pirate_ship_decorated_suspension as decorated

# Importing the decorated builder patches base.build so the exact approved
# proxy.009 geometry (including the pirate-hat totem) is reused unchanged.
base = decorated.base


def main():
    a = base.argv()
    c = base.load(a.recipe)
    forbidden = c.get("forbiddenTopology", [])
    if c.get("contract") != base.CONTRACT or "end_portals_at_bow_and_stern" not in forbidden:
        raise RuntimeError("corrected clean reference contract required")

    studio = base.bs.load_json(a.studio_preset)
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    base.bs.clear_scene()
    scene = base.bs.configure_scene(
        studio,
        tuple(map(int, studio["render"]["sourceResolution"])),
        str(out),
    )
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    M = {k: base.material(v) for k, v in c["materials"].items()}

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    root = bpy.context.object
    root.name = "AssetRoot"
    root["assetId"] = base.ASSET
    root["cameraContract"] = "CH_CAMERA_V1"
    root["styleContract"] = c["styleContract"]
    root["footprint"] = "7x6"
    root["proceduralContract"] = base.CONTRACT

    # This is the monkey-patched decorated build from proxy.009.
    base.build(root, c, M)

    recv = studio["shadowReceiver"]
    rm = base.bs.make_material(
        "ShadowReceiver",
        recv["materialColor"],
        float(recv.get("roughness", 1)),
    )
    ground = base.bs.add_box(
        "ShadowReceiverPlane",
        recv["location"],
        [30, 21, float(recv["dimensions"][2])],
        rm,
        0,
    )

    authored = [o for o in bpy.context.scene.objects if o.type == "MESH" and o != ground]
    base.bs.calibrate_ortho_scale(scene, authored, safety_margin=.14)
    base.bs.set_direction(root, base.bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    metadata = {
        "contract": base.CONTRACT,
        "assetId": base.ASSET,
        "modelingMethod": "approved_proxy_009_geometry_four_canonical_directions",
        "reference": "user supplied real ride photos",
        "directions": [d["id"] for d in base.bs.DIRECTIONS],
        "cameraContract": "CH_CAMERA_V1",
    }
    (out / "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    profile = base.scene_gate.load_profile(a.preflight_profile)
    pre = base.scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=c["footprint"],
        profile=profile,
        asset_id=base.ASSET,
        report_path=out / "preflight_report.json",
    )
    base.scene_gate.require_pass(pre)

    if a.stage == "proxy":
        reports = {}
        for direction in base.bs.DIRECTIONS:
            base.bs.set_direction(root, direction)
            bpy.context.view_layer.update()
            did = direction["id"]
            reports[did] = base.scene_gate.render_proxy(
                scene=scene,
                authored=authored,
                output_path=out / f"proxy_{did}.png",
                profile=profile,
                asset_id=base.ASSET,
                direction=did,
            )
        (out / "proxy_report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")

    # Return scene to canonical south before saving the .blend.
    base.bs.set_direction(root, base.bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    if a.save_blend:
        q = Path(a.save_blend).resolve()
        q.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(q))


if __name__ == "__main__":
    main()
