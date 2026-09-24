"""Regression for colored RGB hidden behind transparent source pixels."""

import unittest
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile

from PIL import Image

from visitor_forge_2d.core import LayerComposer
from visitor_forge_2d.cli import command_prototype
from visitor_forge_2d.character import generate_v1_south_assets, validate_v1_character
from visitor_forge_2d.core import load_character_definition, load_pose

ROOT = Path(__file__).resolve().parents[1]


class AlphaTransformTests(unittest.TestCase):
    def test_transparent_source_color_does_not_bleed_into_articulated_edge(self) -> None:
        part = Image.new("RGBA", (16, 16), (255, 0, 0, 0))
        part.putpixel((7, 7), (0, 0, 255, 255))

        transformed = LayerComposer._transform_canvas(part, (1, 0, 0.5, 0, 1, 0.5))
        edge_pixels = [
            transformed.getpixel((x, y))
            for y in range(transformed.height)
            for x in range(transformed.width)
            if 0 < transformed.getpixel((x, y))[3] < 255
        ]

        self.assertTrue(edge_pixels)
        self.assertTrue(all(red == 0 and green == 0 and blue > 0 for red, green, blue, _ in edge_pixels))

    def test_duplicate_pose_cannot_overwrite_frame(self) -> None:
        definition = load_character_definition(ROOT / "definitions/visitor_male_01.south.json")
        poses = [load_pose(ROOT / "poses" / name) for name in ("south_idle.json", "south_walk_a.json", "south_walk_b.json", "south_walk_b.json")]
        with self.assertRaisesRegex(ValueError, "Duplicate pose ID"):
            validate_v1_character(definition, poses)

    def test_prototype_uses_definition_id_for_review_strips(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            definition_data = json.loads((ROOT / "definitions/visitor_male_01.south.json").read_text(encoding="utf-8"))
            definition_data["characterId"] = "visitor_review_test"
            definition_path = root / "definition.json"
            definition_path.write_text(json.dumps(definition_data), encoding="utf-8")
            args = argparse.Namespace(definition=str(definition_path), pose=[str(ROOT / "poses" / name) for name in ("south_idle.json", "south_walk_a.json", "south_walk_b.json")], asset_root=str(root / "assets"), output=str(root / "output"))
            with contextlib.redirect_stdout(io.StringIO()):
                command_prototype(args)
            self.assertTrue((root / "output/visitor_review_test_south_review_strip.png").is_file())
            self.assertTrue((root / "output/visitor_review_test_south_gameplay_strip.png").is_file())
            self.assertTrue((root / "output/visitor_review_test_south_in_world_review.png").is_file())
            measurements = json.loads((root / "output/visitor_review_test_south_review_metrics.json").read_text())
            self.assertLessEqual(measurements["footRowRangePx"], 2)
            self.assertTrue(all(value > 0 for value in measurements["changedSilhouetteFractionFromIdle"]))
            self.assertFalse(measurements["artApproved"])

    def test_prototype_preserves_manual_part_until_explicit_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            generate_v1_south_assets(root)
            part = root / "visitor_male_01/south/torso.png"
            with Image.open(part) as image:
                edited = image.copy()
            edited.putpixel((70, 75), (255, 0, 0, 255))
            edited.save(part)
            manual_bytes = part.read_bytes()

            generate_v1_south_assets(root)
            self.assertEqual(part.read_bytes(), manual_bytes)
            manifest = json.loads((part.parent / "generated_parts.json").read_text())
            self.assertIn("torso.png", manifest["preservedOverrides"])

            generate_v1_south_assets(root, overwrite=True)
            self.assertNotEqual(part.read_bytes(), manual_bytes)


if __name__ == "__main__":
    unittest.main()
