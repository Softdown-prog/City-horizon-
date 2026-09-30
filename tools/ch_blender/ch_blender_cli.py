#!/usr/bin/env python3
"""Agent-first CLI for CH Blender.

Stable machine-facing interface:
  doctor         validate the pinned Blender executable and repository contracts
  validate-job   validate one job without Blender or output files
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
AUTHORING_CORE_CONTRACT_ID = "CH_AUTHORING_CORE_V1"
AUTHORING_CORE_CONTRACT_PATH = REPO_ROOT / "tools/ch_blender/contracts/ch_authoring_core_v1.json"
AUTHORING_RECIPE_CONTRACT_ID = "CH_AUTHORING_RECIPE_V1"


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


def authoring_core_contract() -> dict:
    data = json.loads(AUTHORING_CORE_CONTRACT_PATH.read_text(encoding="utf-8"))
    if data.get("contract") != AUTHORING_CORE_CONTRACT_ID:
        raise RuntimeError(f"Expected {AUTHORING_CORE_CONTRACT_ID} at {AUTHORING_CORE_CONTRACT_PATH}")
    authoring = data.get("authoring", {})
    if authoring.get("singlePhysicalModel") is not True:
        raise RuntimeError("CH_AUTHORING_CORE_V1 must require one physical model")
    if authoring.get("directionViewsFromRootRotation") is not True:
        raise RuntimeError("CH_AUTHORING_CORE_V1 must derive directions from root rotation")
    if authoring.get("preferredInterface") != AUTHORING_RECIPE_CONTRACT_ID:
        raise RuntimeError("CH_AUTHORING_CORE_V1 preferred interface must be CH_AUTHORING_RECIPE_V1")
    required = {"soft_form", "tapered_segment", "rounded_box", "curve_tube", "torus"}
    primitives = set(data.get("primitives", []))
    if not required.issubset(primitives):
        raise RuntimeError(f"CH_AUTHORING_CORE_V1 is missing primitives: {sorted(required - primitives)}")
    gate = data.get("qualityGate", {})
    if gate.get("preflight") is not True or gate.get("proxyReview") is not True or gate.get("finalAfterApproval") is not True:
        raise RuntimeError("CH_AUTHORING_CORE_V1 quality gate must require preflight, proxy review and approval")
    return data


def authoring_core_summary() -> dict:
    data = authoring_core_contract()
    return {
        "contract": data["contract"],
        "path": AUTHORING_CORE_CONTRACT_PATH.relative_to(REPO_ROOT).as_posix(),
        "preferredInterface": data["authoring"]["preferredInterface"],
        "singlePhysicalModel": data["authoring"]["singlePhysicalModel"],
        "directionViewsFromRootRotation": data["authoring"]["directionViewsFromRootRotation"],
        "primitives": data["primitives"],
        "runtimeRepresentation": data["runtimeRepresentation"],
    }


def cmd_doctor(args: argparse.Namespace) -> int:
    blender = resolve_blender(args.blender)
    identity = blender_identity(blender)
    m = manifest()
    parametric = parametric_contract_summary()
    authoring_core = authoring_core_summary()
    declared = m.get("cityHorizonContracts", {}).get("parametricAuthoring")
    if declared != PARAMETRIC_CONTRACT_ID:
        raise RuntimeError(
            f"Manifest parametricAuthoring contract {declared!r} does not match {PARAMETRIC_CONTRACT_ID}"
        )
    declared_core = m.get("cityHorizonContracts", {}).get("authoringCore")
    if declared_core != AUTHORING_CORE_CONTRACT_ID:
        raise RuntimeError(
            f"Manifest authoringCore contract {declared_core!r} does not match {AUTHORING_CORE_CONTRACT_ID}"
        )
    declared_recipe = m.get("cityHorizonContracts", {}).get("authoringRecipe")
    if declared_recipe != AUTHORING_RECIPE_CONTRACT_ID:
        raise RuntimeError(
            f"Manifest authoringRecipe contract {declared_recipe!r} does not match {AUTHORING_RECIPE_CONTRACT_ID}"
        )
    payload = {
        "contract": "CH_BLENDER_DOCTOR_V1",
        "status": "ok",
        "repoRoot": str(REPO_ROOT),
        "manifest": str(MANIFEST_PATH.relative_to(REPO_ROOT)),
        "blender": identity,
        "contracts": m["cityHorizonContracts"],
        "parametricAuthoring": parametric,
        "authoringCore": authoring_core,
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
        validate_job(job_path)
        blender = resolve_blender(args.blender)
        payload = run_job(job_path, blender)
        emit(payload, report_path)
        return EXIT["OK"]
    except WorkerError as exc:
        payload = error_report(job_path, exc)
        emit(payload, report_path)
        return EXIT.get(exc.code, 1)


def cmd_validate_job(args: argparse.Namespace) -> int:
    job_path = (REPO_ROOT / args.job).resolve() if not Path(args.job).is_absolute() else Path(args.job).resolve()
    report_path = (REPO_ROOT / args.report).resolve() if args.report and not Path(args.report).is_absolute() else (Path(args.report).resolve() if args.report else None)
    try:
        job = validate_job(job_path)
        emit({
            "contract": "CH_BLENDER_JOB_VALIDATION_V1",
            "status": "ok",
            "jobId": job["jobId"],
            "operation": job["operation"],
            "qualityStage": job.get("qualityStage"),
            "authoringRecipe": job.get("authoringRecipe"),
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
            "defaultProfile": "tools/ch_blender/preflight_profiles/ch_asset_default_v1.json",
        },
        "parametricAuthoring": parametric_contract_summary(),
        "authoringCore": authoring_core_summary(),
        "authoringRecipeContract": AUTHORING_RECIPE_CONTRACT_ID,
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
                    "authoringRecipe",
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
                "optional": ["args", "expectedOutputs", "outputDir", "authoringRecipe"],
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
