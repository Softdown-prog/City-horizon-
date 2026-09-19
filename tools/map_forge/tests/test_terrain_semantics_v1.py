import json
import os
import unittest

from tools.map_forge.core.command_executor import CommandExecutor
from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.native_bridge import get_native_core
from tools.map_forge.core.terrain_semantics import (
    TerrainSemanticContractError, load_terrain_semantic_catalog, native_catalog_json, validate_definition,
)


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ASSET_ROOT = os.path.join(ROOT, "build", "Debug")


class TerrainSemanticsV1Tests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_terrain_semantic_catalog(ASSET_ROOT)
        self.model = MapModel({"saveVersion": 7, "terrain": [], "buildings": [], "roads": []})
        self.executor = CommandExecutor(self.model, ASSET_ROOT, {}, terrain_semantic_catalog=self.catalog)

    def test_visual_only_preserves_existing_semantics(self):
        self.model.set_terrain(1, 2, "assets/terrain/old.png", "cement_path", True)
        result = self.executor.execute({"action": "paint_terrain", "x": 1, "y": 2,
                                        "texture": "assets/terrain/grass_isometric_01.png", "paintMode": "visual_only"})
        self.assertTrue(result["success"])
        entry = self.model.get_terrain_at(1, 2)
        self.assertEqual(entry["terrainDefinition"], "cement_path")
        self.assertEqual(entry["texture"], "assets/terrain/grass_isometric_01.png")

    def test_visual_plus_semantics_writes_declared_id_and_native_navigation(self):
        result = self.executor.execute({"action": "paint_terrain", "x": 3, "y": 4,
                                        "terrainDefinition": "cement_path", "paintMode": "visual_plus_semantics"})
        self.assertTrue(result["success"])
        entry = self.model.get_terrain_at(3, 4)
        self.assertEqual(entry["terrainDefinition"], "cement_path")
        self.assertEqual(entry["texture"], self.catalog["cement_path"]["visualMaterial"])
        ch = get_native_core()
        doc = ch.MapDocument(json.dumps(self.model.raw_data))
        info = ch.inspect_tile_channels_with_terrain_catalog(doc, 3, 4, native_catalog_json(self.catalog))
        self.assertEqual(info.navigation_state, ch.SemanticState.VALID)
        self.assertEqual(info.sidewalk_state, ch.SemanticState.VALID)

    def test_visual_material_alone_is_not_a_pedestrian_route(self):
        # The identical cement appearance is not sufficient to create a route.
        result = self.executor.execute({"action": "paint_terrain", "x": 5, "y": 6,
                                        "texture": self.catalog["cement_path"]["visualMaterial"],
                                        "paintMode": "visual_only"})
        self.assertTrue(result["success"])
        ch = get_native_core()
        doc = ch.MapDocument(json.dumps(self.model.raw_data))
        info = ch.inspect_tile_channels_with_terrain_catalog(doc, 5, 6, native_catalog_json(self.catalog))
        self.assertNotEqual(info.navigation_state, ch.SemanticState.VALID)
        self.assertNotEqual(info.sidewalk_state, ch.SemanticState.VALID)

    def test_unknown_definition_fails_closed(self):
        result = self.executor.execute({"action": "paint_terrain", "x": 0, "y": 0,
                                        "terrainDefinition": "fake_cement", "paintMode": "visual_plus_semantics"})
        self.assertFalse(result["success"])
        self.assertIsNone(self.model.get_terrain_at(0, 0))

    def test_unknown_semantic_property_is_rejected(self):
        definition = dict(self.catalog["cement_path"])
        definition["semantic"] = dict(definition["semantic"], flies=True)
        with self.assertRaises(TerrainSemanticContractError):
            validate_definition(definition)


if __name__ == "__main__":
    unittest.main()
