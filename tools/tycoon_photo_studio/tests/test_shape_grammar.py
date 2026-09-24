"""Preflight checks for the procedural 3D source expander (no Blender needed)."""

import copy
import unittest

from tools.tycoon_photo_studio.generate_shape_grammar_asset import expand


def valid_grammar():
    return {
        "contract": "CITY_HORIZON_SHAPE_GRAMMAR_V1",
        "assetId": "test_building",
        "seed": 42,
        "footprint": {"widthTiles": 2, "depthTiles": 2},
        "mass": {"width": 4.5, "depth": 4.5, "floorHeight": 1.2, "floorCount": {"min": 2, "max": 3}},
        "materials": {"wallPalette": ["wall"], "trim": "trim", "glass": "glass", "roof": "roof", "door": "door"},
        "materialDefinitions": {name: {} for name in ("wall", "trim", "glass", "roof", "door")},
        "grammar": {"vertical": [{"height": 1.3}, {"height": 0.25}], "facades": {"residential": {"patternChoices": [["window", "balcony", "wall"]], "moduleWidth": 0.8}}},
        "constraints": {"balconyMaxPerFacade": 1},
        "roofProps": {"maxCount": 0},
    }


class ShapeGrammarTests(unittest.TestCase):
    def test_expansion_is_deterministic_and_allows_zero_roof_props(self):
        grammar = valid_grammar()
        first = expand(grammar)
        self.assertEqual(first, expand(grammar))
        self.assertFalse(any(part["name"].startswith("RoofProp_") for part in first["parts"]))
        self.assertEqual(first["footprint"]["occupiedCells"], [[0, 0], [1, 0], [0, 1], [1, 1]])

    def test_rejects_invalid_geometry_before_blender(self):
        for section, key, value in (
            ("mass", "width", -1),
            ("mass", "depth", float("nan")),
            ("mass", "floorHeight", 0),
            ("footprint", "widthTiles", 1.5),
            ("roofProps", "maxCount", -1),
        ):
            with self.subTest(section=section, key=key, value=value):
                grammar = copy.deepcopy(valid_grammar())
                grammar[section][key] = value
                with self.assertRaises(ValueError):
                    expand(grammar)

    def test_rejects_empty_facade_patterns(self):
        grammar = valid_grammar()
        grammar["grammar"]["facades"]["residential"]["patternChoices"] = [[]]
        with self.assertRaisesRegex(ValueError, "patternChoices"):
            expand(grammar)


if __name__ == "__main__":
    unittest.main()
