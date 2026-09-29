#!/usr/bin/env python3
"""Prepare one City Horizon audio asset and optionally register it in audio_catalog.json.

Legacy jobs remain supported. CH Audio Lab V1 adds:
- effect / ambient / music mastering presets;
- optional loudness normalization and fades;
- deterministic ffprobe validation;
- SHA-256 proof and JSON report;
- review-only jobs that do not mutate the runtime catalog.

Runtime audio remains OGG/Vorbis at 48 kHz.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


CONTRACT = "CH_AUDIO_ASSET_REPORT_V1"
SUPPORTED_KINDS = {"effect", "ambient", "music"}


def run_checked(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_audio(path: Path) -> dict[str, Any]:
    result = run_checked([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels,duration:format=duration",
        "-of", "json", str(path),
    ], capture=True)
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    if not streams:
        raise SystemExit(f"no audio stream found in {path}")
    stream = streams[0]
    duration_raw = stream.get("duration") or payload.get("format", {}).get("duration") or 0
    try:
        duration = float(duration_raw)
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "codec": str(stream.get("codec_name", "")),
        "sampleRate": int(stream.get("sample_rate", 0) or 0),
        "channels": int(stream.get("channels", 0) or 0),
        "durationSeconds": round(duration, 6),
    }


def default_mastering(kind: str) -> dict[str, Any]:
    if kind == "music":
        return {"channels": 2, "quality": 5, "targetLufs": -16.0, "truePeakDb": -1.5}
    if kind == "ambient":
        return {"channels": 2, "quality": 5, "targetLufs": -20.0, "truePeakDb": -2.0}
    return {"channels": 1, "quality": 4, "targetLufs": -18.0, "truePeakDb": -1.5}


def build_audio_filter(job: dict[str, Any], kind: str) -> str | None:
    preset = default_mastering(kind)
    mastering = dict(job.get("mastering") or {})
    normalize = bool(mastering.get("normalize", job.get("normalize", False)))
    filters: list[str] = []

    if normalize:
        target_lufs = float(mastering.get("targetLufs", preset["targetLufs"]))
        true_peak = float(mastering.get("truePeakDb", preset["truePeakDb"]))
        lra = float(mastering.get("lra", 11.0))
        filters.append(f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}")

    fade_in = float(mastering.get("fadeInSeconds", 0.0) or 0.0)
    if fade_in > 0:
        filters.append(f"afade=t=in:st=0:d={fade_in}")

    fade_out = float(mastering.get("fadeOutSeconds", 0.0) or 0.0)
    requested_duration = float(job.get("durationSeconds", 0.0) or 0.0)
    if fade_out > 0 and requested_duration > fade_out:
        start = max(0.0, requested_duration - fade_out)
        filters.append(f"afade=t=out:st={start}:d={fade_out}")

    return ",".join(filters) if filters else None


def update_catalog(job: dict[str, Any], output: Path, kind: str, key: str, mode: str) -> None:
    catalog_path = Path(job.get("catalog", "assets/audio/audio_catalog.json"))
    if not catalog_path.is_file():
        raise SystemExit(f"catalog not found: {catalog_path}")

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    audio_root = catalog_path.parent
    try:
        relative = output.resolve().relative_to(audio_root.resolve()).as_posix()
    except ValueError as exc:
        raise SystemExit("registered audio output must live under the catalog audio directory") from exc

    if kind in {"effect", "ambient"}:
        events = catalog.setdefault("events", {})
        if key not in events:
            raise SystemExit(f"unknown audio event: {key}")
        if mode == "replace":
            events[key] = [relative]
        elif mode == "append":
            if relative not in events[key]:
                events[key].append(relative)
        else:
            raise SystemExit(f"unsupported effect mode: {mode}")
    else:
        music = catalog.setdefault("music", {})
        if mode != "replace":
            raise SystemExit("music jobs currently support only replace mode")
        music[key] = relative

    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", type=Path)
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg and ffprobe are required")

    job = json.loads(args.job.read_text(encoding="utf-8"))
    source = Path(job["source"])
    output = Path(job["output"])
    kind = str(job.get("kind", "effect"))
    key = str(job.get("event") if kind in {"effect", "ambient"} else job.get("slot"))
    mode = str(job.get("mode", "append" if kind in {"effect", "ambient"} else "replace"))
    register = bool(job.get("register", True))
    report_path = Path(job.get("report", str(output.with_suffix(".audio_report.json"))))

    if not source.is_file():
        raise SystemExit(f"source not found: {source}")
    if output.suffix.lower() != ".ogg":
        raise SystemExit("runtime/review output must use .ogg")
    if kind not in SUPPORTED_KINDS:
        raise SystemExit(f"unsupported kind: {kind}")
    if register and (not key or key == "None"):
        raise SystemExit("registered audio job requires event for effects/ambient or slot for music")

    preset = default_mastering(kind)
    mastering = dict(job.get("mastering") or {})
    channels = int(mastering.get("channels", preset["channels"]))
    quality = int(mastering.get("quality", preset["quality"]))
    if channels not in {1, 2}:
        raise SystemExit("mastering channels must be 1 or 2")
    if not 0 <= quality <= 10:
        raise SystemExit("Vorbis quality must be between 0 and 10")

    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-vn",
    ]
    requested_duration = float(job.get("durationSeconds", 0.0) or 0.0)
    if requested_duration > 0:
        command += ["-t", f"{requested_duration:.6f}"]

    audio_filter = build_audio_filter(job, kind)
    if audio_filter:
        command += ["-af", audio_filter]

    command += [
        "-ac", str(channels), "-ar", "48000",
        "-c:a", "libvorbis", "-q:a", str(quality),
        str(output),
    ]
    run_checked(command)

    probe = probe_audio(output)
    if probe["codec"] != "vorbis":
        raise SystemExit(f"unexpected runtime codec: {probe['codec']}")
    if probe["sampleRate"] != 48000:
        raise SystemExit(f"unexpected runtime sample rate: {probe['sampleRate']}")
    if probe["channels"] != channels:
        raise SystemExit(f"unexpected runtime channel count: {probe['channels']}")
    if probe["durationSeconds"] <= 0:
        raise SystemExit("generated runtime audio has zero duration")

    if register:
        update_catalog(job, output, kind, key, mode)

    report = {
        "contract": CONTRACT,
        "status": "ok",
        "kind": kind,
        "key": key if register else None,
        "registered": register,
        "mode": mode,
        "source": str(source),
        "output": str(output),
        "sourceSha256": sha256_file(source),
        "outputSha256": sha256_file(output),
        "probe": probe,
        "mastering": {
            "channels": channels,
            "sampleRate": 48000,
            "vorbisQuality": quality,
            "normalize": bool(mastering.get("normalize", job.get("normalize", False))),
            "filter": audio_filter,
        },
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
