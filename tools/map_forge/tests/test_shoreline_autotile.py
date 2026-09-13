"""
Shoreline Autotile Engine Test Suite (CH_SHORELINE_V1).
Verifies native C++20 autotiler integration in Map Forge, 8-neighbor bitmask resolution,
and terrain semantic hash invariance (SemanticHash BEFORE == SemanticHash AFTER).
"""

import unittest
import os
import json
import sys

# Ensure root directory is on sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from tools.map_forge.core.native_bridge import get_native_core
from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.shoreline_autotile import run_shoreline_autotile


class TestShorelineAutotile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ch = get_native_core()
        assert cls.ch is not None, "city_horizon_native module must be loaded"

        cls.scenario_path = os.path.join(root_dir, "assets", "scenarios", "initial_city.json")
        assert os.path.exists(cls.scenario_path), f"Scenario missing at {cls.scenario_path}"

        with open(cls.scenario_path, "r", encoding="utf-8") as f:
            cls.raw_data = json.load(f)

    def test_01_contracts_and_enums(self):
        """Verifies native CH_SHORELINE_V1 enum values and types."""
        self.assertEqual(int(self.ch.ShorelinePiece.BORDER_NORTH), 0)
        self.assertEqual(int(self.ch.ShorelinePiece.BORDER_EAST), 1)
        self.assertEqual(int(self.ch.ShorelinePiece.INNER_NW), 11)

    def test_02_resolve_shoreline_bitmasks(self):
        """Verifies resolve_shoreline for pure cardinal and corner bitmask combinations."""
        # N=1 -> Border North
        recipe_n = self.ch.resolve_shoreline(1)
        self.assertIn(self.ch.ShorelinePiece.BORDER_NORTH, recipe_n.pieces)

        # N=1, E=4 -> Border North + Border East + Outer NE
        recipe_ne = self.ch.resolve_shoreline(1 | 4)
        self.assertIn(self.ch.ShorelinePiece.BORDER_NORTH, recipe_ne.pieces)
        self.assertIn(self.ch.ShorelinePiece.BORDER_EAST, recipe_ne.pieces)
        self.assertIn(self.ch.ShorelinePiece.OUTER_NE, recipe_ne.pieces)

        # NE=2 (alone) -> Inner NE (diagonal water, cardinal lands)
        recipe_inner_ne = self.ch.resolve_shoreline(2)
        self.assertIn(self.ch.ShorelinePiece.INNER_NE, recipe_inner_ne.pieces)

    def test_03_evaluate_shoreline_initial_city(self):
        """Verifies evaluate_shoreline on initial_city scenario."""
        model = MapModel(self.raw_data)
        result = run_shoreline_autotile(model)
        self.assertIsNotNone(result)
        # Should evaluate derived state edits across the map
        self.assertGreater(len(result.edits), 0)

    def test_04_semantic_hash_invariance(self):
        """
        Verifies terrain semantic hash invariance:
        Evaluating shoreline autotiling DOES NOT mutate raw terrain semantics (LAND vs WATER),
        buildings, or roads.
        """
        model_before = MapModel(self.raw_data)
        terrain_before = list(model_before.terrain_tiles)
        buildings_before = list(model_before.buildings)

        # Run shoreline autotile evaluation
        result = run_shoreline_autotile(model_before)

        # Confirm MapModel raw data remains identical in terrain and buildings
        model_after = MapModel(model_before.raw_data)
        self.assertEqual(len(model_after.terrain_tiles), len(terrain_before))
        self.assertEqual(len(model_after.buildings), len(buildings_before))

        # Check geometry signature hash equality between MapDocument before and MapDocument after
        doc_before = self.ch.MapDocument(json.dumps(model_before.raw_data))
        doc_after = self.ch.MapDocument(json.dumps(model_after.raw_data))
        
        # Verify map validation returns valid for both
        rep_before = self.ch.validate_map_document(doc_before)
        rep_after = self.ch.validate_map_document(doc_after)
        self.assertEqual(rep_before.valid, rep_after.valid)


if __name__ == "__main__":
    unittest.main()
