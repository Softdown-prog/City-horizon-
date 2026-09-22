#!/usr/bin/env python3
"""Prepare one City Horizon audio asset and register it in audio_catalog.json.

The worker is intentionally small and deterministic: source files may be MP3,
MP4, WAV, FLAC or other formats supported by ffmpeg; runtime audio is written
as OGG/Vorbis. A JSON job describes the source, destination and catalog slot.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def run_checked(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", type=Path)
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg and ffprobe are required")

    job = json.loads(args.job.read_text(encoding="utf-8"))
    source = Path(job["source"])
    output = Path(job["output"])
    catalog_path = Path(job.get("catalog", "assets/audio/audio_catalog.json"))
    kind = str(job.get("kind", "effect"))
    key = str(job.get("event") if kind == "effect" else job.get("slot"))
    mode = str(job.get("mode", "append" if kind == "effect" else "replace"))

    if not source.is_file():
        raise SystemExit(f"source not found: {source}")
    if output.suffix.lower() != ".ogg":
        raise SystemExit("runtime output must use .ogg")
    if kind not in {"effect", "music"}:
        raise SystemExit(f"unsupported kind: {kind}")
    if not key or key == "None":
        raise SystemExit("audio job requires event for effects or slot for music")

    output.parent.mkdir(parents=True, exist_ok=True)
    channels = "1" if kind == "effect" else "2"
    quality = "4" if kind == "effect" else "5"
    run_checked([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-vn", "-ac", channels, "-ar", "48000",
        "-c:a", "libvorbis", "-q:a", quality,
        str(output),
    ])

    run_checked([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels",
        "-of", "default=noprint_wrappers=1", str(output),
    ])

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    audio_root = catalog_path.parent
    relative = output.relative_to(audio_root).as_posix()

    if kind == "effect":
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
    print(f"PASS kind={kind} key={key} source={source} output={output} mode={mode}")


if __name__ == "__main__":
    main()
