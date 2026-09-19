"""
Generates procedural seamless 256x256 RGB material textures for terrain rendering:
- dirt_01.png
- stone_01.png
- sand_01.png
- gravel_01.png

Saves textures to assets/materials/terrain/.
"""

import os
import math
import random
from PIL import Image

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "materials", "terrain")
TEX_SIZE = 256

def make_seamless_perlin_2d(width, height, scale, base_color, noise_color, seed=42):
    # Generates a seamless tileable texture using 4D toroid-mapped noise sampling or 2D periodic sin/cos
    random.seed(seed)
    # Generate random gradient lattice periodic over width, height
    grid_w = max(4, int(width / scale))
    grid_h = max(4, int(height / scale))
    
    gx = [[random.uniform(-1, 1) for _ in range(grid_h)] for _ in range(grid_w)]
    gy = [[random.uniform(-1, 1) for _ in range(grid_h)] for _ in range(grid_w)]
    
    # Normalize gradients
    for ix in range(grid_w):
        for iy in range(grid_h):
            length = math.hypot(gx[ix][iy], gy[ix][iy]) or 1.0
            gx[ix][iy] /= length
            gy[ix][iy] /= length

    def fade(t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    def lerp(a, b, t):
        return a + t * (b - a)

    def sample_noise(x, y):
        # Map x, y seamlessly by taking periodic lattice lookup
        unit_x = (x / width) * grid_w
        unit_y = (y / height) * grid_h

        x0 = int(unit_x) % grid_w
        y0 = int(unit_y) % grid_h
        x1 = (x0 + 1) % grid_w
        y1 = (y0 + 1) % grid_h

        dx0 = unit_x - int(unit_x)
        dy0 = unit_y - int(unit_y)
        dx1 = dx0 - 1.0
        dy1 = dy0 - 1.0

        sx = fade(dx0)
        sy = fade(dy0)

        n00 = gx[x0][y0] * dx0 + gy[x0][y0] * dy0
        n10 = gx[x1][y0] * dx1 + gy[x0][y0] * dy0
        n01 = gx[x0][y1] * dx0 + gy[x0][y1] * dy1
        n11 = gx[x1][y1] * dx1 + gy[x0][y1] * dy1

        nx0 = lerp(n00, n10, sx)
        nx1 = lerp(n01, n11, sx)
        return lerp(nx0, nx1, sy)

    img = Image.new("RGB", (width, height))
    pixels = img.load()

    for y in range(height):
        for x in range(width):
            # Octave 1
            n1 = sample_noise(x, y)
            # Octave 2
            n2 = sample_noise((x * 2) % width, (y * 2) % height) * 0.5
            # Octave 3
            n3 = sample_noise((x * 4) % width, (y * 4) % height) * 0.25
            
            n = (n1 + n2 + n3) / 1.75
            t = (n + 1.0) * 0.5  # Normalize to 0..1
            t = max(0.0, min(1.0, t))

            r = int(base_color[0] + (noise_color[0] - base_color[0]) * t)
            g = int(base_color[1] + (noise_color[1] - base_color[1]) * t)
            b = int(base_color[2] + (noise_color[2] - base_color[2]) * t)

            pixels[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    return img

def create_dirt_texture():
    # Rich earthy brown dirt
    base = (90, 65, 45)
    noise = (140, 105, 75)
    return make_seamless_perlin_2d(TEX_SIZE, TEX_SIZE, 32, base, noise, seed=101)

def create_stone_texture():
    # Cobblestone slate grey with tile structure
    base = (80, 85, 90)
    noise = (160, 165, 170)
    img = make_seamless_perlin_2d(TEX_SIZE, TEX_SIZE, 48, base, noise, seed=202)
    pixels = img.load()
    # Add subtle stone block grid
    for y in range(TEX_SIZE):
        for x in range(TEX_SIZE):
            grid_x = (x % 32 == 0) or ((x + 16) % 32 == 0 and (y // 32) % 2 == 1)
            grid_y = (y % 32 == 0)
            if grid_x or grid_y:
                r, g, b = pixels[x, y]
                pixels[x, y] = (int(r * 0.6), int(g * 0.6), int(b * 0.6))
    return img

def create_sand_texture():
    # Warm golden / beige sand
    base = (210, 185, 135)
    noise = (235, 215, 165)
    return make_seamless_perlin_2d(TEX_SIZE, TEX_SIZE, 24, base, noise, seed=303)

def create_gravel_texture():
    # Multi-toned grey pebble gravel
    base = (110, 110, 115)
    noise = (190, 190, 195)
    img = make_seamless_perlin_2d(TEX_SIZE, TEX_SIZE, 16, base, noise, seed=404)
    pixels = img.load()
    random.seed(505)
    # Add micro pebble noise
    for y in range(TEX_SIZE):
        for x in range(TEX_SIZE):
            if random.random() < 0.15:
                pebble_shade = random.randint(-40, 40)
                r, g, b = pixels[x, y]
                pixels[x, y] = (
                    max(0, min(255, r + pebble_shade)),
                    max(0, min(255, g + pebble_shade)),
                    max(0, min(255, b + pebble_shade))
                )
    return img

def generate_all():
    os.makedirs(OUT_DIR, exist_ok=True)
    dirt = create_dirt_texture()
    dirt.save(os.path.join(OUT_DIR, "dirt_01.png"))
    
    stone = create_stone_texture()
    stone.save(os.path.join(OUT_DIR, "stone_01.png"))

    sand = create_sand_texture()
    sand.save(os.path.join(OUT_DIR, "sand_01.png"))

    gravel = create_gravel_texture()
    gravel.save(os.path.join(OUT_DIR, "gravel_01.png"))

    print(f"Generated 4 seamless terrain material textures in {OUT_DIR}")

if __name__ == "__main__":
    generate_all()
