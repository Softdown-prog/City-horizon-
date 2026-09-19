import os
from PIL import Image, ImageDraw

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PROPS_DIR = os.path.join(REPO_ROOT, 'assets', 'props')
os.makedirs(PROPS_DIR, exist_ok=True)

# 1. Base Tower (128x160)
base = Image.new('RGBA', (128, 160), (0, 0, 0, 0))
d = ImageDraw.Draw(base)

# Roof / Cap
d.polygon([(36, 50), (64, 20), (92, 50)], fill=(160, 40, 30, 255), outline=(100, 20, 15, 255))
# Stone/Wood Tower Body
d.polygon([(36, 50), (92, 50), (104, 152), (24, 152)], fill=(130, 110, 90, 255), outline=(70, 55, 40, 255))
# Door
d.rectangle([(54, 115), (74, 152)], fill=(40, 30, 20, 255), outline=(20, 15, 10, 255))
# Hub Mount Point marker at (64, 48)
d.ellipse([(58, 42), (70, 54)], fill=(180, 180, 190, 255), outline=(80, 80, 90, 255))

base_path = os.path.join(PROPS_DIR, 'windmill_base.png')
base.save(base_path)
print(f'Saved {base_path}')

# 2. Rotor Blades (128x128) - Center / Pivot at (64, 64)
rotor = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
rd = ImageDraw.Draw(rotor)

# 4 Blades
# Top blade
rd.polygon([(58, 56), (70, 56), (72, 10), (56, 10)], fill=(240, 240, 230, 255), outline=(100, 100, 90, 255))
# Right blade
rd.polygon([(72, 58), (72, 70), (118, 72), (118, 56)], fill=(240, 240, 230, 255), outline=(100, 100, 90, 255))
# Bottom blade
rd.polygon([(70, 72), (58, 72), (56, 118), (72, 118)], fill=(240, 240, 230, 255), outline=(100, 100, 90, 255))
# Left blade
rd.polygon([(56, 70), (56, 58), (10, 56), (10, 72)], fill=(240, 240, 230, 255), outline=(100, 100, 90, 255))

# Center cap / Pivot
rd.ellipse([(56, 56), (72, 72)], fill=(200, 60, 50, 255), outline=(100, 30, 25, 255))

rotor_path = os.path.join(PROPS_DIR, 'windmill_rotor.png')
rotor.save(rotor_path)
print(f'Saved {rotor_path}')

# 3. Manifest (windmill_small_01.json)
manifest_content = """{
  "contract": "CH_ANIMATED_PROP_V1",
  "id": "windmill_small_01",
  "base_static": "assets/props/windmill_base.png",
  "baseWidth": 128.0,
  "baseHeight": 160.0,
  "atlas": "assets/props/windmill_rotor.png",
  "presentation": "transform_rotation",
  "mountPointX": 64.0,
  "mountPointY": 48.0,
  "pivotX": 64.0,
  "pivotY": 64.0
}
"""

manifest_path = os.path.join(PROPS_DIR, 'windmill_small_01.json')
with open(manifest_path, 'w', encoding='utf-8') as f:
    f.write(manifest_content)
print(f'Saved {manifest_path}')
