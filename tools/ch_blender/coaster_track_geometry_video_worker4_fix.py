#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKER = HERE / 'coaster_track_geometry_video_worker4.py'

spec = importlib.util.spec_from_file_location('ch_coaster_track_geometry_worker4_base', WORKER)
if spec is None or spec.loader is None:
    raise RuntimeError('cannot load coaster track geometry worker')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

base_loader = worker.load_v5_module
base_track_patch = worker.patch_track_source


def patch_track_source_with_visual_weight(source: str) -> str:
    source = base_track_patch(source)
    replacements = {
        'outline.setWidthF(5.2);': 'outline.setWidthF(6.2);',
        'steel.setWidthF(3.0);': 'steel.setWidthF(3.6);',
        'spineOutline.setWidthF(8.0);': 'spineOutline.setWidthF(10.0);',
        'spinePen.setWidthF(5.0);': 'spinePen.setWidthF(6.2);',
        'tieOutline.setWidthF(4.0);': 'tieOutline.setWidthF(4.8);',
        'tiePen.setWidthF(2.5);': 'tiePen.setWidthF(3.0);',
        'railShadow.setWidthF(4.4);': 'railShadow.setWidthF(5.4);',
        'railPen.setWidthF(2.5);': 'railPen.setWidthF(3.2);',
    }
    for old, new in replacements.items():
        if old not in source:
            raise RuntimeError(f'visual track marker missing: {old}')
        source = source.replace(old, new, 1)
    return source


def load_v5_module_with_output_dirs():
    v5 = base_loader()
    original_structure = v5.structure
    original_motion = v5.motion

    def structure(out):
        out.mkdir(parents=True, exist_ok=True)
        result = original_structure(out)
        path = out / 'coaster_project_video_main_v5.cpp'
        source = path.read_text(encoding='utf-8')
        marker = '''    painter.drawRoundedRect(QRectF(sign.x()-20.0, sign.y()-8.0, 40.0, 16.0), 3.0, 3.0);\n}'''
        if marker not in source:
            raise RuntimeError('station refinement marker missing')
        refinement = r'''    painter.drawRoundedRect(QRectF(sign.x()-20.0, sign.y()-8.0, 40.0, 16.0), 3.0, 3.0);

    // V6 presentation pass: stronger eaves, platform railings and a defined
    // entrance apron make the station read as part of the attraction rather
    // than a bare rectangle beside the track.
    QPen eave(QColor(238,184,61)); eave.setWidthF(2.2);
    painter.setPen(eave);
    painter.drawLine(p.map(9.4,-3.0,2.31), p.map(25.6,-3.0,2.31));
    painter.drawLine(p.map(9.4, 3.0,2.31), p.map(25.6, 3.0,2.31));

    QPen railOutline(QColor(55,42,36)); railOutline.setWidthF(3.5);
    QPen railGold(QColor(222,169,57)); railGold.setWidthF(1.8);
    for (double y : {-2.72, 2.72}) {
        const QPointF ra = p.map(10.2,y,0.88), rb = p.map(24.8,y,0.88);
        painter.setPen(railOutline); painter.drawLine(ra,rb);
        painter.setPen(railGold); painter.drawLine(ra,rb);
        for (double x : {10.2, 13.8, 17.5, 21.2, 24.8}) {
            const QPointF pa = p.map(x,y,0.08), pb = p.map(x,y,0.92);
            painter.setPen(railOutline); painter.drawLine(pa,pb);
            painter.setPen(railGold); painter.drawLine(pa,pb);
        }
    }

    QPolygonF apron;
    apron << p.map(8.0,-1.35,0.035) << p.map(9.5,-1.35,0.035)
          << p.map(9.5, 1.35,0.035) << p.map(8.0, 1.35,0.035);
    painter.setPen(QPen(QColor(83,67,51),1.6));
    painter.setBrush(QColor(208,180,135));
    painter.drawPolygon(apron);

    QPen platformJoint(QColor(150,119,82,150)); platformJoint.setWidthF(1.0);
    painter.setPen(platformJoint);
    for (double x : {12.0, 15.5, 19.0, 22.5}) {
        painter.drawLine(p.map(x,-3.0,0.045), p.map(x,3.0,0.045));
    }
}'''
        source = source.replace(marker, refinement, 1)
        path.write_text(source, encoding='utf-8')
        return result

    def motion(out):
        out.mkdir(parents=True, exist_ok=True)
        return original_motion(out)

    v5.structure = structure
    v5.motion = motion
    return v5


worker.patch_track_source = patch_track_source_with_visual_weight
worker.load_v5_module = load_v5_module_with_output_dirs
worker.main()
