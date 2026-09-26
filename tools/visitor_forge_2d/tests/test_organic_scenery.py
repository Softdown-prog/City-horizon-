import json
from pathlib import Path

from PIL import Image

from visitor_forge_2d.core.organic_scenery import export, render


def _recipe() -> dict:
    return {
        "contract": "CH_2D_ORGANIC_SCENERY_V1",
        "id": "test_pine",
        "canvas": [192, 256],
        "anchor": [96, 239],
        "seed": 7,
        "camera": {"contract": "CH_CAMERA_V1", "tile": [128, 64]},
        "palette": {
            "ground_shadow": "#17271F", "trunk_top": "#B87948", "trunk_bottom": "#6E4128",
            "trunk_light": "#DCA066", "back_top": "#245540", "back_bottom": "#10342B",
            "mid_top": "#4E855F", "mid_bottom": "#235440", "front_top": "#67A071",
            "front_bottom": "#326A50", "highlight": "#ADD18A", "occlusion": "#123B30"
        },
        "tiers": [
            {"y": 34, "span": 22, "thickness": 16, "skew": 0},
            {"y": 72, "span": 40, "thickness": 21, "skew": -1},
            {"y": 116, "span": 58, "thickness": 25, "skew": 1},
            {"y": 166, "span": 74, "thickness": 28, "skew": -1},
            {"y": 201, "span": 82, "thickness": 27, "skew": 0}
        ]
    }


def test_organic_scenery_is_deterministic_and_camera_gated(tmp_path: Path) -> None:
    recipe = _recipe()
    first, metadata = render(recipe)
    second, _ = render(recipe)
    assert first.tobytes() == second.tobytes()
    assert first.mode == "RGBA" and first.size == (192, 256)
    assert metadata["camera"]["contract"] == "CH_CAMERA_V1"
    assert metadata["anchor"] == [96, 239]

    source = tmp_path / "pine.json"
    source.write_text(json.dumps(recipe), encoding="utf-8")
    result = export(source, tmp_path / "out")
    with Image.open(result["isometricReview"]) as review:
        assert review.size == (768, 480)


def test_canonical_pine_stays_above_minimum_opaque_height() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source = project_root / "examples" / "pine_tree_organic_v1.json"
    recipe = json.loads(source.read_text(encoding="utf-8"))
    frame, _ = render(recipe)
    bounds = frame.getchannel("A").getbbox()
    assert bounds is not None
    opaque_height = bounds[3] - bounds[1]
    minimum = int(recipe.get("validation", {}).get("minimumOpaqueHeightPx", 200))
    assert minimum >= 200
    assert opaque_height >= minimum, f"canonical pine opaque height {opaque_height}px is below {minimum}px"


def test_organic_scenery_rejects_wrong_camera() -> None:
    recipe = _recipe()
    recipe["camera"]["tile"] = [64, 64]
    try:
        render(recipe)
        assert False, "noncanonical camera tile accepted"
    except ValueError as exc:
        assert "128x64" in str(exc)


def test_broadleaf_crown_is_deterministic_and_differs_from_conifer(tmp_path: Path) -> None:
    """crownStyle:broadleaf must render, be deterministic, and produce a distinct
    silhouette from the same recipe rendered as a conifer."""
    recipe = _recipe()
    recipe["crownStyle"] = "broadleaf"

    first, meta_first = render(recipe)
    second, _ = render(recipe)
    assert first.tobytes() == second.tobytes(), "broadleaf render is not deterministic"
    assert first.mode == "RGBA" and first.size == (192, 256)
    assert meta_first["crownStyle"] == "broadleaf"

    # The conifer and broadleaf crowns occupy different regions — pixel counts
    # in the upper quarter of the canvas differ because conifers are narrow at
    # the top while broadleaf clusters span more of the width at mid-crown.
    conifer_recipe = dict(recipe)
    conifer_recipe["crownStyle"] = "conifer"
    conifer_frame, conifer_meta = render(conifer_recipe)
    assert conifer_meta["crownStyle"] == "conifer"
    assert first.tobytes() != conifer_frame.tobytes(), (
        "broadleaf and conifer produced identical pixels; crown dispatch is broken"
    )

    # Export round-trip: isometric review file must be created.
    source = tmp_path / "broadleaf.json"
    source.write_text(json.dumps(recipe), encoding="utf-8")
    result = export(source, tmp_path / "out")
    with Image.open(result["isometricReview"]) as review:
        assert review.size == (768, 480)


def test_organic_scenery_rejects_unknown_crown_style() -> None:
    recipe = _recipe()
    recipe["crownStyle"] = "mushroom"
    try:
        render(recipe)
        assert False, "unknown crownStyle accepted"
    except ValueError as exc:
        assert "crownStyle" in str(exc)
        assert "mushroom" in str(exc)
