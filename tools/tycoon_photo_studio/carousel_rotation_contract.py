"""Validation and Blender sampling helpers for CH_CAROUSEL_ROTATION_V1."""
from __future__ import annotations
import math

REVIEW_FRAMES=(1,5,9,13,17,21,25,29,33,37,41,45)

def validate_recipe(recipe):
    geo=recipe.get("geometry",{})
    animation=recipe.get("animation",{})
    mask=recipe.get("colorMask",{})

    stripe_count=int(geo.get("canopySegments",0))
    primary_count=int(geo.get("canopyPrimaryStripeCount",0))
    secondary_count=int(geo.get("canopySecondaryStripeCount",0))
    if stripe_count!=24:
        raise RuntimeError(f"CH_CAROUSEL_ROTATION_V1 requires 24 canopy stripes, got {stripe_count}")
    if primary_count!=12 or secondary_count!=12 or primary_count+secondary_count!=stripe_count:
        raise RuntimeError("CH_CAROUSEL_ROTATION_V1 requires 12 primary + 12 secondary canopy stripes")

    if animation.get("contract")!="CH_CAROUSEL_ROTATION_V1":
        raise RuntimeError("Carousel animation must declare CH_CAROUSEL_ROTATION_V1")
    frame_start=int(animation.get("frameStart",1))
    frame_end=int(animation.get("frameEnd",0))
    frame_count=int(animation.get("frameCount",0))
    closure_frame=int(animation.get("loopClosureFrame",0))
    angular_step=float(animation.get("angularStepDegrees",0.0))
    full_rotation=float(animation.get("fullRotationDegrees",360.0))
    if frame_count!=48:
        raise RuntimeError(f"CH_CAROUSEL_ROTATION_V1 requires 48 production frames, got {frame_count}")
    if frame_end-frame_start+1!=frame_count:
        raise RuntimeError("Carousel frameStart/frameEnd do not describe exactly 48 production frames")
    if closure_frame!=frame_start+frame_count:
        raise RuntimeError("Carousel loopClosureFrame must be the non-exported frame immediately after frame 48")
    expected_step=full_rotation/frame_count
    if not math.isclose(expected_step,7.5,abs_tol=1e-8) or not math.isclose(angular_step,expected_step,abs_tol=1e-8):
        raise RuntimeError(f"Carousel angularStepDegrees must be 7.5, got {angular_step}")
    if bool(animation.get("exportLoopClosureFrame",True)):
        raise RuntimeError("The 360-degree loop closure frame must never be exported")

    if mask.get("contract")!="CH_COLOR_MASK_V1" or not bool(mask.get("enabled",False)):
        raise RuntimeError("Carousel must declare its CH_COLOR_MASK_V1 canopy stripe mask")
    if mask.get("scope")!="canopy_stripe_families_only":
        raise RuntimeError("Carousel color mask may target canopy stripe families only")
    channels=mask.get("channels",{})
    if channels.get("R")!="canopy_primary_stripes":
        raise RuntimeError("Carousel primary stripes must use the R mask channel")
    if channels.get("G")!="canopy_secondary_stripes":
        raise RuntimeError("Carousel secondary stripes must use the G mask channel")
    if channels.get("B")!="unused":
        raise RuntimeError("Carousel B mask channel must remain unused")

    return {
      "frameStart":frame_start,"frameEnd":frame_end,"frameCount":frame_count,
      "loopClosureFrame":closure_frame,"angularStepDegrees":expected_step,
      "fps":int(animation.get("fps",8)),"reviewFrames":list(REVIEW_FRAMES)
    }

def frame_angle_degrees(recipe,frame):
    spec=validate_recipe(recipe)
    if frame<spec["frameStart"] or frame>spec["frameEnd"]:
        raise ValueError(f"Frame {frame} is outside the exported carousel range")
    return (frame-spec["frameStart"])*spec["angularStepDegrees"]

def apply_rotor_sampling(rotor,recipe):
    spec=validate_recipe(recipe)
    rotor.animation_data_clear()
    rotor.rotation_mode="XYZ"
    rotor.rotation_euler[2]=0.0
    rotor.keyframe_insert(data_path="rotation_euler",index=2,frame=spec["frameStart"])
    rotor.rotation_euler[2]=math.tau
    rotor.keyframe_insert(data_path="rotation_euler",index=2,frame=spec["loopClosureFrame"])
    if rotor.animation_data and rotor.animation_data.action:
        for curve in rotor.animation_data.action.fcurves:
            for key in curve.keyframe_points:
                key.interpolation="LINEAR"
    rotor["rotationContract"]="CH_CAROUSEL_ROTATION_V1"
    rotor["exportedFrameCount"]=spec["frameCount"]
    rotor["angularStepDegrees"]=spec["angularStepDegrees"]
    rotor["loopClosureFrame"]=spec["loopClosureFrame"]
    rotor["loopClosureExported"]=False
    return spec
