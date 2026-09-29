import pytest

from visitor_forge_2d.component_gallery import (
    CONTRACT,
    get_component,
    instantiate_component,
    load_component_gallery,
    search_components,
)


def test_seed_gallery_has_declared_count_and_unique_ids() -> None:
    gallery = load_component_gallery()
    assert gallery["contract"] == CONTRACT
    assert gallery["targetCount"] >= 700
    assert gallery["currentCount"] == 192
    ids = [item["id"] for item in gallery["items"]]
    assert len(ids) == len(set(ids)) == 192


def test_gallery_has_multiple_reusable_domains() -> None:
    gallery = load_component_gallery()
    categories = {item["category"] for item in gallery["items"]}
    assert {"wood_structure", "metal_structure", "hardware", "marine", "street",
            "organic_detail", "surface_finish"}.issubset(categories)


def test_search_and_instantiate_component() -> None:
    results = search_components(family="wood_plank", tags=["bench", "plank"])
    assert len(results) == 16
    node = instantiate_component(results[0]["id"], x=12, y=18, scale=1.5)
    assert node["componentId"] == results[0]["id"]
    assert node["transform"]["translate"] == [12, 18]
    assert node["transform"]["scale"] == 1.5


def test_component_rejects_unsupported_material() -> None:
    component_id = search_components(family="marine_fitting")[0]["id"]
    with pytest.raises(ValueError, match="not supported"):
        instantiate_component(component_id, material="wood")


def test_missing_component_is_explicit() -> None:
    with pytest.raises(KeyError):
        get_component("does_not_exist")
