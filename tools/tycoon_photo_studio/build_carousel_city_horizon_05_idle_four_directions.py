#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import bpy

import build_carousel_city_horizon_05_guarded as base


def main():
    a = base.args()
    recipe = json.loads(Path(a.recipe).read_text(encoding="utf-8"))
    if recipe.get("contract") != base.CONTRACT:
        raise RuntimeError("Expected CITY_HORIZON_CAROUSEL_V5 recipe")
    if recipe.get("lifecycle", {}).get("status") != "draft":
        raise RuntimeError("Carousel V5 must remain draft")
    if recipe.get("lifecycle", {}).get("exemplarStatus") != "not_approved_exemplar":
        raise RuntimeError("Draft carousel must not be treated as an approved exemplar")

    studio = base.bs.load_json(a.studio_preset)
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    scene, root, ground, authored = base.build(recipe, studio, out)

    metadata = {
        "contract": "CH_CAROUSEL_IDLE_4DIR_V1",
        "assetId": base.ASSET_ID,
        "sourceRecipeContract": base.CONTRACT,
        "status": "draft",
        "exemplarStatus": "not_approved_exemplar",
        "cameraContract": "CH_CAMERA_V1",
        "directions": [d["id"] for d in base.bs.DIRECTIONS],
        "motionState": "idle_static",
        "note": "Static four-direction idle review only; no runtime promotion implied."
    }
    (out / "idle_manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    profile = base.scene_gate.load_profile(a.preflight_profile)
    pre = base.scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=base.ASSET_ID,
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
                output_path=out / f"idle_{did}.png",
                profile=profile,
                asset_id=base.ASSET_ID,
                direction=did,
            )
        (out / "idle_report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    elif a.stage == "preflight":
        print("[CH_GATE] Carousel V5 idle 4dir preflight PASS")
    else:
        raise RuntimeError("CH_FINAL_BLOCKED_DRAFT: idle review is proxy-only until explicit approval")

    base.bs.set_direction(root, base.bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    if a.save_blend:
        p = Path(a.save_blend).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(p))


if __name__ == "__main__":
    main()
