"""
Advanced Procedural 2D Tycoon Tree Generator for City Horizon.

Recreates the rich, multi-cluster, branched broadleaf tree style of classic
isometric Tycoon games (Zoo Tycoon 1 / RCT2) using purely 2D procedural math,
supersampled vector composite rendering, leaf dappling, and post-stylization.
"""

from __future__ import annotations
import math
import random
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/visitor_forge_2d/src"))
sys.path.insert(0, str(ROOT / "tools/tycoon_photo_studio"))

from visitor_forge_2d.core.organic_scenery import isometric_board, review_board
from stylize_foliage_2d import stylize_color, load_profile

SCALE = 4  # 4x supersampling for clean Lanczos downsample

def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))

def quad_bezier(p0, p1, p2, t):
    u = 1.0 - t
    return (
        u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
    )

def draw_tapered_branch(draw, p0, p1, p2, w0, w1, color, samples=32):
    for i in range(samples + 1):
        t = i / samples
        x, y = quad_bezier(p0, p1, p2, t)
        w = (w0 + (w1 - w0) * t) * SCALE
        r = max(1.0, w * 0.5)
        cx, cy = x * SCALE, y * SCALE
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)

def generate_cluster_mask(size, rx, ry, lobes=16, jitter=0.18, seed=1):
    rng = random.Random(seed)
    w, h = size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    cx, cy = w // 2, h // 2
    pts = []
    for i in range(lobes):
        angle = 2.0 * math.pi * i / lobes
        r_mod = 1.0 + rng.uniform(-jitter, jitter)
        px = cx + math.cos(angle) * rx * SCALE * r_mod
        py = cy + math.sin(angle) * ry * SCALE * r_mod
        pts.append((round(px), round(py)))
    draw.polygon(pts, fill=255)
    return mask

def render_shaded_cluster(size, rx, ry, pal, seed=1):
    w, h = size
    mask = generate_cluster_mask(size, rx, ry, lobes=18, jitter=0.20, seed=seed)
    if mask.getbbox() is None:
        return Image.new("RGBA", size, (0, 0, 0, 0))
    
    top_col = hex_to_rgb(pal["highlight"])
    mid_col = hex_to_rgb(pal["mid_top"])
    bot_col = hex_to_rgb(pal["back_bottom"])
    
    # 3D sphere volume shading: light comes from top-left (40% x, 35% y)
    surf = Image.new("RGBA", size, (0, 0, 0, 0))
    pix = surf.load()
    mp = mask.load()
    
    cx, cy = w * 0.40, h * 0.35
    max_r = max(rx, ry) * SCALE * 1.2
    
    for y in range(h):
        for x in range(w):
            if mp[x, y] < 30:
                continue
            dist = math.hypot(x - cx, y - cy) / max_r
            t = max(0.0, min(1.0, dist))
            if t < 0.45:
                color = lerp_color(top_col, mid_col, t / 0.45)
            else:
                color = lerp_color(mid_col, bot_col, (t - 0.45) / 0.55)
            pix[x, y] = (*color, mp[x, y])
            
    # Add leaf dabs around border
    rng = random.Random(seed + 999)
    draw = ImageDraw.Draw(surf, "RGBA")
    bbox = mask.getbbox()
    if bbox:
        coords = [(x, y) for y in range(bbox[1], bbox[3]) for x in range(bbox[0], bbox[2]) if 60 <= mp[x, y] <= 220]
        if coords:
            for _ in range(round(rx * ry * 0.4)):
                x, y = rng.choice(coords)
                r_dab = rng.uniform(1.2, 3.2) * SCALE
                col_dab = top_col if rng.random() < 0.55 else mid_col
                alpha_dab = rng.randint(140, 230)
                draw.ellipse((x - r_dab, y - r_dab, x + r_dab, y + r_dab), fill=(*col_dab, alpha_dab))
                
    return surf

def build_advanced_tycoon_tree(spec):
    canvas_w, canvas_h = spec["canvas"]
    W, H = canvas_w * SCALE, canvas_h * SCALE
    anchor_x, anchor_y = spec["anchor"]
    pal = spec["palette"]
    seed = spec.get("seed", 42)
    rng = random.Random(seed)
    
    work = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    
    # 1. Ground Shadow
    shadow_w = spec.get("shadowWidth", 96)
    sm = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sm).ellipse(
        ((anchor_x - shadow_w // 2) * SCALE, (anchor_y - 10) * SCALE,
         (anchor_x + shadow_w // 2) * SCALE, (anchor_y + 6) * SCALE),
        fill=140
    )
    sm = sm.filter(ImageFilter.GaussianBlur(2.5 * SCALE))
    sh_color = hex_to_rgb(pal.get("ground_shadow", "#18241C"))
    sh = Image.new("RGBA", (W, H), (*sh_color, 0))
    sh.putalpha(sm)
    work.alpha_composite(sh)
    
    # 2. Wood Skeleton (Main Trunk + Primary Boughs + Secondary Branches)
    wood_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_wood = ImageDraw.Draw(wood_layer)
    trunk_color = hex_to_rgb(pal["trunk_top"])
    dark_trunk = hex_to_rgb(pal["trunk_bottom"])
    
    branches = spec["branches"]
    # Draw dark backing first for depth
    for b in branches:
        draw_tapered_branch(draw_wood, b["p0"], b.get("p1", b["p0"]), b["p2"],
                            b["w0"] * 1.15, b["w1"] * 1.15, dark_trunk)
    # Draw main trunk wood
    for b in branches:
        draw_tapered_branch(draw_wood, b["p0"], b.get("p1", b["p0"]), b["p2"],
                            b["w0"], b["w1"], trunk_color)
        
    # Bark highlight lines
    tc = hex_to_rgb(pal.get("trunk_light", "#BA7C48"))
    for b in branches[:2]:  # main trunks
        p0, p2 = b["p0"], b["p2"]
        lx0, ly0 = (p0[0] + 1) * SCALE, p0[1] * SCALE
        lx2, ly2 = (p2[0] + 1) * SCALE, p2[1] * SCALE
        draw_wood.line((lx0, ly0, lx2, ly2), fill=(*tc, 180), width=round(1.5 * SCALE))
        
    work.alpha_composite(wood_layer)
    
    # 3. Multi-Cluster Foliage Clouds (Rear -> Mid -> Front)
    clusters = spec["clusters"]
    for i, cl in enumerate(clusters):
        cx, cy = cl["pos"]
        rx, ry = cl["radius"]
        c_seed = seed + i * 137
        
        c_surf = render_shaded_cluster((W, H), rx, ry, pal, seed=c_seed)
        
        # Position cluster centered on (cx, cy)
        c_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        off_x = round((cx - W // (2 * SCALE)) * SCALE)
        off_y = round((cy - H // (2 * SCALE)) * SCALE)
        c_img.alpha_composite(c_surf, (off_x, off_y))
        
        work.alpha_composite(c_img)
        
    # 4. Global Unsharp & Downsample to 1x Gameplay Canvas
    downsampled = work.convert("RGBa").resize((canvas_w, canvas_h), Image.Resampling.LANCZOS).convert("RGBA")
    
    # 5. Apply City Horizon 2D Stylization Pipeline (stylize_foliage_2d.py)
    profile = load_profile(None)
    profile["paletteColors"] = spec.get("paletteColors", 54)
    profile["posterizeBitsPerChannel"] = spec.get("posterizeBits", 5)
    profile["saturationMultiplier"] = spec.get("saturation", 1.18)
    profile["contrastMultiplier"] = spec.get("contrast", 1.08)
    profile["outlineAlpha"] = spec.get("outlineAlpha", 38)
    profile["woodToneCount"] = 4
    profile["woodOrganicStrength"] = 0.32
    
    stylized = stylize_color(downsampled, profile)
    
    return downsampled, stylized

# ── Palette: Warm Bark & Rich Zoo Green ───────────────────────────────────────
PALETTE_SUMMER = {
    "ground_shadow": "#1A231C",
    "trunk_top":     "#8C5A32",
    "trunk_bottom":  "#482A14",
    "trunk_light":   "#BA7C48",
    "back_top":      "#254D2A",
    "back_bottom":   "#122518",
    "mid_top":       "#3D7442",
    "mid_bottom":    "#224C2C",
    "front_top":     "#55966A",
    "front_bottom":  "#316040",
    "highlight":     "#88C872",
    "occlusion":     "#143018",
}

# ── Recipe: Zoo Tycoon Replication Tree 1 (Forked Savannah Broadleaf) ─────────
SPEC_ZOO_TREE_1 = {
    "id": "park_tree_zoo_broadleaf_01",
    "canvas": [192, 256],
    "anchor": [96, 248],
    "seed": 91238,
    "palette": PALETTE_SUMMER,
    "branches": [
        # Base trunk flared
        {"p0": [96, 248], "p1": [96, 200], "p2": [96, 160], "w0": 16.0, "w1": 10.5},
        # Left main bough
        {"p0": [96, 160], "p1": [78, 125], "p2": [58, 92],  "w0": 9.5,  "w1": 4.5},
        # Center main bough
        {"p0": [96, 160], "p1": [94, 118], "p2": [90, 70],  "w0": 8.0,  "w1": 3.5},
        # Right main bough
        {"p0": [96, 160], "p1": [116, 128], "p2": [134, 94], "w0": 9.5, "w1": 4.0},
        # Sub-branches
        {"p0": [78, 125], "p1": [68, 105], "p2": [52, 85],  "w0": 4.5,  "w1": 2.2},
        {"p0": [116, 128], "p1": [128, 108], "p2": [142, 82], "w0": 4.5, "w1": 2.2},
    ],
    "clusters": [
        # Rear depth clusters
        {"pos": [55, 90],  "radius": [26, 22]},
        {"pos": [138, 92], "radius": [26, 22]},
        {"pos": [92, 68],  "radius": [28, 24]},
        # Mid main cloud clusters
        {"pos": [48, 80],  "radius": [32, 26]},
        {"pos": [90, 58],  "radius": [36, 28]},
        {"pos": [135, 82], "radius": [32, 26]},
        # Front top highlight clusters
        {"pos": [68, 72],  "radius": [30, 24]},
        {"pos": [112, 70], "radius": [30, 24]},
    ],
}

# ── Recipe: Zoo Tycoon Replication Tree 2 (Tall Broadleaf Canopy) ─────────────
SPEC_ZOO_TREE_2 = {
    "id": "park_tree_zoo_broadleaf_02",
    "canvas": [224, 288],
    "anchor": [112, 278],
    "seed": 53421,
    "palette": {
        "ground_shadow": "#1A231C",
        "trunk_top":     "#86542D",
        "trunk_bottom":  "#422410",
        "trunk_light":   "#B57744",
        "back_top":      "#224B27",
        "back_bottom":   "#102316",
        "mid_top":       "#3A723F",
        "mid_bottom":    "#204A2A",
        "front_top":     "#529466",
        "front_bottom":  "#2E5F3C",
        "highlight":     "#84C66E",
        "occlusion":     "#122E16",
    },
    "branches": [
        {"p0": [112, 278], "p1": [112, 210], "p2": [112, 160], "w0": 18.0, "w1": 11.0},
        {"p0": [112, 160], "p1": [85, 125],  "p2": [58, 88],   "w0": 10.0, "w1": 4.5},
        {"p0": [112, 160], "p1": [110, 115], "p2": [108, 62],  "w0": 9.0,  "w1": 3.8},
        {"p0": [112, 160], "p1": [140, 125], "p2": [168, 85],  "w0": 10.0, "w1": 4.5},
        {"p0": [85, 125],  "p1": [70, 100],  "p2": [48, 75],   "w0": 4.5,  "w1": 2.0},
        {"p0": [140, 125], "p1": [156, 102], "p2": [178, 72],  "w0": 4.5,  "w1": 2.0},
    ],
    "clusters": [
        {"pos": [52, 85],   "radius": [30, 24]},
        {"pos": [170, 82],  "radius": [30, 24]},
        {"pos": [108, 60],  "radius": [34, 28]},
        {"pos": [45, 70],   "radius": [34, 28]},
        {"pos": [108, 48],  "radius": [38, 30]},
        {"pos": [175, 70],  "radius": [34, 28]},
        {"pos": [78, 58],   "radius": [32, 26]},
        {"pos": [140, 58],  "radius": [32, 26]},
    ],
}

if __name__ == "__main__":
    OUT = ROOT / "tools/tycoon_photo_studio/output/trees_advanced_tycoon"
    OUT.mkdir(parents=True, exist_ok=True)
    
    specs = [SPEC_ZOO_TREE_1, SPEC_ZOO_TREE_2]
    
    print("Generating Advanced Multi-Cluster Tycoon 2D Trees …")
    
    raw_frames = []
    styl_frames = []
    isos = []
    
    for spec in specs:
        raw_img, styl_img = build_advanced_tycoon_tree(spec)
        
        raw_path = OUT / f"{spec['id']}_raw.png"
        styl_path = OUT / f"{spec['id']}_stylized.png"
        iso_path = OUT / f"{spec['id']}_isometric_review.png"
        rev_path = OUT / f"{spec['id']}_review.png"
        
        raw_img.save(raw_path)
        styl_img.save(styl_path)
        
        iso = isometric_board(styl_img, spec['anchor'], f"CH_CAMERA_V1 / Advanced 2D Tycoon Tree / {spec['id']}")
        iso.save(iso_path)
        isos.append(iso)
        
        rev = review_board(styl_img)
        rev.save(rev_path)
        
        raw_frames.append(raw_img)
        styl_frames.append(styl_img)
        
        print(f"  [OK] {spec['id']} -> {styl_path}")
        
    # Build Raw vs Stylized comparison board
    CELL_W, CELL_H = 240, 320
    comp_board = Image.new("RGBA", (CELL_W * len(specs), CELL_H * 2 + 40), (46, 77, 55, 255))
    d_comp = ImageDraw.Draw(comp_board)
    
    d_comp.text((16, 8), "ROW 1: Raw Multi-Cluster Procedural 2D Render", fill=(247, 244, 220, 255))
    d_comp.text((16, CELL_H + 24), "ROW 2: City Horizon 2D Foliage & Wood Stylized Pass (stylize_foliage_2d.py)", fill=(247, 244, 220, 255))
    
    for i, (r_frame, s_frame, spec) in enumerate(zip(raw_frames, styl_frames, specs)):
        ox = i * CELL_W + (CELL_W - r_frame.width) // 2
        comp_board.alpha_composite(r_frame, (ox, 28))
        comp_board.alpha_composite(s_frame, (ox, CELL_H + 44))
        d_comp.text((i * CELL_W + 16, CELL_H - 12), spec['id'], fill=(220, 232, 205, 255))
        
    comp_path = OUT / "advanced_trees_raw_vs_stylized.png"
    comp_board.save(comp_path)
    
    # Build Iso board
    iso_comb = Image.new("RGBA", (isos[0].width, sum(i.height for i in isos)), (46, 77, 55, 255))
    cy = 0
    for iso in isos:
        iso_comb.alpha_composite(iso, (0, cy))
        cy += iso.height
    iso_comb_path = OUT / "advanced_trees_isometric_board.png"
    iso_comb.save(iso_comb_path)
    
    print("\nDone! Files saved in:", OUT)
    print(f"  Comparison board: {comp_path}")
    print(f"  Isometric board:  {iso_comb_path}")
