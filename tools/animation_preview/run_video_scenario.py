#!/usr/bin/env python3
"""Run deterministic City Horizon validation scenarios through an authoritative renderer.

A CH_VIDEO_SCENARIO_V1 file describes a base renderer request plus time-based events
and keyframed JSON fields. For every frame this runner writes the resolved request,
asks the configured renderer to produce a PNG, and then optionally builds GIF/video
review artifacts through the existing CH Video Lab pipeline.

The scenario runner never screen-scrapes and never treats generated video as runtime
truth. The renderer-produced PNG sequence remains the authoritative visual evidence.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

from make_gif import CONTRACT as GIF_CONTRACT, build_from_manifest as build_gif_from_manifest
from make_video import CONTRACT as VIDEO_CONTRACT, build_from_manifest as build_video_from_manifest

CONTRACT = "CH_VIDEO_SCENARIO_V1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _load_scenario(path: Path) -> dict:
    payload = _load_json(path)
    if payload.get("contract") != CONTRACT:
        raise ValueError(f"Expected {CONTRACT}, got {payload.get('contract')!r}")
    return payload


def _base_request(scenario_path: Path, scenario: dict) -> dict:
    inline = scenario.get("baseRequest")
    file_name = scenario.get("baseRequestFile")
    if inline is not None and file_name is not None:
        raise ValueError("Use baseRequest or baseRequestFile, not both")
    if inline is not None:
        if not isinstance(inline, dict):
            raise ValueError("baseRequest must be an object")
        return copy.deepcopy(inline)
    if file_name is None:
        raise ValueError("Scenario requires baseRequest or baseRequestFile")
    request_path = (scenario_path.parent / str(file_name)).resolve()
    return _load_json(request_path)


def _split_path(path: str) -> list[str]:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise ValueError("JSON path must not be empty")
    return parts


def _set_path(root: dict, path: str, value: Any) -> None:
    parts = _split_path(path)
    cursor: Any = root
    for part in parts[:-1]:
        if not isinstance(cursor, dict):
            raise ValueError(f"Cannot descend through non-object at {path!r}")
        child = cursor.get(part)
        if child is None:
            child = {}
            cursor[part] = child
        if not isinstance(child, dict):
            raise ValueError(f"Path component {part!r} in {path!r} is not an object")
        cursor = child
    if not isinstance(cursor, dict):
        raise ValueError(f"Cannot set path {path!r}")
    cursor[parts[-1]] = copy.deepcopy(value)


def _key_time(keyframe: dict, fps: int) -> float:
    if "time" in keyframe:
        return float(keyframe["time"])
    if "frame" in keyframe:
        return int(keyframe["frame"]) / float(fps)
    raise ValueError("keyframe requires time or frame")


def _smoothstep(alpha: float) -> float:
    return alpha * alpha * (3.0 - 2.0 * alpha)


def _lerp(a: Any, b: Any, alpha: float) -> Any:
    if isinstance(a, bool) or isinstance(b, bool):
        return copy.deepcopy(a if alpha < 1.0 else b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) + (float(b) - float(a)) * alpha
    if (
        isinstance(a, list)
        and isinstance(b, list)
        and len(a) == len(b)
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in a + b)
    ):
        return [float(x) + (float(y) - float(x)) * alpha for x, y in zip(a, b)]
    return copy.deepcopy(a if alpha < 1.0 else b)


def _sample_track(track: dict, time_s: float, fps: int) -> Any:
    keyframes = track.get("keyframes")
    if not isinstance(keyframes, list) or not keyframes:
        raise ValueError(f"Track {track.get('path')!r} requires keyframes")
    ordered = sorted(keyframes, key=lambda item: _key_time(item, fps))
    if any("value" not in item for item in ordered):
        raise ValueError(f"Track {track.get('path')!r} keyframes require value")

    if time_s <= _key_time(ordered[0], fps):
        return copy.deepcopy(ordered[0]["value"])
    if time_s >= _key_time(ordered[-1], fps):
        return copy.deepcopy(ordered[-1]["value"])

    interpolation = str(track.get("interpolation", "linear")).lower()
    for left, right in zip(ordered, ordered[1:]):
        left_t = _key_time(left, fps)
        right_t = _key_time(right, fps)
        if left_t <= time_s <= right_t:
            if interpolation in {"step", "hold"} or math.isclose(right_t, left_t):
                return copy.deepcopy(left["value"])
            alpha = (time_s - left_t) / (right_t - left_t)
            if interpolation in {"smooth", "smoothstep", "ease"}:
                alpha = _smoothstep(alpha)
            elif interpolation != "linear":
                raise ValueError(f"Unsupported interpolation: {interpolation}")
            return _lerp(left["value"], right["value"], alpha)

    return copy.deepcopy(ordered[-1]["value"])


def _event_time(event: dict, fps: int) -> float:
    if "time" in event:
        return float(event["time"])
    if "frame" in event:
        return int(event["frame"]) / float(fps)
    raise ValueError("event requires time or frame")


def _apply_events(request: dict, events: list[dict], time_s: float, fps: int) -> None:
    for event in sorted(events, key=lambda item: _event_time(item, fps)):
        if _event_time(event, fps) > time_s + 1e-9:
            break
        patch = event.get("set", {})
        if not isinstance(patch, dict):
            raise ValueError("event.set must be an object mapping JSON paths to values")
        for path, value in patch.items():
            _set_path(request, str(path), value)


def _format_arg(value: str, *, index: int, time_s: float, output: Path, request: Path) -> str:
    return (
        value.replace("{index}", str(index))
        .replace("{index03}", f"{index:03d}")
        .replace("{index06}", f"{index:06d}")
        .replace("{time}", f"{time_s:.6f}")
        .replace("{timeMs}", str(int(round(time_s * 1000.0))))
        .replace("{output}", str(output))
        .replace("{request}", str(request))
    )


def run_scenario(scenario_path: Path) -> dict:
    scenario_path = scenario_path.resolve()
    scenario = _load_scenario(scenario_path)
    base = scenario_path.parent
    request_template = _base_request(scenario_path, scenario)

    fps = max(1, min(120, int(scenario.get("fps", 30))))
    if "frameCount" in scenario:
        frame_count = int(scenario["frameCount"])
    else:
        duration = float(scenario.get("durationSeconds", 0.0))
        frame_count = int(round(duration * fps))
    if frame_count < 2:
        raise ValueError("Scenario requires at least two frames")

    output_dir = (base / scenario.get("outputDir", "scenario_output")).resolve()
    frames_dir = output_dir / "frames"
    requests_dir = output_dir / "requests"
    frames_dir.mkdir(parents=True, exist_ok=True)
    requests_dir.mkdir(parents=True, exist_ok=True)

    renderer = scenario.get("renderer", {})
    if not isinstance(renderer, dict):
        raise ValueError("renderer must be an object")
    command = renderer.get("command")
    if not isinstance(command, list) or not command:
        raise ValueError("renderer.command must be a non-empty argv array")
    cwd = (base / renderer.get("cwd", ".")).resolve()

    tracks = scenario.get("tracks", [])
    events = scenario.get("events", [])
    if not isinstance(tracks, list) or not all(isinstance(item, dict) for item in tracks):
        raise ValueError("tracks must be an array of objects")
    if not isinstance(events, list) or not all(isinstance(item, dict) for item in events):
        raise ValueError("events must be an array of objects")

    frames: list[Path] = []
    request_hashes: list[str] = []
    for index in range(frame_count):
        time_s = index / float(fps)
        resolved = copy.deepcopy(request_template)
        _apply_events(resolved, events, time_s, fps)
        for track in tracks:
            path = track.get("path")
            if not isinstance(path, str) or not path:
                raise ValueError("Each track requires a non-empty path")
            _set_path(resolved, path, _sample_track(track, time_s, fps))

        request_path = requests_dir / f"request_{index:06d}.json"
        request_path.write_text(
            json.dumps(resolved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        request_hashes.append(_sha256(request_path))

        output = frames_dir / f"frame_{index:06d}.png"
        argv = [
            _format_arg(str(arg), index=index, time_s=time_s, output=output, request=request_path)
            for arg in command
        ]
        subprocess.run(argv, cwd=cwd, check=True)
        if not output.is_file():
            raise RuntimeError(f"Renderer did not create {output}")
        frames.append(output)

    frame_refs = [str(path.relative_to(output_dir)) for path in frames]

    gif_cfg = scenario.get("gif", {})
    gif_report = None
    if gif_cfg is not False:
        if not isinstance(gif_cfg, dict):
            raise ValueError("gif must be an object or false")
        if bool(gif_cfg.get("enabled", True)):
            gif_manifest = {
                "contract": GIF_CONTRACT,
                "id": scenario.get("id"),
                "reviewOnly": bool(scenario.get("reviewOnly", True)),
                "frames": frame_refs,
                "durationMs": int(gif_cfg.get("durationMs", round(1000 / fps))),
                "loop": int(gif_cfg.get("loop", 0)),
                "pingPong": bool(gif_cfg.get("pingPong", False)),
                "background": gif_cfg.get("background", [24, 30, 36]),
                "output": gif_cfg.get("output", "scenario_preview.gif"),
                "contactSheet": gif_cfg.get("contactSheet", "scenario_contact_sheet.png"),
            }
            gif_manifest_path = output_dir / "animation_preview_manifest.json"
            gif_manifest_path.write_text(json.dumps(gif_manifest, indent=2), encoding="utf-8")
            gif_report = build_gif_from_manifest(gif_manifest_path)

    video_cfg = scenario.get("video", {"output": "scenario_validation.mp4"})
    video_report = None
    if video_cfg is not False:
        if not isinstance(video_cfg, dict):
            raise ValueError("video must be an object or false")
        if bool(video_cfg.get("enabled", True)):
            video_manifest = {
                "contract": VIDEO_CONTRACT,
                "id": scenario.get("id"),
                "reviewOnly": bool(scenario.get("reviewOnly", True)),
                "frames": frame_refs,
                "fps": int(video_cfg.get("fps", fps)),
                "pingPong": bool(video_cfg.get("pingPong", False)),
                "background": video_cfg.get("background", [24, 30, 36]),
                "output": video_cfg.get("output", "scenario_validation.mp4"),
            }
            video_manifest_path = output_dir / "video_preview_manifest.json"
            video_manifest_path.write_text(json.dumps(video_manifest, indent=2), encoding="utf-8")
            video_report = build_video_from_manifest(video_manifest_path)

    report = {
        "contract": CONTRACT,
        "status": "ok",
        "id": scenario.get("id"),
        "reviewOnly": bool(scenario.get("reviewOnly", True)),
        "scenario": str(scenario_path),
        "scenarioSha256": _sha256(scenario_path),
        "outputDir": str(output_dir),
        "fps": fps,
        "frameCount": frame_count,
        "durationSeconds": frame_count / float(fps),
        "frames": frame_refs,
        "requestSha256": request_hashes,
        "gif": gif_report,
        "video": video_report,
    }
    report_path = output_dir / "scenario_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a deterministic City Horizon video validation scenario"
    )
    parser.add_argument("--scenario", type=Path, required=True)
    args = parser.parse_args()
    run_scenario(args.scenario)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
