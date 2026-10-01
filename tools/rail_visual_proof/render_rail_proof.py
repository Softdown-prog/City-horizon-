from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw


@dataclass
class Mesh:
    vertices: List[Tuple[float, float, float]] = field(default_factory=list)
    triangles: List[Tuple[int, int, int]] = field(default_factory=list)


@dataclass
class Geometry:
    name: str
    meshes: Dict[str, Mesh] = field(default_factory=dict)


def parse_export(path: Path) -> List[Geometry]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "CH_RAIL_VISUAL_PROOF_V1":
        raise RuntimeError("unsupported rail proof export")

    items: List[Geometry] = []
    current: Geometry | None = None
    mesh: Mesh | None = None

    for raw in lines[1:]:
        parts = raw.split()
        if not parts:
            continue
        tag = parts[0]
        if tag == "GEOMETRY":
            current = Geometry(parts[1])
            items.append(current)
        elif tag == "MESH":
            if current is None:
                raise RuntimeError("mesh outside geometry")
            mesh = Mesh()
            current.meshes[parts[1]] = mesh
        elif tag == "V":
            if mesh is None:
                raise RuntimeError("vertex outside mesh")
            mesh.vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif tag == "T":
            if mesh is None:
                raise RuntimeError("triangle outside mesh")
            mesh.triangles.append((int(parts[1]), int(parts[2]), int(parts[3])))
        elif tag == "END_GEOMETRY":
            current = None
            mesh = None
    return items


def project(p: Tuple[float, float, float], scale: float, ox: float, oy: float) -> Tuple[float, float]:
    x, y, z = p
    sx = (x - y) * scale + ox
    sy = (x + y) * scale * 0.5 - z * scale * 1.35 + oy
    return sx, sy


def bounds(items: List[Geometry]) -> Tuple[float, float, float, float]:
    xs: List[float] = []
    ys: List[float] = []
    for item in items:
        for mesh in item.meshes.values():
            for v in mesh.vertices:
                sx, sy = project(v, 1.0, 0.0, 0.0)
                xs.append(sx)
                ys.append(sy)
    return min(xs), min(ys), max(xs), max(ys)


def triangle_normal(verts: List[Tuple[float, float, float]]) -> Tuple[float, float, float]:
    ax, ay, az = verts[0]
    bx, by, bz = verts[1]
    cx, cy, cz = verts[2]
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1.0e-9:
        return 0.0, 0.0, 1.0
    return nx / length, ny / length, nz / length


def clamp_channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def shade_color(
    base: Tuple[int, int, int, int],
    mesh_name: str,
    verts: List[Tuple[float, float, float]],
) -> Tuple[int, int, int, int]:
    nx, ny, nz = triangle_normal(verts)
    up = abs(nz)

    # Soft north-west studio light. Absolute lateral components keep opposite
    # rail faces readable without introducing direction-dependent flashing.
    lateral = 0.55 * abs(nx) + 0.45 * abs(ny)
    shade = 0.66 + 0.30 * up + 0.08 * lateral

    cx = sum(v[0] for v in verts) / 3.0
    cy = sum(v[1] for v in verts) / 3.0
    variation = math.sin(cx * 19.17 + cy * 37.31)

    if mesh_name == "ballast":
        shade += variation * 0.035
    elif mesh_name == "sleepers":
        shade += variation * 0.045
        if up > 0.72:
            shade += 0.035
    elif mesh_name in ("left_rail", "right_rail"):
        # The rail head catches a narrow cool highlight; vertical sides stay
        # darker, which makes the rectangular procedural section read as steel.
        if up > 0.72:
            shade += 0.20
        else:
            shade -= 0.055

    r, g, b, a = base
    return (
        clamp_channel(r * shade),
        clamp_channel(g * shade),
        clamp_channel(b * shade),
        a,
    )


def draw_scene(items: List[Geometry], highlight: str | None = None) -> Image.Image:
    width, height = 960, 640
    img = Image.new("RGBA", (width, height), (234, 239, 228, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    minx, miny, maxx, maxy = bounds(items)
    spanx = max(maxx - minx, 1.0)
    spany = max(maxy - miny, 1.0)
    scale = min((width - 150) / spanx, (height - 120) / spany)
    ox = 75 - minx * scale
    oy = 60 - miny * scale

    # Quiet MapForge-like ground guide so the track remains the focus.
    for gx in range(-12, 14):
        a = project((gx, -10, -0.02), scale, ox, oy)
        b = project((gx, 14, -0.02), scale, ox, oy)
        draw.line([a, b], fill=(128, 145, 124, 32), width=1)
    for gy in range(-10, 15):
        a = project((-12, gy, -0.02), scale, ox, oy)
        b = project((13, gy, -0.02), scale, ox, oy)
        draw.line([a, b], fill=(128, 145, 124, 32), width=1)

    palette = {
        "ballast": (132, 130, 122, 255),
        "sleepers": (104, 68, 43, 255),
        "left_rail": (92, 101, 108, 255),
        "right_rail": (92, 101, 108, 255),
    }
    active_palette = {
        "ballast": (151, 137, 97, 255),
        "sleepers": (132, 83, 43, 255),
        "left_rail": (214, 168, 66, 255),
        "right_rail": (214, 168, 66, 255),
    }

    triangles = []
    for item in items:
        for mesh_name, mesh in item.meshes.items():
            base = (active_palette if item.name == highlight else palette)[mesh_name]
            for tri in mesh.triangles:
                verts = [mesh.vertices[i] for i in tri]
                depth = sum(v[0] + v[1] + v[2] * 3.0 for v in verts) / 3.0
                pts = [project(v, scale, ox, oy) for v in verts]
                color = shade_color(base, mesh_name, verts)
                triangles.append((depth, pts, color, mesh_name))

    for _, pts, color, mesh_name in sorted(triangles, key=lambda t: t[0]):
        # Tiny contact shadow for raised wood/steel makes the Z thickness legible
        # while staying compatible with the classic pre-rendered tycoon look.
        if mesh_name != "ballast":
            shadow = [(x + 1.0, y + 1.8) for x, y in pts]
            draw.polygon(shadow, fill=(24, 29, 25, 38))
        draw.polygon(pts, fill=color)

    # Labels and legend.
    draw.rounded_rectangle((24, 20, 440, 104), radius=14, fill=(20, 24, 28, 220))
    draw.text((42, 36), "CITY HORIZON — TRILHO PROCEDURAL REFINADO", fill=(255, 255, 255, 255))
    draw.text((42, 62), "Geometria real: RailMeshBuilder / RailPathBuilder", fill=(210, 215, 220, 255))
    draw.text((42, 82), "lastro pedra + dormentes madeira + aço sombreado", fill=(210, 215, 220, 255))

    draw.rounded_rectangle((width - 292, 20, width - 24, 90), radius=12, fill=(255, 255, 255, 225), outline=(50, 55, 60, 110))
    draw.text((width - 274, 36), "Câmera: projeção CH 2:1", fill=(32, 36, 40, 255))
    draw.text((width - 274, 58), "Volume: lastro + dormentes + aço", fill=(32, 36, 40, 255))

    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    items = parse_export(Path(args.input))
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    png = draw_scene(items)
    png.save(outdir / "rail_proof.png", format="PNG", optimize=False)

    sequence = [None, "straight_a", "curve", "straight_b", "turnout_lead", "turnout_through", "turnout_diverging", None]
    frames = [draw_scene(items, h) for h in sequence]
    frames[0].save(
        outdir / "rail_proof.gif",
        save_all=True,
        append_images=frames[1:],
        duration=520,
        loop=0,
        disposal=2,
    )

    print(outdir / "rail_proof.png")
    print(outdir / "rail_proof.gif")


if __name__ == "__main__":
    main()
