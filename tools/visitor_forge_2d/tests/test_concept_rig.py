from pathlib import Path

from visitor_forge_2d.character import validate_v1_character
from visitor_forge_2d.character.concept_rig import build_concept_rig
from visitor_forge_2d.character.review import frame_measurements
from visitor_forge_2d.core import LayerComposer, alpha_safe_resize, load_character_definition, load_pose


TOOL_ROOT = Path(__file__).resolve().parents[1]


def test_concept_rig_keeps_identity_and_foot_anchor(tmp_path: Path) -> None:
    assets = tmp_path / "parts"
    definition_path = tmp_path / "concept.json"
    result = build_concept_rig(
        TOOL_ROOT / "art/concepts/visitor_male_01_south_master.png", assets, definition_path,
    )
    assert len(result["parts"]) == 16  # 15 animated body parts and a fixed shadow
    assert all(Path(path).is_file() for path in result["parts"])

    definition = load_character_definition(definition_path)
    poses = [load_pose(TOOL_ROOT / f"poses/concept/south_{name}.json")
             for name in ("idle", "walk_a", "walk_b")]
    validate_v1_character(definition, poses)
    composer = LayerComposer(assets)
    frames = [alpha_safe_resize(composer.compose(definition, pose), (128, 128))
              for pose in poses]
    metrics = frame_measurements(frames, (64, 116))
    assert metrics["footRowRangePx"] <= 1
    assert all(0.025 <= change <= 0.12
               for change in metrics["changedSilhouetteFractionFromIdle"])
