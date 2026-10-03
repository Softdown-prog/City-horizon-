"""Exercise actual tree/character main paths and all poses, with one cheap render each.

Other passes check evaluated bounds and studio state instead of spending on full bakes.
No candidate is approved or promoted.
"""
import argparse
import json
import sys
from pathlib import Path
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/tycoon_photo_studio"))
import build_scene as bs
import build_classic_tree
import build_character
from render_geometry import proxy_resolution_for, scene_studio_state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    output = Path(args.output).resolve()
    original_color, original_shadow = bs.render_color_pass, bs.render_shadow_pass
    results = []
    try:
        for builder, config, metadata_name, expected_count in (
            (build_classic_tree, "park_tree_broadleaf_01.fractal.json", "studio_metadata.json", 4),
            (build_character, "visitor_male_red_02.json", "character_studio_metadata.json", 64),
        ):
            directory = output / builder.__name__
            directory.mkdir(parents=True, exist_ok=True)
            count = [0]
            def check_and_render(scene, authored, ground, path):
                assert scene_studio_state(scene) == scene["ch.studioState"]
                for obj in authored:
                    if obj.hide_render:
                        continue
                    mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                    for corner in mesh.bound_box:
                        point = world_to_camera_view(scene, scene.camera, mesh.matrix_world @ Vector(corner))
                        assert -0.015 <= point.x <= 1.015 and -0.015 <= point.y <= 1.015, (obj.name, tuple(point))
                if count[0] == 0:
                    resolution = (scene.render.resolution_x, scene.render.resolution_y)
                    samples = scene.cycles.samples
                    scene.render.resolution_x, scene.render.resolution_y = proxy_resolution_for(resolution, 256)
                    scene.cycles.samples = 2
                    try:
                        original_color(scene, authored, ground, str(directory / "integration_proxy.png"))
                    finally:
                        scene.render.resolution_x, scene.render.resolution_y = resolution
                        scene.cycles.samples = samples
                count[0] += 1
            bs.render_color_pass = check_and_render
            bs.render_shadow_pass = lambda *a, **k: None
            sys.argv = ["blender", "--", "--output", str(directory), "--asset-config",
                        str(ROOT / "tools/tycoon_photo_studio/assets" / config), "--studio-preset",
                        str(ROOT / "tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json")]
            builder.main()
            metadata = json.loads((directory / metadata_name).read_text())
            assert count[0] == expected_count, (builder.__name__, count)
            assert metadata["studioFingerprint"] == bpy.context.scene["ch.studioFingerprint"]
            assert metadata["renderResolution"][0] * metadata["finalResolution"][1] == metadata["renderResolution"][1] * metadata["finalResolution"][0]
            results.append({"builder": builder.__name__, "checkedPoses": count[0], "studioFingerprint": metadata["studioFingerprint"]})
    finally:
        bs.render_color_pass, bs.render_shadow_pass = original_color, original_shadow
    (output / "legacy_builder_results.json").write_text(json.dumps(results, indent=2))
    print("CH_LEGACY_BUILDER_PROBE: PASS")


if __name__ == "__main__":
    main()
