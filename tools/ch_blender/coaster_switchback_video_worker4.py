#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import coaster_worker_task as base


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--output", required=True)
    return p.parse_args(argv)


def run(cmd):
    print("+", " ".join(str(x) for x in cmd), flush=True)
    subprocess.run([str(x) for x in cmd], cwd=base.REPO, check=True)


def main():
    args = parse_args()
    project_path = (base.REPO / args.project).resolve()
    outdir = (base.REPO / args.output).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    project = base.load_json(project_path)
    if project.get("contract") != "CH_MAPFORGE_COASTER_PROJECT_V1":
        raise SystemExit("unsupported coaster project contract")
    if project.get("projectId") != "coaster.flame.switchback.02":
        raise SystemExit("wrong project: expected coaster.flame.switchback.02")

    # Fail before rendering if the authored route is not actually closed.
    base.build_route(project)

    # Stage the exact authored source up front so the worker contract cannot
    # report a false failure after a successful render/encode.
    staged_project = outdir / "coaster_flame_switchback_02.mapforge.json"
    shutil.copy2(project_path, staged_project)

    build = base.REPO / "build/ch-coaster-switchback-worker4"
    temp = base.REPO / "out/ch_blender_agent/.coaster_switchback_video_tmp"
    frames = temp / "frames"
    if temp.exists():
        shutil.rmtree(temp)
    frames.mkdir(parents=True, exist_ok=True)

    run(["cmake", "-S", "tools/animation_preview/coaster_video_proof", "-B", build, "-G", "Ninja"])
    run(["cmake", "--build", build, "--target", "MapForge2CoasterVideoProof", "--parallel"])

    renderer = build / "MapForge2CoasterVideoProof"
    atlas = base.REPO / "assets/vehicles/coaster_flame_01/car_pose_atlas_v2.png"
    run([renderer, frames, atlas, project_path])

    capture = base.load_json(frames / "capture_meta.json")
    frame_count = int(capture["frameCount"])
    video = outdir / "coaster_flame_switchback_02_worker4.mp4"
    sheet = outdir / "contact_sheet_switchback_02.png"

    run(["ffmpeg", "-y", "-framerate", "30", "-i", str(frames / "frame_%04d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", video])

    interval = max(1, frame_count // 12)
    vf = f"select='not(mod(n\\,{interval}))',scale=640:-1,tile=4x3"
    run(["ffmpeg", "-y", "-i", video, "-vf", vf, "-frames:v", "1", sheet])

    shutil.copy2(frames / "capture_meta.json", outdir / "capture_meta.json")
    base.write_json(outdir / "video_report.json", {
        "contract": "CH_COASTER_WORKER4_VIDEO_REPORT_V1",
        "status": "ok",
        "workerSlot": 4,
        "projectId": project["projectId"],
        "projectName": project["name"],
        "frameCount": frame_count,
        "fps": 30,
        "routeLengthM": capture.get("routeMeters"),
        "lapSeconds": capture.get("lapSeconds"),
        "video": video.name,
        "contactSheet": sheet.name,
        "source": "dedicated-distinct-authored-project"
    })
    shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    main()
