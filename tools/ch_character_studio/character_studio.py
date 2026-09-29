#!/usr/bin/env python3
"""CH Character Studio Art V0.

Commands:
  validate-spec        validate an editable character art specification
  make-job             create a canonical guarded CH Blender base-pass job
  make-inspection-job  create a non-canonical rotatable review-camera job
  compose              combine Blender base pass + paint layers into a preview PNG
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDIO_DIR = REPO_ROOT / "tools/ch_character_studio"
MANIFEST_PATH = STUDIO_DIR / "studio_manifest.json"
SPEC_CONTRACT = "CH_CHARACTER_ART_SPEC_V0"
COLOR_MASK_CONTRACT = "CH_CHARACTER_COLOR_MASK_V0"
HAND_SOCKET_CONTRACT = "CH_CHARACTER_HAND_SOCKET_V0"
JOB_CONTRACT = "CH_BLENDER_AGENT_JOB_V1"
FRAME = (48, 64)
GROUND_ANCHOR = [24, 60]
DIRECTIONS = ["S", "E", "N", "W"]
ANIMATION_FRAMES = ["idle"] + [f"walk_{index:02d}" for index in range(8)]
HAND_SOCKETS = {"left_hand", "right_hand"}
OBJECT_DEPTHS = {"auto", "back", "front"}
MASK_BANKS = {
    "appearance": {"R": "skin", "G": "hair", "B": "appearance_accent"},
    "clothing": {"R": "primary_clothing", "G": "secondary_clothing", "B": "clothing_accent"},
    "held_object": {"R": "object_primary", "G": "object_secondary", "B": "object_accent"},
}
LAYER_ORDER = [
    "silhouette", "skin", "hair", "face", "upper_clothing", "lower_clothing",
    "footwear", "accessories_back", "accessories_front", "paint_over", "outline",
]


class StudioError(RuntimeError):
    pass


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StudioError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StudioError(f"invalid JSON: {path}: {exc}") from exc


def _is_number_pair(value: object) -> bool:
    return isinstance(value, list) and len(value) == 2 and all(isinstance(item, (int, float)) for item in value)


def validate_spec(path: Path) -> dict:
    data = read_json(path)
    errors: list[str] = []
    if data.get("contract") != SPEC_CONTRACT:
        errors.append(f"contract must be {SPEC_CONTRACT}")
    if not str(data.get("characterId", "")).strip():
        errors.append("characterId is required")
    if data.get("frame", {}).get("size") != list(FRAME):
        errors.append(f"frame.size must be {list(FRAME)}")
    if data.get("frame", {}).get("groundAnchor") != GROUND_ANCHOR:
        errors.append(f"frame.groundAnchor must be {GROUND_ANCHOR}")
    if data.get("directions") != DIRECTIONS:
        errors.append(f"directions must be {DIRECTIONS}")
    if data.get("motion", {}).get("source") != "approved_ch_actor":
        errors.append("motion.source must be approved_ch_actor")
    if data.get("motion", {}).get("allowArtToModifyPose") is not False:
        errors.append("motion.allowArtToModifyPose must be false")

    spatial = data.get("spatial")
    if spatial is not None:
        if spatial.get("contract") != "CH_CHARACTER_SPATIAL_V0":
            errors.append("spatial.contract must be CH_CHARACTER_SPATIAL_V0")
        if spatial.get("groundAnchorPx") != GROUND_ANCHOR:
            errors.append("spatial.groundAnchorPx must be [24,60]")
        footprint = spatial.get("footprint") or {}
        if footprint.get("shape") != "ellipse":
            errors.append("spatial.footprint.shape must be ellipse")
        if not _is_number_pair(footprint.get("radiusMeters")):
            errors.append("spatial.footprint.radiusMeters must be numeric [x,y]")

    appearance = data.get("appearance") or {}
    palette = appearance.get("palette") or {}
    for key in ["skin", "hair", "primary", "secondary", "shoes"]:
        value = palette.get(key)
        if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
            errors.append(f"appearance.palette.{key} must be #RRGGBB")
    names = [layer.get("name") for layer in appearance.get("layers", []) if isinstance(layer, dict)]
    unknown = sorted(set(names) - set(LAYER_ORDER))
    if unknown:
        errors.append(f"unknown art layer(s): {', '.join(unknown)}")

    color_masks = data.get("colorMasks")
    if color_masks is not None:
        if not isinstance(color_masks, dict):
            errors.append("colorMasks must be an object")
        else:
            if color_masks.get("contract") != COLOR_MASK_CONTRACT:
                errors.append(f"colorMasks.contract must be {COLOR_MASK_CONTRACT}")
            if color_masks.get("alpha") != "coverage":
                errors.append("colorMasks.alpha must be coverage")
            banks = color_masks.get("banks") or {}
            for bank_name, expected_channels in MASK_BANKS.items():
                if banks.get(bank_name) != expected_channels:
                    errors.append(f"colorMasks.banks.{bank_name} must be {expected_channels}")

    held_object = data.get("heldObject")
    if held_object is not None:
        if not isinstance(held_object, dict):
            errors.append("heldObject must be an object")
        else:
            if held_object.get("contract") != HAND_SOCKET_CONTRACT:
                errors.append(f"heldObject.contract must be {HAND_SOCKET_CONTRACT}")
            if held_object.get("socket") not in HAND_SOCKETS:
                errors.append(f"heldObject.socket must be one of {sorted(HAND_SOCKETS)}")
            if held_object.get("depth") not in OBJECT_DEPTHS:
                errors.append(f"heldObject.depth must be one of {sorted(OBJECT_DEPTHS)}")
            if not _is_number_pair(held_object.get("gripAnchor")):
                errors.append("heldObject.gripAnchor must be numeric [x,y]")
            if not _is_number_pair(held_object.get("offset")):
                errors.append("heldObject.offset must be numeric [x,y]")
            if "enabled" in held_object and not isinstance(held_object.get("enabled"), bool):
                errors.append("heldObject.enabled must be boolean")

    if errors:
        raise StudioError("; ".join(errors))
    return data


def make_job(spec_path: Path, output_path: Path, stage: str, direction: str, frame: str) -> dict:
    spec = validate_spec(spec_path)
    if stage not in {"preflight", "proxy", "final"}:
        raise StudioError("stage must be preflight, proxy or final")
    if direction not in DIRECTIONS:
        raise StudioError(f"direction must be one of {DIRECTIONS}")
    if frame not in ANIMATION_FRAMES:
        raise StudioError(f"frame must be one of {ANIMATION_FRAMES}")
    character_id = spec["characterId"]
    pose_id = f"{direction.lower()}_{frame}"
    output_dir = f"out/ch_character_studio/{character_id}/{stage}/{pose_id}"
    job_id = f"character.{character_id}.studio.{stage}.{pose_id}.001"
    job = {
        "contract": JOB_CONTRACT, "jobId": job_id, "operation": "guarded_blender_script",
        "script": "tools/ch_character_studio/blender_character_base.py", "qualityStage": stage,
        "args": ["--character-spec", spec_path.relative_to(REPO_ROOT).as_posix(), "--output", output_dir,
                 "--direction", direction, "--frame", frame, "--camera-mode", "canonical"],
        "outputDir": output_dir,
        "expectedOutputs": [f"{output_dir}/base.png", f"{output_dir}/landmarks.json", f"{output_dir}/character_base_report.json"],
    }
    if stage == "final":
        approval = spec.get("approval") or {}
        sha = approval.get("approvedProxySha256")
        if not approval.get("proxyReviewed") or not isinstance(sha, str) or len(sha) != 64:
            raise StudioError("final requires approval.proxyReviewed=true and a 64-char approvedProxySha256")
        job["approval"] = {"proxyReviewed": True, "approvedProxySha256": sha}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    return job


def make_inspection_job(spec_path: Path, output_path: Path, direction: str, frame: str, yaw: float, pitch: float, ortho_scale: float, resolution_scale: int) -> dict:
    spec = validate_spec(spec_path)
    if direction not in DIRECTIONS or frame not in ANIMATION_FRAMES:
        raise StudioError("invalid direction/frame for inspection")
    if not -360.0 <= yaw <= 360.0:
        raise StudioError("inspection yaw must be between -360 and 360")
    if not 5.0 <= pitch <= 80.0:
        raise StudioError("inspection pitch must be between 5 and 80")
    if not 1.2 <= ortho_scale <= 4.0:
        raise StudioError("inspection ortho scale must be between 1.2 and 4.0")
    if resolution_scale not in {1, 2, 3, 4, 6, 8}:
        raise StudioError("inspection resolution scale must be 1,2,3,4,6 or 8")
    character_id = spec["characterId"]
    view_id = f"yaw{yaw:g}_pitch{pitch:g}_zoom{ortho_scale:g}".replace("-", "m").replace(".", "p")
    output_dir = f"out/ch_character_studio/{character_id}/inspection/{direction.lower()}_{frame}/{view_id}"
    job = {
        "contract": JOB_CONTRACT,
        "jobId": f"character.{character_id}.inspection.{direction.lower()}.{frame}.{view_id}.001",
        "operation": "guarded_blender_script",
        "script": "tools/ch_character_studio/blender_character_base.py",
        "qualityStage": "proxy",
        "args": [
            "--character-spec", spec_path.relative_to(REPO_ROOT).as_posix(), "--output", output_dir,
            "--direction", direction, "--frame", frame, "--camera-mode", "inspection",
            "--inspection-yaw", str(yaw), "--inspection-pitch", str(pitch),
            "--inspection-ortho-scale", str(ortho_scale), "--inspection-resolution-scale", str(resolution_scale)
        ],
        "outputDir": output_dir,
        "expectedOutputs": [f"{output_dir}/inspection.png", f"{output_dir}/landmarks.json", f"{output_dir}/character_base_report.json"],
        "metadata": {"runtimeExportAllowed": False, "purpose": "agent_visual_inspection_only"}
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    return job


def compose(spec_path: Path, base_path: Path, layers_dir: Path, out_path: Path) -> None:
    spec = validate_spec(spec_path)
    base = Image.open(base_path).convert("RGBA")
    if base.size != FRAME:
        raise StudioError(f"base image must be {FRAME}, got {base.size}")
    result = base.copy()
    enabled = {layer["name"]: layer for layer in spec.get("appearance", {}).get("layers", []) if isinstance(layer, dict) and layer.get("enabled", True)}
    for name in LAYER_ORDER:
        layer = enabled.get(name)
        if not layer:
            continue
        path = layers_dir / (layer.get("file") or f"{name}.png")
        if not path.is_file():
            if layer.get("required", False):
                raise StudioError(f"required layer missing: {path}")
            continue
        image = Image.open(path).convert("RGBA")
        if image.size != FRAME:
            raise StudioError(f"layer {name} must be {FRAME}, got {image.size}")
        opacity = max(0.0, min(1.0, float(layer.get("opacity", 1.0))))
        if opacity < 1.0:
            image.putalpha(image.getchannel("A").point(lambda p: round(p * opacity)))
        result.alpha_composite(image)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(out_path)


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_validate = sub.add_parser("validate-spec"); p_validate.add_argument("--spec", type=Path, required=True)
    p_job = sub.add_parser("make-job")
    p_job.add_argument("--spec", type=Path, required=True); p_job.add_argument("--stage", choices=("preflight", "proxy", "final"), required=True)
    p_job.add_argument("--direction", choices=DIRECTIONS, default="S"); p_job.add_argument("--frame", choices=ANIMATION_FRAMES, default="idle"); p_job.add_argument("--out", type=Path, required=True)
    p_inspect = sub.add_parser("make-inspection-job")
    p_inspect.add_argument("--spec", type=Path, required=True); p_inspect.add_argument("--direction", choices=DIRECTIONS, default="S"); p_inspect.add_argument("--frame", choices=ANIMATION_FRAMES, default="idle")
    p_inspect.add_argument("--yaw", type=float, default=45.0); p_inspect.add_argument("--pitch", type=float, default=30.0); p_inspect.add_argument("--ortho-scale", type=float, default=2.05); p_inspect.add_argument("--resolution-scale", type=int, default=4); p_inspect.add_argument("--out", type=Path, required=True)
    p_compose = sub.add_parser("compose"); p_compose.add_argument("--spec", type=Path, required=True); p_compose.add_argument("--base", type=Path, required=True); p_compose.add_argument("--layers", type=Path, required=True); p_compose.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.cmd == "validate-spec":
            data = validate_spec((REPO_ROOT / args.spec).resolve() if not args.spec.is_absolute() else args.spec)
            emit({"contract":"CH_CHARACTER_STUDIO_VALIDATION_V0","status":"ok","characterId":data["characterId"]})
        elif args.cmd == "make-job":
            spec = (REPO_ROOT / args.spec).resolve() if not args.spec.is_absolute() else args.spec; out = (REPO_ROOT / args.out).resolve() if not args.out.is_absolute() else args.out
            emit({"contract":"CH_CHARACTER_STUDIO_JOB_V0","status":"ok","job":make_job(spec,out,args.stage,args.direction,args.frame)})
        elif args.cmd == "make-inspection-job":
            spec = (REPO_ROOT / args.spec).resolve() if not args.spec.is_absolute() else args.spec; out = (REPO_ROOT / args.out).resolve() if not args.out.is_absolute() else args.out
            emit({"contract":"CH_CHARACTER_STUDIO_INSPECTION_JOB_V0","status":"ok","job":make_inspection_job(spec,out,args.direction,args.frame,args.yaw,args.pitch,args.ortho_scale,args.resolution_scale)})
        elif args.cmd == "compose":
            spec = (REPO_ROOT / args.spec).resolve() if not args.spec.is_absolute() else args.spec; base = (REPO_ROOT / args.base).resolve() if not args.base.is_absolute() else args.base; layers = (REPO_ROOT / args.layers).resolve() if not args.layers.is_absolute() else args.layers; out = (REPO_ROOT / args.out).resolve() if not args.out.is_absolute() else args.out
            compose(spec, base, layers, out); emit({"contract":"CH_CHARACTER_STUDIO_COMPOSE_V0","status":"ok","output":str(out)})
        return 0
    except StudioError as exc:
        emit({"contract":"CH_CHARACTER_STUDIO_ERROR_V0","status":"error","message":str(exc)}); return 2


if __name__ == "__main__":
    raise SystemExit(main())
