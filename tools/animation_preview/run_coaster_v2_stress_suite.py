#!/usr/bin/env python3
import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path

LAYOUTS = {
    "compact": "C++/MapForge2/projects/coaster_flame_stress_compact.mapforge.json",
    "steep": "C++/MapForge2/projects/coaster_flame_stress_steep.mapforge.json",
    "wide": "C++/MapForge2/projects/coaster_flame_stress_wide.mapforge.json",
}


def run(cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(x) for x in cmd], check=True)


def validate_meta(meta_path: Path, frames_dir: Path):
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    actual = len(list(frames_dir.glob("frame_*.png")))
    expected = math.ceil(meta["routeMeters"] / meta["trainSpeedMps"] * meta["fps"]) + 1
    if meta.get("contract") != "CH_COASTER_FULL_LAP_CAPTURE_V1" or meta.get("fullLap") is not True:
        raise RuntimeError("stress capture is not a complete lap")
    if meta.get("frameCount") != expected or actual != expected:
        raise RuntimeError(f"stress frame mismatch meta={meta.get('frameCount')} actual={actual} expected={expected}")
    if abs(meta.get("firstLeadDistanceMeters", 1.0)) > 1e-9 or abs(meta.get("lastLeadDistanceMeters", 1.0)) > 1e-9:
        raise RuntimeError("stress capture did not return lead car to route origin")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renderer", required=True)
    ap.add_argument("--atlas", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    root = Path(args.output)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    summary = {"contract": "CH_COASTER_V2_STRESS_SUITE_V1", "status": "ok", "layouts": {}}

    for slug, project in LAYOUTS.items():
        out = root / slug
        frames = out / "frames"
        frames.mkdir(parents=True)
        run([args.renderer, frames, args.atlas, project])
        generated_meta = frames / "capture_meta.json"
        meta_path = out / "capture_meta.json"
        generated_meta.replace(meta_path)
        meta = validate_meta(meta_path, frames)

        video = out / f"coaster_{slug}_full_lap.mp4"
        sheet = out / "contact_sheet_full_lap.png"
        probe = out / "ffprobe.json"
        run(["ffmpeg", "-y", "-framerate", str(meta["fps"]), "-i", frames / "frame_%04d.png",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", video])
        sample_fps = 16.0 / max(meta["lapSeconds"], 0.001)
        run(["ffmpeg", "-y", "-i", video, "-vf", f"fps={sample_fps},scale=480:-1,tile=4x4",
             "-frames:v", "1", sheet])
        with probe.open("w", encoding="utf-8") as fh:
            subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
                            "-of", "json", video], check=True, stdout=fh)
        summary["layouts"][slug] = {
            "project": project,
            "routeMeters": meta["routeMeters"],
            "lapSeconds": meta["lapSeconds"],
            "frameCount": meta["frameCount"],
            "fullLapValidated": True,
            "video": video.name,
            "contactSheet": sheet.name,
        }

    (root / "stress_suite_report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
