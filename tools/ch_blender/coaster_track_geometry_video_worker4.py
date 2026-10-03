#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASE = REPO / 'C++/MapForge2/src/coaster_project_video_main.cpp'
PROOF = REPO / 'C++/MapForge2/src/coaster_video_proof_main.cpp'
PROJECT = REPO / 'C++/MapForge2/projects/coaster_flame_switchback_02.mapforge.json'
V5 = REPO / 'tools/ch_blender/coaster_switchback_v5_pool.py'
ATLAS = REPO / 'assets/vehicles/coaster_flame_01/car_pose_atlas_v2.png'


def parse_args():
    av = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument('--project', default=str(PROJECT.relative_to(REPO)))
    p.add_argument('--output', required=True)
    return p.parse_args(av)


def repo_path(value: str) -> Path:
    p = Path(value)
    p = (p if p.is_absolute() else REPO / p).resolve()
    p.relative_to(REPO)
    return p


def run(command):
    print('+', ' '.join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=REPO, check=True)


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def load_v5_module():
    spec = importlib.util.spec_from_file_location('ch_coaster_switchback_v5', V5)
    if spec is None or spec.loader is None:
        raise RuntimeError('cannot load Switchback V5 worker module')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def patch_track_source(source: str) -> str:
    include = '#include "../../../src/coaster_track_geometry.h"\n'
    if include not in source:
        marker = '#include "../../../src/coaster_centerline_route.h"\n'
        if marker not in source:
            raise RuntimeError('coaster centerline include marker missing')
        source = source.replace(marker, marker + include, 1)

    begin = source.index('void draw_supports(')
    end = source.index('void draw_station(', begin)
    replacement = r'''void draw_supports(QPainter& painter, const Projection& projection,
                   const ch::coaster::CenterlineRoute& route) {
    ch::coaster::CoasterTrackStyle style{};
    style.support_spacing_m = 5.2;
    const auto geometry = ch::coaster::build_coaster_track_geometry(route, style);
    if (!geometry.valid()) return;

    QPen outline(QColor(47, 52, 55));
    outline.setWidthF(5.2);
    outline.setCapStyle(Qt::RoundCap);
    QPen steel(QColor(119, 128, 133));
    steel.setWidthF(3.0);
    steel.setCapStyle(Qt::RoundCap);

    for (const auto& support : geometry.supports) {
        const QPointF top = projection.map(support.top.x, support.top.y, support.top.z);
        const QPointF bottom = projection.map(support.bottom.x, support.bottom.y, support.bottom.z + 0.02);
        painter.setPen(outline);
        painter.drawLine(top, bottom);
        painter.setPen(steel);
        painter.drawLine(top, bottom);
        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor(60, 63, 65));
        painter.drawEllipse(bottom, 3.2, 1.8);
    }
}

void draw_track(QPainter& painter, const Projection& projection,
                const ch::coaster::CenterlineRoute& route) {
    ch::coaster::CoasterTrackStyle style{};
    style.support_spacing_m = 5.2;
    const auto geometry = ch::coaster::build_coaster_track_geometry(route, style);
    if (!geometry.valid()) return;

    QPainterPath groundShadow, spine, railLeft, railRight;
    bool first = true;
    for (const auto& frame : geometry.frames) {
        const QPointF shadow = projection.map(frame.center.x + 0.30, frame.center.y + 0.30, 0.02);
        const QPointF s = projection.map(frame.spine.x, frame.spine.y, frame.spine.z);
        const QPointF l = projection.map(frame.left_rail.x, frame.left_rail.y, frame.left_rail.z);
        const QPointF r = projection.map(frame.right_rail.x, frame.right_rail.y, frame.right_rail.z);
        if (first) {
            groundShadow.moveTo(shadow);
            spine.moveTo(s);
            railLeft.moveTo(l);
            railRight.moveTo(r);
            first = false;
        } else {
            groundShadow.lineTo(shadow);
            spine.lineTo(s);
            railLeft.lineTo(l);
            railRight.lineTo(r);
        }
    }

    painter.setBrush(Qt::NoBrush);
    QPen shadowPen(QColor(24, 43, 25, 58));
    shadowPen.setWidthF(7.0);
    shadowPen.setCapStyle(Qt::RoundCap);
    shadowPen.setJoinStyle(Qt::RoundJoin);
    painter.setPen(shadowPen);
    painter.drawPath(groundShadow);

    QPen spineOutline(QColor(70, 25, 23));
    spineOutline.setWidthF(8.0);
    spineOutline.setJoinStyle(Qt::RoundJoin);
    painter.setPen(spineOutline);
    painter.drawPath(spine);

    QPen spinePen(QColor(171, 53, 42));
    spinePen.setWidthF(5.0);
    spinePen.setJoinStyle(Qt::RoundJoin);
    painter.setPen(spinePen);
    painter.drawPath(spine);

    QPen tieOutline(QColor(44, 46, 48));
    tieOutline.setWidthF(4.0);
    tieOutline.setCapStyle(Qt::RoundCap);
    QPen tiePen(QColor(90, 94, 97));
    tiePen.setWidthF(2.5);
    tiePen.setCapStyle(Qt::RoundCap);
    for (const auto& tie : geometry.ties) {
        const QPointF a = projection.map(tie.left.x, tie.left.y, tie.left.z);
        const QPointF b = projection.map(tie.right.x, tie.right.y, tie.right.z);
        painter.setPen(tieOutline);
        painter.drawLine(a, b);
        painter.setPen(tiePen);
        painter.drawLine(a, b);
    }

    QPen railShadow(QColor(82, 88, 92));
    railShadow.setWidthF(4.4);
    railShadow.setJoinStyle(Qt::RoundJoin);
    painter.setPen(railShadow);
    painter.drawPath(railLeft);
    painter.drawPath(railRight);

    QPen railPen(QColor(229, 232, 234));
    railPen.setWidthF(2.5);
    railPen.setJoinStyle(Qt::RoundJoin);
    painter.setPen(railPen);
    painter.drawPath(railLeft);
    painter.drawPath(railRight);

    QPen liftPen(QColor(236, 180, 57));
    liftPen.setWidthF(2.0);
    QPen brakePen(QColor(45, 47, 49));
    brakePen.setWidthF(3.0);
    for (std::size_t i = 0; i < geometry.ties.size(); i += 5U) {
        const auto& tie = geometry.ties[i];
        const auto sample = route.sample(tie.distance_m);
        if (!sample) continue;
        const auto marker = ch::coaster::track_point(*sample, 0.0, 0.15);
        const QPointF p = projection.map(marker.x, marker.y, marker.z);
        if (sample->drive_mode == ch::coaster::DriveMode::Lift) {
            painter.setPen(liftPen);
            painter.drawEllipse(p, 1.7, 1.7);
        } else if (sample->drive_mode == ch::coaster::DriveMode::Brake) {
            painter.setPen(brakePen);
            painter.drawLine(p + QPointF(-2.4, -1.3), p + QPointF(2.4, 1.3));
        }
    }
}

'''
    source = source[:begin] + replacement + source[end:]
    source = source.replace('draw_track(painter,projection,samples);',
                            'draw_track(painter,projection,route);')
    source = source.replace('draw_track(painter, projection, samples);',
                            'draw_track(painter, projection, route);')
    return source


def patch_proof_source(source: str) -> str:
    return source.replace('draw_track(painter, projection, samples);',
                          'draw_track(painter, projection, route);')


def main():
    args = parse_args()
    source_project = repo_path(args.project)
    out = repo_path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    tmp = REPO / 'out/ch_blender_agent/.coaster_track_geometry_v5_tmp'
    build = REPO / 'build/ch-coaster-track-geometry-v5-worker4'
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    geometry_dir = tmp / 'geometry'
    structure_dir = tmp / 'structure'
    motion_dir = tmp / 'motion'
    frames = tmp / 'frames'
    frames.mkdir(parents=True)

    v5 = load_v5_module()
    v5.geometry(source_project, geometry_dir)
    v5.structure(structure_dir)
    v5.motion(motion_dir)

    project = geometry_dir / 'coaster_flame_switchback_04.mapforge.json'
    structure = structure_dir / 'coaster_project_video_main_v5.cpp'
    motion = motion_dir / 'coaster_video_proof_main_v5.cpp'
    if not project.is_file() or not structure.is_file() or not motion.is_file():
        raise RuntimeError('V5 refinement inputs were not regenerated')

    patched_structure = tmp / 'coaster_project_video_main_track_geometry.cpp'
    patched_motion = tmp / 'coaster_video_proof_main_track_geometry.cpp'
    patched_structure.write_text(patch_track_source(structure.read_text(encoding='utf-8')), encoding='utf-8')
    patched_motion.write_text(patch_proof_source(motion.read_text(encoding='utf-8')), encoding='utf-8')

    original_base = tmp / 'original_base.cpp'
    original_proof = tmp / 'original_proof.cpp'
    shutil.copy2(BASE, original_base)
    shutil.copy2(PROOF, original_proof)

    try:
        shutil.copy2(patched_structure, BASE)
        shutil.copy2(patched_motion, PROOF)
        run(['cmake', '-S', 'tools/animation_preview/coaster_video_proof', '-B', build, '-G', 'Ninja'])
        run(['cmake', '--build', build, '--target', 'MapForge2CoasterVideoProof', '--parallel'])
        renderer = build / 'MapForge2CoasterVideoProof'
        run([renderer, frames, ATLAS, project])

        capture = load(frames / 'capture_meta.json')
        frame_count = int(capture['frameCount'])
        mp4 = out / 'coaster_flame_switchback_v5_track_geometry.mp4'
        sheet = out / 'contact_sheet_switchback_v5_track_geometry.png'
        run(['ffmpeg', '-y', '-framerate', '30', '-i', frames / 'frame_%04d.png',
             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4])
        interval = max(1, frame_count // 12)
        vf = f"select='not(mod(n\\,{interval}))',scale=640:-1,tile=4x3"
        run(['ffmpeg', '-y', '-i', mp4, '-vf', vf, '-frames:v', '1', '-update', '1', sheet])

        shutil.copy2(frames / 'capture_meta.json', out / 'capture_meta.json')
        shutil.copy2(project, out / 'coaster_flame_switchback_04.mapforge.json')
        write(out / 'track_geometry_report.json', {
            'contract': 'CH_COASTER_TRACK_GEOMETRY_VIDEO_PROOF_V1',
            'status': 'ok',
            'trackContract': 'CH_COASTER_TRACK_GEOMETRY_V1',
            'projectId': 'coaster.flame.switchback.04',
            'sourceRevision': 'Switchback V5',
            'frameCount': frame_count,
            'fps': 30,
            'routeLengthM': capture.get('routeMeters'),
            'lapSeconds': capture.get('lapSeconds'),
            'motionModel': capture.get('motionModel'),
            'usesRuntimeTrackGeometry': True,
            'railFrame': 'transported_centerline_right_up',
            'video': mp4.name,
            'contactSheet': sheet.name,
        })
        write(out / 'worker_summary.json', {
            'contract': 'CH_COASTER_WORKER_TASK_REPORT_V2',
            'task': 'track_geometry_video',
            'status': 'ok',
        })
    finally:
        shutil.copy2(original_base, BASE)
        shutil.copy2(original_proof, PROOF)


if __name__ == '__main__':
    main()
