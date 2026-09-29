#!/usr/bin/env python3
"""CH Character Studio Art V0.

The Studio does not animate characters itself. It owns appearance authoring and
uses the approved CH Actor / CH Blender contracts for camera, pose and depth.

Commands:
  validate-spec  validate an editable character art specification
  make-job       create a guarded CH Blender base-pass + landmarks job
  compose        combine Blender base pass + paint layers into a preview PNG
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
JOB_CONTRACT = "CH_BLENDER_AGENT_JOB_V1"
FRAME = (48, 64)
GROUND_ANCHOR = [24, 60]
DIRECTIONS = ["S", "E", "N", "W"]
ANIMATION_FRAMES = ["idle"] + [f"walk_{index:02d}" for index in range(8)]
LAYER_ORDER = [
    "silhouette",
    "skin",
    "hair",
    "face",
    "upper_clothing",
    "lower_clothing",
    "footwear",
    "accessories_back",
    "accessories_front",
    "paint_over",
    "outline",
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

    appearance = data.get("appearance") or {}
    palette = appearance.get("palette") or {}
    required_palette = ["skin", "hair", "primary", "secondary", "shoes"]
    for key in required_palette:
        value = palette.get(key)
        if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
            errors.append(f"appearance.palette.{key} must be #RRGGBB")

    layers = appearance.get("layers") or []
    names = [layer.get("name") for layer in layers if isinstance(layer, dict)]
    unknown = sorted(set(names) - set(LAYER_ORDER))
    if unknown:
        errors.append(f"unknown art layer(s): {', '.join(unknown)}")

    if errors:
        raise StudioError("; ".join(errors))
    return data


def make_job(
    spec_path: Path,
    output_path: Path,
    stage: str,
    direction: str,
    frame: str,
) -> dict:
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
        "contract": JOB_CONTRACT,
        "jobId": job_id,
        "operation": "guarded_blender_script",
        "script": "tools/ch_character_studio/blender_character_base.py",
        "qualityStage": stage,
        "args": [
            "--character-spec",
            spec_path.relative_to(REPO_ROOT).as_posix(),
            "--output",
            output_dir,
            "--direction",
            direction,
            "--frame",
            frame,
        ],
        "outputDir": output_dir,
        "expectedOutputs": [
            f"{output_dir}/base.png",
            f"{output_dir}/landmarks.json",
            f"{output_dir}/character_base_report.json",
        ],
    }
    if stage == "final":
        approval = spec.get("approval") or {}
        sha = approval.get("approvedProxySha256")
        if not approval.get("proxyReviewed") or not isinstance(sha, str) or len(sha) != 64:
            raise StudioError(
                "final requires approval.proxyReviewed=true and a 64-char approvedProxySha256"
            )
        job["approval"] = {
            "proxyReviewed": True,
            "approvedProxySha256": sha,
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
    enabled = {
        layer["name"]: layer
        for layer in spec.get("appearance", {}).get("layers", [])
        if isinstance(layer, dict) and layer.get("enabled", True)
    }
    for name in LAYER_ORDER:
        layer = enabled.get(name)
        if not layer:
            continue
        file_name = layer.get("file") or f"{name}.png"
        path = layers_dir / file_name
        if not path.is_file():
            if layer.get("required", False):
                raise StudioError(f"required layer missing: {path}")
            continue
        image = Image.open(path).convert("RGBA")
        if image.size != FRAME:
            raise StudioError(f"layer {name} must be {FRAME}, got {image.size}")
        opacity = float(layer.get("opacity", 1.0))
        opacity = max(0.0, min(1.0, opacity))
        if opacity < 1.0:
            alpha = image.getchannel("A").point(lambda p: round(p * opacity))
            image.putalpha(alpha)
        result.alpha_composite(image)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(out_path)


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_validate = sub.add_parser("validate-spec")
    p_validate.add_argument("--spec", type=Path, required=True)

    p_job = sub.add_parser("make-job")
    p_job.add_argument("--spec", type=Path, required=True)
    p_job.add_argument("--stage", choices=("preflight", "proxy", "final"), required=True)
    p_job.add_argument("--direction", choices=DIRECTIONS, default="S")
    p_job.add_argument("--frame", choices=ANIMATION_FRAMES, default="idle")
    p_job.add_argument("--out", type=Path, required=True)

    p_compose = sub.add_parser("compose")
    p_compose.add_argument("--spec", type=Path, required=True)
    p_compose.add_argument("--base", type=Path, required=True)
    p_compose.add_argument("--layers", type=Path, required=True)
    p_compose.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.cmd == "validate-spec":
            data = validate_spec((REPO_ROOT / args.spec).resolve() if not args.spec.is_absolute() else args.spec)
            emit({"contract": "CH_CHARACTER_STUDIO_VALIDATION_V0", "status": "ok", "characterId": data["characterId"]})
        elif args.cmd == "make-job":
            spec = (REPO_ROOT / args.spec).resolve() if not args.spec.is_absolute() else args.spec
            out = (REPO_ROOT / args.out).resolve() if not args.out.is_absolute() else args.out
            job = make_job(spec, out, args.stage, args.direction, args.frame)
            emit({
                "contract": "CH_CHARACTER_STUDIO_JOB_V0",
                "status": "ok",
                "pose": {"direction": args.direction, "frame": args.frame},
                "job": job,
            })
        elif args.cmd == "compose":
            spec = (REPO_ROOT / args.spec).resolve() if not args.spec.is_absolute() else args.spec
            base = (REPO_ROOT / args.base).resolve() if not args.base.is_absolute() else args.base
            layers = (REPO_ROOT / args.layers).resolve() if not args.layers.is_absolute() else args.layers
            out = (REPO_ROOT / args.out).resolve() if not args.out.is_absolute() else args.out
            compose(spec, base, layers, out)
            emit({"contract": "CH_CHARACTER_STUDIO_COMPOSE_V0", "status": "ok", "output": str(out)})
        return 0
    except StudioError as exc:
        emit({"contract": "CH_CHARACTER_STUDIO_ERROR_V0", "status": "error", "message": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
