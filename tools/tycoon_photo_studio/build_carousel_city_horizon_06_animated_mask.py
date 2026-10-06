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
VALID_DIRECTIONS={d["id"]: d for d in bs.DIRECTIONS}

def args():
    av=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p=argparse.ArgumentParser()
    p.add_argument("--recipe",required=True)
    p.add_argument("--studio-preset",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--direction",required=True,choices=tuple(VALID_DIRECTIONS.keys()))
    p.add_argument("--stage",choices=("preflight","proxy","final"),default="proxy")
    p.add_argument("--preflight-profile")
    return p.parse_args(av)

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def mask_material(name,rgba):
    m=bpy.data.materials.new(name)
    m.use_nodes=True
    nodes=m.node_tree.nodes
    links=m.node_tree.links
    nodes.clear()
    out=nodes.new("ShaderNodeOutputMaterial")
    emit=nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value=rgba
    emit.inputs["Strength"].default_value=1.0
    links.new(emit.outputs["Emission"],out.inputs["Surface"])
    return m

def main():
    a=args()
    recipe=json.loads(Path(a.recipe).read_text(encoding="utf-8"))
    if recipe.get("contract")!=CONTRACT:
        raise RuntimeError("Expected CITY_HORIZON_CAROUSEL_V6 recipe")
    approval=recipe.get("animationApproval",{})
    if not approval.get("beautyProductionApproved",False):
        raise RuntimeError("Final beauty must be approved before animated mask")
    if not approval.get("animatedColorMaskApproved",False):
        raise RuntimeError("Animated color mask production is not approved")
    if approval.get("runtimePromotionApproved",False):
        raise RuntimeError("Mask bake must not imply runtime promotion")

    spec=rotation_contract.validate_recipe(recipe)
    if spec["frameCount"]!=48:
        raise RuntimeError("Animated mask requires the canonical 48-frame production contract")

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

    primary=mask_material("CarouselMaskPrimary",(1.0,0.0,0.0,1.0))
    secondary=mask_material("CarouselMaskSecondary",(0.0,1.0,0.0,1.0))
    roof=[]
    for obj in bpy.context.scene.objects:
        if obj.type!="MESH":
            continue
        if obj.name.startswith("Roof_"):
            idx=int(obj.name.split("_")[-1])
            roof.append(obj)
            obj.hide_render=False
            obj.data.materials.clear()
            obj.data.materials.append(primary if idx%2==0 else secondary)
        else:
            obj.hide_render=True

    if len(roof)!=24:
        raise RuntimeError(f"Expected 24 roof wedges, got {len(roof)}")

    original_view={
        "look":scene.view_settings.look,
        "view_transform":scene.view_settings.view_transform,
        "exposure":scene.view_settings.exposure,
        "gamma":scene.view_settings.gamma,
    }

    def restore_studio_view():
        scene.view_settings.view_transform=original_view["view_transform"]
        scene.view_settings.look=original_view["look"]
        scene.view_settings.exposure=original_view["exposure"]
        scene.view_settings.gamma=original_view["gamma"]

    def set_mask_view():
        scene.view_settings.look="None"
        scene.view_settings.view_transform="Standard"
        scene.view_settings.exposure=0
        scene.view_settings.gamma=1

    direction=VALID_DIRECTIONS[a.direction]
    restore_studio_view()
    bs.set_direction(root,direction)
    rotor.rotation_euler[2]=0.0
    bpy.context.view_layer.update()

    # Worker-owned canonical proxy proof.
    set_mask_view()
    proxy_report=scene_gate.render_proxy(
        scene=scene,authored=authored,output_path=out/"proxy_south.png",
        profile=profile,asset_id=ASSET_ID,direction=a.direction)
    restore_studio_view()
    (out/"proxy_report.json").write_text(json.dumps(proxy_report,indent=2),encoding="utf-8")

    scene.render.engine="BLENDER_EEVEE_NEXT"
    scene.render.resolution_x=1280
    scene.render.resolution_y=1280
    scene.render.resolution_percentage=100
    scene.render.film_transparent=True
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGBA"
    set_mask_view()

    frames=[]
    for frame in range(spec["frameStart"],spec["frameEnd"]+1):
        angle=rotation_contract.frame_angle_degrees(recipe,frame)
        rotor.rotation_euler[2]=math.radians(angle)
        bpy.context.view_layer.update()
        path=out/f"mask_{a.direction}_f{frame:02d}.png"
        scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file() or path.stat().st_size==0:
            raise RuntimeError(f"Missing mask frame: {path.name}")
        frames.append({
            "frame":frame,
            "angleDegrees":angle,
            "file":path.name,
            "bytes":path.stat().st_size,
            "sha256":sha256(path)
        })

    restore_studio_view()
    if len(frames)!=48 or not math.isclose(frames[-1]["angleDegrees"],352.5,abs_tol=1e-8):
        raise RuntimeError("Animated mask frame sequence is incomplete or exports the wrong closure")

    manifest={
      "contract":"CH_CAROUSEL_ANIMATED_COLOR_MASK_V1",
      "assetId":"park_carousel_01",
      "sourceAuthoringAssetId":ASSET_ID,
      "rotationContract":"CH_CAROUSEL_ROTATION_V1",
      "colorMaskContract":"CH_COLOR_MASK_V1",
      "direction":a.direction,
      "frameSize":[1280,1280],
      "frameCount":48,
      "fps":spec["fps"],
      "rotationPeriodSeconds":48/spec["fps"],
      "angularStepDegrees":spec["angularStepDegrees"],
      "channels":{
        "R":"canopy_primary_stripes",
        "G":"canopy_secondary_stripes",
        "B":"unused"
      },
      "alpha":"coverage",
      "synchronization":"same direction frame canvas pivot and rotor angle as approved beauty",
      "frames":frames,
      "status":"animated_mask_candidate_waiting_for_runtime_promotion",
      "runtimePromotionApproved":False
    }
    (out/f"mask_{a.direction}_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(f"[CH_GATE] Carousel animated mask {a.direction}: 48/48 frames ready")

if __name__=="__main__":
    main()
