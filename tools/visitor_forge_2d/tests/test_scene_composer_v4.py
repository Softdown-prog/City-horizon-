import json
from pathlib import Path

from visitor_forge_2d.core.scene_composer_v4 import render_scene
from visitor_forge_2d.workers import run_workers, validate_recipe


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _recipe() -> dict:
    return json.loads((EXAMPLES / "prop_rowboat_scene_v4.json").read_text(encoding="utf-8"))


def test_scene_v4_is_deterministic_and_has_critic() -> None:
    recipe = _recipe()
    first, meta1 = render_scene(recipe)
    second, meta2 = render_scene(recipe)
    assert first.mode == "RGBA" and first.size == (256, 192)
    assert first.tobytes() == second.tobytes()
    assert meta1["critic"] == meta2["critic"]
    assert "edgeComplexity" in meta1["critic"]
    assert meta1["contract"] == "CH_2D_SCENE_RECIPE_V4"


def test_scene_v4_worker_exports_visual_critic(tmp_path: Path) -> None:
    result = run_workers(EXAMPLES / "prop_rowboat_scene_v4.json", tmp_path)
    assert result["kind"] == "scene_v4"
    assert "visual_critic" in result["workers"]
    assert result["audit"]["critic"] is not None
    assert Path(result["png"]).is_file()
    assert Path(result["review"]).is_file()
    assert Path(result["isometricReview"]).is_file()


def test_scene_v4_finish_changes_v3_style() -> None:
    recipe = _recipe()
    styled, _ = render_scene(recipe)
    recipe["finish"] = {"edgeBreakupPx": 0, "surfaceVariation": 0, "brushStamps": 0, "brushOpacity": 0}
    plain, _ = render_scene(recipe)
    assert styled.tobytes() != plain.tobytes()


def test_scene_v4_rejects_unbounded_finish_and_wrong_camera() -> None:
    recipe = _recipe()
    recipe["finish"]["brushStamps"] = 10000
    try:
        render_scene(recipe)
        assert False, "unbounded finish passed"
    except ValueError as exc:
        assert "brushStamps" in str(exc)

    recipe = _recipe()
    recipe["camera"]["elevationDeg"] = 35.264
    try:
        validate_recipe(recipe)
        assert False, "wrong camera passed"
    except ValueError as exc:
        assert "CH_CAMERA_V1" in str(exc)
