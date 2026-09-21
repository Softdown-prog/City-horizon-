#!/usr/bin/env python3
"""Deterministic worker for AI-agent driven City Horizon Blender jobs.

This module owns orchestration only. Scene/render logic stays in Blender-side
authoring tools. New agent-authored Blender scripts should use the guarded
quality-stage operation so expensive final bakes cannot happen before preflight
and proxy review.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "tools/ch_blender/ch_blender_manifest.json"
BUILD_SCENE = REPO_ROOT / "tools/tycoon_photo_studio/build_scene.py"
POSTPROCESS = REPO_ROOT / "tools/tycoon_photo_studio/postprocess.py"
DEFAULT_STUDIO = REPO_ROOT / "tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json"
DEFAULT_PREFLIGHT_PROFILE = REPO_ROOT / "tools/ch_blender/preflight_profiles/ch_asset_default_v1.json"

JOB_CONTRACT = "CH_BLENDER_AGENT_JOB_V1"
REPORT_CONTRACT = "CH_BLENDER_AGENT_REPORT_V1"

EXIT = {
    "OK": 0,
    "JOB_INVALID": 10,
    "CONTRACT_MISMATCH": 11,
    "BLENDER_NOT_FOUND": 12,
    "BLENDER_VERSION_MISMATCH": 13,
    "QUALITY_GATE_REQUIRED": 14,
    "BLENDER_FAILED": 20,
    "POSTPROCESS_FAILED": 21,
    "EXPECTED_OUTPUT_MISSING": 22,
}


class WorkerError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise WorkerError("JOB_INVALID", f"Cannot read JSON: {path}", {"error": str(exc)}) from exc
    if not isinstance(value, dict):
        raise WorkerError("JOB_INVALID", f"JSON root must be an object: {path}")
    return value


def _manifest() -> dict[str, Any]:
    return _load_json(MANIFEST_PATH)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _repo_path(value: str, *, must_exist: bool = True) -> Path:
    path = (REPO_ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise WorkerError(
            "JOB_INVALID",
            "Job paths must remain inside the repository workspace",
            {"path": str(path)},
        ) from exc
    if must_exist and not path.exists():
        raise WorkerError("JOB_INVALID", "Required path does not exist", {"path": str(path)})
    return path


def resolve_blender(explicit: str | None = None) -> Path:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    for key in ("CH_BLENDER_EXE", "BLENDER_EXE"):
        if os.environ.get(key):
            candidates.append(os.environ[key])
    discovered = shutil.which("blender")
    if discovered:
        candidates.append(discovered)

    for candidate in candidates:
        path = Path(candidate).expanduser().resolve()
        if path.is_file():
            return path
    raise WorkerError("BLENDER_NOT_FOUND", "Blender executable was not found", {"searched": candidates})


def blender_identity(blender_exe: Path) -> dict[str, str]:
    try:
        completed = subprocess.run(
            [str(blender_exe), "--version"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        raise WorkerError(
            "BLENDER_NOT_FOUND",
            "Failed to execute Blender",
            {"path": str(blender_exe), "error": str(exc)},
        ) from exc

    first_line = (completed.stdout or completed.stderr).splitlines()[0].strip()
    expected = str(_manifest()["upstream"]["tag"]).removeprefix("v")
    if f"Blender {expected}" not in first_line:
        raise WorkerError(
            "BLENDER_VERSION_MISMATCH",
            "Blender version does not match the frozen CH Blender base",
            {"expected": expected, "actual": first_line, "path": str(blender_exe)},
        )
    return {"version": expected, "versionLine": first_line, "executable": str(blender_exe)}


def _command_prefix(blender_exe: Path) -> list[str]:
    command = [str(blender_exe)]
    if platform.system() == "Linux" and shutil.which("xvfb-run"):
        command = ["xvfb-run", "-a", *command]
    return command


def _run(command: list[str], *, error_code: str, env: dict[str, str] | None = None) -> None:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    completed = subprocess.run(command, cwd=REPO_ROOT, env=run_env)
    if completed.returncode != 0:
        raise WorkerError(
            error_code,
            "Command failed",
            {"returnCode": completed.returncode, "command": command},
        )


def _quality_stage(job: dict[str, Any]) -> str:
    stage = str(job.get("qualityStage", "preflight"))
    if stage not in {"preflight", "proxy", "final"}:
        raise WorkerError(
            "JOB_INVALID",
            "qualityStage must be preflight, proxy or final",
            {"qualityStage": stage},
        )
    if stage == "final":
        approval = job.get("approval")
        if not isinstance(approval, dict) or approval.get("proxyReviewed") is not True:
            raise WorkerError(
                "QUALITY_GATE_REQUIRED",
                "Final render requires explicit human proxy review.",
                {"required": "approval.proxyReviewed=true"},
            )
        sha = str(approval.get("approvedProxySha256", "")).lower()
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise WorkerError(
                "QUALITY_GATE_REQUIRED",
                "Final render requires the SHA-256 from the reviewed proxy report.",
                {"required": "approval.approvedProxySha256"},
            )
    return stage


def _validate_job(job: dict[str, Any]) -> None:
    if job.get("contract") != JOB_CONTRACT:
        raise WorkerError(
            "CONTRACT_MISMATCH",
            "Unsupported agent job contract",
            {"expected": JOB_CONTRACT, "actual": job.get("contract")},
        )
    if not isinstance(job.get("jobId"), str) or not job["jobId"].strip():
        raise WorkerError("JOB_INVALID", "jobId must be a non-empty string")
    if job.get("operation") not in {
        "canonical_bake",
        "blender_script",
        "guarded_blender_script",
    }:
        raise WorkerError("JOB_INVALID", "Unsupported operation", {"operation": job.get("operation")})
    if job.get("operation") == "guarded_blender_script":
        _quality_stage(job)


def _output_hashes(root: Path) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    if not root.exists():
        return outputs
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        outputs.append(
            {
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return outputs


def _canonical_bake(job: dict[str, Any], blender_exe: Path):
    asset_config = _repo_path(str(job.get("assetConfig", "")))
    studio_preset = _repo_path(
        str(job.get("studioPreset") or DEFAULT_STUDIO.relative_to(REPO_ROOT))
    )
    output_root = _repo_path(
        str(job.get("outputDir", f"out/ch_blender_agent/{job['jobId']}")),
        must_exist=False,
    )
    source_dir = output_root / "source"
    final_dir = output_root / "final"
    source_dir.mkdir(parents=True, exist_ok=True)

    command = [
        *_command_prefix(blender_exe),
        "--background",
        "--factory-startup",
        "--python-use-system-env",
        "--python",
        str(BUILD_SCENE),
        "--",
        "--asset-config",
        str(asset_config),
        "--studio-preset",
        str(studio_preset),
        "--output",
        str(source_dir),
    ]
    env = {
        "PYTHONPATH": str(REPO_ROOT / "tools/tycoon_photo_studio"),
        "LIBGL_ALWAYS_SOFTWARE": os.environ.get("LIBGL_ALWAYS_SOFTWARE", "1"),
    }
    _run(command, error_code="BLENDER_FAILED", env=env)

    inputs = [
        {"path": asset_config.relative_to(REPO_ROOT).as_posix(), "sha256": _sha256(asset_config)},
        {"path": studio_preset.relative_to(REPO_ROOT).as_posix(), "sha256": _sha256(studio_preset)},
    ]

    if bool(job.get("postprocess", True)):
        final_dir.mkdir(parents=True, exist_ok=True)
        _run(
            [
                sys.executable,
                str(POSTPROCESS),
                "--input",
                str(source_dir),
                "--output",
                str(final_dir),
                "--studio-preset",
                str(studio_preset),
            ],
            error_code="POSTPROCESS_FAILED",
        )
    return output_root, inputs, None


def _validate_expected_outputs(job: dict[str, Any], defaults: list[str] | None = None) -> None:
    expected = job.get("expectedOutputs", defaults or [])
    if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
        raise WorkerError("JOB_INVALID", "expectedOutputs must be an array of repository-relative paths")
    missing = [item for item in expected if not _repo_path(item, must_exist=False).exists()]
    if missing:
        raise WorkerError(
            "EXPECTED_OUTPUT_MISSING",
            "One or more declared outputs were not produced",
            {"missing": missing},
        )


def _blender_script(job: dict[str, Any], blender_exe: Path):
    script = _repo_path(str(job.get("script", "")))
    output_root = _repo_path(
        str(job.get("outputDir", f"out/ch_blender_agent/{job['jobId']}")),
        must_exist=False,
    )
    output_root.mkdir(parents=True, exist_ok=True)

    args = job.get("args", [])
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise WorkerError("JOB_INVALID", "blender_script args must be an ordered array of strings")

    command = [
        *_command_prefix(blender_exe),
        "--background",
        "--factory-startup",
        "--python-use-system-env",
        "--python",
        str(script),
        "--",
        *args,
    ]
    env = {
        "PYTHONPATH": str(REPO_ROOT / "tools/tycoon_photo_studio"),
        "LIBGL_ALWAYS_SOFTWARE": os.environ.get("LIBGL_ALWAYS_SOFTWARE", "1"),
        "CH_AGENT_OUTPUT_DIR": str(output_root),
    }
    _run(command, error_code="BLENDER_FAILED", env=env)
    _validate_expected_outputs(job)
    return output_root, [
        {"path": script.relative_to(REPO_ROOT).as_posix(), "sha256": _sha256(script)}
    ], None


def _guarded_blender_script(job: dict[str, Any], blender_exe: Path):
    stage = _quality_stage(job)
    script = _repo_path(str(job.get("script", "")))
    profile = _repo_path(
        str(job.get("qualityProfile") or DEFAULT_PREFLIGHT_PROFILE.relative_to(REPO_ROOT))
    )
    output_root = _repo_path(
        str(job.get("outputDir", f"out/ch_blender_agent/{job['jobId']}")),
        must_exist=False,
    )
    output_root.mkdir(parents=True, exist_ok=True)

    args = job.get("args", [])
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise WorkerError(
            "JOB_INVALID",
            "guarded_blender_script args must be an ordered array of strings",
        )
    reserved = {"--stage", "--preflight-profile", "--approval-proxy-sha"}
    if any(item in reserved for item in args):
        raise WorkerError(
            "JOB_INVALID",
            "Quality-stage arguments are owned by the CH Blender worker, not job args.",
        )

    command = [
        *_command_prefix(blender_exe),
        "--background",
        "--factory-startup",
        "--python-use-system-env",
        "--python",
        str(script),
        "--",
        *args,
        "--stage",
        stage,
        "--preflight-profile",
        str(profile),
    ]
    approval_sha = None
    if stage == "final":
        approval_sha = str(job["approval"]["approvedProxySha256"]).lower()
        command.extend(["--approval-proxy-sha", approval_sha])

    env = {
        "PYTHONPATH": os.pathsep.join([
            str(REPO_ROOT / "tools/tycoon_photo_studio"),
            str(REPO_ROOT / "tools/ch_blender"),
        ]),
        "LIBGL_ALWAYS_SOFTWARE": os.environ.get("LIBGL_ALWAYS_SOFTWARE", "1"),
        "CH_AGENT_OUTPUT_DIR": str(output_root),
        "CH_QUALITY_STAGE": stage,
    }
    _run(command, error_code="BLENDER_FAILED", env=env)

    rel_root = output_root.relative_to(REPO_ROOT).as_posix()
    defaults = [f"{rel_root}/preflight_report.json"]
    if stage == "proxy":
        defaults.extend([
            f"{rel_root}/proxy_south.png",
            f"{rel_root}/proxy_report.json",
        ])
    elif stage == "final":
        defaults.extend([
            f"{rel_root}/proxy_approval.json",
            f"{rel_root}/studio_metadata.json",
        ])
    _validate_expected_outputs(job, defaults)

    preflight = _load_json(output_root / "preflight_report.json")
    if preflight.get("contract") != "CH_SCENE_PREFLIGHT_V1" or preflight.get("status") != "pass":
        raise WorkerError(
            "BLENDER_FAILED",
            "Guarded builder did not produce a passing CH_SCENE_PREFLIGHT_V1 report.",
            {"preflight": preflight},
        )

    quality = {
        "stage": stage,
        "preflightContract": preflight.get("contract"),
        "preflightStatus": preflight.get("status"),
        "profile": profile.relative_to(REPO_ROOT).as_posix(),
    }
    if stage == "proxy":
        proxy = _load_json(output_root / "proxy_report.json")
        if proxy.get("contract") != "CH_PROXY_RENDER_V1":
            raise WorkerError(
                "BLENDER_FAILED",
                "Guarded builder proxy report contract mismatch.",
                {"actual": proxy.get("contract")},
            )
        quality["proxySha256"] = proxy.get("sha256")
        quality["proxyDirection"] = proxy.get("direction")
    elif stage == "final":
        quality["approvedProxySha256"] = approval_sha
        quality["proxyReviewed"] = True

    inputs = [
        {"path": script.relative_to(REPO_ROOT).as_posix(), "sha256": _sha256(script)},
        {"path": profile.relative_to(REPO_ROOT).as_posix(), "sha256": _sha256(profile)},
    ]
    return output_root, inputs, quality


def run_job(job_path: Path, blender_exe: Path) -> dict[str, Any]:
    job = _load_json(job_path)
    _validate_job(job)
    identity = blender_identity(blender_exe)

    if job["operation"] == "canonical_bake":
        output_root, inputs, quality = _canonical_bake(job, blender_exe)
    elif job["operation"] == "guarded_blender_script":
        output_root, inputs, quality = _guarded_blender_script(job, blender_exe)
    else:
        output_root, inputs, quality = _blender_script(job, blender_exe)

    report = {
        "contract": REPORT_CONTRACT,
        "status": "ok",
        "jobContract": JOB_CONTRACT,
        "jobId": job["jobId"],
        "operation": job["operation"],
        "blender": identity,
        "cityHorizon": _manifest()["cityHorizonContracts"],
        "job": {
            "path": job_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": _sha256(job_path),
        },
        "inputs": inputs,
        "outputRoot": output_root.relative_to(REPO_ROOT).as_posix(),
        "outputs": _output_hashes(output_root),
    }
    if quality is not None:
        report["qualityGate"] = quality
    return report


def error_report(job_path: Path | None, exc: WorkerError) -> dict[str, Any]:
    return {
        "contract": REPORT_CONTRACT,
        "status": "error",
        "error": {"code": exc.code, "message": str(exc), "details": exc.details},
        "job": str(job_path) if job_path else None,
    }
