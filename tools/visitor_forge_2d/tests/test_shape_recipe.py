import json
from pathlib import Path

from PIL import Image

from visitor_forge_2d.core.shape_recipe import export_shape_recipe, render_shape_recipe


def _recipe() -> dict:
    return {
        "contract": "CH_2D_SHAPE_RECIPE_V1", "id": "test_sign", "canvas": [32, 32],
        "anchor": [16, 30], "layers": [
            {"name": "panel", "fill": {"top": "#BBDDAA", "bottom": "#335544"},
             "shapes": [{"type": "rounded_rect", "box": [4, 4, 28, 26], "radius": 2},
                        {"type": "ellipse", "box": [12, 10, 20, 18], "operation": "erase"}],
             "shadow": {"offset": [1, 1], "blur": 0, "opacity": 0.4}},
            {"name": "icon", "fill": {"top": "#FFEABB"},
             "shapes": [{"type": "polygon", "points": [[6, 19], [9, 18], [8, 22]]},
                        {"type": "quadratic", "points": [[22, 20], [24, 17], [27, 19]], "width": 1}]},
        ],
    }


def test_shape_recipe_renders_transparent_prop_and_review(tmp_path: Path) -> None:
    recipe = _recipe()
    frame, metadata = render_shape_recipe(recipe)
    assert frame.mode == "RGBA" and frame.size == (32, 32)
    assert frame.getpixel((0, 0))[3] == 0
    assert frame.getpixel((16, 14))[3] == 0  # erased opening
    assert frame.getpixel((16, 6))[3] > 200
    assert frame.getpixel((16, 24))[3] > 200
    assert frame.getpixel((16, 6)) != frame.getpixel((16, 24))  # painted gradient
    assert metadata["anchor"] == [16.0, 30.0]
    assert metadata["runtimePromotion"] is False

    path = tmp_path / "sign.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    result = export_shape_recipe(path, tmp_path / "out")
    first_export = Path(result["png"]).read_bytes()
    export_shape_recipe(path, tmp_path / "out")
    assert Path(result["png"]).read_bytes() == first_export
    with Image.open(result["review"]) as board:
        assert board.size == (32 * 3 + 48, 32 * 2 + 40)
    assert json.loads(Path(result["metadata"]).read_text())["artApproved"] is False


def test_shape_recipe_rejects_invalid_palette_and_geometry() -> None:
    recipe = _recipe()
    recipe["layers"][0]["fill"]["top"] = "green"
    try:
        render_shape_recipe(recipe)
        assert False, "invalid color accepted"
    except ValueError as exc:
        assert "fill.top" in str(exc)
    recipe["layers"][0]["fill"]["top"] = "#BBDDAA"
    recipe["layers"][0]["shapes"][0]["box"] = [12, 8, 4, 20]
    try:
        render_shape_recipe(recipe)
        assert False, "invalid box accepted"
    except ValueError as exc:
        assert "x0<x1" in str(exc)
