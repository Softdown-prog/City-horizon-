from pathlib import Path

import pytest

from visitor_forge_2d.component_gallery import (
    DEFAULT_GALLERY,
    get_component,
    instantiate_component,
    load_component_gallery,
    search_components,
)


def test_gallery_second_batch_reaches_512_unique_items() -> None:
    gallery = load_component_gallery(DEFAULT_GALLERY)
    assert gallery["targetCount"] == 700
    assert gallery["currentCount"] == 512
    assert gallery["generation"]["familyCount"] == 32
    assert len(gallery["items"]) == 512
    assert len({item["id"] for item in gallery["items"]}) == 512


def test_every_family_expands_to_16_components() -> None:
    gallery = load_component_gallery(DEFAULT_GALLERY)
    counts = {}
    for item in gallery["items"]:
        counts[item["family"]] = counts.get(item["family"], 0) + 1
    assert set(counts) == set(gallery["familyDefinitions"])
    assert all(count == 16 for count in counts.values())


def test_new_hardware_marine_street_and_signage_families_are_searchable() -> None:
    assert len(search_components(family="washer_nut")) == 16
    assert len(search_components(family="dock_bumper")) == 16
    assert len(search_components(family="bench_support")) == 16
    assert len(search_components(family="sign_panel")) == 16
    marine = search_components(category="marine")
    assert {item["family"] for item in marine} >= {"marine_fitting", "ladder_segment", "oar_paddle", "boat_rib", "dock_bumper"}


def test_component_instantiation_keeps_material_guardrails() -> None:
    item = get_component("oar_paddle_oar_md_000")
    assert item["sizePx"] == [42, 5]
    node = instantiate_component(item["id"], x=12, y=18, scale=1.5, material="wood")
    assert node["sizePx"] == [63.0, 7.5]
    assert node["transform"]["translate"] == [12, 18]
    with pytest.raises(ValueError, match="not supported"):
        instantiate_component(item["id"], material="stone")
