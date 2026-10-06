#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import bpy

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CH=ROOT/"tools"/"ch_blender"
for p in (HERE,CH):
    if str(p) not in sys.path: sys.path.insert(0,str(p))

import build_scene as bs
import scene_gate
import build_carousel_city_horizon_05_guarded as base
import carousel_rotation_contract as rotation_contract

CONTRACT="CITY_HORIZON_CAROUSEL_V6"
ASSET_ID="attraction.park_carousel_city_horizon_06"

def args():
    av=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p=argparse.ArgumentParser()
    p.add_argument("--recipe",required=True)
    p.add_argument("--studio-preset",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--stage",choices=("preflight","proxy","final"),default="preflight")
    p.add_argument("--preflight-profile")
    return p.parse_args(av)

def main():
    a=args()
    recipe=json.loads(Path(a.recipe).read_text(encoding="utf-8"))
    if recipe.get("contract")!=CONTRACT:
        raise RuntimeError("Expected CITY_HORIZON_CAROUSEL_V6 recipe")
    if recipe.get("lifecycle",{}).get("status")!="draft":
        raise RuntimeError("V6 animation review must remain draft")
    spec=rotation_contract.validate_recipe(recipe)

    studio=bs.load_json(a.studio_preset)
    out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)

    # Reuse the approved V5 geometry builder; only data-driven V6 subdivision changes.
    base.ASSET_ID=ASSET_ID
    scene,root,ground,authored=base.build(recipe,studio,out)
    rotor=bpy.data.objects.get("CarouselRotor")
    if rotor is None or rotor.parent!=root:
        raise RuntimeError("CarouselRotor missing or detached from AssetRoot")

    profile=scene_gate.load_profile(a.preflight_profile)
    pre=scene_gate.run_preflight(
        scene=scene,authored=authored,footprint=recipe["footprint"],profile=profile,
        asset_id=ASSET_ID,report_path=out/"preflight_report.json")
    scene_gate.require_pass(pre)

    manifest={
      "contract":"CH_CAROUSEL_ANIMATION_REVIEW_V1","assetId":ASSET_ID,
      "productionContract":"CH_CAROUSEL_ROTATION_V1",
      "productionFramesPerDirection":spec["frameCount"],
      "productionTotalBeautyFrames":spec["frameCount"]*4,
      "reviewFrames":spec["reviewFrames"],"reviewFramesPerDirection":len(spec["reviewFrames"]),
      "reviewTotalFrames":len(spec["reviewFrames"])*4,
      "fps":spec["fps"],"angularStepDegrees":spec["angularStepDegrees"],
      "directions":[d["id"] for d in bs.DIRECTIONS],
      "status":"review_only_not_runtime"
    }

    # Canonical worker proxy at SOUTH/frame 1.
    bs.set_direction(root,bs.DIRECTIONS[0])
    rotor.rotation_euler[2]=0.0; bpy.context.view_layer.update()
    rep=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/"proxy_south.png",
        profile=profile,asset_id=ASSET_ID,direction="south")
    (out/"proxy_report.json").write_text(json.dumps(rep,indent=2),encoding="utf-8")

    if a.stage=="proxy":
        for direction in bs.DIRECTIONS:
            bs.set_direction(root,direction)
            did=direction["id"]
            for frame in spec["reviewFrames"]:
                angle=rotation_contract.frame_angle_degrees(recipe,frame)
                rotor.rotation_euler[2]=math.radians(angle)
                bpy.context.view_layer.update()
                path=out/f"review_{did}_f{frame:02d}.png"
                scene_gate.render_proxy(scene=scene,authored=authored,output_path=path,
                    profile=profile,asset_id=ASSET_ID,direction=did)
        (out/"animation_review_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        print(f"[CH_GATE] Carousel V6 animation review ready: {manifest['reviewTotalFrames']} proxy frames")
    elif a.stage=="preflight":
        (out/"animation_review_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        print("[CH_GATE] Carousel V6 animation preflight PASS")
    else:
        raise RuntimeError("CH_FINAL_BLOCKED_DRAFT: full 48-frame production bake requires animation review approval")

if __name__=="__main__":
    main()
