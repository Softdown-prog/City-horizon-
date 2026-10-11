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

def roof_slope(name, corners, thickness, mat, root):
    """Thin real sloped roof surface, not a flat slab painted as tiles."""
    import math
    a, b, c, d = corners
    vertices = [a, b, c, d] + [(p[0], p[1], p[2] - thickness) for p in corners]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5),
             (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = root
    obj.data.materials.append(mat)
    scene_gate.tag(obj, "station.roof")
    return obj

def make_station(root, recipe):
    walls = material("Brick wall brown", (0.37, 0.205, 0.125))
    stone = material("Warm limestone trim", (0.73, 0.65, 0.52))
    roof = material("Dark weathered brown clay roof", (0.255, 0.155, 0.105))
    timber = material("Railway aged timber", (0.30, 0.19, 0.11))
    platform = material("Light gray concrete paving", (0.56, 0.56, 0.53))
    window = material("Blue green railway glass", (0.065, 0.30, 0.37), 0.25)
    steel = material("Iron framework", (0.21, 0.23, 0.22), 0.45, 0.45)
    clock = material("Clock face", (0.87, 0.84, 0.68))
    gold = material("Muted ochre platform safety marking", (0.73, 0.60, 0.24))
    dark = material("Black brown station signboard", (0.12, 0.085, 0.065))
    red = material("Railway burgundy accent", (0.54, 0.15, 0.12))
    bricks = [
        material("Brick ochre brown", (0.46, 0.27, 0.15)),
        material("Brick rust brown", (0.40, 0.21, 0.125)),
        material("Brick deep brown", (0.30, 0.16, 0.095)),
    ]
    mortar = material("Brick mortar", (0.55, 0.47, 0.38))
    concrete_joint = material("Concrete sidewalk seams", (0.39, 0.40, 0.39))
    roof_ridge = material("Clay roof cap tiles", (0.35, 0.205, 0.13))
    # Entire authored geometry stays inside 5x3 tiles (15x9 world units).
    # x = rail direction, open connection at -7.5, end buffer at +6.9.
    box("Long main platform", (0.0, -0.65, 0.17), (14.1, 1.75, 0.34), platform, root, "station.platform", True)
    box("Platform safety edge", (0.0, -1.51, 0.36), (14.1, 0.14, 0.09), stone, root, "station.platform_edge")
    box("Platform yellow warning strip", (0.0, -1.40, 0.363), (13.7, 0.115, 0.025), gold, root, "station.platform_marking")
    box("Paved station forecourt", (-0.5, 2.85, 0.10), (12.9, 2.0, 0.20), platform, root, "station.forecourt", True)
    # Concrete sidewalk slab joints: broad enough to read at actual game size.
    for i in range(1, 6):
        x = -6.95 + i * 2.05
        box(f"Concrete forecourt expansion joint {i}", (x, 2.83, 0.204),
            (0.026, 1.95, 0.008), concrete_joint, root, "station.sidewalk_joint")
    for i in range(1, 7):
        x = -6.95 + i * 2.12
        box(f"Platform expansion joint {i}", (x, -0.62, 0.343),
            (0.025, 1.65, 0.008), concrete_joint, root, "station.platform_joint")
    # Main building on the far side of platform; rail lane remains uncovered.
    box("Station ticket hall", (-0.9, 2.05, 1.28), (7.2, 2.65, 2.56), walls, root, "station.building", True)
    box("Ticket hall sill", (-0.9, 2.05, 0.32), (7.5, 2.85, 0.22), stone, root, "station.foundation", True)
    # True two-sided gable roof, visible pitch and overhanging eaves.
    roof_slope("Clay roof toward platform",
               [(-4.88, 0.30, 2.60), (3.08, 0.30, 2.60),
                (3.08, 2.04, 3.49), (-4.88, 2.04, 3.49)], 0.12, roof, root)
    roof_slope("Clay roof toward street",
               [(-4.88, 2.04, 3.49), (3.08, 2.04, 3.49),
                (3.08, 3.78, 2.60), (-4.88, 3.78, 2.60)], 0.12, roof, root)
    box("Gable roof ridge", (-0.9, 2.04, 3.51), (8.04, 0.20, 0.15),
        roof_ridge, root, "station.roof_ridge")
    for row in range(1, 5):
        t = row / 5.0
        for sign in (-1, 1):
            y = 2.04 + sign * (1.74 * t)
            z = 3.49 - 0.89 * t + 0.025
            box(f"Clay roof horizontal tile seam {row} {sign}", (-0.9, y, z),
                (7.88, 0.045, 0.04), roof_ridge, root, "station.roof_tiles")
    # Real brick courses, with staggered joints and slight material variations.
    # Each raised brick is shallow: reads as masonry without noisy microtexture.
    for row in range(12):
        z = 0.48 + 0.162 * row
        offset = 0.24 if row % 2 else 0.0
        for i in range(14):
            x = -4.45 + 0.48 * i + offset
            if x > 2.56:
                continue
            box(f"Facade brick {row:02d}-{i:02d}", (x, 3.387, z),
                (0.437, 0.026, 0.128), bricks[(i + 2 * row) % 3], root, "station.brick")
        for i in range(6):
            y = 0.85 + i * 0.42 + (0.20 if row % 2 else 0)
            if y > 3.2:
                continue
            box(f"End wall brick {row:02d}-{i:02d}", (2.71, y, z),
                (0.026, 0.38, 0.128), bricks[(2 * i + row) % 3], root, "station.brick")
    # V7: readable staggered brick courses on the RAIL-facing wall, not only
    # the rear facade. Keep a clear reveal around the doorway and windows.
    # At 256px proxy resolution individual mortar lines vanish, so use
    # shallow relief and deliberate color rhythm rather than tiny seams.
    for course in range(11):
        z = 0.47 + course * 0.174
        stagger = 0.27 if course % 2 else 0.0
        for index in range(13):
            x = -4.30 + index * 0.53 + stagger
            if x > 2.43:
                continue
            # Avoid the real door and glass geometry, including their surrounds.
            if (abs(x + 1.90) < 0.82 and z < 2.29) or any(
                abs(x - window_x) < 0.70 and 0.75 < z < 2.24
                for window_x in (-3.45, 0.65, 2.02)
            ):
                continue
            box(f"Rail facade brick course {course:02d} {index:02d}",
                (x, 0.699, z), (0.49, 0.045, 0.136),
                bricks[(course + 2 * index) % len(bricks)], root, "station.brick")
        # Railway-facing facade: visible from the canonical SOUTH game camera.
    # The previous facade details were mostly on the far street side.
    for i, x in enumerate((-3.45, -1.92, 0.65, 2.02)):
        if x == -1.92:
            continue
        box(f"Rail-facing arched window glass {i}", (x, 0.708, 1.44),
            (0.94, 0.055, 1.16), window, root, "station.window")
        box(f"Rail-facing window left jamb {i}", (x - 0.51, 0.747, 1.44),
            (0.11, 0.14, 1.32), stone, root, "station.window_frame")
        box(f"Rail-facing window right jamb {i}", (x + 0.51, 0.747, 1.44),
            (0.11, 0.14, 1.32), stone, root, "station.window_frame")
        box(f"Rail-facing window header {i}", (x, 0.747, 2.10),
            (1.14, 0.16, 0.15), stone, root, "station.window_frame")
        box(f"Rail-facing window sill {i}", (x, 0.76, 0.84),
            (1.20, 0.20, 0.12), stone, root, "station.window_frame")
        box(f"Rail-facing window mullion {i}", (x, 0.772, 1.44),
            (0.075, 0.07, 1.13), timber, root, "station.window_frame")
    # Platform access and prominent sheltered doorway, facing the platform.
    box("Platform entrance door", (-1.90, 0.716, 1.13),
        (1.15, 0.09, 1.93), timber, root, "station.door")
    box("Platform doorway left jamb", (-2.55, 0.77, 1.13),
        (0.13, 0.17, 2.08), stone, root, "station.door_frame")
    box("Platform doorway right jamb", (-1.25, 0.77, 1.13),
        (0.13, 0.17, 2.08), stone, root, "station.door_frame")
    box("Platform doorway lintel", (-1.90, 0.78, 2.20),
        (1.43, 0.18, 0.16), stone, root, "station.door_frame")
    box("Platform entrance step", (-1.90, 0.30, 0.18),
        (1.45, 0.38, 0.13), platform, root, "station.entrance_step")
    # Dark enamel platform-facing station sign, readable at gameplay scale.
    box("Platform-facing STATION B nameboard", (0.0, 0.705, 2.37),
        (2.90, 0.12, 0.39), dark, root, "station.sign")
    box("Platform-facing station sign border", (0.0, 0.785, 2.58),
        (2.94, 0.07, 0.06), stone, root, "station.sign_trim")
    # Large vertical corners and brick ledges outline the actual architecture.
    for x in (-4.40, 2.60):
        box("Rail-facing stone corner", (x, 0.70, 1.40),
            (0.18, 0.17, 2.20), stone, root, "station.trim")
    box("Rail-facing stone stringcourse", (-0.9, 0.70, 2.37),
        (7.22, 0.10, 0.10), stone, root, "station.trim")
    # Strong architectural rhythm on the railway side: prominent brick piers
    # and a projecting ticket-door canopy distinguish this from a warehouse.
    for i, x in enumerate((-4.31, -2.73, -0.98, 1.30, 2.53)):
        box(f"Rail facade masonry pier {i}", (x, 0.672, 1.38),
            (0.18, 0.24, 2.28), bricks[i % len(bricks)], root, "station.brick_pier")
        box(f"Rail facade pier limestone cap {i}", (x, 0.62, 2.49),
            (0.31, 0.31, 0.12), stone, root, "station.pier_cap")
    box("Platform ticket doorway overhead canopy", (-1.92, 0.05, 2.29),
        (1.79, 0.94, 0.14), roof, root, "station.canopy")
    box("Ticket entrance canopy fascia", (-1.92, -0.37, 2.26),
        (1.81, 0.10, 0.13), roof_ridge, root, "station.canopy_trim")
    for x in (-2.69, -1.15):
        box("Door canopy cast iron brackets", (x, 0.25, 1.96),
            (0.10, 0.10, 0.53), steel, root, "station.canopy_support")
    for i, x in enumerate((-3.63, 2.03)):
        box(f"Platform wall lantern mount {i}", (x, 0.54, 2.42),
            (0.14, 0.24, 0.28), steel, root, "station.lantern")
        box(f"Platform wall lantern glass {i}", (x, 0.37, 2.35),
            (0.19, 0.20, 0.29), clock, root, "station.lantern_glass")
        box(f"Platform wall lantern crown {i}", (x, 0.37, 2.53),
            (0.24, 0.25, 0.09), dark, root, "station.lantern")
    # Inset brickwork relief around doors and windows.
    for z in (0.43, 2.26):
        box(f"Rail facade continuous masonry band {z}", (-0.9, 0.691, z),
            (7.12, 0.065, 0.095), mortar, root, "station.mortar_band")
    # Platform furniture remains on concrete rather than in the train corridor.
    box("Platform information panel", (5.55, 0.65, 1.25),
        (0.10, 0.72, 1.20), dark, root, "station.information_board")
    box("Platform information panel footer", (5.55, 0.65, 0.60),
        (0.16, 0.81, 0.10), stone, root, "station.information_board")
    # Gable-side end windows and brick trim, visible in other rotations.
    box("Gable end central glass", (2.735, 1.9, 1.48),
        (0.07, 0.98, 1.16), window, root, "station.window")
    box("Gable end window lintel", (2.785, 1.9, 2.13),
        (0.16, 1.19, 0.14), stone, root, "station.window_frame")
    box("Gable end window sill", (2.785, 1.9, 0.84),
        (0.17, 1.19, 0.13), stone, root, "station.window_frame")
    # Solid roof eaves and decorative bargeboard; preserve the pitched roof.
    for y in (0.31, 3.76):
        box("Roof continuous brown gutter", (-0.9, y, 2.55),
            (7.94, 0.13, 0.12), roof_ridge, root, "station.roof_trim")
    box("Station exterior chimney", (1.80, 2.25, 3.59),
        (0.45, 0.48, 0.78), walls, root, "station.chimney")
    box("Station chimney cap", (1.80, 2.25, 4.01),
        (0.59, 0.59, 0.12), stone, root, "station.chimney")
    box("Entrance canopy", (-1.0, 3.65, 1.95), (5.6, 0.90, 0.16), roof, root, "station.canopy")
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
    # Roof end fascia emphasizes the gable rather than a rectangular flat cap.
    for x in (-4.85, 3.05):
        box("Gable roof end fascia", (x, 2.04, 3.40), (0.075, 0.17, 0.16),
            roof_ridge, root, "station.roof_trim")
    # Shelter roof has a visible shallow pitched profile with a muted timber
    # fascia. The canopy stays clear of the terminal train lane at y=-2.4.
    roof_slope("Platform shelter near roof face",
               [(1.32, -0.92, 2.65), (6.87, -0.92, 2.65),
                (6.87, 0.26, 3.01), (1.32, 0.26, 3.01)], 0.09, roof, root)
    roof_slope("Platform shelter far roof face",
               [(1.32, 0.26, 3.01), (6.87, 0.26, 3.01),
                (6.87, 1.44, 2.65), (1.32, 1.44, 2.65)], 0.09, roof, root)
    box("Platform shelter roof ridge", (4.1, 0.26, 3.04),
        (5.62, 0.17, 0.10), roof_ridge, root, "station.platform_shelter")
    for y in (-0.90, 1.42):
        box("Platform shelter gutter", (4.1, y, 2.62),
            (5.55, 0.10, 0.12), timber, root, "station.platform_shelter_trim")
    # Distinctive timber braces and a sheltered waiting bench.
    for x in (1.75, 4.1, 6.40):
        box("Shelter post footing", (x, 0.89, 0.44),
            (0.32, 0.32, 0.23), stone, root, "station.shelter_footing")
    box("Platform notice frame", (4.35, 1.12, 1.61),
        (1.15, 0.13, 0.72), timber, root, "station.notice")
    box("Platform notice face", (4.35, 1.035, 1.61),
        (0.95, 0.06, 0.53), clock, root, "station.notice")
    # A modest parapet and concrete curb emphasize scale without mini-detail.
    box("Station forecourt concrete curb", (-0.5, 3.88, 0.19),
        (12.7, 0.14, 0.19), stone, root, "station.sidewalk_curb")
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
