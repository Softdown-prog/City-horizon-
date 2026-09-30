#!/usr/bin/env python3
"""Deterministic worker/subagent planner for CH Character Studio.

This tool does not pretend to spawn remote agents. It creates stable, auditable
work packets that any connected agent can consume and return through the same
handoff contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDIO_DIR = REPO_ROOT / "tools/ch_character_studio"
WORKERS_PATH = STUDIO_DIR / "workers/ch_character_workers_v0.json"
HANDOFF_CONTRACT = "CH_CHARACTER_WORKER_HANDOFF_V0"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_value(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def stable_seed(base_seed: int, character_id: str, worker_id: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{character_id}:{worker_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def build_packet(worker: dict, spec: dict, seed: int) -> dict:
    character_id = str(spec.get("characterId", "character_new"))
    worker_seed = stable_seed(seed, character_id, worker["id"])
    rng = random.Random(worker_seed)
    palette_family_order = ["skin", "hair", "neutral", "vivid", "pastel", "earth", "deep", "metal", "fantasy"]
    rng.shuffle(palette_family_order)
    return {
        "contract": "CH_CHARACTER_WORK_PACKET_V0",
        "workerId": worker["id"],
        "characterId": character_id,
        "seed": worker_seed,
        "role": worker["role"],
        "inputs": worker.get("inputs", []),
        "expectedOutputs": worker.get("outputs", []),
        "mayEdit": worker.get("mayEdit", []),
        "contracts": {
            "studio": "CH_CHARACTER_STUDIO_V0",
            "spatial": "CH_CHARACTER_SPATIAL_V0",
            "palette": "CH_CHARACTER_PALETTE_V1",
            "masks": "CH_CHARACTER_COLOR_MASKS_V0",
            "heldObjects": "CH_CHARACTER_HELD_OBJECT_V0"
        },
        "deterministicHints": {
            "paletteFamilyOrder": palette_family_order,
            "randomSelectionRequiresThisSeed": worker_seed
        },
        "inputHashes": {"characterSpec": sha256_value(spec)},
        "rules": [
            "Do not modify approved actor motion or canonical ground anchor.",
            "Use repository-relative paths only.",
            "Do not use inspection camera output as runtime art.",
            "Return a CH_CHARACTER_WORKER_HANDOFF_V0 JSON handoff."
        ]
    }


def plan(spec_path: Path, seed: int, worker_id: str | None) -> dict:
    workers = read_json(WORKERS_PATH)
    spec = read_json(spec_path)
    if workers.get("contract") != "CH_CHARACTER_WORKERS_V0":
        raise RuntimeError("invalid worker profile contract")
    selected = workers.get("workers", [])
    if worker_id:
        selected = [worker for worker in selected if worker.get("id") == worker_id]
        if not selected:
            raise RuntimeError(f"unknown worker: {worker_id}")
    packets = [build_packet(worker, spec, seed) for worker in selected]
    return {
        "contract": "CH_CHARACTER_WORK_PLAN_V0",
        "characterId": spec.get("characterId"),
        "seed": seed,
        "profile": WORKERS_PATH.relative_to(REPO_ROOT).as_posix(),
        "packetOrder": [packet["workerId"] for packet in packets],
        "packets": packets,
        "planSha256": sha256_value(packets)
    }


def validate_handoff(path: Path) -> dict:
    data = read_json(path)
    errors: list[str] = []
    if data.get("contract") != HANDOFF_CONTRACT:
        errors.append(f"contract must be {HANDOFF_CONTRACT}")
    for field in ("workerId", "characterId", "seed", "inputHashes", "status", "outputs", "notes"):
        if field not in data:
            errors.append(f"missing {field}")
    if data.get("status") not in {"planned", "ready", "blocked", "complete", "failed"}:
        errors.append("invalid status")
    if errors:
        raise RuntimeError("; ".join(errors))
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--spec", type=Path, required=True)
    p_plan.add_argument("--seed", type=int, default=1337)
    p_plan.add_argument("--worker")
    p_plan.add_argument("--out", type=Path)

    p_validate = sub.add_parser("validate-handoff")
    p_validate.add_argument("--handoff", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.cmd == "plan":
            spec = args.spec if args.spec.is_absolute() else (REPO_ROOT / args.spec).resolve()
            payload = plan(spec, args.seed, args.worker)
            text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
            if args.out:
                out = args.out if args.out.is_absolute() else (REPO_ROOT / args.out).resolve()
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text, encoding="utf-8")
            sys.stdout.write(text)
        else:
            handoff = args.handoff if args.handoff.is_absolute() else (REPO_ROOT / args.handoff).resolve()
            data = validate_handoff(handoff)
            sys.stdout.write(json.dumps({"status":"ok","workerId":data["workerId"],"handoff":str(handoff)}, indent=2) + "\n")
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        sys.stdout.write(json.dumps({"status":"error","message":str(exc)}, indent=2) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
