"""
Unit test suite for Active Manual Human Editing Mode & Map Export Suite in Map Forge.
Verifies importing game map scenarios, importing asset catalogs, painting terrain,
placing/demolishing building instances, road editing, round-trip verification,
and exporting scenarios for the game executable.
"""

import os
import tempfile
import unittest
from tools.map_forge.importers.map_importer import load_scenario, load_building_catalog
from tools.map_forge.core.command_executor import CommandExecutor
from tools.map_forge.exporters.game_exporter import (
    verify_round_trip, export_game_scenario, export_scenario_manifest
)


class TestManualEditing(unittest.TestCase):
    def setUp(self):
        self.asset_root = r"C:\Users\User\Documents\Codex\2026-09-05\ve"
        self.scenario_path = os.path.join(self.asset_root, "assets", "scenarios", "initial_city.json")
        self.map_model = load_scenario(self.scenario_path)
        self.catalog = load_building_catalog(self.asset_root)
        self.executor = CommandExecutor(self.map_model, self.asset_root, self.catalog, read_only=False)

    def test_01_import_map_and_catalog(self):
        self.assertIsNotNone(self.map_model)
        self.assertGreater(len(self.catalog), 0)
        self.assertIn("beach_lighthouse", self.catalog)

    def test_02_paint_terrain(self):
        res = self.executor.execute({
            "action": "paint_terrain",
            "x": 0,
            "y": 0,
            "texture": "assets/terrain/coast_adjusted/coast_sand_center_01.png"
        })
        self.assertTrue(res.get("success"))
        entry = self.map_model.get_terrain_at(0, 0)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["texture"], "assets/terrain/coast_adjusted/coast_sand_center_01.png")

    def test_03_place_and_remove_building(self):
        initial_count = len(self.map_model.buildings)
        res_place = self.executor.execute({
            "action": "place_building",
            "definitionId": "beach_umbrella_blue",
            "x": -20,
            "y": -20,
            "rotation": 1
        })
        self.assertTrue(res_place.get("success"))
        self.assertEqual(len(self.map_model.buildings), initial_count + 1)

        res_remove = self.executor.execute({
            "action": "remove_building",
            "x": -20,
            "y": -20
        })
        self.assertTrue(res_remove.get("success"))
        self.assertEqual(len(self.map_model.buildings), initial_count)

    def test_04_road_editing(self):
        res_road = self.executor.execute({
            "action": "set_road",
            "x": -22,
            "y": -22,
            "present": True
        })
        self.assertTrue(res_road.get("success"))
        self.assertTrue(self.map_model.is_road_at(-22, -22))

    def test_05_round_trip_verification(self):
        success, message = verify_round_trip(self.map_model)
        self.assertTrue(success, message)

    def test_06_export_game_scenario(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_json = os.path.join(tmp_dir, "test_custom_city.json")
            res = export_game_scenario(self.map_model, target_json, self.asset_root, self.catalog)
            self.assertTrue(res.get("success"))
            self.assertTrue(os.path.exists(target_json))

            manifest_json = os.path.join(tmp_dir, "manifest.json")
            manifest_path = export_scenario_manifest(self.map_model, manifest_json, self.asset_root, self.catalog)
            self.assertTrue(os.path.exists(manifest_path))


if __name__ == "__main__":
    unittest.main()
