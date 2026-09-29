import random

from PIL import Image

from visitor_forge_2d.core import brushes


def test_leaf_cluster_broadleaf_is_deterministic():
    a = Image.new("L", (256 * 4, 320 * 4))
    b = Image.new("L", a.size)
    brushes.leaf_cluster_broadleaf(a, random.Random(1234), 128, 120, 36, 24, satellites=5)
    brushes.leaf_cluster_broadleaf(b, random.Random(1234), 128, 120, 36, 24, satellites=5)
    assert a.tobytes() == b.tobytes()
    assert a.getbbox() is not None


def test_maple_brush_respects_group_mask():
    mask = Image.new("L", (256 * 4, 320 * 4))
    brushes.leaf_cluster_round(mask, random.Random(7), 128, 120, 32, 24)
    layer = Image.new("RGBA", mask.size)
    brushes.leaf_cluster_maple(
        layer,
        random.Random(7),
        mask,
        (128, 120),
        (32, 24),
        ("#C42130", "#F33D31", "#B61B25"),
        highlight_color="#FF694B",
        shadow_color="#6B1123",
    )
    alpha = layer.getchannel("A")
    assert alpha.getbbox() is not None
    # Every painted maple pixel must remain inside the authored cluster mask.
    leaked = Image.eval(alpha, lambda px: 255 if px else 0)
    outside = Image.new("L", mask.size, 255)
    outside = Image.frombytes("L", mask.size, bytes(255 - value for value in mask.tobytes()))
    assert Image.composite(leaked, Image.new("L", mask.size), outside).getbbox() is None


def test_gap_cutter_removes_alpha_from_existing_mass():
    mask = Image.new("L", (256 * 4, 320 * 4))
    brushes.leaf_cluster_round(mask, random.Random(9), 128, 120, 48, 34)
    before = sum(mask.getdata())
    brushes.silhouette_gap_cutter(mask, random.Random(9), 128, 120, 48, 34, count=5)
    after = sum(mask.getdata())
    assert after < before


def test_branch_tapered_draws_continuous_branch():
    mask = Image.new("L", (256 * 4, 320 * 4))
    brushes.branch_tapered(mask, (128, 300), (118, 235), (92, 170), 14, 2.2)
    assert mask.getbbox() is not None
