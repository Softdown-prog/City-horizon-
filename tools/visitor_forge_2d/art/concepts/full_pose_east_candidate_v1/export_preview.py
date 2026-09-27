"""Downsample two complete EAST walk paintings for a gameplay-scale review."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
TOOL_ROOT = HERE.parents[2]
sys.path.insert(0, str(TOOL_ROOT / "src"))

from visitor_forge_2d.core.exporter import alpha_safe_resize  # noqa: E402


def main() -> None:
    frames: list[Image.Image] = []
    source_hashes = {}
    for phase in ("a", "b"):
        path = HERE / f"east_pose_{phase}_master.png"
        with Image.open(path) as image:
            master = image.convert("RGBA")
        if master.size != (512, 512):
            raise ValueError(f"{path.name} must be 512x512")
        source_hashes[phase] = hashlib.sha256(path.read_bytes()).hexdigest()
        frame = alpha_safe_resize(master, (128, 128))
        frame.save(HERE / f"east_walk_{phase}.png")
        frames.append(frame)

    detail = Image.new("RGBA", (256, 128), (77, 116, 51, 255))
    detail.alpha_composite(frames[0])
    detail.alpha_composite(frames[1], (128, 0))
    detail.save(HERE / "east_walk_128px.png")

    board = Image.new("RGBA", (3 * 100, 91), (77, 116, 51, 255))
    draw = ImageDraw.Draw(board)
    idle_path = TOOL_ROOT / "art/concepts/frames_preview/east_idle.png"
    with Image.open(idle_path) as idle_file:
        idle = idle_file.convert("RGBA")
    for i, (label, frame) in enumerate(zip(("idle", "A", "B"), (idle, *frames))):
        board.alpha_composite(frame.resize((75, 75), Image.Resampling.LANCZOS), (i * 100 + 12, 1))
        draw.text((i * 100 + 42, 76), label, fill="white")
    board.save(HERE / "east_walk_56px.png")

    motion = []
    for frame in frames:
        cell = Image.new("RGBA", (100, 91), (77, 116, 51, 255))
        cell.alpha_composite(frame.resize((75, 75), Image.Resampling.LANCZOS), (12, 1))
        motion.append(cell)
    motion[0].save(HERE / "east_walk_56px.gif", save_all=True,
                   append_images=motion[1:], duration=[270, 270], loop=0, disposal=2)
    (HERE / "source.json").write_text(json.dumps({
        "originalMaster": "art/concepts/visitor_male_01_east_master.png",
        "sourceSha256": source_hashes,
        "anchor": [64, 116],
        "frameDurationMs": 270,
        "runtimePromotion": False,
        "status": "visual review pending",
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
