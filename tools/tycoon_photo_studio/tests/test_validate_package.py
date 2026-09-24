"""Exercise package validation against real PNGs and a large-asset frame."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from tools.tycoon_photo_studio import validate_package


class PackageValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.asset = {"assetId": "test", "assetType": "static_building", "studioPreset": "studio", "footprint": {"widthTiles": 2, "depthTiles": 2}}
        self.studio = {"id": "studio", "camera": {"contract": "CH_CAMERA_V1"}, "render": {"finalResolution": [2, 2]}, "postProcess": {"paletteColors": 128, "candidateVariant": 1}}
        self.views = []
        self.files = {}
        for direction, turns in (("south", 0), ("east", 1), ("west", 3), ("north", 2)):
            name = f"test_{direction}.png"
            color = f"test_{direction}_color.png"
            shadow = f"test_{direction}_shadow.png"
            image = Image.new("RGBA", (3, 3), (0, 0, 0, 0))
            image.putpixel((1, 1), (80, 100, 120, 255))
            image.save(self.root / name)
            image.save(self.root / color)
            Image.new("RGBA", (3, 3)).save(self.root / shadow)
            self.views.append({"direction": direction, "quarterTurns": turns, "file": name, "colorPass": color, "shadowPass": shadow, "pivot": {"x": 1, "y": 2}, "spriteAlphaBounds": [1, 1, 2, 2], "objectAlphaBounds": [1, 1, 2, 2]})
            self.files[direction] = name
        for key, name, size in (("spriteSheet", "sheet.png", (12, 3)), ("atlas", "atlas.png", (4, 3)), ("reviewSheet", "review.png", (3, 3)), ("styleMatrix", "style.png", (3, 3)), ("context4Dir", "context.png", (3, 3))):
            Image.new("RGBA", size).save(self.root / name)
            self.files[key] = name
        self.manifest = {
            "contract": "TYCOON_ASSET_BAKE_V1", "sourceContract": "TYCOON_ASSET_SOURCE_V1", "assetId": "test", "assetType": "static_building", "studioPreset": "studio", "cameraContract": "CH_CAMERA_V1", "gridContract": "CH_GRID_V1", "directionCount": 4, "directionOrder": ["south", "east", "west", "north"], "footprint": self.asset["footprint"], "finalFrameResolution": [3, 3], "paletteColorCount": 128, "candidatePostProcess": {"variantId": 1}, "views": self.views,
            "atlas": {"frames": [{"direction": view["direction"], "x": i, "y": 0, "w": 1, "h": 1, "pivotX": 0, "pivotY": 1, "sourceBounds": [1, 1, 2, 2]} for i, view in enumerate(self.views)]}, "files": self.files,
        }

    def validate(self):
        for name, data in (("manifest.json", self.manifest), ("asset.json", self.asset), ("studio.json", self.studio)):
            (self.root / name).write_text(json.dumps(data), encoding="utf-8")
        argv = ["validate_package.py", "--manifest", str(self.root / "manifest.json"), "--asset-config", str(self.root / "asset.json"), "--studio-preset", str(self.root / "studio.json")]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            validate_package.main()

    def test_dynamic_frame_larger_than_studio_minimum_passes(self):
        self.validate()

    def test_alpha_bounds_must_match_png(self):
        self.views[0]["spriteAlphaBounds"] = [0, 0, 3, 3]
        with self.assertRaisesRegex(RuntimeError, "Sprite alpha bounds differ"):
            self.validate()

    def test_wrong_size_or_color_mode_fails(self):
        target = self.root / self.views[0]["file"]
        Image.new("RGB", (3, 3), (10, 20, 30)).save(target)
        with self.assertRaisesRegex(RuntimeError, "must be RGBA"):
            self.validate()
        Image.new("RGBA", (2, 2), (10, 20, 30, 255)).save(target)
        with self.assertRaisesRegex(RuntimeError, "size differs"):
            self.validate()


if __name__ == "__main__":
    unittest.main()
