"""Rounded human-silhouette refinement for the City Horizon visitor MVP.

V3 keeps the guarded V1/V2 contracts and conservative two-frame walk. It changes
only authoring/review presentation:

- torso is a smooth multi-ring human volume instead of a beveled prism;
- V2 tapered limbs, rounded joints, head and shoes are reused;
- SOUTH proxy is deliberately framed as a close visual-review shot so silhouette
  problems are visible before any four-direction bake is allowed.

The close proxy is not a runtime scale decision. Runtime scale is validated later
in gameplay context after the body silhouette is approved.
"""
from __future__ import annotations

import math

import bpy

import build_scene as bs
import build_visitor_guarded as v1
import build_visitor_guarded_v2 as v2


def rounded_torso(authored, parent, name, location, dimensions, material,
                  top_width_scale=1.0, bottom_width_scale=0.78,
                  top_depth_scale=0.96, bottom_depth_scale=0.82,
                  bevel=0.045):
    """Create a smooth torso with shoulder/chest/waist cross-sections.

    The signature intentionally matches V2.tapered_prism so the rest of the
    visitor rig remains unchanged.
    """
    width, depth, height = map(float, dimensions)
    segments = 16

    # z, width scale, depth scale. More shoulder mass at the top and a gentle
    # waist reduction keep the old-tycoon silhouette readable without a box body.
    rings = [
        (-0.50, max(0.68, bottom_width_scale * 0.92), max(0.72, bottom_depth_scale * 0.96)),
        (-0.18, 0.78, 0.84),
        (0.18, 0.90, 0.90),
        (0.43, 1.00, 0.96),
        (0.50, 0.92, 0.90),
    ]

    vertices = []
    for zf, wscale, dscale in rings:
        z = zf * height
        rx = width * wscale * 0.5
        ry = depth * dscale * 0.5
        for i in range(segments):
            angle = (2.0 * math.pi * i) / segments
            vertices.append((rx * math.cos(angle), ry * math.sin(angle), z))

    faces = []
    ring_count = len(rings)
    for r in range(ring_count - 1):
        start = r * segments
        nxt = (r + 1) * segments
        for i in range(segments):
            j = (i + 1) % segments
            faces.append((start + i, start + j, nxt + j, nxt + i))

    # End caps.
    faces.append(tuple(reversed(tuple(range(segments)))))
    last = (ring_count - 1) * segments
    faces.append(tuple(last + i for i in range(segments)))

    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj.parent = parent
    obj.location = tuple(location)

    # One subdivision level rounds the cross-section while preserving the compact
    # tycoon silhouette. Shade smoothing avoids primitive facets after downsample.
    subdivision = obj.modifiers.new(name="VisitorTorsoSubdivision", type="SUBSURF")
    subdivision.subdivision_type = "CATMULL_CLARK"
    subdivision.levels = 1
    subdivision.render_levels = 1
    for polygon in obj.data.polygons:
        polygon.use_smooth = True

    authored.append(obj)
    return obj


# Reuse every V2 body improvement except the prism torso.
v2.tapered_prism = rounded_torso
v1.build_visitor = v2.build_visitor_v2

_original_build_for_gate = v1.build_for_gate


def build_for_gate_close_review(args):
    result = _original_build_for_gate(args)
    asset, studio, scene, ground, authored, rig, out = result

    # Review-only close framing. This makes the body silhouette inspectable and
    # does not establish the final runtime character size.
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.24)
    bpy.context.view_layer.update()
    rig["root"]["reviewProxyFraming"] = "close_silhouette_review_only"
    return result


v1.build_for_gate = build_for_gate_close_review


if __name__ == "__main__":
    v1.main()
