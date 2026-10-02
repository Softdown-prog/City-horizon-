"""Guarded Blender builder for Viking Ship rebuild V6 TARGET.

V6 uses only viking_ship_rebuild_v6_target_geometry for ride-specific geometry.
The legacy 5x4 validator in the shared Viking builder is compatibility-shimmed only
for this recipe; authoritative metadata and review remain 7x6.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import build_viking_ship_guarded as base
import viking_ship_rebuild_v6_target_geometry as target

_REAL_LOAD_JSON = base.load_json
_BASE_BUILD_FOR_GATE = base.build_for_gate
_BASE_WRITE_METADATA = base.write_metadata


def _compat_load_json(path):
    data = _REAL_LOAD_JSON(path)
    if data.get('rebuild', {}).get('id') == 'CH_VIKING_SHIP_REBUILD_V6_TARGET':
        data = copy.deepcopy(data)
        data['footprint'] = {'widthTiles': 5, 'depthTiles': 4}
    return data


def _build_base(root, geometry, materials):
    return target.build_base(root, geometry, materials)


def _build_supports(root, geometry, materials):
    return target.build_supports(root, geometry, materials)


def _build_loading_zone(root, geometry, materials):
    return target.build_loading_zone(root, geometry, materials)


def _build_swing_group(root, geometry, materials):
    return target.build_swing_group(root, geometry, materials)


base.hull_sections = target.hull_sections
base.build_base = _build_base
base.build_supports = _build_supports
base.build_loading_zone = _build_loading_zone
base.build_swing_group = _build_swing_group


def _target_gate(recipe):
    g = recipe['geometry']
    fp = recipe['footprint']
    if fp.get('widthTiles') != 7 or fp.get('depthTiles') != 6:
        raise RuntimeError('CH_VIKING_V6_REQUIRES_7X6')
    if float(g['pivotZ']) < 22.0:
        raise RuntimeError('CH_VIKING_V6_PIVOT_TOO_LOW')
    if float(g['shipLength']) < 18.0:
        raise RuntimeError('CH_VIKING_V6_SHIP_TOO_SHORT')
    if int(g['seatRows']) < 12:
        raise RuntimeError('CH_VIKING_V6_SEATING_TOO_SPARSE')
    if float(g['platformTopZ']) < 1.2 or float(g['stairWidth']) < 4.5:
        raise RuntimeError('CH_VIKING_V6_PLATFORM_NOT_SUBSTANTIAL')
    if float(g['supportBeamWidth']) < 1.1:
        raise RuntimeError('CH_VIKING_V6_SUPPORTS_TOO_THIN')
    return {
        'passed': True,
        'footprint': '7x6',
        'pivotZ': g['pivotZ'],
        'shipLength': g['shipLength'],
        'seatRows': g['seatRows'],
        'supportBeamWidth': g['supportBeamWidth'],
        'platformTopZ': g['platformTopZ'],
        'stairWidth': g['stairWidth'],
    }


def _build_for_gate_v6(args):
    actual = _REAL_LOAD_JSON(args.recipe)
    if actual.get('rebuild', {}).get('id') != 'CH_VIKING_SHIP_REBUILD_V6_TARGET':
        raise RuntimeError('CH_VIKING_V6_WRONG_RECIPE')
    report = _target_gate(actual)

    base.load_json = _compat_load_json
    try:
        recipe, studio, scene, root, pivot, ground, authored, out = _BASE_BUILD_FOR_GATE(args)
    finally:
        base.load_json = _REAL_LOAD_JSON

    recipe['footprint'] = copy.deepcopy(actual['footprint'])
    recipe['rebuild'] = copy.deepcopy(actual['rebuild'])
    root['footprint'] = '7x6'
    root['rebuildContract'] = 'CH_VIKING_SHIP_REBUILD_V6_TARGET'
    root['legacyVikingGeometryUsed'] = False
    root['approvedTargetImageDriven'] = True
    root['targetScaleGatePassed'] = True
    root['targetGate'] = json.dumps(report, sort_keys=True)
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v6(recipe, scene, out):
    _BASE_WRITE_METADATA(recipe, scene, out)
    path = Path(out) / 'studio_metadata.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    payload['stage'] = 'v6_target_image_redraw_proxy'
    payload['recipe'] = 'tools/tycoon_photo_studio/assets/park_viking_ship_7x6.rebuild_v6_target.json'
    payload['builder'] = 'tools/tycoon_photo_studio/build_viking_ship_rebuild_v6_target_guarded.py'
    payload['geometryPass'] = 'tools/tycoon_photo_studio/viking_ship_rebuild_v6_target_geometry.py'
    payload['rebuildContract'] = 'CH_VIKING_SHIP_REBUILD_V6_TARGET'
    payload['footprint'] = {'widthTiles': 7, 'depthTiles': 6}
    payload['legacyVikingGeometryUsed'] = False
    payload['approvedTargetImageDriven'] = True
    payload['targetGate'] = _target_gate(recipe)
    payload['reviewAgainst'] = [
        'massive decorated A-frame',
        'large axle and bearing housings',
        'long deep ship with dense seating',
        'long suspension arms',
        'raised industrial platform',
        'wide stairs and perimeter railings',
    ]
    payload['animationDeferred'] = True
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


base.build_for_gate = _build_for_gate_v6
base.write_metadata = _write_metadata_v6

if __name__ == '__main__':
    base.main()
