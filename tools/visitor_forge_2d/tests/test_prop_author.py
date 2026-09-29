import json
from pathlib import Path

import pytest

from visitor_forge_2d.prop_author import CONTRACT, author_prop_recipe, interpret_prop_prompt, run_prop_author


def test_prop_prompt_routes_boat_pier_and_sign() -> None:
    assert interpret_prop_prompt("barco usado de madeira") == {"archetype": "rowboat", "condition": "used"}
    assert interpret_prop_prompt("píer envelhecido") == {"archetype": "pier", "condition": "weathered"}
    assert interpret_prop_prompt("placa nova") == {"archetype": "sign", "condition": "pristine"}


def test_prop_author_builds_weathered_pier_deterministically() -> None:
    brief = {"contract": CONTRACT, "id": "pier_weathered_study", "prompt": "píer de madeira envelhecido", "seed": 301}
    first, report1 = author_prop_recipe(brief)
    second, report2 = author_prop_recipe(brief)
    assert first == second
    assert report1 == report2
    assert first["contract"] == "CH_2D_SCENE_RECIPE_V4"
    assert first["camera"]["contract"] == "CH_CAMERA_V1"
    assert first["authorIntent"] == {"archetype": "pier", "condition": "weathered"}
    assert first["finish"]["brushStamps"] >= 34
    assert any(region["style"] == "plank_seams" for region in first["finishRegions"])
    assert report1["template"] == "prop_pier_scene_v4.json"
    assert report1["runtimePromotion"] is False


def test_prop_author_condition_changes_scene_without_changing_contract() -> None:
    used, _ = author_prop_recipe({"contract": CONTRACT, "id": "boat_used", "archetype": "rowboat", "condition": "used", "seed": 17})
    pristine, _ = author_prop_recipe({"contract": CONTRACT, "id": "boat_clean", "archetype": "rowboat", "condition": "pristine", "seed": 17})
    assert used["contract"] == pristine["contract"] == "CH_2D_SCENE_RECIPE_V4"
    assert pristine["finish"]["brushStamps"] <= 10
    assert pristine["finish"]["surfaceVariation"] <= used["finish"]["surfaceVariation"]


def test_prop_author_runs_pier_through_workers(tmp_path: Path) -> None:
    result = run_prop_author({"contract": CONTRACT, "id": "pier_worker_study", "archetype": "pier", "seed": 77}, tmp_path)
    assert result["status"] == "review_ready"
    assert Path(result["png"]).is_file()
    assert Path(result["review"]).is_file()
    report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    assert report["archetype"] == "pier"
    assert report["render"]["kind"] == "scene_v4"
    assert report["runtimePromotion"] is False


def test_prop_author_rejects_ambiguous_or_unsupported_requests() -> None:
    with pytest.raises(ValueError, match="multiple prop archetypes"):
        interpret_prop_prompt("barco ao lado de um píer")
    with pytest.raises(ValueError, match="unsupported prop"):
        interpret_prop_prompt("um avião")
    with pytest.raises(ValueError, match="only pristine"):
        author_prop_recipe({"contract": CONTRACT, "id": "old_sign", "archetype": "sign", "condition": "weathered"})
