"""CH Blender parametric-authoring helpers.

This module brings the parts of mature DCC parametric workflows that make sense
for City Horizon into Blender without pretending Blender is 3ds Max.  It keeps
source geometry editable, records deterministic procedural intent, standardizes
metric scale/mapping metadata, and tracks external source provenance.  Runtime
remains pre-rendered 2D RGBA; no modifier or shader becomes an SDL dependency.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import bpy

CONTRACT_ID = "CH_PARAMETRIC_AUTHORING_V1"
CONTRACT_PATH = Path(__file__).resolve().parent / "contracts" / "ch_parametric_authoring_v1.json"


def load_contract() -> dict:
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if data.get("contract") != CONTRACT_ID:
        raise RuntimeError(f"Expected {CONTRACT_ID} at {CONTRACT_PATH}")
    return data


def configure_metric_units(scene: bpy.types.Scene) -> None:
    """Use one Blender unit per metre for authored real-world dimensions."""
    contract = load_contract()
    scene.unit_settings.system = contract["units"]["system"]
    scene.unit_settings.length_unit = contract["units"]["lengthUnit"]
    scene.unit_settings.scale_length = float(contract["units"]["blenderUnitMeters"])
    scene["chParametricContract"] = CONTRACT_ID
    scene["chUnitScaleMeters"] = float(contract["units"]["blenderUnitMeters"])


def tag_parametric_root(root: bpy.types.Object, *, authoring_mode: str = "non_destructive") -> None:
    root["chParametricContract"] = CONTRACT_ID
    root["chAuthoringMode"] = authoring_mode


def _stage_index(stage: str) -> int:
    stages = load_contract()["modifierStack"]["stageOrder"]
    if stage not in stages:
        raise ValueError(f"Unknown CH parametric stage {stage!r}; expected one of {stages}")
    return stages.index(stage)


def add_modifier_stage(
    obj: bpy.types.Object,
    *,
    modifier_type: str,
    name: str,
    stage: str,
    selection_channel: str | None = None,
) -> bpy.types.Modifier:
    """Create and tag a modifier as one ordered non-destructive authoring stage.

    `selection_channel` is normally a vertex group or named attribute.  It
    records sub-object intent even when a particular Blender modifier exposes
    the actual selector through a modifier-specific property.
    """
    stage_index = _stage_index(stage)
    tagged = [
        (int(mod.get("chStageIndex", -1)), mod.name)
        for mod in obj.modifiers
        if mod.get("chParametricContract") == CONTRACT_ID
    ]
    if tagged and stage_index < max(index for index, _ in tagged):
        raise ValueError(
            f"Modifier stage {stage!r} would precede an existing later CH stage on {obj.name!r}"
        )

    modifier = obj.modifiers.new(name=name, type=modifier_type)
    modifier["chParametricContract"] = CONTRACT_ID
    modifier["chStage"] = stage
    modifier["chStageIndex"] = stage_index
    if selection_channel:
        modifier["chSelectionChannel"] = selection_channel
    return modifier


def tag_shared_world_deformer(
    controller: bpy.types.Object,
    targets: Iterable[bpy.types.Object],
    *,
    kind: str,
) -> None:
    """Record one world-space/shared deformation relationship.

    Blender equivalents are Lattice, Geometry Nodes, or empty-driven modifier
    controls.  This metadata keeps the relation auditable across asset builders.
    """
    allowed = set(load_contract()["modifierStack"]["sharedWorldDeformers"])
    normalized = kind.upper()
    if normalized not in allowed:
        raise ValueError(f"Unsupported shared deformer {kind!r}; expected one of {sorted(allowed)}")
    controller["chParametricContract"] = CONTRACT_ID
    controller["chWorldDeformerKind"] = normalized
    target_names = sorted({target.name for target in targets})
    controller["chWorldDeformerTargets"] = json.dumps(target_names, separators=(",", ":"))


def tag_procedural_generator(
    root: bpy.types.Object,
    *,
    generator_kind: str,
    seed: int,
    parameters: dict | None = None,
) -> None:
    """Attach deterministic Forest-Pack/RailClone-style generator provenance."""
    if not isinstance(seed, int):
        raise TypeError("CH procedural seed must be an integer")
    tag_parametric_root(root)
    root["chGeneratorKind"] = generator_kind
    root["chProceduralSeed"] = seed
    if parameters:
        root["chGeneratorParameters"] = json.dumps(parameters, sort_keys=True, separators=(",", ":"))


def tag_real_world_mapping(
    datablock,
    *,
    meters_per_repeat: float,
    coordinate_space: str = "UV",
) -> None:
    """Record MapScaler-style physical texture scale without hard-coding UV size."""
    if meters_per_repeat <= 0.0:
        raise ValueError("meters_per_repeat must be > 0")
    allowed = set(load_contract()["mapping"]["preferredCoordinates"])
    coordinate_space = coordinate_space.upper()
    if coordinate_space not in allowed:
        raise ValueError(f"Unsupported mapping coordinate space {coordinate_space!r}")
    datablock["chParametricContract"] = CONTRACT_ID
    datablock["chMetersPerRepeat"] = float(meters_per_repeat)
    datablock["chMappingCoordinates"] = coordinate_space


def sha256_file(path: str | Path) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tag_source_link(
    root: bpy.types.Object,
    *,
    source_kind: str,
    source_path: str | Path,
    source_unit_scale_meters: float,
    source_sha256: str | None = None,
    reimport_policy: str | None = None,
) -> None:
    """Track external-source identity for deterministic reimport workflows.

    This is intentionally not a claim of native RVT/DWG live-link support.
    Unsupported Autodesk-native files must be converted through an approved
    interchange format before entering this Blender pipeline.
    """
    contract = load_contract()
    path = Path(source_path)
    if source_unit_scale_meters <= 0.0:
        raise ValueError("source_unit_scale_meters must be > 0")
    digest = source_sha256 or (sha256_file(path) if path.is_file() else None)
    if not digest or len(digest) != 64:
        raise ValueError("source_sha256 must be a 64-character SHA-256 digest")

    tag_parametric_root(root)
    root["chSourceKind"] = source_kind.upper()
    root["chSourcePath"] = path.as_posix()
    root["chSourceSha256"] = digest.lower()
    root["chSourceUnitScaleMeters"] = float(source_unit_scale_meters)
    root["chSourceReimportPolicy"] = (
        reimport_policy or contract["sourceLink"]["defaultReimportPolicy"]
    )


def validate_parametric_object(obj: bpy.types.Object) -> list[str]:
    """Return machine-friendly validation errors for one authored object."""
    errors: list[str] = []
    contract = load_contract()
    stages = contract["modifierStack"]["stageOrder"]
    previous = -1
    for modifier in obj.modifiers:
        if modifier.get("chParametricContract") != CONTRACT_ID:
            continue
        stage = modifier.get("chStage")
        if stage not in stages:
            errors.append(f"CH_PARAMETRIC_UNKNOWN_STAGE:{obj.name}:{modifier.name}:{stage}")
            continue
        index = stages.index(stage)
        if index < previous:
            errors.append(f"CH_PARAMETRIC_STAGE_ORDER:{obj.name}:{modifier.name}:{stage}")
        previous = index

    if obj.get("chGeneratorKind") and "chProceduralSeed" not in obj:
        errors.append(f"CH_PARAMETRIC_SEED_REQUIRED:{obj.name}")
    if obj.get("chMetersPerRepeat") is not None and float(obj["chMetersPerRepeat"]) <= 0.0:
        errors.append(f"CH_PARAMETRIC_MAPPING_SCALE:{obj.name}")
    if obj.get("chSourceKind") and len(str(obj.get("chSourceSha256", ""))) != 64:
        errors.append(f"CH_PARAMETRIC_SOURCE_HASH:{obj.name}")
    return errors
