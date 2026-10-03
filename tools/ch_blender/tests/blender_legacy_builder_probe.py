"""Exercise tree/character main paths and all poses, with cheap character color renders.

Character shadows are transparent diagnostic placeholders; the framing probe tests real shadow passes.
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
                if count[0] == 0 or builder is build_character:
                    resolution = (scene.render.resolution_x, scene.render.resolution_y)
                    samples = scene.cycles.samples
                    scene.render.resolution_x, scene.render.resolution_y = proxy_resolution_for(resolution, 256)
                    scene.cycles.samples = 2
                    try:
                        destination = path if builder is build_character else str(directory / "integration_proxy.png")
                        original_color(scene, authored, ground, destination)
                    finally:
                        scene.render.resolution_x, scene.render.resolution_y = resolution
                        scene.cycles.samples = samples
                count[0] += 1
            bs.render_color_pass = check_and_render
            def diagnostic_shadow(scene, authored, ground, path):
                if builder is build_character:
                    image = bpy.data.images.new("DiagnosticEmptyShadow", width=256, height=256, alpha=True)
                    image.pixels.foreach_set([0.0] * (256 * 256 * 4))
                    image.filepath_raw = path
                    image.file_format = "PNG"
                    image.save()
                    bpy.data.images.remove(image)
            bs.render_shadow_pass = diagnostic_shadow
            sys.argv = ["blender", "--", "--output", str(directory), "--asset-config",
                        str(ROOT / "tools/tycoon_photo_studio/assets" / config), "--studio-preset",
                        str(ROOT / "tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json")]
            builder.main()
            metadata = json.loads((directory / metadata_name).read_text())
            assert count[0] == expected_count, (builder.__name__, count)
            assert metadata["studioFingerprint"] == bpy.context.scene["ch.studioFingerprint"]
            assert metadata["renderResolution"][0] * metadata["finalResolution"][1] == metadata["renderResolution"][1] * metadata["finalResolution"][0]
            if builder is build_character:
                native = metadata["renderResolution"]
                for direction in metadata["directions"]:
                    for frame in direction["frames"]:
                        pivot = frame["groundOriginSourcePx"]
                        pivot["x"] *= 256 / native[0]
                        pivot["y"] *= 256 / native[1]
                metadata["renderResolution"] = [256, 256]
                metadata["diagnosticProbe"] = {"samples": 2, "emptyShadows": True, "productionBake": False}
                (directory / metadata_name).write_text(json.dumps(metadata, indent=2))
            results.append({"builder": builder.__name__, "checkedPoses": count[0], "studioFingerprint": metadata["studioFingerprint"]})
    finally:
        bs.render_color_pass, bs.render_shadow_pass = original_color, original_shadow
    (output / "legacy_builder_results.json").write_text(json.dumps(results, indent=2))
    print("CH_LEGACY_BUILDER_PROBE: PASS")


if __name__ == "__main__":
    main()
