"""CH Blender guarded procedural terminal station B, 5x3 tiles, four canonical directions."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for folder in (HERE, ROOT / "tools" / "ch_blender"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import build_scene as bs
import scene_gate

def args_parse():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    p.add_argument("--save-blend", default=None)
    return p.parse_args(argv)

def material(name, color, roughness=0.8, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    if shader is None:
        raise RuntimeError("CH_STATION_MATERIAL_INVALID")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    mat.diffuse_color = (*color, 1.0)
    return mat

def box(name, position, dimensions, mat, root, role, ground=False):
    obj = bs.add_box(name, position, dimensions, mat, 0.0)
    obj.parent = root
    scene_gate.tag(obj, role, ground_contact=ground)
    return obj

def make_station(root, recipe):
    walls = material("Warm station terracotta", (0.63, 0.31, 0.19))
    stone = material("Cream limestone trim", (0.89, 0.77, 0.52))
    roof = material("Deep blue slate roof", (0.12, 0.28, 0.40))
    timber = material("Railway aged timber", (0.30, 0.19, 0.11))
    platform = material("Warm concrete paving", (0.69, 0.63, 0.53))
    window = material("Blue green railway glass", (0.065, 0.30, 0.37), 0.25)
    steel = material("Iron framework", (0.21, 0.23, 0.22), 0.45, 0.45)
    clock = material("Clock face", (0.87, 0.84, 0.68))
    gold = material("Golden platform safety marking", (0.92, 0.66, 0.11))
    dark = material("Dark blue signboard", (0.07, 0.18, 0.29))
    red = material("Railway burgundy accent", (0.54, 0.15, 0.12))
    # Entire authored geometry stays inside 5x3 tiles (15x9 world units).
    # x = rail direction, open connection at -7.5, end buffer at +6.9.
    box("Long main platform", (0.0, -0.65, 0.17), (14.1, 1.75, 0.34), platform, root, "station.platform", True)
    box("Platform safety edge", (0.0, -1.51, 0.36), (14.1, 0.14, 0.09), stone, root, "station.platform_edge")
    box("Platform yellow warning strip", (0.0, -1.40, 0.363), (13.7, 0.115, 0.025), gold, root, "station.platform_marking")
    box("Paved station forecourt", (-0.5, 2.85, 0.10), (12.9, 2.0, 0.20), platform, root, "station.forecourt", True)
    # Main building on the far side of platform; rail lane remains uncovered.
    box("Station ticket hall", (-0.9, 2.05, 1.28), (7.2, 2.65, 2.56), walls, root, "station.building", True)
    box("Ticket hall sill", (-0.9, 2.05, 0.32), (7.5, 2.85, 0.22), stone, root, "station.foundation", True)
    box("Roof upper volume", (-0.9, 2.05, 2.83), (7.85, 3.07, 0.60), roof, root, "station.roof")
    box("Roof ridge", (-0.9, 2.05, 3.20), (7.85, 0.30, 0.20), stone, root, "station.roof")
    box("Entrance canopy", (-1.0, 3.65, 1.95), (5.6, 0.90, 0.22), roof, root, "station.canopy")
    box("Entrance canopy golden edge", (-1.0, 4.06, 1.92), (5.55, 0.09, 0.09), gold, root, "station.canopy_trim")
    box("Facade horizontal cream band", (-0.9, 3.39, 2.43), (7.21, 0.12, 0.13), stone, root, "station.trim")
    for x in (-4.18, 2.38):
        box("Corner pilaster", (x, 3.365, 1.39), (0.20, 0.15, 2.15), stone, root, "station.trim")
    box("Railway nameboard", (-0.9, 3.48, 2.53), (3.10, 0.15, 0.40), dark, root, "station.sign")
    box("Nameboard top gilt edge", (-0.9, 3.58, 2.75), (3.12, 0.06, 0.07), gold, root, "station.sign_trim")
    box("Main double doorway", (-0.90, 3.404, 1.13), (1.32, 0.07, 1.93), timber, root, "station.door")
    for ix, x in enumerate((-3.35, 1.60)):
        box(f"Hall window {ix}", (x, 3.411, 1.62), (1.05, 0.075, 1.12), window, root, "station.window")
        box(f"Window lintel {ix}", (x, 3.46, 2.22), (1.28, 0.14, 0.14), stone, root, "station.trim")
        box(f"Window lower ledge {ix}", (x, 3.46, 1.03), (1.28, 0.18, 0.11), stone, root, "station.trim")
        box(f"Window central sash {ix}", (x, 3.51, 1.62), (0.09, 0.075, 1.10), stone, root, "station.window_frame")
    box("Station clock case", (-0.9, 3.52, 2.91), (0.68, 0.13, 0.68), clock, root, "station.clock")
    box("Station clock center", (-0.90, 3.60, 2.91), (0.13, 0.05, 0.13), dark, root, "station.clock_detail")
    box("Station clock hand", (-0.84, 3.62, 2.95), (0.25, 0.04, 0.06), dark, root, "station.clock_detail")
    for x in (-3.65, -2.55, -1.45, -0.35, 0.75, 1.85):
        box("Slate roof tile rib", (x, 2.05, 3.17), (0.065, 2.80, 0.035), stone, root, "station.roof_trim")
    box("Long platform shelter roof", (4.1, 0.30, 2.80), (5.55, 2.40, 0.25), roof, root, "station.platform_shelter")
    box("Shelter roof gold fascia", (4.1, -0.91, 2.78), (5.40, 0.085, 0.10), gold, root, "station.platform_shelter_trim")
    for i, x in enumerate((1.75, 4.1, 6.40)):
        box(f"Shelter post {i}", (x, 0.89, 1.40), (0.17, 0.17, 2.80), steel, root, "station.shelter_post")
        box(f"Shelter beam {i}", (x, 0.10, 2.64), (0.16, 2.3, 0.17), steel, root, "station.structure")
    for i, x in enumerate((2.2, 4.2)):
        box(f"Waiting bench {i}", (x, 0.72, 0.55), (1.12, 0.36, 0.17), timber, root, "station.bench")
        box(f"Waiting bench back {i}", (x, 0.96, 0.77), (1.12, 0.09, 0.48), red, root, "station.bench_detail")
    # Terminal buffer makes the closed end legible without extending across entry.
    box("Terminal buffer beam", (6.82, -2.4, 0.62), (0.20, 1.45, 0.38), timber, root, "station.buffer")
    for y in (-2.94, -1.86):
        box("Terminal buffer iron support", (6.76, y, 0.34), (0.21, 0.14, 0.58), steel, root, "station.buffer_support")
    root["stationEntryPortLocalWorld"] = recipe["entryPortLocalWorld"]
    root["stationStopLocalWorld"] = recipe["terminalStopLocalWorld"]
    root["stationType"] = "terminal"
    root["directionPolicy"] = recipe["directionPolicy"]

def main():
    args = args_parse()
    recipe = bs.load_json(args.recipe)
    if recipe.get("contract") != "CH_RAIL_STATION_SOURCE_V1" or recipe.get("footprint") != "5x3":
        raise RuntimeError("CH_STATION_RECIPE_CONTRACT")
    preset = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    bs.clear_scene()
    scene = bs.configure_scene(preset, tuple(map(int, preset["render"]["sourceResolution"])), str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    root = bpy.data.objects.new("AssetRoot", None)
    bpy.context.scene.collection.objects.link(root)
    root.rotation_mode = "XYZ"
    root["assetId"] = recipe["assetId"]
    root["assetType"] = "rail_terminal_station"
    root["footprint"] = "5x3"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["styleContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["gridContract"] = "CH_GRID_V1"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    make_station(root, recipe)
    receiver = preset["shadowReceiver"]
    groundmat = bs.make_material("ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0)))
    ground = bs.add_box("ShadowReceiverPlane", receiver["location"], receiver["dimensions"], groundmat, 0.0)
    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.12)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    profile = scene_gate.load_profile(args.preflight_profile)
    report = scene_gate.run_preflight(
        scene=scene, authored=authored, footprint={"widthTiles": 5, "depthTiles": 3},
        profile=profile, asset_id=recipe["assetId"], report_path=out / "preflight_report.json")
    scene_gate.require_pass(report)
    if args.stage == "proxy":
        proxy = scene_gate.render_proxy(
            scene=scene, authored=authored, output_path=out / "proxy_south.png",
            profile=profile, asset_id=recipe["assetId"], direction="south")
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
    elif args.stage == "final":
        if not re.fullmatch(r"[a-f0-9]{64}", args.approval_proxy_sha or ""):
            raise RuntimeError("CH_FINAL_REQUIRES_REVIEWED_PROXY")
        ground.hide_render = True
        directions = []
        for direction in bs.DIRECTIONS:
            bs.set_direction(root, direction)
            filename = f"rail_terminal_station_b_{direction['id']}_source.png"
            scene.render.filepath = str(out / filename)
            bpy.ops.render.render(write_still=True)
            directions.append({"id": direction["id"], "file": filename,
                               "rotationDegrees": direction["rotationDegrees"]})
        (out / "station_source_manifest.json").write_text(json.dumps({
            "contract": "CH_RAIL_TERMINAL_STATION_SOURCE_BAKE_V1",
            "assetId": recipe["assetId"], "footprint": "5x3",
            "directionPolicy": recipe["directionPolicy"],
            "entryPortLocalWorld": recipe["entryPortLocalWorld"],
            "terminalStopLocalWorld": recipe["terminalStopLocalWorld"],
            "directions": directions,
        }, indent=2), encoding="utf-8")
    if args.save_blend:
        target = Path(args.save_blend).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
    print(f"[CH_STATION] {args.stage} complete for {recipe['assetId']}")

if __name__ == "__main__":
    main()
