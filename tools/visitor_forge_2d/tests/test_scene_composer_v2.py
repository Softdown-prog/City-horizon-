import json
from pathlib import Path

from visitor_forge_2d.core.scene_composer_v2 import render_scene
from visitor_forge_2d.workers import run_workers, validate_recipe


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _recipe() -> dict:
    return json.loads((EXAMPLES / "prop_rowboat_scene_v2.json").read_text(encoding="utf-8"))


def test_scene_v2_is_deterministic_and_carries_lighting() -> None:
    recipe = _recipe()
    first, first_meta = render_scene(recipe)
    second, second_meta = render_scene(recipe)
    assert first.mode == "RGBA" and first.size == (256, 192)
    assert first.tobytes() == second.tobytes()
    assert first_meta["bounds"] == second_meta["bounds"]
    assert first_meta["lighting"]["direction"] == [-1, -1]


def test_scene_v2_worker_exports_review(tmp_path: Path) -> None:
    source = EXAMPLES / "prop_rowboat_scene_v2.json"
    result = run_workers(source, tmp_path)
    assert result["kind"] == "scene_v2"
    assert Path(result["png"]).is_file()
    assert Path(result["review"]).is_file()
    assert Path(result["isometricReview"]).is_file()
    assert result["audit"]["alpha"] == "RGBA"


def test_scene_v2_rejects_unknown_material() -> None:
    recipe = _recipe()
    recipe["layers"][1]["material"]["type"] = "magic_plastic"
    try:
        render_scene(recipe)
        assert False, "unknown material passed"
    except ValueError as exc:
        assert "type must be one of" in str(exc)


def test_scene_v2_still_requires_ch_camera() -> None:
    recipe = _recipe()
    recipe["camera"]["tile"] = [64, 64]
    try:
        validate_recipe(recipe)
        assert False, "wrong camera passed"
    except ValueError as exc:
        assert "CH_CAMERA_V1" in str(exc)
