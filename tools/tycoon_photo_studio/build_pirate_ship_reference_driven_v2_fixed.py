#!/usr/bin/env python3
from __future__ import annotations
import math
import bpy
import build_pirate_ship_reference_driven as base


def build_boat_fixed(root, cfg, M, pivot_z):
    center = float(cfg['centerZ'])
    stations = cfg['stations']

    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, pivot_z))
    pivot = bpy.context.object
    pivot.name = 'SwingPivot'
    pivot.parent = root

    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, center - pivot_z))
    boat = bpy.context.object
    boat.name = 'BoatRoot'
    boat.parent = pivot

    hull = base.loft_hull('ReferenceDrivenHull', stations, M['wood'], boat)

    for side, label in ((-1, 'Port'), (1, 'Starboard')):
        pts = [(float(s['x']), side * float(s['halfWidth']), float(s['gunwaleZ']) + .05) for s in stations]
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            base.beam(f'{label}Gunwale_{i}', a, b, .20, .16, M['accent'], boat)

    for i, s in enumerate(stations[1:-1], 1):
        x = float(s['x'])
        hw = float(s['halfWidth'])
        fz = float(s['floorZ']) + .14
        base.beam(f'CrossRib_{i}', (x, -hw * .92, fz), (x, hw * .92, fz), .16, .18, M['accent'], boat)

    rows = int(cfg['seatRows'])
    span = float(cfg['seatSpan'])
    for i in range(rows):
        x = -span * .5 + span * i / max(1, rows - 1)
        s = base.interp_station(stations, x)
        hw = float(s['halfWidth'])
        floor = float(s['floorZ'])
        base.box(f'SeatBase_{i}', (x, 0, floor + .72), (.72, max(.8, hw * 1.52), .22), M['seat'], boat, .035)
        base.box(f'SeatBack_{i}', (x + .23, 0, floor + 1.18), (.16, max(.8, hw * 1.48), .74), M['seat'], boat, .025)

    for idx, label in ((0, 'Stern'), (-1, 'Bow')):
        s = stations[idx]
        x = float(s['x'])
        hw = float(s['halfWidth'])
        gz = float(s['gunwaleZ'])
        base.box(f'{label}Crest', (x, 0, gz + .65), (.30, hw * 1.55, 1.55), M['trim'], boat, .05)

    # Recipe suspension anchors are WORLD coordinates. Since the suspension
    # meshes are children of SwingPivot, convert every anchor to pivot-local
    # coordinates before creating geometry. The previous builder accidentally
    # added pivotZ twice, producing a 43 m tall false envelope.
    susp = cfg['suspension']
    for i, (top_world, attach_world) in enumerate(zip(susp['topAnchors'], susp['boatAnchors'])):
        top = (float(top_world[0]), float(top_world[1]), float(top_world[2]) - pivot_z)
        attach = (float(attach_world[0]), float(attach_world[1]), float(attach_world[2]) - pivot_z)
        base.beam(f'Suspension_{i}', top, attach, float(susp['beamWidth']), float(susp['beamDepth']), M['accent'], pivot)
        base.cylinder(f'SuspensionJoint_{i}', attach, .38, .46, M['frame'], (math.radians(90), 0, 0), pivot, 20)

    return pivot, hull


base.build_boat = build_boat_fixed

if __name__ == '__main__':
    base.main()
