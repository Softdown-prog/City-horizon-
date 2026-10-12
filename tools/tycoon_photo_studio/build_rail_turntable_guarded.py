#!/usr/bin/env python3
"""City Horizon guarded CH Blender authoring: 7.2m railway turntable.

The *base* remains stationary and may be promoted as four camera-canonical
sprites after review. The *bridge* rotates in the actual game at the locomotive
pivot; render it separately to prevent baking a motion ghost into the base.

This script intentionally produces only proxies until a verified proxy hash
and source fingerprint are explicitly approved through CH Blender.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
STUDIO_ROOT = ROOT / "tools" / "tycoon_photo_studio"
CH_BLENDER_ROOT = ROOT / "tools" / "ch_blender"
for directory in (STUDIO_ROOT, CH_BLENDER_ROOT):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402

CONTRACT = "CH_RAIL_TURNTABLE_ASSET_V1"
ASSET_ID = "rail_turntable_7m2_01"
DIRECTIONS = ("south", "east", "west", "north")
DIAMETER = 7.2
BRIDGE_LENGTH = 6.7
RAIL_GAUGE = 0.74


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile")
    parser.add_argument("--approval-proxy-sha")
    parser.add_argument("--save-blend")
    return parser.parse_args(argv)


def verified_recipe(path: str) -> dict:
    recipe = bs.load_json(path)
    physics = recipe.get("physical", {})
    if (recipe.get("contract") != CONTRACT or recipe.get("assetId") != ASSET_ID or
        recipe.get("cameraContract") != "CH_CAMERA_V1" or
        recipe.get("footprint") != {"widthTiles": 3, "depthTiles": 3} or
        float(physics.get("diameterMetres", 0)) != DIAMETER or
        float(physics.get("bridgeLengthMetres", 0)) != BRIDGE_LENGTH or
        float(physics.get("gaugeMetres", 0)) != RAIL_GAUGE or
        physics.get("turntablePivotMetres") != [0.0, 0.0, 0.0]):
        raise RuntimeError("CH_RAIL_TURNTABLE_CONTRACT_MISMATCH")
    return recipe


def material(name: str, color, roughness=0.8, metallic=0.0):
    return bs.make_material(name, tuple(color), roughness, metallic)


def make_empty(name: str):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    return obj


def cylinder(name, radius, depth, z, mat, root, role, count=72):
    bpy.ops.mesh.primitive_cylinder_add(vertices=count, radius=radius, depth=depth, location=(0, 0, z))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.parent = root
    scene_gate.tag(obj, role)
    return obj


def torus(name, major, minor, z, mat, root, role):
    bpy.ops.mesh.primitive_torus_add(
        major_segments=72, minor_segments=12,
        location=(0, 0, z), major_radius=major, minor_radius=minor)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.parent = root
    scene_gate.tag(obj, role)
    return obj


def box(name, position, dimensions, mat, root, role, *, rotation=0.0):
    obj = bs.add_box(name, position, dimensions, mat, 0.0)
    obj.parent = root
    obj.rotation_euler[2] = rotation
    scene_gate.tag(obj, role)
    return obj


def build_model(root, recipe):
    palette = recipe["palette"]
    mats = {
        "concrete": material("TurntableGraniteConcrete", palette["concrete"], 0.88),
        "pit": material("TurntableDeepPit", palette["pit"], 0.96),
        "pitInset": material("TurntableInsetMetal", palette["pitInset"], 0.76, 0.23),
        "rim": material("TurntableStoneOuterRim", palette["rim"], 0.84),
        "rimHighlight": material("TurntableStoneCoping", palette["rimHighlight"], 0.8),
        "steel": material("TurntableStructuralSteel", palette["steel"], 0.58, 0.28),
        "rail": material("TurntableRailHead", palette["rail"], 0.42, 0.48),
        "wood": material("TurntableTimberBridge", palette["wood"], 0.84),
        "woodLight": material("TurntableTimberHighlight", palette["woodLight"], 0.9),
        "hazard": material("TurntableOchreWarning", palette["hazard"], 0.76),
    }
    base = []
    bridge = []

    # Keep all pit geometry below the rail's world-ground z=0. External edges
    # terminate at the 7.2m diameter. The deck itself is centered on z~0.1.
    base.append(cylinder("ConcretePitFoundation", 3.56, .16, -.19, mats["concrete"], root, "rail.turntable.foundation"))
    base.append(cylinder("PitRecess", 3.25, .045, -.085, mats["pit"], root, "rail.turntable.pit"))
    base.append(cylinder("InnerSteelBasin", 3.04, .030, -.058, mats["pitInset"], root, "rail.turntable.pit"))
    base.append(torus("GranitePitLedge", 3.43, .115, -.047, mats["rim"], root, "rail.turntable.rim"))
    base.append(torus("SafetyRimInner", 3.18, .045, -.014, mats["rimHighlight"], root, "rail.turntable.rim"))
    # Fourteen subtle radial mounting plates and twelve rivets: legible in
    # small 256px previews without glossy photorealism.
    for index in range(16):
        a = 2.0 * math.pi * index / 16.0
        x, y = 3.40 * math.cos(a), 3.40 * math.sin(a)
        tone = mats["hazard"] if index % 4 == 0 else mats["steel"]
        base.append(box(
            f"RimAnchor_{index:02d}", (x,y,-.008), (.26,.11,.04),
            tone, root, "rail.turntable.rim_detail", rotation=a))
    for index in range(12):
        a = 2.0 * math.pi * index / 12.0
        x, y = 2.93*math.cos(a), 2.93*math.sin(a)
        part = cylinder(
            f"PitBearing_{index:02d}", .07, .055, -.018,
            mats["steel"], root, "rail.turntable.pit_bearing",count=8)
        part.location.x=x
        part.location.y=y

    # Moving bridge is exported as separate transparent RGBA layer. It must
    # NOT be rendered into the base layer: otherwise game rotation ghosts.
    bridge.append(box("BridgeMainFrame",(0,0,.058),(BRIDGE_LENGTH,1.40,.11),
                      mats["steel"],root,"rail.turntable.bridge"))
    for side in (-1,1):
        y=side*.67
        bridge.append(box(f"BridgeSideGirder_{side:+d}",(0,y,.12),
                          (6.65,.13,.19),mats["steel"],root,"rail.turntable.bridge"))
        bridge.append(box(f"BridgeRail_{side:+d}",(0,side*RAIL_GAUGE*.5,.195),
                          (6.62,.07,.075),mats["rail"],root,"rail.turntable.rail"))
    for index in range(9):
        x=-2.8+index*.7
        bridge.append(box(f"BridgeSleepers_{index:02d}",(x,0,.155),
                          (.17,1.14,.075),
                          mats["woodLight"] if index % 3 == 0 else mats["wood"],
                          root,"rail.turntable.sleeper"))
    bridge.append(cylinder("BridgeCenterBearing",.32,.09,.10,mats["steel"],root,
                           "rail.turntable.pivot",count=24))
    bridge.append(cylinder("BridgeTopCap",.135,.025,.257,mats["rimHighlight"],root,
                           "rail.turntable.pivot",count=16))
    # An unobtrusive motor housing at the bridge's edge, grounded to the
    # MOVING bridge, not the pit.
    bridge.append(box("BridgeDriveHousing",(2.75,.52,.215),
                      (.49,.24,.22),mats["steel"],root,"rail.turntable.bridge"))
    return base, bridge


def output_manifest(out, scene, *, stage, records, recipe):
    payload = {
        "contract": "CH_RAIL_TURNTABLE_LAYERED_BAKE_V1",
        "assetId": ASSET_ID,
        "qualityStage": stage,
        "cameraContract": "CH_CAMERA_V1",
        "cameraYawDegrees": 45,
        "cameraElevationDegrees": 30,
        "footprintTiles": [3,3],
        "diameterMetres": DIAMETER,
        "bridgeLengthMetres": BRIDGE_LENGTH,
        "gaugeMetres": RAIL_GAUGE,
        "pivotMetres": [0,0,0],
        "orthographicScale": scene.camera.data.ortho_scale,
        "resolution": [scene.render.resolution_x,scene.render.resolution_y],
        "directions": list(DIRECTIONS),
        "layers": records,
        "approvedForRuntime": False,
        "requiresReview": True,
        "sourceRecipe": str(recipe),
        "notes": "Base must be stationary. Bridge is an independent rotating visual layer. Proxy is not promotion.",
    }
    (out/"rail_turntable_layer_manifest.json").write_text(
        json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def main():
    args = parse_args()
    recipe = verified_recipe(args.recipe)
    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=True)
    profile = scene_gate.load_profile(args.preflight_profile)

    bs.clear_scene()
    scene = bs.configure_scene(
        studio, tuple(map(int,studio["render"]["sourceResolution"])), str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    root = make_empty("AssetRoot")
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["gridContract"] = "CH_GRID_V1"
    root["styleContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["runtimeRepresentation"] = "2D_RGBA_base_plus_rotating_bridge"
    root["physicalDiameterMetres"] = DIAMETER
    root["turntablePivot"] = [0.0,0.0,0.0]

    base, bridge = build_model(root,recipe)
    receiver=studio["shadowReceiver"]
    ground=bs.add_box("ShadowReceiverPlane",receiver["location"],
                      receiver["dimensions"],
                      material("ShadowReceiver",receiver["materialColor"]),0.0)
    authored=base+bridge
    # Every direction rotates only the asset root, not the studio.
    bs.calibrate_ortho_scale(scene,authored,safety_margin=.12)
    bs.set_direction(root,bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    report=scene_gate.run_preflight(
        scene=scene,authored=authored,footprint=recipe["footprint"],
        profile=profile,asset_id=ASSET_ID,
        report_path=out/"preflight_report.json")
    scene_gate.require_pass(report)
    if args.stage=="preflight":
        if args.save_blend:
            bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.save_blend).resolve()))
        print("CH_RAIL_TURNTABLE_PREFLIGHT_PASS")
        return

    if args.stage=="final" and not re.fullmatch(r"[0-9a-f]{64}",(args.approval_proxy_sha or "")):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY")

    records={}
    for direction in bs.DIRECTIONS:
        view = direction["id"]
        bs.set_direction(root,direction)
        bpy.context.view_layer.update()
        records[view]={}
        layers=("assembly","base") if args.stage=="proxy" else ("base","bridge")
        for layer in layers:
            for part in base:
                part.hide_render = layer == "bridge"
            for part in bridge:
                part.hide_render = layer == "base"
            outfile = out / f"rail_turntable_{layer}_{view}.png"
            if args.stage=="proxy":
                result=scene_gate.render_proxy(
                    scene=scene,authored=authored,output_path=outfile,
                    profile=profile,asset_id=ASSET_ID,direction=view)
                records[view][layer]=result
            else:
                ground.hide_render = True
                scene.render.filepath=str(outfile)
                bpy.ops.render.render(write_still=True)
                records[view][layer]={
                    "path":outfile.name,
                    "sha256":hashlib.sha256(outfile.read_bytes()).hexdigest(),
                    "resolution":[scene.render.resolution_x,scene.render.resolution_y]}
    for part in base+bridge:
        part.hide_render=False
    output_manifest(out,scene,stage=args.stage,records=records,recipe=args.recipe)
    if args.save_blend:
        dest=Path(args.save_blend).resolve()
        dest.parent.mkdir(parents=True,exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(dest))
    print("CH_RAIL_TURNTABLE_"+args.stage.upper()+"_PASS")


if __name__ == "__main__":
    main()
