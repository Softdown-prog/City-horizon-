#!/usr/bin/env python3
"""Capture a deterministic City Horizon runtime session and build review media.

CH_RUNTIME_VIDEO_JOB_V1 runs the real city_builder executable once in validation
capture mode. The runtime advances with a fixed timeline and writes authoritative
PNG frames; this script then feeds those frames into the existing GIF/video writers.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from make_gif import CONTRACT as GIF_CONTRACT, build_from_manifest as build_gif_from_manifest
from make_video import CONTRACT as VIDEO_CONTRACT, build_from_manifest as build_video_from_manifest

CONTRACT = "CH_RUNTIME_VIDEO_JOB_V1"
RUNTIME_REPORT_CONTRACT = "CH_RUNTIME_FRAME_CAPTURE_V1"


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("contract") != CONTRACT:
        raise ValueError(f"Expected {CONTRACT}, got {payload.get('contract')!r}")
    return payload


def capture_runtime(job_path: Path) -> dict:
    job_path = job_path.resolve()
    job = _load(job_path)
    base = job_path.parent

    executable = job.get("executable")
    if not isinstance(executable, str) or not executable:
        raise ValueError("job requires executable")
    executable_path = (base / executable).resolve() if not Path(executable).is_absolute() else Path(executable)

    output_dir = (base / job.get("outputDir", "runtime_video_output")).resolve()
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    fps = max(1, min(120, int(job.get("fps", 30))))
    frame_count = int(job.get("frameCount", 120))
    if frame_count < 2 or frame_count > 36000:
        raise ValueError("frameCount must be between 2 and 36000")

    cwd = (base / job.get("cwd", ".")).resolve()
    command = [
        str(executable_path),
        "--validation-capture-dir", str(frames_dir),
        "--validation-frames", str(frame_count),
        "--validation-fps", str(fps),
        "--validation-weather", str(job.get("weather", "sunny")),
    ]
    if bool(job.get("hideUi", True)):
        command.append("--validation-hide-ui")
    else:
        command.append("--validation-show-ui")
    if bool(job.get("paused", False)):
        command.append("--validation-paused")

    extra_args = job.get("args", [])
    if not isinstance(extra_args, list):
        raise ValueError("args must be an array")
    command.extend(str(arg) for arg in extra_args)

    subprocess.run(command, cwd=cwd, check=True)

    runtime_report_path = frames_dir / "runtime_capture_report.json"
    if not runtime_report_path.is_file():
        raise RuntimeError("runtime did not create runtime_capture_report.json")
    runtime_report = json.loads(runtime_report_path.read_text(encoding="utf-8"))
    if runtime_report.get("contract") != RUNTIME_REPORT_CONTRACT or runtime_report.get("status") != "ok":
        raise RuntimeError("runtime capture report is invalid")

    frames = sorted(frames_dir.glob("frame_*.png"))
    if len(frames) != frame_count:
        raise RuntimeError(f"expected {frame_count} runtime frames, found {len(frames)}")
    frame_refs = [str(path.relative_to(output_dir)) for path in frames]

    gif_report = None
    gif_cfg = job.get("gif", {})
    if gif_cfg is not False:
        if not isinstance(gif_cfg, dict):
            raise ValueError("gif must be an object or false")
        if bool(gif_cfg.get("enabled", True)):
            manifest = {
                "contract": GIF_CONTRACT,
                "id": job.get("id"),
                "reviewOnly": True,
                "frames": frame_refs,
                "durationMs": int(gif_cfg.get("durationMs", round(1000 / fps))),
                "loop": int(gif_cfg.get("loop", 0)),
                "pingPong": bool(gif_cfg.get("pingPong", False)),
                "background": gif_cfg.get("background", [24, 30, 36]),
                "output": gif_cfg.get("output", "runtime_validation.gif"),
                "contactSheet": gif_cfg.get("contactSheet", "runtime_contact_sheet.png"),
            }
            manifest_path = output_dir / "animation_preview_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            gif_report = build_gif_from_manifest(manifest_path)

    video_report = None
    video_cfg = job.get("video", {"output": "runtime_validation.mp4"})
    if video_cfg is not False:
        if not isinstance(video_cfg, dict):
            raise ValueError("video must be an object or false")
        if bool(video_cfg.get("enabled", True)):
            manifest = {
                "contract": VIDEO_CONTRACT,
                "id": job.get("id"),
                "reviewOnly": True,
                "frames": frame_refs,
                "fps": int(video_cfg.get("fps", fps)),
                "pingPong": bool(video_cfg.get("pingPong", False)),
                "background": video_cfg.get("background", [24, 30, 36]),
                "output": video_cfg.get("output", "runtime_validation.mp4"),
            }
            manifest_path = output_dir / "video_preview_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            video_report = build_video_from_manifest(manifest_path)

    report = {
        "contract": CONTRACT,
        "status": "ok",
        "id": job.get("id"),
        "job": str(job_path),
        "executable": str(executable_path),
        "outputDir": str(output_dir),
        "fps": fps,
        "frameCount": frame_count,
        "runtime": runtime_report,
        "gif": gif_report,
        "video": video_report,
    }
    report_path = output_dir / "runtime_video_job_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a deterministic City Horizon runtime video")
    parser.add_argument("--job", type=Path, required=True)
    args = parser.parse_args()
    capture_runtime(args.job)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
