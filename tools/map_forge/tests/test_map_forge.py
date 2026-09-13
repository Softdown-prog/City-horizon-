"""
Unit tests for City Horizon Map Forge Phase 1 Core.
Tests lossless JSON round-trip, isometric projection math, validation, and read-only CLI commands.
"""

import unittest
import os
import sys

# Ensure root directory is on sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from tools.map_forge.importers.map_importer import load_scenario, load_building_catalog
from tools.map_forge.exporters.game_exporter import verify_round_trip
from tools.map_forge.core.projection import tile_visual_top_world, world_to_screen, screen_to_tile, Camera
from tools.map_forge.core.validator import validate_map
from tools.map_forge.core.command_executor import ReadOnlyCommandExecutor
from tools.map_forge.recipes.coastal_forest_hydroelectric import build_coastal_forest_hydroelectric


class TestMapForgePhase1(unittest.TestCase):
    def setUp(self):
        candidates = [
            r"C:\Users\User\Documents\Codex\2026-09-05\ve\assets\scenarios\initial_city.json",
            r"C:\Users\User\Documents\Codex\2026-09-05\ve\build\Debug\assets\scenarios\initial_city.json",
            r"C:\Users\User\Documents\Codex\2026-09-05\ve\build\assets\scenarios\initial_city.json",
        ]
        self.scenario_path = next((p for p in candidates if os.path.exists(p)), candidates[0])
        self.asset_root = os.path.dirname(os.path.dirname(self.scenario_path))

    def test_01_lossless_round_trip(self):
        map_model = load_scenario(self.scenario_path)
        self.assertIsNotNone(map_model.raw_data)
        
        success, message = verify_round_trip(map_model)
        self.assertTrue(success, f"Round-trip failed: {message}")

    def test_02_isometric_projection_math(self):
        cam = Camera(world_x=0.0, world_y=0.0, zoom=1.0)
        vw, vh = 1280.0, 720.0

        # Test origin tile (0, 0)
        wx, wy = tile_visual_top_world(0, 0)
        self.assertEqual((wx, wy), (0.0, 0.0))

        sx, sy = world_to_screen(wx, wy, cam, vw, vh)
        self.assertEqual((sx, sy), (640.0, 360.0))

        tx, ty = screen_to_tile(sx, sy, cam, vw, vh)
        self.assertEqual((tx, ty), (0, 0))

        # Test arbitrary tile (10, -5)
        wx, wy = tile_visual_top_world(10, -5)
        sx, sy = world_to_screen(wx, wy, cam, vw, vh)
        tx, ty = screen_to_tile(sx, sy, cam, vw, vh)
        self.assertEqual((tx, ty), (10, -5))

    def test_03_map_validator(self):
        map_model = load_scenario(self.scenario_path)
        catalog = load_building_catalog(self.asset_root)
        
        result = validate_map(map_model, self.asset_root, catalog)
        self.assertTrue(result["valid"], f"Validation failed with errors: {result['errors']}")
        self.assertGreater(result["stats"]["terrain_count"], 0)
        self.assertGreater(result["stats"]["buildings_count"], 0)

    def test_04_read_only_command_executor(self):
        map_model = load_scenario(self.scenario_path)
        catalog = load_building_catalog(self.asset_root)
        executor = ReadOnlyCommandExecutor(map_model, self.asset_root, catalog)

        # Test inspect-tile
        res_tile = executor.execute({"action": "inspect_tile", "x": -10, "y": 17})
        self.assertEqual(res_tile["tileX"], -10)
        self.assertEqual(res_tile["tileY"], 17)
        self.assertIsNotNone(res_tile["terrain"])

        # Test read-only rejection of mutation action
        res_mutation = executor.execute({"action": "paint_terrain"})
        self.assertFalse(res_mutation.get("success", True))
        self.assertIn("Phase 1 Read-Only Mode", res_mutation.get("error", ""))

    def test_05_coastal_recipe_is_non_destructive_and_valid(self):
        source = load_scenario(self.scenario_path)
        catalog = load_building_catalog(self.asset_root)
        generated = build_coastal_forest_hydroelectric(source.raw_data, catalog)
        self.assertEqual(len(source.buildings), 35)
        self.assertEqual(len(generated["buildings"]), 45)
        self.assertIn("hydroelectric_01", [entry["definitionId"] for entry in generated["buildings"]])
        generated_model = type(source)(generated)
        result = validate_map(generated_model, self.asset_root, catalog)
        self.assertTrue(result["valid"], result["errors"])


if __name__ == "__main__":
    unittest.main()
