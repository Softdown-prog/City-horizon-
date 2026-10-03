#!/usr/bin/env python3
"""Bounded concurrent worker pool for CH Blender agent jobs.

The pool deliberately sits above ``agent_worker`` instead of duplicating render
logic. Every job still passes the existing CH_BLENDER_AGENT_JOB_V1 validation
and quality gates. Parallelism is bounded because each worker launches an
independent Blender process and can consume significant RAM/CPU.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from agent_worker import (
    EXIT,
    REPO_ROOT,
    WorkerError,
    blender_identity,
    error_report,
    resolve_blender,
    run_job,
    validate_job,
)

POOL_CONTRACT = "CH_BLENDER_WORKER_POOL_V1"
POOL_RESULT_CONTRACT = "CH_BLENDER_WORKER_POOL_REPORT_V1"
DEFAULT_MAX_WORKERS = 2
MAX_ALLOWED_WORKERS = 8


@dataclass(frozen=True)
class PreparedJob:
    path: Path
    job_id: str
    operation: str
    quality_stage: str | None
    output_dir: Path
    report_path: Path


def _repo_path(value: str | Path, *, must_exist: bool = False) -> Path:
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise WorkerError(
            "JOB_INVALID",
            "Pool paths must remain inside the repository workspace",
            {"path": str(path)},
        ) from exc
    if must_exist and not path.exists():
        raise WorkerError("JOB_INVALID", "Required pool path does not exist", {"path": str(path)})
    return path


def _display(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _safe_report_name(job_id: str) -> str:
    return "".join(ch for ch in job_id if ch.isalnum() or ch in "._-") or "job"


def _effective_workers(requested: int | None) -> int:
    if requested is None:
        raw = os.environ.get("CH_BLENDER_POOL_SIZE", "").strip()
        if raw:
            try:
                requested = int(raw)
            except ValueError as exc:
                raise WorkerError("JOB_INVALID", "CH_BLENDER_POOL_SIZE must be an integer") from exc
        else:
            requested = DEFAULT_MAX_WORKERS
    if requested < 1 or requested > MAX_ALLOWED_WORKERS:
        raise WorkerError(
            "JOB_INVALID",
            f"Worker pool size must be between 1 and {MAX_ALLOWED_WORKERS}",
            {"requested": requested},
        )
    return requested


def prepare_jobs(job_paths: Iterable[Path], reports_dir: Path) -> list[PreparedJob]:
    """Validate all jobs and reject unsafe collisions before Blender starts."""
    prepared: list[PreparedJob] = []
    ids: dict[str, str] = {}
    outputs: dict[Path, str] = {}

    for raw_path in job_paths:
        path = _repo_path(raw_path, must_exist=True)
        job = validate_job(path)
        job_id = str(job["jobId"])
        output = _repo_path(job.get("outputDir", f"out/ch_blender_agent/{job_id}"))

        if job_id in ids:
            raise WorkerError(
                "JOB_INVALID",
                "Worker pool contains duplicate jobId values",
                {"jobId": job_id, "first": ids[job_id], "second": _display(path)},
            )
        ids[job_id] = _display(path)

        if output in outputs:
            raise WorkerError(
                "JOB_INVALID",
                "Worker pool jobs must not share outputDir",
                {"outputDir": _display(output), "firstJobId": outputs[output], "secondJobId": job_id},
            )
        outputs[output] = job_id

        prepared.append(
            PreparedJob(
                path=path,
                job_id=job_id,
                operation=str(job["operation"]),
                quality_stage=job.get("qualityStage"),
                output_dir=output,
                report_path=reports_dir / f"{_safe_report_name(job_id)}.report.json",
            )
        )
    return prepared


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _execute(prepared: PreparedJob, blender: Path, slot: int) -> dict[str, Any]:
    started = time.time()
    thread_name = threading.current_thread().name
    try:
        payload = run_job(prepared.path, blender)
        payload["pool"] = {
            "contract": POOL_CONTRACT,
            "slot": slot,
            "thread": thread_name,
            "elapsedSeconds": round(time.time() - started, 3),
        }
        _write_json(prepared.report_path, payload)
        return {
            "jobId": prepared.job_id,
            "status": "ok",
            "job": _display(prepared.path),
            "report": _display(prepared.report_path),
            "outputDir": _display(prepared.output_dir),
            "elapsedSeconds": payload["pool"]["elapsedSeconds"],
        }
    except WorkerError as exc:
        payload = error_report(prepared.path, exc)
        payload["pool"] = {
            "contract": POOL_CONTRACT,
            "slot": slot,
            "thread": thread_name,
            "elapsedSeconds": round(time.time() - started, 3),
        }
        _write_json(prepared.report_path, payload)
        return {
            "jobId": prepared.job_id,
            "status": "error",
            "job": _display(prepared.path),
            "report": _display(prepared.report_path),
            "outputDir": _display(prepared.output_dir),
            "elapsedSeconds": payload["pool"]["elapsedSeconds"],
            "error": payload["error"],
        }
    except Exception as exc:  # Keep the pool alive so sibling jobs still report.
        payload = {
            "contract": "CH_BLENDER_AGENT_REPORT_V1",
            "status": "error",
            "error": {"code": "UNEXPECTED", "message": str(exc), "details": {}},
            "job": _display(prepared.path),
            "pool": {
                "contract": POOL_CONTRACT,
                "slot": slot,
                "thread": thread_name,
                "elapsedSeconds": round(time.time() - started, 3),
            },
        }
        _write_json(prepared.report_path, payload)
        return {
            "jobId": prepared.job_id,
            "status": "error",
            "job": _display(prepared.path),
            "report": _display(prepared.report_path),
            "outputDir": _display(prepared.output_dir),
            "elapsedSeconds": payload["pool"]["elapsedSeconds"],
            "error": payload["error"],
        }


def run_pool(
    job_paths: Iterable[Path],
    *,
    blender: Path,
    max_workers: int,
    reports_dir: Path,
) -> dict[str, Any]:
    prepared = prepare_jobs(job_paths, reports_dir)
    if not prepared:
        raise WorkerError("JOB_INVALID", "Worker pool requires at least one job")

    # Resolve/version-check once before parallel Blender startup. Individual jobs
    # retain their existing identity check as a defense-in-depth contract check.
    identity = blender_identity(blender)
    worker_count = min(max_workers, len(prepared))
    started = time.time()
    results: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="ch-blender-worker") as executor:
        futures: dict[Future[dict[str, Any]], int] = {}
        for index, job in enumerate(prepared):
            slot = (index % worker_count) + 1
            futures[executor.submit(_execute, job, blender, slot)] = index

        indexed: dict[int, dict[str, Any]] = {}
        for future in as_completed(futures):
            indexed[futures[future]] = future.result()
        results = [indexed[index] for index in range(len(prepared))]

    failed = [item for item in results if item["status"] != "ok"]
    return {
        "contract": POOL_RESULT_CONTRACT,
        "status": "error" if failed else "ok",
        "pool": {
            "maxWorkers": max_workers,
            "activeWorkers": worker_count,
            "queuedJobs": len(prepared),
            "elapsedSeconds": round(time.time() - started, 3),
        },
        "blender": identity,
        "succeeded": len(results) - len(failed),
        "failed": len(failed),
        "results": results,
    }


def _collect_jobs(args: argparse.Namespace) -> list[Path]:
    if args.job:
        return [_repo_path(item, must_exist=True) for item in args.job]
    if args.jobs_file:
        list_path = _repo_path(args.jobs_file, must_exist=True)
        jobs = []
        for raw in list_path.read_text(encoding="utf-8").splitlines():
            value = raw.strip()
            if value and not value.startswith("#"):
                jobs.append(_repo_path(value, must_exist=True))
        return jobs
    root = _repo_path(args.dir, must_exist=True)
    if not root.is_dir():
        raise WorkerError("JOB_INVALID", "--dir must be a directory", {"path": _display(root)})
    return sorted(root.glob("*.job.json"))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Bounded concurrent CH Blender worker pool")
    root.add_argument("--job", action="append", default=None, help="Job path; repeatable")
    root.add_argument("--jobs-file", default=None, help="Text file containing one repository-relative job path per line")
    root.add_argument("--dir", default="tools/ch_blender/jobs", help="Fallback job directory")
    root.add_argument("--workers", type=int, default=None, help=f"Concurrent Blender workers (1-{MAX_ALLOWED_WORKERS})")
    root.add_argument("--blender", default=None)
    root.add_argument("--reports-dir", default="out/ch_blender_agent/reports")
    root.add_argument("--report", default="out/ch_blender_agent/pool_report.json")
    return root


def main() -> int:
    args = parser().parse_args()
    report_path = _repo_path(args.report)
    try:
        if args.job and args.jobs_file:
            raise WorkerError("JOB_INVALID", "Use either --job or --jobs-file, not both")
        jobs = _collect_jobs(args)
        workers = _effective_workers(args.workers)
        blender = resolve_blender(args.blender)
        payload = run_pool(
            jobs,
            blender=blender,
            max_workers=workers,
            reports_dir=_repo_path(args.reports_dir),
        )
        _write_json(report_path, payload)
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return EXIT["OK"] if payload["status"] == "ok" else 1
    except WorkerError as exc:
        payload = {
            "contract": POOL_RESULT_CONTRACT,
            "status": "error",
            "error": {"code": exc.code, "message": str(exc), "details": exc.details},
        }
        _write_json(report_path, payload)
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return EXIT.get(exc.code, 1)


if __name__ == "__main__":
    raise SystemExit(main())
