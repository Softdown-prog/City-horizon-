#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
import bpy

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CH=ROOT/"tools"/"ch_blender"
for p in (HERE,CH):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

import build_scene as bs
import scene_gate
import build_carousel_city_horizon_05_guarded as base
import carousel_rotation_contract as rotation_contract

CONTRACT="CITY_HORIZON_CAROUSEL_V6"
ASSET_ID="attraction.park_carousel_city_horizon_06"
DIRECTIONS=bs.DIRECTIONS

def args():
    av=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p=argparse.ArgumentParser()
    p.add_argument("--recipe",required=True)
    p.add_argument("--studio-preset",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--stage",choices=("preflight","proxy","final"),default="proxy")
    p.add_argument("--preflight-profile")
    return p.parse_args(av)

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def main():
    a=args()
    recipe=json.loads(Path(a.recipe).read_text(encoding="utf-8"))
    if recipe.get("contract")!=CONTRACT:
        raise RuntimeError("Expected CITY_HORIZON_CAROUSEL_V6 recipe")
    approval=recipe.get("animationApproval",{})
    if not approval.get("beautyProductionApproved",False):
        raise RuntimeError("Beauty production is not explicitly approved")
    if approval.get("runtimePromotionApproved",False):
        raise RuntimeError("This bake must not imply runtime promotion")
    if approval.get("animatedColorMaskApproved",False):
        raise RuntimeError("Animated mask is a separate production step")

    spec=rotation_contract.validate_recipe(recipe)
    if spec["frameCount"]!=48 or not math.isclose(spec["angularStepDegrees"],7.5,abs_tol=1e-8):
        raise RuntimeError("Canonical 48-frame/7.5-degree contract required")

    studio=bs.load_json(a.studio_preset)
    out=Path(a.output).resolve()
    out.mkdir(parents=True,exist_ok=True)

    base.ASSET_ID=ASSET_ID
    scene,root,ground,authored=base.build(recipe,studio,out)
    rotor=bpy.data.objects.get("CarouselRotor")
    if rotor is None or rotor.parent!=root:
        raise RuntimeError("CarouselRotor missing or detached from AssetRoot")

    profile=scene_gate.load_profile(a.preflight_profile)
    pre=scene_gate.run_preflight(
        scene=scene,authored=authored,footprint=recipe["footprint"],
        profile=profile,asset_id=ASSET_ID,
        report_path=out/"preflight_report.json")
    scene_gate.require_pass(pre)

    # Canonical worker proof. This remains a proxy gate only.
    bs.set_direction(root,DIRECTIONS[0])
    rotor.rotation_euler[2]=0.0
    bpy.context.view_layer.update()
    rep=scene_gate.render_proxy(
        scene=scene,authored=authored,output_path=out/"proxy_south.png",
        profile=profile,asset_id=ASSET_ID,direction="south")
    (out/"proxy_report.json").write_text(json.dumps(rep,indent=2),encoding="utf-8")

    # Runtime-size beauty candidate. Match the approved review presentation:
    # transparent RGBA, fixed studio, EEVEE, no shadow receiver plane.
    ground.hide_render=True
    scene.render.engine="BLENDER_EEVEE_NEXT"
    scene.render.resolution_x=1280
    scene.render.resolution_y=1280
    scene.render.resolution_percentage=100
    scene.render.film_transparent=True
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGBA"

    records={}
    expected_total=48*len(DIRECTIONS)
    produced=0

    for direction in DIRECTIONS:
        bs.set_direction(root,direction)
        did=direction["id"]
        frames=[]
        for frame in range(spec["frameStart"],spec["frameEnd"]+1):
            angle=rotation_contract.frame_angle_degrees(recipe,frame)
            rotor.rotation_euler[2]=math.radians(angle)
            bpy.context.view_layer.update()

            path=out/f"beauty_{did}_f{frame:02d}.png"
            scene.render.filepath=str(path)
            bpy.ops.render.render(write_still=True)
            if not path.is_file() or path.stat().st_size==0:
                raise RuntimeError(f"Missing beauty output: {path.name}")
            frames.append({
                "frame":frame,
                "angleDegrees":angle,
                "file":path.name,
                "bytes":path.stat().st_size,
                "sha256":sha256(path)
            })
            produced+=1
        records[did]=frames

    if produced!=expected_total:
        raise RuntimeError(f"Expected {expected_total} beauty frames, produced {produced}")

    # Verify no accidental 360-degree duplicate was exported.
    for did,frames in records.items():
        if frames[-1]["frame"]!=48 or not math.isclose(frames[-1]["angleDegrees"],352.5,abs_tol=1e-8):
            raise RuntimeError(f"{did}: final exported frame is not 352.5 degrees")

    manifest={
      "contract":"CH_CAROUSEL_BEAUTY_PRODUCTION_V1",
      "assetId":ASSET_ID,
      "sourceRecipe":"park_carousel_city_horizon_06.carousel.json",
      "rotationContract":"CH_CAROUSEL_ROTATION_V1",
      "cameraContract":"CH_CAMERA_V1",
      "format":"PNG_RGBA",
      "frameSize":[1280,1280],
      "transparentBackground":True,
      "directionOrder":[d["id"] for d in DIRECTIONS],
      "framesPerDirection":48,
      "totalFrames":expected_total,
      "fps":spec["fps"],
      "rotationPeriodSeconds":48/spec["fps"],
      "angularStepDegrees":spec["angularStepDegrees"],
      "loopClosureFrame":49,
      "loopClosureExported":False,
      "records":records,
      "status":"beauty_candidate_waiting_for_validation",
      "runtimePromotionApproved":False,
      "animatedColorMaskGenerated":False
    }
    (out/"beauty_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(f"[CH_GATE] Carousel V6 beauty production ready: {produced} frames at 1280x1280")

if __name__=="__main__":
    main()
