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
    mesh_name = ""

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
            mesh_name = parts[1]
            mesh = Mesh()
            current.meshes[mesh_name] = mesh
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
            mesh_name = ""
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


def draw_scene(items: List[Geometry], highlight: str | None = None) -> Image.Image:
    width, height = 960, 640
    img = Image.new("RGBA", (width, height), (239, 242, 233, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    minx, miny, maxx, maxy = bounds(items)
    spanx = max(maxx - minx, 1.0)
    spany = max(maxy - miny, 1.0)
    scale = min((width - 150) / spanx, (height - 120) / spany)
    ox = 75 - minx * scale
    oy = 60 - miny * scale

    # Simple ground guide.
    for gx in range(-12, 14):
        a = project((gx, -10, -0.02), scale, ox, oy)
        b = project((gx, 14, -0.02), scale, ox, oy)
        draw.line([a, b], fill=(170, 180, 160, 38), width=1)
    for gy in range(-10, 15):
        a = project((-12, gy, -0.02), scale, ox, oy)
        b = project((13, gy, -0.02), scale, ox, oy)
        draw.line([a, b], fill=(170, 180, 160, 38), width=1)

    palette = {
        "ballast": (118, 111, 102, 255),
        "sleepers": (95, 61, 38, 255),
        "left_rail": (73, 78, 84, 255),
        "right_rail": (73, 78, 84, 255),
    }
    active_palette = {
        "ballast": (133, 120, 84, 255),
        "sleepers": (118, 72, 38, 255),
        "left_rail": (210, 160, 56, 255),
        "right_rail": (210, 160, 56, 255),
    }

    triangles = []
    for item in items:
        for mesh_name, mesh in item.meshes.items():
            color = (active_palette if item.name == highlight else palette)[mesh_name]
            for tri in mesh.triangles:
                verts = [mesh.vertices[i] for i in tri]
                depth = sum(v[0] + v[1] + v[2] * 3.0 for v in verts) / 3.0
                pts = [project(v, scale, ox, oy) for v in verts]
                triangles.append((depth, pts, color))

    for _, pts, color in sorted(triangles, key=lambda t: t[0]):
        draw.polygon(pts, fill=color)

    # Labels and legend.
    draw.rounded_rectangle((24, 20, 420, 104), radius=14, fill=(20, 24, 28, 214))
    draw.text((42, 36), "CITY HORIZON — PROVA VISUAL DO TRILHO PROCEDURAL", fill=(255, 255, 255, 255))
    draw.text((42, 62), "Geometria real: RailMeshBuilder / RailPathBuilder", fill=(210, 215, 220, 255))
    draw.text((42, 82), "reta → curva → agulha/bifurcação", fill=(210, 215, 220, 255))

    draw.rounded_rectangle((width - 276, 20, width - 24, 86), radius=12, fill=(255, 255, 255, 220), outline=(50, 55, 60, 120))
    draw.text((width - 258, 36), "Câmera de prova: projeção 2:1", fill=(32, 36, 40, 255))
    draw.text((width - 258, 58), "Volume: lastro + dormentes + aço", fill=(32, 36, 40, 255))

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
