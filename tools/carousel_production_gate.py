#!/usr/bin/env python3
import argparse, json, math, statistics
from pathlib import Path
from PIL import Image, ImageDraw


def alpha_bbox(frame):
    return frame.getchannel("A").getbbox()


def nonempty_ratio(frame):
    hist = frame.getchannel("A").histogram()
    opaque = sum(hist[1:])
    return opaque / float(frame.width * frame.height)


def edge_clear(frame, margin=2):
    alpha = frame.getchannel("A")
    w, h = frame.size
    strips = [
        alpha.crop((0, 0, w, margin)),
        alpha.crop((0, h - margin, w, h)),
        alpha.crop((0, 0, margin, h)),
        alpha.crop((w - margin, 0, w, h)),
    ]
    return all(strip.getbbox() is None for strip in strips)


def crop_frames(sheet, fw, fh, count, cols):
    frames = []
    for i in range(count):
        x = (i % cols) * fw
        y = (i // cols) * fh
        frames.append(sheet.crop((x, y, x + fw, y + fh)).convert("RGBA"))
    return frames


def make_lod(frames, out):
    scales = [1.0, 0.75, 0.5]
    cell_w = frames[0].width + 36
    row_h = frames[0].height + 48
    canvas = Image.new("RGBA", (cell_w * 4, row_h * len(scales)), (28, 35, 38, 255))
    draw = ImageDraw.Draw(canvas)
    picks = [0, len(frames) // 4, len(frames) // 2, (3 * len(frames)) // 4]
    for row, scale in enumerate(scales):
        for col, index in enumerate(picks):
            frame = frames[index]
            size = (max(1, round(frame.width * scale)), max(1, round(frame.height * scale)))
            small = frame.resize(size, Image.Resampling.LANCZOS)
            x = col * cell_w + (cell_w - small.width) // 2
            y = row * row_h + 26 + (frames[0].height - small.height) // 2
            canvas.alpha_composite(small, (x, y))
            draw.text((col * cell_w + 8, row * row_h + 6), f"{int(scale * 100)}%  frame {index + 1:02d}", fill=(222, 230, 226, 255))
    canvas.save(out)


def make_coherence(frames, bboxes, out):
    fw, fh = frames[0].size
    cell_w = fw // 2 + 20
    cell_h = fh // 2 + 34
    cols = 4
    rows = math.ceil(len(frames) / cols)
    canvas = Image.new("RGBA", (cols * cell_w, rows * cell_h), (24, 30, 33, 255))
    draw = ImageDraw.Draw(canvas)
    for i, frame in enumerate(frames):
        small = frame.resize((fw // 2, fh // 2), Image.Resampling.LANCZOS)
        x = (i % cols) * cell_w + 10
        y = (i // cols) * cell_h + 24
        canvas.alpha_composite(small, (x, y))
        draw.text((x, y - 18), f"F{i + 1:02d}", fill=(223, 228, 218, 255))
        box = bboxes[i]
        if box:
            draw.rectangle((x + box[0] // 2, y + box[1] // 2, x + box[2] // 2, y + box[3] // 2), outline=(224, 177, 72, 255), width=1)
    canvas.save(out)


def make_context(frame, bakery_path, out):
    width, height = 1280, 720
    canvas = Image.new("RGBA", (width, height), (93, 128, 78, 255))
    draw = ImageDraw.Draw(canvas)
    tile_w, tile_h = 128, 64
    origin_x, origin_y = width // 2, 230

    for gx in range(-6, 7):
        for gy in range(-5, 6):
            cx = origin_x + (gx - gy) * (tile_w // 2)
            cy = origin_y + (gx + gy) * (tile_h // 2)
            diamond = [(cx, cy - tile_h // 2), (cx + tile_w // 2, cy), (cx, cy + tile_h // 2), (cx - tile_w // 2, cy)]
            fill = (112, 146, 88, 255) if (gx + gy) % 2 == 0 else (107, 140, 84, 255)
            draw.polygon(diamond, fill=fill)
            draw.line(diamond + [diamond[0]], fill=(89, 120, 72, 150), width=1)

    for gx in range(-5, 6):
        cx = origin_x + gx * (tile_w // 2)
        cy = origin_y + gx * (tile_h // 2)
        diamond = [(cx, cy - tile_h // 2), (cx + tile_w // 2, cy), (cx, cy + tile_h // 2), (cx - tile_w // 2, cy)]
        draw.polygon(diamond, fill=(84, 87, 87, 255))

    ride = frame.copy()
    ride.thumbnail((300, 300), Image.Resampling.LANCZOS)
    canvas.alpha_composite(ride, (origin_x - ride.width // 2, origin_y + 145 - ride.height))

    bakery = Path(bakery_path)
    if bakery.exists():
        building = Image.open(bakery).convert("RGBA")
        building.thumbnail((260, 260), Image.Resampling.LANCZOS)
        canvas.alpha_composite(building, (origin_x - 430, origin_y + 185 - building.height))

    draw.rectangle((18, 18, 620, 72), fill=(24, 30, 33, 220))
    draw.text((32, 30), "CAROUSEL GAME-CONTEXT GATE — CH_CAMERA_V1 / repository building neighbor", fill=(233, 229, 213, 255))
    canvas.save(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--bakery", default="assets/buildings/bakery_01_lvl1.png")
    args = parser.parse_args()

    out = Path(args.directory)
    manifests = sorted(out.glob("*_manifest.json"))
    if not manifests:
        raise SystemExit("carousel production gate: runtime manifest missing")

    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    sheet_info = manifest["export"]["spritesheet"]
    sheet = Image.open(out / sheet_info["file"]).convert("RGBA")
    frame_w = int(sheet_info["frameWidth"])
    frame_h = int(sheet_info["frameHeight"])
    cols = int(sheet_info["columns"])
    frame_count = len(manifest.get("frameSamples", []))
    if frame_count <= 0:
        raise SystemExit("carousel production gate: frame samples missing")

    frames = crop_frames(sheet, frame_w, frame_h, frame_count, cols)
    bboxes = [alpha_bbox(frame) for frame in frames]
    if any(box is None for box in bboxes):
        raise SystemExit("carousel production gate: empty frame")

    widths = [box[2] - box[0] for box in bboxes]
    heights = [box[3] - box[1] for box in bboxes]
    bottoms = [box[3] for box in bboxes]
    ratios = [nonempty_ratio(frame) for frame in frames]
    edges = [edge_clear(frame, 2) for frame in frames]

    bottom_span = max(bottoms) - min(bottoms)
    width_cv = statistics.pstdev(widths) / max(1.0, statistics.mean(widths))
    height_cv = statistics.pstdev(heights) / max(1.0, statistics.mean(heights))

    pass_edge = all(edges)
    pass_anchor = bottom_span <= 10
    pass_extent = width_cv <= 0.16 and height_cv <= 0.12
    pass_coverage = min(ratios) >= 0.025 and max(ratios) <= 0.65
    passed = pass_edge and pass_anchor and pass_extent and pass_coverage

    make_lod(frames, out / "carousel_lod_gate.png")
    make_coherence(frames, bboxes, out / "carousel_frame_coherence_gate.png")
    make_context(frames[0], args.bakery, out / "carousel_game_context_gate.png")

    runtime_png = out.parent / "assets" / "amusement" / "carousel" / "classic" / "carousel_classic_01.png"
    runtime_png.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(runtime_png)

    report = {
        "version": "carousel_visual_production_gate_1",
        "pass": passed,
        "automaticChecks": {
            "noFrameClipping": {"pass": pass_edge},
            "anchorBottomSpanPx": {"value": bottom_span, "max": 10, "pass": pass_anchor},
            "widthCoefficientVariation": {"value": width_cv, "max": 0.16},
            "heightCoefficientVariation": {"value": height_cv, "max": 0.12},
            "stableSilhouetteExtent": {"pass": pass_extent},
            "coverageRange": {"min": min(ratios), "max": max(ratios), "pass": pass_coverage},
        },
        "reviewArtifacts": ["carousel_lod_gate.png", "carousel_frame_coherence_gate.png", "carousel_game_context_gate.png"],
        "runtimeFixture": "assets/amusement/carousel/classic/carousel_classic_01.png",
        "humanApprovalRequired": True,
        "humanRule": "Automatic PASS means technically production-safe only. Final visual approval requires gameplay-scale human review.",
    }
    (out / "carousel_production_gate.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not passed:
        raise SystemExit("carousel production gate failed technical visual checks")


if __name__ == "__main__":
    main()
