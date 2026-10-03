#!/usr/bin/env python3
"""Agent-first CLI for CH Blender.

Stable machine-facing interface:
  doctor         validate the pinned Blender executable and repository contracts
  validate-job   validate one job without Blender or output files
  validate-jobs  validate many jobs (default: all queued jobs) and report every failure
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
    validate_job,
)

PARAMETRIC_CONTRACT_ID = "CH_PARAMETRIC_AUTHORING_V1"
PARAMETRIC_CONTRACT_PATH = REPO_ROOT / "tools/ch_blender/contracts/ch_parametric_authoring_v1.json"


def emit(payload: dict, path: Path | None = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def parametric_contract() -> dict:
    data = json.loads(PARAMETRIC_CONTRACT_PATH.read_text(encoding="utf-8"))
    if data.get("contract") != PARAMETRIC_CONTRACT_ID:
        raise RuntimeError(f"Expected {PARAMETRIC_CONTRACT_ID} at {PARAMETRIC_CONTRACT_PATH}")
    units = data.get("units", {})
    if units.get("system") != "METRIC" or float(units.get("blenderUnitMeters", 0.0)) != 1.0:
        raise RuntimeError("CH_PARAMETRIC_AUTHORING_V1 must use METRIC units at 1 Blender unit = 1 metre")
    stage_order = data.get("modifierStack", {}).get("stageOrder", [])
    expected_stages = ["source", "shape", "deform", "surface", "uv", "detail", "finalize"]
    if stage_order != expected_stages:
        raise RuntimeError(f"Unexpected CH parametric modifier stage order: {stage_order}")
    if not data.get("proceduralSystems", {}).get("deterministicSeedRequired", False):
        raise RuntimeError("CH parametric procedural systems must require deterministic seeds")
    if data.get("sourceLink", {}).get("nativeDynamicAutodeskLink") is not False:
        raise RuntimeError("CH Blender must not claim native Autodesk RVT/DWG dynamic-link support")
    if not data.get("quality", {}).get("authoringSourceMustRemainEditable", False):
        raise RuntimeError("CH parametric authoring source must remain editable")
    return data


def parametric_contract_summary() -> dict:
    data = parametric_contract()
    return {
        "contract": data["contract"],
        "path": PARAMETRIC_CONTRACT_PATH.relative_to(REPO_ROOT).as_posix(),
        "metricUnitMeters": data["units"]["blenderUnitMeters"],
        "modifierStageOrder": data["modifierStack"]["stageOrder"],
        "deterministicProceduralSeeds": data["proceduralSystems"]["deterministicSeedRequired"],
        "trackedSourceReimport": data["sourceLink"]["supportedPolicy"],
        "nativeAutodeskDynamicLink": data["sourceLink"]["nativeDynamicAutodeskLink"],
        "runtimeRepresentation": data["runtimeRepresentation"],
    }


def cmd_doctor(args: argparse.Namespace) -> int:
    blender = resolve_blender(args.blender)
    identity = blender_identity(blender)
    m = manifest()
    parametric = parametric_contract_summary()
    declared = m.get("cityHorizonContracts", {}).get("parametricAuthoring")
    if declared != PARAMETRIC_CONTRACT_ID:
        raise RuntimeError(
            f"Manifest parametricAuthoring contract {declared!r} does not match {PARAMETRIC_CONTRACT_ID}"
        )
    payload = {
        "contract": "CH_BLENDER_DOCTOR_V1",
        "status": "ok",
        "repoRoot": str(REPO_ROOT),
        "manifest": str(MANIFEST_PATH.relative_to(REPO_ROOT)),
        "blender": identity,
        "contracts": m["cityHorizonContracts"],
        "parametricAuthoring": parametric,
        "agentJobContract": JOB_CONTRACT,
        "agentReportContract": REPORT_CONTRACT,
    }
    emit(payload, Path(args.report).resolve() if args.report else None)
    return EXIT["OK"]


def _resolve_path(value: str | None) -> Path | None:
    """Resolve a CLI path argument; relative paths are anchored at the repository root."""
    if not value:
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def cmd_run_job(args: argparse.Namespace) -> int:
    job_path = _resolve_path(args.job)
    report_path = _resolve_path(args.report)
    try:
        validate_job(job_path)
        blender = resolve_blender(args.blender)
        payload = run_job(job_path, blender)
        emit(payload, report_path)
        return EXIT["OK"]
    except WorkerError as exc:
        payload = error_report(job_path, exc)
        emit(payload, report_path)
        return EXIT.get(exc.code, 1)


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def cmd_validate_jobs(args: argparse.Namespace) -> int:
    """Validate many jobs without Blender; every job is checked even if earlier ones fail."""
    if args.job:
        paths = [_resolve_path(value) for value in args.job]
    else:
        root = _resolve_path(args.dir)
        paths = sorted(root.glob("*.job.json")) if root and root.is_dir() else []
    report_path = _resolve_path(args.report)
    if not paths:
        emit({
            "contract": "CH_BLENDER_JOB_BATCH_VALIDATION_V1",
            "status": "error",
            "error": {"code": "JOB_INVALID", "message": "no job files found to validate"},
        }, report_path)
        return EXIT["JOB_INVALID"]
    results, failures = [], []
    for path in paths:
        try:
            job = validate_job(path)
            results.append({
                "job": _display_path(path),
                "status": "ok",
                "jobId": job["jobId"],
                "operation": job["operation"],
                "qualityStage": job.get("qualityStage"),
            })
        except WorkerError as exc:
            failures.append(exc.code)
            results.append({
                "job": _display_path(path),
                "status": "error",
                "error": {"code": exc.code, "message": str(exc), "details": exc.details},
            })
    emit({
        "contract": "CH_BLENDER_JOB_BATCH_VALIDATION_V1",
        "status": "error" if failures else "ok",
        "total": len(results),
        "valid": len(results) - len(failures),
        "invalid": len(failures),
        "results": results,
    }, report_path)
    return EXIT.get(failures[0], 1) if failures else EXIT["OK"]


def cmd_validate_job(args: argparse.Namespace) -> int:
    job_path = _resolve_path(args.job)
    report_path = _resolve_path(args.report)
    try:
        job = validate_job(job_path)
        emit({
            "contract": "CH_BLENDER_JOB_VALIDATION_V1",
            "status": "ok",
            "jobId": job["jobId"],
            "operation": job["operation"],
            "qualityStage": job.get("qualityStage"),
            "job": job_path.relative_to(REPO_ROOT).as_posix(),
        }, report_path)
        return EXIT["OK"]
    except WorkerError as exc:
        emit(error_report(job_path, exc), report_path)
        return EXIT.get(exc.code, 1)


def cmd_contract(_: argparse.Namespace) -> int:
    payload = {
        "contract": JOB_CONTRACT,
        "reportContract": REPORT_CONTRACT,
        "qualityContracts": {
            "preflight": "CH_SCENE_PREFLIGHT_V1",
            "proxy": "CH_PROXY_RENDER_V1",
            "approval": "CH_PROXY_APPROVAL_V1",
            "assetRequirements": "CH_ASSET_REQUIREMENTS_V1",
            "pixelReview": "CH_PROXY_PIXEL_REVIEW_V1",
            "defaultProfile": "tools/ch_blender/preflight_profiles/ch_asset_default_v1.json",
        },
        "parametricAuthoring": parametric_contract_summary(),
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
                    "assetRequirements",
                ],
                "sourceReviewBinding": "approval.sourceFingerprint from the reviewed proxy qualityGate",
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

    validate = sub.add_parser("validate-job", help="Check a job without Blender or output files")
    validate.add_argument("--job", required=True)
    validate.add_argument("--report", default=None)
    validate.set_defaults(func=cmd_validate_job)

    validate_many = sub.add_parser(
        "validate-jobs",
        help="Check many jobs without Blender (default: every tools/ch_blender/jobs/*.job.json)",
    )
    validate_many.add_argument("--job", action="append", default=None,
                               help="Job file to check; repeatable. Overrides --dir.")
    validate_many.add_argument("--dir", default="tools/ch_blender/jobs")
    validate_many.add_argument("--report", default=None)
    validate_many.set_defaults(func=cmd_validate_jobs)

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
