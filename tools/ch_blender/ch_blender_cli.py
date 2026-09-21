#!/usr/bin/env python3
"""Agent-first CLI for CH Blender.

Stable machine-facing interface:
  doctor         validate the pinned Blender executable and repository contracts
  run-job        execute one CH_BLENDER_AGENT_JOB_V1 JSON job
  print-contract print the machine-readable worker contract
  cache-key      print the canonical shared GitHub cache key

Human-oriented interactive UI is intentionally out of scope.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_worker import (
    EXIT,
    JOB_CONTRACT,
    MANIFEST_PATH,
    REPORT_CONTRACT,
    REPO_ROOT,
    WorkerError,
    blender_identity,
    error_report,
    resolve_blender,
    run_job,
)


def emit(payload: dict, path: Path | None = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def cmd_doctor(args: argparse.Namespace) -> int:
    blender = resolve_blender(args.blender)
    identity = blender_identity(blender)
    payload = {
        "contract": "CH_BLENDER_DOCTOR_V1",
        "status": "ok",
        "repoRoot": str(REPO_ROOT),
        "manifest": str(MANIFEST_PATH.relative_to(REPO_ROOT)),
        "blender": identity,
        "contracts": manifest()["cityHorizonContracts"],
        "agentJobContract": JOB_CONTRACT,
        "agentReportContract": REPORT_CONTRACT,
    }
    emit(payload, Path(args.report).resolve() if args.report else None)
    return EXIT["OK"]


def cmd_run_job(args: argparse.Namespace) -> int:
    job_path = (
        (REPO_ROOT / args.job).resolve()
        if not Path(args.job).is_absolute()
        else Path(args.job).resolve()
    )
    report_path = (
        (REPO_ROOT / args.report).resolve()
        if args.report and not Path(args.report).is_absolute()
        else (Path(args.report).resolve() if args.report else None)
    )
    try:
        blender = resolve_blender(args.blender)
        payload = run_job(job_path, blender)
        emit(payload, report_path)
        return EXIT["OK"]
    except WorkerError as exc:
        payload = error_report(job_path, exc)
        emit(payload, report_path)
        return EXIT.get(exc.code, 1)


def cmd_contract(_: argparse.Namespace) -> int:
    payload = {
        "contract": JOB_CONTRACT,
        "reportContract": REPORT_CONTRACT,
        "qualityContracts": {
            "preflight": "CH_SCENE_PREFLIGHT_V1",
            "proxy": "CH_PROXY_RENDER_V1",
            "approval": "CH_PROXY_APPROVAL_V1",
            "defaultProfile": "tools/ch_blender/preflight_profiles/ch_asset_default_v1.json",
        },
        "operations": {
            "guarded_blender_script": {
                "preferredForNewAssets": True,
                "required": ["contract", "jobId", "operation", "script", "qualityStage"],
                "qualityStages": ["preflight", "proxy", "final"],
                "finalRequires": [
                    "approval.proxyReviewed=true",
                    "approval.approvedProxySha256=<64 hex chars>",
                ],
                "optional": [
                    "args",
                    "expectedOutputs",
                    "outputDir",
                    "qualityProfile",
                    "approval",
                ],
            },
            "canonical_bake": {
                "legacyForNewAgentAssets": True,
                "required": ["contract", "jobId", "operation", "assetConfig"],
                "optional": ["studioPreset", "outputDir", "postprocess"],
                "defaults": {
                    "studioPreset": "tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json",
                    "outputDir": "out/ch_blender_agent/<jobId>",
                    "postprocess": True,
                },
            },
            "blender_script": {
                "legacyUnguarded": True,
                "required": ["contract", "jobId", "operation", "script"],
                "optional": ["args", "expectedOutputs", "outputDir"],
                "defaults": {
                    "args": [],
                    "expectedOutputs": [],
                    "outputDir": "out/ch_blender_agent/<jobId>",
                },
            },
        },
        "exitCodes": EXIT,
        "binaryResolutionOrder": [
            "--blender",
            "CH_BLENDER_EXE",
            "BLENDER_EXE",
            "PATH:blender",
        ],
        "pathPolicy": "repository_workspace_only",
        "newAssetPolicy": "preflight_then_proxy_then_explicitly_approved_final",
    }
    emit(payload)
    return EXIT["OK"]


def cmd_cache_key(_: argparse.Namespace) -> int:
    m = manifest()
    version = str(m["upstream"]["tag"]).removeprefix("v")
    revision = str(m.get("cache", {}).get("revision", 1))
    emit(
        {
            "contract": "CH_BLENDER_CACHE_KEY_V1",
            "version": version,
            "key": f"ch-blender-binary-${{OS}}-${{ARCH}}-{version}-r{revision}",
        }
    )
    return EXIT["OK"]


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="ch-blender",
        description="Deterministic City Horizon Blender interface for agents",
    )
    sub = root.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--blender", default=None)
    doctor.add_argument("--report", default=None)
    doctor.set_defaults(func=cmd_doctor)

    run = sub.add_parser("run-job")
    run.add_argument("--job", required=True)
    run.add_argument("--blender", default=None)
    run.add_argument("--report", default=None)
    run.set_defaults(func=cmd_run_job)

    contract = sub.add_parser("print-contract")
    contract.set_defaults(func=cmd_contract)

    cache = sub.add_parser("cache-key")
    cache.set_defaults(func=cmd_cache_key)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.func(args)
    except WorkerError as exc:
        emit(error_report(None, exc))
        return EXIT.get(exc.code, 1)
    except Exception as exc:
        emit(
            {
                "contract": REPORT_CONTRACT,
                "status": "error",
                "error": {"code": "UNEXPECTED", "message": str(exc)},
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
