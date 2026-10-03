"""Regressions that previously distorted/cropped game assets and hid stale inputs."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/ch_blender"))
sys.path.insert(0, str(ROOT / "tools/tycoon_photo_studio"))
from render_geometry import source_resolution_for, proxy_resolution_for, ortho_spans, fit_ortho_scale, require_same_aspect, studio_fingerprint
from postprocess import make_direction_review, make_style_matrix, make_context_panel
from proxy_review import write_proxy_review
from agent_worker import validate_job, WorkerError, _input_records, _source_fingerprint


class RenderQualityTests(unittest.TestCase):
    def test_source_preserves_aspect_when_legacy_power_of_two_did_not(self):
        for final in ((320, 288), (448, 352), (1024, 1024), (2048, 2048), (640, 448)):
            source = source_resolution_for(final)
            require_same_aspect(source, final)
            self.assertLessEqual(max(source), 4096)
        with self.assertRaisesRegex(ValueError, "stretch"):
            require_same_aspect((2048, 2048), (320, 288))

    def test_proxy_retains_exact_camera_aspect(self):
        self.assertEqual(proxy_resolution_for((1280, 1152), 256), (250, 225))
        self.assertEqual(proxy_resolution_for((1024, 2048), 256), (128, 256))

    def test_source_identity_includes_options_but_not_output_location(self):
        inputs = [{"path": "builder.py", "sha256": "a" * 64}]
        first = _source_fingerprint(inputs, ["--output", "out/a", "--height", "3"])
        self.assertEqual(first, _source_fingerprint(inputs, ["--output", "out/b", "--height", "3"]))
        self.assertNotEqual(first, _source_fingerprint(inputs, ["--output", "out/a", "--height", "6"]))

    def test_blender_sensor_fit_landscape_and_portrait(self):
        self.assertEqual(ortho_spans(10, (200, 100)), (10, 5))
        self.assertEqual(ortho_spans(10, (100, 200)), (5, 10))
        for size in ((200, 100), (100, 200)):
            scale = fit_ortho_scale(8, 6, size)
            span_x, span_y = ortho_spans(scale, size)
            self.assertGreater(span_x, 16)
            self.assertGreater(span_y, 12)

    def test_large_review_does_not_clip_native_pixels(self):
        sprite = Image.new("RGBA", (1024, 768), (0, 0, 0, 0))
        sprite.putpixel((1023, 767), (255, 0, 255, 255))
        candidates = dict.fromkeys(("south", "east", "west", "north"), sprite)
        pivots = dict.fromkeys(candidates, {"x": 512, "y": 700})
        board = make_direction_review(candidates, pivots)
        self.assertEqual(board.getpixel((16 + 1023, 44 + 767)), (255, 0, 255, 255))
        matrix = make_style_matrix({key: [sprite] * 4 for key in candidates})
        self.assertEqual(matrix.getpixel((110 + 1023, 62 + 767)), (255, 0, 255, 255))

    def test_context_keeps_entire_large_sprite_and_calibrates_world_tile(self):
        sprite = Image.new("RGBA", (1280, 1280), (255, 0, 255, 255))
        panel = make_context_panel(sprite, {"x": 640, "y": 1100}, "SOUTH",
                                   {"widthTiles": 7, "depthTiles": 6}, 256)
        # Half-size gameplay calibration produces 640x640, fully contained.
        counts = dict((color, count) for count, color in panel.getcolors(panel.width * panel.height))
        self.assertGreaterEqual(counts.get((255, 0, 255, 255), 0), 640 * 640 - 400)

    def test_proxy_empty_alpha_rejected_even_with_valid_png(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            Image.new("RGBA", (32, 32)).save(out / "proxy_south.png")
            with self.assertRaisesRegex(ValueError, "no visible asset"):
                write_proxy_review(out, {"resolution": [32, 32], "sha256": "a" * 64}, {})

    def test_fingerprint_ignores_resolution_but_detects_changed_lights(self):
        studio = {"world": {"strength": 0.4}, "lights": [{"energy": 10}], "render": {"exposure": 0}}
        fingerprint = studio_fingerprint(studio)
        studio["render"]["sourceResolution"] = [2048, 2048]
        self.assertEqual(studio_fingerprint(studio), fingerprint)
        studio["lights"][0]["energy"] = 20
        self.assertNotEqual(studio_fingerprint(studio), fingerprint)

    def test_missing_recipe_and_wrong_camera_rejected_without_blender(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory)
            job = {"contract": "CH_BLENDER_AGENT_JOB_V1", "jobId": "test.proxy", "operation": "guarded_blender_script",
                   "qualityStage": "proxy", "script": "tools/tycoon_photo_studio/build_small_commercial_guarded.py",
                   "outputDir": "out/test-quality", "args": ["--output", "out/test-quality", "--recipe", str(path / "missing.json")]}
            job_path = path / "job.json"
            job_path.write_text(json.dumps(job))
            with self.assertRaises(WorkerError):
                validate_job(job_path)
            bad = path / "bad.json"
            bad.write_text(json.dumps({"camera": {"contract": "CH_CAMERA_V1", "yawDegrees": 90}}))
            job["args"] = ["--output", "out/test-quality", "--studio-preset", str(bad)]
            job_path.write_text(json.dumps(job))
            with self.assertRaisesRegex(WorkerError, "45 degree"):
                validate_job(job_path)

    def test_source_identity_includes_imported_geometry_and_recipe(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            script, helper, profile, recipe = [root / name for name in ("builder.py", "geometry_probe.py", "profile.json", "recipe.json")]
            script.write_text("import geometry_probe\n")
            helper.write_text("WIDTH = 3\n")
            profile.write_text("{}")
            recipe.write_text('{"width": 3}')
            args = ["--recipe", str(recipe)]
            first = _source_fingerprint(_input_records(script, profile, args))
            helper.write_text("WIDTH = 6\n")
            second = _source_fingerprint(_input_records(script, profile, args))
            self.assertNotEqual(first, second)
            recipe.write_text('{"width": 6}')
            self.assertNotEqual(second, _source_fingerprint(_input_records(script, profile, args)))


if __name__ == "__main__":
    unittest.main()
