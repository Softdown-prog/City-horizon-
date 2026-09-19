"""
CH_MASK_V1 Pilot Building Execution & Composite Preview Generator.
Processes house_small_01 variants manifest and outputs side-by-side visual comparison artifacts.
"""

import os
import sys
import json
from PIL import Image, ImageDraw, ImageFont

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from tools.asset_masks.apply_mask_variant import process_mask_manifest
from tools.asset_masks.mask_contract import compute_file_sha256


def run_pilot_pipeline():
    manifest_path = os.path.join(repo_root, "assets", "source_masks", "house_small_01", "house_small_01_variants.json")
    output_dir = os.path.join(repo_root, "assets", "generated", "variants", "house_small_01")
    artifact_dir = r"C:\Users\User\.gemini\antigravity\brain\33fb56cd-389b-4045-91b2-e978e5156ea4"

    print("==================================================")
    print("CH_MASK_V1 — PILOT GENERATION (house_small_01)")
    print("==================================================")
    print(f"Manifest Path: {manifest_path}")
    print(f"Output Dir:    {output_dir}")

    # 1. Process manifest
    png_paths, json_paths = process_mask_manifest(manifest_path, output_dir)

    print("\n--- GENERATED VARIANTS ---")
    for p, j in zip(png_paths, json_paths):
        sha_p = compute_file_sha256(p)
        print(f"Variant PNG:  {os.path.basename(p)}")
        print(f"  SHA-256:    {sha_p}")
        print(f"Sidecar JSON: {os.path.basename(j)}")

    # 2. Build Composite Side-by-Side Image
    base_png_path = os.path.join(repo_root, "assets", "buildings", "house_suburban_01_lvl1.png")
    base_img = Image.open(base_png_path).convert("RGBA")
    w, h = base_img.size

    labels = ["Original Base", "Coastal Blue", "Suburban Beige", "Aged (Weathered)"]
    images = [base_img] + [Image.open(p).convert("RGBA") for p in png_paths]

    margin = 20
    header_h = 40
    comp_w = len(images) * w + (len(images) + 1) * margin
    comp_h = h + margin * 2 + header_h

    # Dark background preview card
    comp_img = Image.new("RGBA", (comp_w, comp_h), (24, 30, 38, 255))
    draw = ImageDraw.Draw(comp_img)

    for idx, (img, label) in enumerate(zip(images, labels)):
        x_pos = margin + idx * (w + margin)
        y_pos = margin + header_h

        # Draw panel container background box
        draw.rectangle(
            [x_pos - 4, y_pos - 4, x_pos + w + 4, y_pos + h + 4],
            fill=(34, 42, 54, 255),
            outline=(50, 70, 90, 255),
            width=1
        )

        # Paste sprite
        comp_img.paste(img, (x_pos, y_pos), img)

        # Text label
        draw.text((x_pos, y_pos - header_h + 10), label, fill=(220, 240, 255))

    composite_path = os.path.join(artifact_dir, "mask_pilot_composite.png")
    comp_img.save(composite_path, format="PNG")
    print(f"\nComposite preview saved to: {composite_path}")

    return png_paths, composite_path

if __name__ == "__main__":
    run_pilot_pipeline()
