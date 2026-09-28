import json
from pathlib import Path

import pytest

from visitor_forge_2d.art_author import CONTRACT, author_recipe, interpret_prompt, run_art_author


def test_author_round_trip_from_portuguese_intent(tmp_path: Path) -> None:
    brief = {"contract": CONTRACT, "id": "autumn_tree_case",
             "prompt": "árvore folhosa de outono, copa arredondada e densa"}
    first, report = author_recipe(brief)
    second, _ = author_recipe(brief)
    assert first == second
    assert first["camera"]["contract"] == "CH_CAMERA_V1"
    assert first["broadleafStructure"]["layout"] == "continuous"
    assert first["broadleafStructure"]["masses"] == 59
    assert report["artApproved"] is False

    result = run_art_author(brief, tmp_path)
    saved = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    assert Path(result["png"]).is_file()
    assert Path(result["isometricReview"]).is_file()
    assert saved["status"] == "review_ready"
    assert saved["critique"]["status"] == "human_visual_review_required"
    assert saved["render"]["pngSha256"]
    assert saved["artApproved"] is False


def test_author_routes_other_families_without_guessing() -> None:
    for subject, contract in (("conifer", "CH_2D_ORGANIC_SCENERY_V1"),
                              ("flower_bed", "CH_2D_ORGANIC_SCENERY_V1"),
                              ("sign", "CH_2D_SHAPE_RECIPE_V1")):
        recipe, _ = author_recipe({"contract": CONTRACT, "id": f"study_{subject}", "subject": subject})
        assert recipe["contract"] == contract
    assert interpret_prompt("um pinheiro alto") == {"subject": "conifer", "silhouette": "tall"}
    custom, _ = author_recipe({"contract": CONTRACT, "id": "custom_tree", "subject": "custom",
                               "template": "park_tree_broadleaf_early_autumn_v1.json",
                               "recipeUpdates": {"broadleafStructure": {"masses": 52}}})
    assert custom["broadleafStructure"]["masses"] == 52


def test_organic_styles_choose_distinct_canopies_and_named_palettes() -> None:
    oiti, _ = author_recipe({"contract": CONTRACT, "id": "oiti_study",
                             "prompt": "oiti de copa fechada, verde fresco", "seed": 11})
    angico, _ = author_recipe({"contract": CONTRACT, "id": "angico_study",
                               "prompt": "angico de copa aberta, verde profundo", "seed": 11})
    assert oiti["broadleafStructure"]["profile"] == "domed"
    assert angico["broadleafStructure"]["profile"] == "branching"
    assert oiti["palette"]["highlight"] != angico["palette"]["highlight"]
    assert oiti["camera"] == angico["camera"]
    with pytest.raises(ValueError, match="unknown organic palette"):
        author_recipe({"contract": CONTRACT, "id": "bad_palette", "subject": "broadleaf",
                       "palette": "neon"})


def test_unknown_subject_and_protected_contract_are_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        author_recipe({"contract": CONTRACT, "id": "rocket", "prompt": "uma nave espacial"})
    with pytest.raises(ValueError, match="frozen"):
        author_recipe({"contract": CONTRACT, "id": "edited_sign", "subject": "custom",
                       "template": "park_wayfinding_sign.json",
                       "recipeUpdates": {"camera": {"contract": "wrong"}}})
    with pytest.raises(ValueError, match="filename"):
        author_recipe({"contract": CONTRACT, "id": "escape", "subject": "custom", "template": "../escape.json"})
