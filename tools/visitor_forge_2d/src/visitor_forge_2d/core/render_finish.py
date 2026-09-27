from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

CONTRACT = "CH_2D_RENDER_FINISH_V1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_recipe(path: Path) -> dict:
    recipe = json.loads(path.read_text(encoding="utf-8"))
    if recipe.get("contract") != CONTRACT:
        raise ValueError(f"Expected {CONTRACT}, got {recipe.get('contract')!r}")
    return recipe


def finish_render(input_path: Path, output_path: Path, recipe_path: Path,
                  review_path: Path | None = None) -> dict:
    """Apply a deterministic 2D finishing pass without changing silhouette or alpha.

    This pass is intentionally conservative. It is meant for high-resolution Blender
    masters that already have approved geometry/camera/clearance. It may improve color
    separation and local readability, but alpha, canvas dimensions and object placement
    remain authoritative from the input render.
    """
    recipe = _load_recipe(recipe_path)
    source = Image.open(input_path).convert("RGBA")
    alpha = source.getchannel("A")
    rgb = source.convert("RGB")

    if min(source.size) < int(recipe.get("minimumInputDimensionPx", 1)):
        raise ValueError(
            f"Input {source.size} is below minimumInputDimensionPx="
            f"{recipe.get('minimumInputDimensionPx')}"
        )

    finish = recipe.get("finish", {})
    work = ImageEnhance.Color(rgb).enhance(float(finish.get("color", 1.0)))
    work = ImageEnhance.Contrast(work).enhance(float(finish.get("contrast", 1.0)))
    work = work.filter(ImageFilter.UnsharpMask(
        radius=float(finish.get("unsharpRadius", 1.0)),
        percent=int(finish.get("unsharpPercent", 0)),
        threshold=int(finish.get("unsharpThreshold", 0)),
    ))
    work = ImageEnhance.Sharpness(work).enhance(float(finish.get("sharpness", 1.0)))

    # Protect antialiased edges so the pass never invents a new silhouette or halo.
    edge_low = int(finish.get("edgeGuardLowAlpha", 18))
    edge_high = int(finish.get("edgeGuardHighAlpha", 150))
    if edge_high <= edge_low:
        raise ValueError("edgeGuardHighAlpha must be greater than edgeGuardLowAlpha")
    edge_guard = alpha.point(
        lambda p: 0 if p <= edge_low else 255 if p >= edge_high
        else int((p - edge_low) * 255 / (edge_high - edge_low))
    )
    finished_rgb = Image.composite(work, rgb, edge_guard)

    # RGB under fully transparent pixels is forced to black to keep alpha-safe edges.
    visible = alpha.point(lambda p: 255 if p > 0 else 0)
    finished_rgb = Image.composite(
        finished_rgb,
        Image.new("RGB", source.size, (0, 0, 0)),
        visible,
    )
    finished = finished_rgb.convert("RGBA")
    finished.putalpha(alpha)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    finished.save(output_path, format="PNG", optimize=False)

    review = None
    if review_path is not None:
        review_w = int(recipe.get("review", {}).get("cellWidth", 600))
        review_h = int(recipe.get("review", {}).get("cellHeight", 600))
        board = Image.new("RGBA", (review_w * 2, review_h), (22, 28, 34, 255))

        def cell(image: Image.Image) -> Image.Image:
            canvas = Image.new("RGBA", (review_w, review_h), (22, 28, 34, 255))
            copy = image.copy()
            copy.thumbnail((review_w - 20, review_h - 50), Image.Resampling.LANCZOS)
            x = (review_w - copy.width) // 2
            y = 35 + (review_h - 35 - copy.height) // 2
            canvas.alpha_composite(copy, (x, y))
            return canvas

        board.alpha_composite(cell(source), (0, 0))
        board.alpha_composite(cell(finished), (review_w, 0))
        draw = ImageDraw.Draw(board)
        draw.text((20, 12), "source master", fill=(235, 235, 235, 255))
        draw.text((review_w + 20, 12), "procedural 2D finish", fill=(235, 235, 235, 255))
        review_path.parent.mkdir(parents=True, exist_ok=True)
        board.save(review_path, format="PNG", optimize=False)
        review = str(review_path)

    return {
        "contract": CONTRACT,
        "status": "ok",
        "input": str(input_path),
        "output": str(output_path),
        "review": review,
        "size": list(source.size),
        "inputSha256": _sha256(input_path),
        "outputSha256": _sha256(output_path),
        "alphaPreserved": True,
        "geometryChanged": False,
    }
