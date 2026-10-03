"""Run with pinned Blender --background --python-exit-code 1 --python this_file -- --output DIR.

Exercises real evaluated meshes, camera projections and proxy renders. No runtime
assets are modified or approved. The before/after geometry is identical.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tools/ch_blender"), str(ROOT / "tools/tycoon_photo_studio")]
import build_scene as bs
import scene_gate
from render_geometry import source_resolution_for, proxy_resolution_for


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parser.parse_args(argv)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    studio = bs.load_json(ROOT / "tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json")
    bs.clear_scene()
    final = (640, 448)
    source = source_resolution_for(final)
    scene = bs.configure_scene(studio, source, str(out))
    body = bs.add_box("QualityProbe", [0, 0, 1.5], [12, 6, 3],
                      bs.make_material("ProbeTimber", [0.42, 0.21, 0.10, 1], 0.85), 0.12)
    roof = bs.add_box("Roof", [0, 0, 3.1], [12.6, 6.6, 0.25],
                      bs.make_material("ProbeRoof", [0.12, 0.3, 0.2, 1], 0.85), 0.04)
    objects = [body, roof]
    root = bs.create_asset_root(objects)
    scene_gate.tag(body, "building.body", ground_contact=True)
    scene_gate.tag(roof, "building.roof")
    footprint = {"widthTiles": 5, "depthTiles": 3}
    requirements = {"assetId": "quality_probe", "footprint": footprint,
                    "requiredRoles": ["building.body", "building.roof"], "minDimensions": [12, 6, 3]}
    scale = bs.calibrate_ortho_scale(scene, objects)
    profile = scene_gate.load_profile()
    report = scene_gate.run_preflight(scene=scene, authored=objects, footprint=footprint,
                                      asset_id="quality_probe", requirements=requirements, profile=profile)
    scene_gate.require_pass(report)
    assert set(report["projectedViews"]) == {"south", "east", "west", "north"}
    # Measured world tile confirms the claimed dimetric 2:1 ground basis.
    points = [world_to_camera_view(scene, scene.camera, Vector(pt)) for pt in
              ((0, 0, 0), (3, 0, 0), (3, 3, 0), (0, 3, 0))]
    width = (max(p.x for p in points) - min(p.x for p in points)) * source[0]
    height = (max(p.y for p in points) - min(p.y for p in points)) * source[1]
    assert abs(width / height - 2.0) < 0.001, (width, height)

    # Legacy source/final aspect stretched this identical geometry by 40%.
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 4
    scene.render.resolution_x, scene.render.resolution_y = (640, 320)
    scene.render.filepath = str(out / "before_source.png")
    bpy.ops.render.render(write_still=True)
    scene.render.resolution_x, scene.render.resolution_y = proxy_resolution_for(source, 640)
    scene.render.filepath = str(out / "after_source.png")
    bpy.ops.render.render(write_still=True)

    # A cheap proxy uses the SAME aspect and preserves authored hidden objects.
    scene.render.resolution_x, scene.render.resolution_y = source
    proxy = scene_gate.render_proxy(scene=scene, authored=objects, output_path=out / "proxy_south.png",
                                    asset_id="quality_probe", profile={**profile, "proxy": {"resolution": 320, "engine": "CYCLES"}})
    assert tuple(proxy["resolution"]) == proxy_resolution_for(source, 320)
    assert proxy["projectedTileWidthPx"] > 0
    (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2))
    (out / "preflight_report.json").write_text(json.dumps(report, indent=2))

    # Final passes must not resurrect hidden alternatives or leak shadow-only visibility.
    hidden = bs.add_box("HiddenAlternative", [40, 40, 1], [1, 1, 1], body.data.materials[0], 0)
    hidden.parent = root
    hidden.hide_render = True
    objects.append(hidden)
    ground = bs.add_box("ProbeGround", [0, 0, -0.1], [30, 30, 0.1], body.data.materials[0], 0)
    ground.hide_render = True
    ground.is_shadow_catcher = False
    scene.render.resolution_x, scene.render.resolution_y = (160, 112)
    scene.cycles.samples = 2
    before_visibility = [(obj.hide_render, obj.visible_camera, obj.visible_shadow) for obj in objects]
    bs.render_color_pass(scene, objects, ground, str(out / "color_visibility_probe.png"))
    bs.render_shadow_pass(scene, objects, ground, str(out / "shadow_visibility_probe.png"))
    assert before_visibility == [(obj.hide_render, obj.visible_camera, obj.visible_shadow) for obj in objects]
    assert ground.hide_render and not ground.is_shadow_catcher
    scene.render.resolution_x, scene.render.resolution_y = source

    # Objective requested dimensions/parts are enforced, rather than merely documented.
    mismatch = scene_gate.run_preflight(scene=scene, authored=objects, footprint=footprint,
        asset_id="quality_probe", requirements={**requirements, "minDimensions": [20, 6, 3]})
    assert any(v["code"] == "CH_PREFLIGHT_REQUIREMENTS" for v in mismatch["violations"])
    original_camera = scene.camera.rotation_euler.copy()
    scene.camera.rotation_euler.x += 0.2
    bpy.context.view_layer.update()
    camera_fail = scene_gate.run_preflight(scene=scene, authored=objects, footprint=footprint)
    assert any(v["code"] == "CH_PREFLIGHT_CAMERA" for v in camera_fail["violations"])
    scene.camera.rotation_euler = original_camera
    light = next(obj for obj in scene.objects if obj.type == "LIGHT")
    light.data.energy += 1
    bpy.context.view_layer.update()
    light_fail = scene_gate.run_preflight(scene=scene, authored=objects, footprint=footprint)
    assert any(v["code"] == "CH_PREFLIGHT_STUDIO_DRIFT" for v in light_fail["violations"])
    light.data.energy -= 1

    # Actual modifier output must participate in the bounds, not only source vertices.
    modifier = body.modifiers.new("OversizedArray", "ARRAY")
    modifier.count = 4
    modifier.relative_offset_displace = (1, 0, 0)
    bpy.context.view_layer.update()
    oversize = scene_gate.run_preflight(scene=scene, authored=objects, footprint=footprint)
    assert any(v["code"] == "CH_PREFLIGHT_FOOTPRINT" for v in oversize["violations"])
    body.modifiers.remove(modifier)

    (out / "comparison_metrics.json").write_text(json.dumps({
        "contract": "CH_RENDER_QUALITY_COMPARISON_V1", "blenderVersion": bpy.app.version_string,
        "geometryChanged": False, "oldSource": [4096, 2048], "oldFinal": list(final),
        "oldAnisotropicStretch": (final[0] / 4096) / (final[1] / 2048),
        "newSource": list(source), "newFinal": list(final), "newAnisotropicStretch": 1.0,
        "measuredTileRatio": width / height, "allFourViewsFit": True,
        "cameraDriftRejected": True, "lightDriftRejected": True,
        "modifierGeometryChecked": True, "requestedDimensionsChecked": True,
        "finalPassVisibilityRestored": True,
        "orthoScale": scale}, indent=2))
    print("CH_RENDER_QUALITY_COMPARISON_V1: PASS")


if __name__ == "__main__":
    main()
