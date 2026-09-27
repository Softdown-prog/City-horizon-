"""Offline 2D bake of the CH Actor Lab visitor; requires only Pillow.

The character is drawn from one small 3D joint description projected through
CH_CAMERA_V1. This is a separate, deterministic production candidate: it does
not execute the browser prototype or copy pixels from a black-background shot.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

FRAME = (48, 64)
ANCHOR = (24, 60)
SUPERSAMPLE = 4
YAW = math.radians(45)
ELEVATION = math.radians(30)
SCALE = 52
COLORS = {
    "jacket": "#15803d", "shirt": "#f8fafc", "pants": "#1d4ed8",
    "hair": "#5a3825", "skin": "#f6c29e", "shoes": "#1f2937",
}
# +Z projects screen SW, +X SE, -X NW and -Z NE. Keep these
# rotations in lockstep with the engine's logical X/Y tile projection.
DIRECTIONS = (("S", "SW", 0), ("E", "SE", math.pi / 2),
              ("W", "NW", -math.pi / 2), ("N", "NE", math.pi))


def rgb(hex_color: str, factor: float = 1) -> tuple[int, int, int, int]:
    value = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(max(0, min(255, round(c * factor))) for c in value) + (255,)


def phases(count: int) -> list[float]:
    if count == 2:
        return [.25, .75]
    return [i / count for i in range(count)]


class ActorPainter:
    def __init__(self, direction: float, phase: float, *, idle: bool = False):
        self.direction = direction
        self.phase = phase
        self.idle = idle
        self.image = Image.new("RGBA", (FRAME[0] * SUPERSAMPLE,
                                        FRAME[1] * SUPERSAMPLE))
        self.draw = ImageDraw.Draw(self.image)
        self.sine = 0 if idle else math.sin(2 * math.pi * phase)
        self.cosine = 0 if idle else math.cos(2 * math.pi * phase)
        self.bob = 0 if idle else .004 * abs(math.sin(4 * math.pi * phase))

    def project(self, point: tuple[float, float, float]) -> tuple[float, float]:
        x, y, z = point
        c, s = math.cos(self.direction), math.sin(self.direction)
        x, z = c * x + s * z, -s * x + c * z
        right = math.cos(YAW) * x - math.sin(YAW) * z
        up = math.cos(ELEVATION) * y - math.sin(ELEVATION) * (
            math.sin(YAW) * x + math.cos(YAW) * z)
        return ((ANCHOR[0] + SCALE * right) * SUPERSAMPLE,
                (ANCHOR[1] - SCALE * up) * SUPERSAMPLE)

    def depth(self, point: tuple[float, float, float]) -> float:
        x, _, z = point
        c, s = math.cos(self.direction), math.sin(self.direction)
        x, z = c * x + s * z, -s * x + c * z
        return math.sin(YAW) * x + math.cos(YAW) * z

    def ellipse(self, center: tuple[float, float], radius: tuple[float, float],
                fill: tuple[int, int, int, int], outline=None, width: float = 0) -> None:
        x, y = center
        rx, ry = radius[0] * SUPERSAMPLE, radius[1] * SUPERSAMPLE
        box = (round(x - rx), round(y - ry), round(x + rx), round(y + ry))
        self.draw.ellipse(box, fill=fill, outline=outline,
                          width=max(1, round(width * SUPERSAMPLE)))

    def stroke(self, a, b, width: float, fill, shade=None) -> None:
        p, q = self.project(a), self.project(b)
        w = round(width * SUPERSAMPLE)
        self.draw.line((p, q), fill=rgb("#132334"), width=w + 2 * SUPERSAMPLE,
                       joint="curve")
        for pos in (p, q):
            self.ellipse(pos, (width / 2 + 1, width / 2 + 1), rgb("#132334"))
        self.draw.line((p, q), fill=fill, width=w, joint="curve")
        for pos in (p, q):
            self.ellipse(pos, (width / 2, width / 2), fill)
        if shade:
            self.draw.line((p[0] - SUPERSAMPLE, p[1], q[0] - SUPERSAMPLE, q[1]),
                           fill=shade, width=max(1, w // 5))

    def leg(self, sign: int) -> None:
        swing = sign * self.sine
        hip = (sign * .078, .405, 0)
        z = .145 * swing + .025 * sign * self.cosine
        # Two weight-transfer poses at phase 0 and 0.5 stay distinct.
        lifted = max(0, swing) * .032 + max(0, sign * self.cosine) * .012
        foot = (sign * (.082 + .008 * abs(self.sine)), .035 + lifted, z)
        knee = (sign * .08, .225 + lifted * .33,
                z * .42 - .028 * max(0, swing))
        base = rgb(COLORS["pants"], .78 if sign < 0 else .95)
        self.stroke(hip, knee, 5.0, base, rgb(COLORS["pants"], 1.13))
        self.stroke(knee, (foot[0], foot[1] + .055, foot[2] - .016),
                    4.6, base, rgb(COLORS["pants"], 1.18))
        toe = (foot[0], foot[1], foot[2] + .085)
        self.stroke((foot[0], foot[1], foot[2] - .03), toe, 3.8,
                    rgb(COLORS["shoes"]), rgb(COLORS["shoes"], 1.45))

    def arm(self, sign: int) -> None:
        opposite = -sign * self.sine
        shoulder = (sign * .175, .685 + self.bob, -.005)
        elbow = (sign * .205, .565 + self.bob, .055 * opposite)
        hand = (sign * .19, .445 + self.bob, .115 * opposite + .01)
        base = rgb(COLORS["jacket"], .77 if sign < 0 else 1.03)
        self.stroke(shoulder, elbow, 4.5, base, rgb(COLORS["jacket"], 1.2))
        self.stroke(elbow, (hand[0], hand[1] + .042, hand[2]),
                    3.7, base)
        p = self.project(hand)
        self.ellipse(p, (1.7, 2.2), rgb(COLORS["skin"]),
                     outline=rgb("#a86d4a"), width=.5)

    def torso(self) -> None:
        coords = [(-.12, .415, .015), (.12, .415, .015),
                  (.145, .685, .015), (.085, .724, .005),
                  (-.085, .724, .005), (-.145, .685, .015)]
        points = [self.project((x, y + self.bob, z)) for x, y, z in coords]
        self.draw.polygon(points, fill=rgb(COLORS["jacket"]),
                          outline=rgb("#0c5339"), width=SUPERSAMPLE)
        # A visible chest and two lapels make SOUTH/EAST unambiguously frontal.
        facing = math.cos(self.direction - YAW)
        if facing > .2:
            chest = [self.project((x, y + self.bob, .113)) for x, y in
                     [(-.048, .68), (.048, .68), (.052, .455), (-.052, .455)]]
            self.draw.polygon(chest, fill=rgb(COLORS["shirt"]),
                              outline=rgb("#cbd5d6"), width=SUPERSAMPLE)
            for sign in (-1, 1):
                p = [self.project((x, y + self.bob, .126)) for x, y in
                     [(sign * .05, .705), (sign * .105, .67),
                      (sign * .085, .465), (sign * .053, .465)]]
                self.draw.polygon(p, fill=rgb(COLORS["jacket"], 1.10))
        else:
            p, q = self.project((-.07, .69, -.045)), self.project((-.05, .46, -.045))
            self.draw.line((p, q), fill=rgb(COLORS["jacket"], 1.13),
                           width=SUPERSAMPLE)

    def head(self) -> None:
        front = math.cos(self.direction - YAW)
        center = self.project((0, .875 + self.bob, 0))
        self.ellipse(center, (8.4, 8.4), rgb("#402919"))
        self.ellipse((center[0] - SUPERSAMPLE, center[1] - SUPERSAMPLE),
                     (7.5, 7.2), rgb(COLORS["hair"]),
                     outline=rgb("#3b261b"), width=.5)
        if front > .2:
            face_center = self.project((0, .858 + self.bob, .113))
            self.ellipse(face_center, (5.7, 6.3), rgb(COLORS["skin"]),
                         outline=rgb("#ae7654"), width=.5)
            hairline = (face_center[0], face_center[1] - 4.7 * SUPERSAMPLE)
            self.ellipse(hairline, (6.2, 2.6), rgb(COLORS["hair"]),
                         outline=rgb("#3b261b"), width=.3)
            for x in (-2.1, 2.1):
                self.ellipse((face_center[0] + x * SUPERSAMPLE,
                              face_center[1] + .1 * SUPERSAMPLE),
                             (.62, .85), rgb("#31241d"))
        else:
            self.ellipse((center[0] - SUPERSAMPLE, center[1] - 2 * SUPERSAMPLE),
                         (5.3, 2.7), rgb(COLORS["hair"], 1.17))

    def render(self) -> Image.Image:
        # Ground shadow is separate and never baked into the body silhouette.
        ground = self.project((0, .004, 0))
        self.ellipse((ground[0], ground[1] + SUPERSAMPLE), (9, 2.4),
                     (12, 21, 22, 63))
        order = sorted((-1, 1), key=lambda sign: self.depth((sign * .18, 0, 0)))
        for sign in order:
            self.leg(sign)
        self.arm(order[0])
        self.torso()
        self.arm(order[1])
        self.head()
        return self.image.resize(FRAME, Image.Resampling.LANCZOS)


def map_board(sheet: Image.Image, count: int, capture: Path, out: Path) -> None:
    background = Image.open(capture).convert("RGBA").crop((260, 310, 640, 690))
    if background.size != (380, 380):
        raise ValueError("MapForge capture must cover the established review crop")
    board = Image.new("RGBA", (760, 760))
    for row, (logical, screen, _) in enumerate(DIRECTIONS):
        scene = background.copy()
        indices = (count // 4, 3 * count // 4) if count >= 4 else (0, 1)
        for col, (x, y) in zip(indices, ((142, 306), (200, 335))):
            sprite = sheet.crop((col * FRAME[0], row * FRAME[1],
                                 (col + 1) * FRAME[0], (row + 1) * FRAME[1]))
            scene.alpha_composite(sprite, (x - ANCHOR[0], y - ANCHOR[1]))
        draw = ImageDraw.Draw(scene)
        draw.rectangle((0, 0, 210, 34), fill=(13, 30, 27, 235))
        draw.text((9, 9), f"{logical} / {screen}   passos {indices[0]} e {indices[1]}",
                  fill="white")
        board.alpha_composite(scene, ((row % 2) * 380, (row // 2) * 380))
    draw = ImageDraw.Draw(board)
    draw.rectangle((0, 735, 760, 760), fill=(13, 30, 27, 235))
    draw.text((9, 742), "Previa em escala de jogo sobre captura MapForge; nao e runtime SDL3.",
              fill=(255, 240, 211))
    board.convert("RGB").save(out)


def map_motion(sheet: Image.Image, count: int, capture: Path, out: Path) -> None:
    background = Image.open(capture).convert("RGBA").crop((260, 310, 640, 690))
    vectors = ((-64, 32), (64, 32), (-64, -32), (64, -32))
    surfaces = (("cimento", (143, 151, 149, 225)), ("areia", (184, 153, 101, 225)),
                ("rua", (88, 97, 106, 230)), ("terra", (151, 117, 83, 225)))
    frames = []
    for tick in range(count * 2):
        board = Image.new("RGBA", (760, 760))
        for row, (logical, screen, _) in enumerate(DIRECTIONS):
            scene = background.copy()
            dx, dy = vectors[row]
            # A labelled validation overlay. The actual runtime reads the
            # RoadManager / SidewalkManager; this captured map has only grass.
            overlay = Image.new("RGBA", scene.size)
            floor = ImageDraw.Draw(overlay)
            surface_name, fill = surfaces[row]
            for step in range(3):
                cx, cy = 142 + step * dx, 306 + step * dy
                floor.polygon(((cx, cy - 32), (cx + 64, cy),
                               (cx, cy + 32), (cx - 64, cy)),
                              fill=fill, outline=(50, 60, 61, 255), width=1)
            scene.alpha_composite(overlay)
            # 0.30 tile/s at eight 137.5 ms frames: world motion is continuous.
            progress = .30 * tick * (1.1 / count)
            foot_x = 142 + round(dx * progress)
            foot_y = 306 + round(dy * progress)
            contact = ImageDraw.Draw(scene)
            contact.ellipse((foot_x - 2, foot_y - 2, foot_x + 2, foot_y + 2),
                            fill=(250, 205, 84, 255))
            col = tick % count
            sprite = sheet.crop((col * FRAME[0], row * FRAME[1],
                                 (col + 1) * FRAME[0], (row + 1) * FRAME[1]))
            scene.alpha_composite(sprite, (foot_x - ANCHOR[0], foot_y - ANCHOR[1]))
            draw = ImageDraw.Draw(scene)
            draw.rectangle((0, 0, 154, 31), fill=(13, 30, 27, 235))
            draw.text((8, 8), f"{logical} / {screen}  {surface_name}  q{col}", fill="white")
            board.alpha_composite(scene, ((row % 2) * 380, (row // 2) * 380))
        frames.append(board.convert("RGB"))
    duration = round(1100 / count)
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=duration, loop=0, optimize=True)


def generate(output: Path, frame_count: int, capture: Path | None,
             catalog_path: Path | None = None) -> dict:
    if frame_count not in (2, 4, 8):
        raise ValueError("frame count must be 2, 4 or 8")
    output.mkdir(parents=True, exist_ok=True)
    phase_list = phases(frame_count)
    sheet = Image.new("RGBA", (FRAME[0] * frame_count, FRAME[1] * 4))
    frame_dir = output / "frames"
    frame_dir.mkdir(exist_ok=True)
    for row, (logical, _, angle) in enumerate(DIRECTIONS):
        for col, phase in enumerate(phase_list):
            frame = ActorPainter(angle, phase).render()
            sheet.alpha_composite(frame, (col * FRAME[0], row * FRAME[1]))
            frame.save(frame_dir / f"{logical.lower()}_walk_{col:02d}.png")
    sheet.save(output / "ch_actor_walk.png")
    idle = Image.new("RGBA", (FRAME[0], FRAME[1] * 4))
    for row, (logical, _, angle) in enumerate(DIRECTIONS):
        frame = ActorPainter(angle, 0, idle=True).render()
        idle.alpha_composite(frame, (0, row * FRAME[1]))
        frame.save(frame_dir / f"{logical.lower()}_idle.png")
    idle.save(output / "ch_actor_idle.png")
    manifest = {
        "contract": "CH_ACTOR_SOFTWARE_CANDIDATE_V1", "status": "CANDIDATE",
        "camera": {"yawDeg": 45, "elevationDeg": 30, "projection": "orthographic"},
        "frame": {"width": FRAME[0], "height": FRAME[1], "anchor": ANCHOR},
        "sheet": {"width": sheet.width, "height": sheet.height,
                  "rows": [d[0] for d in DIRECTIONS], "framePhases": phase_list},
        "palette": COLORS, "runtimePromotion": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if catalog_path:
        clips = []
        prefix = "tools/ch_actor_lab/art/software_v1/frames"
        for logical, _, _ in DIRECTIONS:
            direction = {"S": "south", "E": "east", "W": "west", "N": "north"}[logical]
            key = logical.lower()
            clips.append({"id": f"idle_{direction}", "state": "idle",
                          "direction": direction, "fps": 1, "loop": True,
                          "frames": [f"{prefix}/{key}_idle.png"]})
            clips.append({"id": f"walking_{direction}", "state": "walking",
                          "direction": direction, "fps": frame_count / 1.1,
                          "loop": True,
                          "frames": [f"{prefix}/{key}_walk_{i:02d}.png"
                                     for i in range(frame_count)]})
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(json.dumps({"id": "ch_actor_software_v1",
                                            "status": "candidate_f8_only",
                                            "clips": clips}, indent=2) + "\n")
    if capture:
        map_board(sheet, frame_count, capture, output / "walk_on_map.png")
        map_motion(sheet, frame_count, capture, output / "walk_on_map.gif")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, choices=(2, 4, 8), default=8)
    parser.add_argument("--map-capture", type=Path)
    parser.add_argument("--catalog", type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.output, args.frames, args.map_capture,
                              args.catalog), indent=2))
