"""Create deterministic casual-clothing variants from the approved worker PNGs.

The source silhouette, alpha, canvas and per-frame anchor are copied exactly.
Only the two uniform colour families are remapped, which keeps all 16 frames
perfectly compatible with the existing MobileAnimation definition.
"""

from colorsys import hsv_to_rgb, rgb_to_hsv
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "pedestrians" / "worker_cleaner_female"
VARIANTS = {
    "citizen_casual_blue": {
        "shirt_hue": 0.58,
        "shirt_saturation": 0.56,
        "trouser_hue": 0.61,
        "trouser_saturation": 0.48,
    },
    "citizen_casual_coral": {
        "shirt_hue": 0.025,
        "shirt_saturation": 0.70,
        "trouser_hue": 0.63,
        "trouser_saturation": 0.42,
    },
    "citizen_female_light_blue": {
        "shirt_hue": 0.58,
        "shirt_saturation": 0.52,
        "trouser_hue": 0.61,
        "trouser_saturation": 0.44,
        "skin_hue": 0.055,
        "skin_saturation": 0.34,
        "skin_value_scale": 1.34,
    },
    "citizen_female_dark_coral": {
        "shirt_hue": 0.020,
        "shirt_saturation": 0.68,
        "trouser_hue": 0.63,
        "trouser_saturation": 0.42,
        "skin_hue": 0.055,
        "skin_saturation": 0.50,
        "skin_value_scale": 0.73,
    },
}


def recolour(pixel: tuple[int, int, int, int], style: dict[str, float]) -> tuple[int, int, int, int]:
    red, green, blue, alpha = pixel
    if alpha == 0:
        return pixel
    hue, saturation, value = rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
    # High-vis lime shirt: yellow-green range.  The value is deliberately
    # retained so shading from the original 3D render remains intact.
    if saturation > 0.25 and 0.16 <= hue <= 0.34 and value > 0.20:
        hue, saturation = style["shirt_hue"], style["shirt_saturation"]
    # Teal work trousers: cyan-green range.  Boots, hair and skin lie outside
    # this range and are therefore untouched.
    elif saturation > 0.20 and 0.39 <= hue <= 0.56 and value > 0.12:
        hue, saturation = style["trouser_hue"], style["trouser_saturation"]
    # Existing skin pixels are warm, moderately saturated and brighter than
    # the hair/boots.  The value multiplier retains the original light/shadow
    # structure while producing a genuinely distinct skin tone.
    elif "skin_hue" in style and saturation > 0.18 and hue <= 0.10 and value > 0.25:
        hue = style["skin_hue"]
        saturation = style["skin_saturation"]
        value = min(1.0, value * style["skin_value_scale"])
    red, green, blue = hsv_to_rgb(hue, saturation, value)
    return round(red * 255), round(green * 255), round(blue * 255), alpha


for variant, style in VARIANTS.items():
    for direction in ("se", "sw", "nw", "ne"):
        source_dir = SOURCE / direction
        destination_dir = ROOT / "assets" / "pedestrians" / variant / direction
        destination_dir.mkdir(parents=True, exist_ok=True)
        for source_path in sorted(source_dir.glob("frame_*.png")):
            with Image.open(source_path).convert("RGBA") as source_image:
                result = Image.new("RGBA", source_image.size)
                result.putdata([recolour(pixel, style) for pixel in source_image.getdata()])
                result.save(destination_dir / source_path.name)
    print(f"created {variant}")
