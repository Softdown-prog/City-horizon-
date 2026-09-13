import unittest
import os
import copy
from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.command_executor import CommandExecutor
from tools.map_forge.importers.map_importer import load_scenario, load_building_catalog

try:
    import city_horizon_native as ch_native
    HAS_NATIVE = True
except ImportError:
    HAS_NATIVE = False


class TestTransactions(unittest.TestCase):
    def setUp(self):
        self.asset_root = r"C:\Users\User\Documents\Codex\2026-09-05\ve"
        self.scenario_path = os.path.join(self.asset_root, "assets", "scenarios", "initial_city.json")
        self.building_catalog = load_building_catalog(self.asset_root)

        self.initial_data = {
            "terrain": [{"tileX": 0, "tileY": 0, "texture": "assets/terrain/grass_isometric_01.png"}],
            "buildings": [
                {
                    "instanceId": 100,
                    "definitionId": "beach_umbrella_blue",
                    "tileX": 10,
                    "tileY": 10,
                    "rotation": 0
                }
            ],
            "roads": [{"tileX": 5, "tileY": 5}],
            "nextBuildingInstanceId": 101
        }
        self.map_model = MapModel(copy.deepcopy(self.initial_data))
        self.executor = CommandExecutor(self.map_model, self.asset_root, self.building_catalog)

    def test_single_mutation_undo_redo(self):
        # 1. Paint terrain
        res = self.executor.execute({"action": "paint_terrain", "x": 0, "y": 0, "texture": "assets/terrain/coast_sand_center_01.png"})
        self.assertTrue(res["success"])
        self.assertEqual(self.map_model.get_terrain_at(0, 0)["texture"], "assets/terrain/coast_sand_center_01.png")

        # 2. Undo
        undo_res = self.executor.execute({"action": "undo"})
        self.assertTrue(undo_res["success"])
        self.assertEqual(self.map_model.get_terrain_at(0, 0)["texture"], "assets/terrain/grass_isometric_01.png")

        # 3. Redo
        redo_res = self.executor.execute({"action": "redo"})
        self.assertTrue(redo_res["success"])
        self.assertEqual(self.map_model.get_terrain_at(0, 0)["texture"], "assets/terrain/coast_sand_center_01.png")

    def test_building_demolish_and_place_undo(self):
        # Demolish building
        res = self.executor.execute({"action": "remove_building", "x": 10, "y": 10})
        self.assertTrue(res["success"])
        self.assertIsNone(self.map_model.get_building_at(10, 10))

        # Undo demolition -> building restored with exact instanceId 100
        undo_res = self.executor.execute({"action": "undo"})
        self.assertTrue(undo_res["success"])
        b = self.map_model.get_building_at(10, 10)
        self.assertIsNotNone(b)
        self.assertEqual(b["instanceId"], 100)
        self.assertEqual(b["definitionId"], "beach_umbrella_blue")

    def test_batch_transaction_undo_redo(self):
        # Begin batch transaction
        self.executor.execute({"action": "begin_transaction", "description": "Paint Coast Batch"})

        self.executor.execute({"action": "paint_terrain", "x": 0, "y": 0, "texture": "assets/terrain/coast_sand_center_01.png"})
        self.executor.execute({"action": "set_road", "x": 5, "y": 5, "present": False})
        self.executor.execute({"action": "place_building", "definitionId": "beach_umbrella_blue", "x": 2, "y": 2})

        self.executor.execute({"action": "commit_transaction"})

        # Verify mutation state
        self.assertEqual(self.map_model.get_terrain_at(0, 0)["texture"], "assets/terrain/coast_sand_center_01.png")
        self.assertFalse(self.map_model.is_road_at(5, 5))
        self.assertIsNotNone(self.map_model.get_building_at(2, 2))

        # Single Undo reverts all 3 operations atomically
        undo_res = self.executor.execute({"action": "undo"})
        self.assertTrue(undo_res["success"])

        self.assertEqual(self.map_model.get_terrain_at(0, 0)["texture"], "assets/terrain/grass_isometric_01.png")
        self.assertTrue(self.map_model.is_road_at(5, 5))
        self.assertIsNone(self.map_model.get_building_at(2, 2))

    @unittest.skipUnless(HAS_NATIVE, "Native C++ extension city_horizon_native not available")
    def test_geometry_hash_equivalence_after_undo_redo(self):
        doc = ch_native.MapDocument.load_from_file(self.scenario_path)
        self.assertIsNotNone(doc)

        definitions_dir = os.path.join(self.asset_root, "assets", "definitions")
        catalog = ch_native.BuildingCatalog()
        catalog.load_from_directory(definitions_dir)

        camera = ch_native.CameraState()
        camera.zoom = 1.0
        camera.rotation = ch_native.CameraRotation.r0

        baseline_hash = ch_native.compute_document_geometry_signature(doc, catalog, camera, 1280.0, 720.0).compute_hash()

        # Load into MapModel, perform edits, then undo everything back to baseline
        model = load_scenario(self.scenario_path)
        executor = CommandExecutor(model, self.asset_root, self.building_catalog)

        executor.execute({"action": "paint_terrain", "x": 10, "y": 10, "texture": "assets/terrain/coast_sand_center_01.png"})
        executor.execute({"action": "set_road", "x": 12, "y": 12, "present": True})
        executor.execute({"action": "place_building", "definitionId": "beach_umbrella_blue", "x": 15, "y": 15})

        # Undo all 3 edits
        executor.execute({"action": "undo"})
        executor.execute({"action": "undo"})
        executor.execute({"action": "undo"})

        # Re-evaluate hash on restored document
        restored_doc = ch_native.MapDocument(model.raw_json)
        restored_hash = ch_native.compute_document_geometry_signature(restored_doc, catalog, camera, 1280.0, 720.0).compute_hash()

        self.assertEqual(baseline_hash, restored_hash, f"Hash divergence after undo cycle: Baseline={baseline_hash}, Restored={restored_hash}")


if __name__ == "__main__":
    unittest.main()
