"""CH Blender proxy study of a canopy for the approved 48x64 pedestrian.

The static fabric is baked in the frozen CH studio. The lower shaft belongs to
the actor overlay compositor because its endpoint follows the animated hand.
The guarded final stage renders four views after the reviewed SOUTH proxy.
Neither stage promotes art to the runtime assets directory.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))
import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402

ASSET_ID = "character.ch_actor_green_01.umbrella_canopy_study"


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def build_canopy():
    # A raised central crown and three radial rings give the canopy a visible
    # side profile after reducing it to the pedestrian's 48x64 frame.
    # Different gores get the same neutral textile with tiny value
    # changes, leaving the fixed studio lights to define the larger volumes.
    fabric = [bs.make_material(f"Fabric_{i}", (0.82 * v, 0.82 * v, 0.79 * v, 1), 0.91)
              for i, v in enumerate((0.95, 1.0, 1.04, 0.98, 0.92, 0.99, 1.03, 0.97,
                                       0.94, 1.01, 1.04, 0.99))]
    piping = bs.make_material("WovenEdge", (0.32, 0.41, 0.42, 1), 0.85)
    ferrule = bs.make_material("BrushedMetalTip", (0.43, 0.48, 0.49, 1), 0.48, 0.28)
    rings = ((0.25, 1.43), (0.49, 1.29), (0.72, 1.07))
    segments = 12
    vertices = [(0.0, 0.0, 1.49)]
    for radius, z in rings:
        for i in range(segments):
            a = 2 * math.pi * i / segments
            # Gentle scallop at the outside edge, the point of each gore lower.
            dz = -0.028 if radius == rings[-1][0] and i % 2 == 0 else 0.0
            vertices.append((radius * math.cos(a), radius * math.sin(a), z + dz))
    faces = []
    material_indices = []
    for i in range(segments):
        faces.append((0, 1 + i, 1 + (i + 1) % segments))
        material_indices.append(i)
    for ring in range(len(rings) - 1):
        for i in range(segments):
            nxt = (i + 1) % segments
            faces.append((1 + ring * segments + i,
                          1 + (ring + 1) * segments + i,
                          1 + (ring + 1) * segments + nxt,
                          1 + ring * segments + nxt))
            material_indices.append(i)
    mesh = bpy.data.meshes.new("CutAndSewnGores")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    dome = bpy.data.objects.new("UmbrellaFabric", mesh)
    bpy.context.collection.objects.link(dome)
    for mat in fabric:
        dome.data.materials.append(mat)
    for polygon, index in zip(dome.data.polygons, material_indices):
        polygon.material_index = index
        polygon.use_smooth = True
    solid = dome.modifiers.new("FabricThickness", "SOLIDIFY")
    solid.thickness = 0.009
    scene_gate.tag(dome, "prop.umbrella.fabric")

    details = []
    def tube(name, points, material, radius, role):
        curve = bpy.data.curves.new(name, "CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 2
        curve.bevel_depth = radius
        curve.bevel_resolution = 1
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for point, xyz in zip(spline.points, points):
            point.co = (*xyz, 1.0)
        obj = bpy.data.objects.new(name, curve)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(material)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target="MESH")
        obj = bpy.context.object
        scene_gate.tag(obj, role)
        details.append(obj)

    for i in range(segments):
        a = 2 * math.pi * i / segments
        tube(f"GoreSeam_{i:02}", [(r * math.cos(a), r * math.sin(a), z + 0.006)
                                    for r, z in rings], piping, 0.004,
             "prop.umbrella.stitch")
    tube("ScallopedBinding", [(0.72 * math.cos(2 * math.pi * i / 72),
                                0.72 * math.sin(2 * math.pi * i / 72),
                                1.07 - (0.028 if (i // 6) % 2 == 0 else 0))
                               for i in range(73)], piping, 0.009,
         "prop.umbrella.binding")
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.018, radius2=0.005,
                                    depth=0.10, location=(0, 0, 1.54))
    tip = bpy.context.object
    tip.name = "UmbrellaFerrule"
    tip.data.materials.append(ferrule)
    scene_gate.tag(tip, "prop.umbrella.ferrule")
    details.append(tip)
    return [dome, *details], dome, details


def render_fabric_mask(scene, dome, details, path, *, accent_only=False):
    previous = (scene.render.engine, scene.render.resolution_x,
                scene.render.resolution_y, scene.render.filepath)
    original_materials = list(dome.data.materials)
    def emission_material(name, color):
        emission = bpy.data.materials.new(name)
        emission.use_nodes = True
        nodes = emission.node_tree.nodes
        nodes.clear()
        output = nodes.new("ShaderNodeOutputMaterial")
        source = nodes.new("ShaderNodeEmission")
        source.inputs["Color"].default_value = (color, color, color, 1)
        emission.node_tree.links.new(source.outputs[0], output.inputs[0])
        return emission

    white = emission_material("MaskWhiteEmission", 1.0)
    black = emission_material("MaskBlackEmission", 0.0)
    try:
        for i in range(len(original_materials)):
            # Six alternating gores make broad, readable colored stripes.
            # All other gores stay white; the fixed ribs and edge stay unmasked.
            dome.data.materials[i] = white if not accent_only or i % 2 == 0 else black
        for obj in details:
            obj.hide_render = True
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.render.resolution_x = scene.render.resolution_y = 256
        scene.render.filepath = str(path)
        scene.render.film_transparent = True
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        bpy.ops.render.render(write_still=True)
    finally:
        for i, material in enumerate(original_materials):
            dome.data.materials[i] = material
        for obj in details:
            obj.hide_render = False
        (scene.render.engine, scene.render.resolution_x,
         scene.render.resolution_y, scene.render.filepath) = previous


def main():
    args = parse_args()
    studio = bs.load_json(args.studio_preset)
    profile = scene_gate.load_profile(args.preflight_profile)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    bs.clear_scene()
    scene = bs.configure_scene(studio, (512, 512), str(output))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    authored, dome, details = build_canopy()
    root = bs.create_asset_root(authored)
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    report = scene_gate.run_preflight(scene=scene, authored=authored,
                                      footprint={"widthTiles": 1, "depthTiles": 1},
                                      profile=profile, asset_id=ASSET_ID,
                                      report_path=output / "preflight_report.json")
    scene_gate.require_pass(report)
    if args.stage == "proxy":
        proxy = scene_gate.render_proxy(scene=scene, authored=authored,
                                        output_path=output / "proxy_south.png",
                                        profile=profile, asset_id=ASSET_ID,
                                        direction="south")
        (output / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        render_fabric_mask(scene, dome, details, output / "fabric_mask_south.png")
        render_fabric_mask(scene, dome, details, output / "accent_mask_south.png", accent_only=True)
    elif args.stage == "final":
        if not args.approval_proxy_sha or len(args.approval_proxy_sha) != 64:
            raise ValueError("The final bake requires the reviewed SOUTH proxy SHA-256")
        (output / "proxy_approval.json").write_text(json.dumps({
            "contract": "CH_PROXY_APPROVAL_V1",
            "assetId": ASSET_ID,
            "reviewed": True,
            "proxySha256": args.approval_proxy_sha,
        }, indent=2), encoding="utf-8")
        (output / "studio_metadata.json").write_text(json.dumps({
            "assetId": ASSET_ID,
            "cameraContract": "CH_CAMERA_V1",
            "studioPreset": "CH_TYCOON_STUDIO_V1",
            "resolution": [256, 256],
            "directions": [direction["id"] for direction in bs.DIRECTIONS],
            "passes": ["canopy", "fabric_mask", "accent_mask"],
        }, indent=2), encoding="utf-8")
        for direction in bs.DIRECTIONS:
            bs.set_direction(root, direction)
            name = direction["id"]
            scene_gate.render_proxy(scene=scene, authored=authored,
                                    output_path=output / f"canopy_{name}.png",
                                    profile=profile, asset_id=ASSET_ID,
                                    direction=name)
            render_fabric_mask(scene, dome, details, output / f"fabric_mask_{name}.png")
            render_fabric_mask(scene, dome, details, output / f"accent_mask_{name}.png",
                               accent_only=True)


if __name__ == "__main__":
    main()
