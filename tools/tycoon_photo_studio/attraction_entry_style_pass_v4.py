"""Style pass v4 for the shared City Horizon attraction entrance.

This pass builds on v3 instead of replacing the measured entrance system. It
adds broad, gameplay-readable architectural finishing: a stronger marquee crown,
proper tower feet, ticket-booth sales details, a scalloped awning valance,
finished turnstile caps and queue-post pedestals.

The runtime remains 2D. Blender is only the deterministic authoring source.
"""
from __future__ import annotations

import bpy

import attraction_entry_style_pass as v3


def _add_marquee_crown(root, recipe, mats, fw, scene_gate):
    g = recipe["geometry"]
    cx = float(g["gateCenterX"])
    y = float(g["gateCenterY"])
    spring_z = float(g["archSpringZ"])
    rise = float(g["archRise"])
    depth = float(g["marqueeDepth"])
    crown_w = float(g.get("marqueeCrownWidth", 1.10))
    crown_h = float(g.get("marqueeCrownHeight", 0.42))
    inset = float(g.get("marqueeCrownInset", 0.08))
    crown_base = spring_z + rise - crown_h * 0.55

    gold = v3._crest_points(cx, crown_base, crown_w + 0.16, crown_h + 0.12, 16)
    blue = v3._crest_points(cx, crown_base + 0.04, crown_w, crown_h, 16)
    v3._extruded_polygon_xz(
        root, scene_gate, "V4MarqueeCrownGold", gold,
        y - depth * 0.43, depth * 0.42, mats["parkGold"],
        "attraction.entry_marquee_crown",
    )
    v3._extruded_polygon_xz(
        root, scene_gate, "V4MarqueeCrownBlue", blue,
        y - depth * 0.43 - inset, depth * 0.26, mats["parkBlue"],
        "attraction.entry_marquee_crown",
    )

    # Secondary cream underline gives the arch a layered manufactured edge.
    half_span = float(g["marqueeVisualHalfSpan"]) * 0.95
    trim_points = v3._arch_band_points(
        cx,
        spring_z - float(g["marqueeOuterThickness"]) * 0.20,
        half_span,
        rise * 0.94,
        0.075,
        max(20, int(g.get("archSegments", 28))),
    )
    v3._extruded_polygon_xz(
        root, scene_gate, "V4MarqueeCreamInnerTrim", trim_points,
        y - depth * 0.60, depth * 0.17, mats["parkCream"],
        "attraction.entry_marquee_trim",
    )


def _add_tower_feet(root, recipe, mats, fw, scene_gate):
    g = recipe["geometry"]
    cx = float(g["gateCenterX"])
    y = float(g["gateCenterY"])
    clear_w = float(g["gateClearWidth"])
    col_w = float(g["gateColumnWidth"])
    col_d = float(g["gateColumnDepth"])
    base_h = float(g["baseHeight"])
    plinth_w = col_w * float(g.get("towerBasePlinthWidthScale", 1.55))
    plinth_d = col_d * float(g.get("towerBasePlinthDepthScale", 1.45))
    plinth_h = float(g.get("towerBasePlinthHeight", 0.18))

    for side, sign in (("Left", -1.0), ("Right", 1.0)):
        x = cx + sign * (clear_w * 0.5 + col_w * 0.5)
        v3._box(
            fw, root, scene_gate, f"V4TowerFootCream{side}",
            (x, y, base_h + plinth_h * 0.5),
            (plinth_w, plinth_d, plinth_h), mats["parkCream"], 0.045,
            "attraction.entry_portal_foot",
        )
        v3._box(
            fw, root, scene_gate, f"V4TowerFootGold{side}",
            (x, y, base_h + plinth_h + 0.035),
            (plinth_w * 0.82, plinth_d * 0.82, 0.07), mats["parkGold"], 0.025,
            "attraction.entry_portal_foot",
        )


def _add_kiosk_sales_details(root, recipe, mats, fw, scene_gate):
    g = recipe["geometry"]
    base_h = float(g["baseHeight"])
    kw = float(g["kioskWidth"])
    kd = float(g["kioskDepth"])
    kh = float(g["kioskHeight"])
    kx = float(g["kioskCenterX"])
    ky = float(g["kioskCenterY"])
    front_y = ky - kd * 0.5
    counter_z = base_h + float(g["counterHeight"])

    # Window mullion reads as an actual ticket-sales window at compact scale.
    v3._box(
        fw, root, scene_gate, "V4TicketWindowMullion",
        (kx, front_y - 0.13, base_h + kh * 0.60),
        (0.055, 0.055, kh * 0.40), mats["parkCream"], 0.015,
        "attraction.ticket_window_mullion",
    )

    # Small terminal/cash block sits on the counter without becoming micro-detail.
    terminal_w = float(g.get("kioskTerminalWidth", 0.22))
    v3._box(
        fw, root, scene_gate, "V4TicketTerminal",
        (kx + kw * 0.20, front_y - 0.27, counter_z + 0.10),
        (terminal_w, 0.17, 0.20), mats["parkBlue"], 0.028,
        "attraction.ticket_terminal",
    )
    v3._box(
        fw, root, scene_gate, "V4TicketTerminalFace",
        (kx + kw * 0.20, front_y - 0.365, counter_z + 0.11),
        (terminal_w * 0.68, 0.025, 0.10), mats["parkGreen"], 0.01,
        "attraction.ticket_terminal_display",
    )

    # Fare/menu plaque on the kiosk face to communicate ticket purchase.
    board_w = float(g.get("kioskMenuBoardWidth", 0.24))
    board_h = float(g.get("kioskMenuBoardHeight", 0.48))
    board_x = kx + kw * 0.38
    board_z = base_h + kh * 0.51
    v3._box(
        fw, root, scene_gate, "V4TicketMenuFrame",
        (board_x, front_y - 0.125, board_z),
        (board_w + 0.08, 0.045, board_h + 0.08), mats["parkGold"], 0.022,
        "attraction.ticket_menu",
    )
    v3._box(
        fw, root, scene_gate, "V4TicketMenuFace",
        (board_x, front_y - 0.151, board_z),
        (board_w, 0.025, board_h), mats["parkCream"], 0.018,
        "attraction.ticket_menu",
    )
    for i in range(3):
        z = board_z + board_h * (0.22 - i * 0.22)
        v3._box(
            fw, root, scene_gate, f"V4TicketMenuLine_{i}",
            (board_x, front_y - 0.169, z),
            (board_w * (0.68 if i == 0 else 0.52), 0.012, 0.035),
            mats["parkBlue"] if i != 1 else mats["parkCoral"], 0.006,
            "attraction.ticket_menu_mark",
        )

    # Rounded-looking valance blocks under the striped awning strengthen the
    # amusement-park silhouette without relying on tiny texture detail.
    awning_w = kw + float(g.get("awningSideOverhang", 0.28)) * 2.0
    count = max(5, int(g.get("awningStripeCount", 7)))
    piece_w = awning_w / count
    valance_h = float(g.get("awningValanceHeight", 0.16))
    awning_z = base_h + kh * 0.91
    valance_y = front_y - float(g.get("awningDepth", 0.58)) * 0.72
    for i in range(count):
        x = kx - awning_w * 0.5 + piece_w * (i + 0.5)
        mat = mats["parkCoral"] if i % 2 == 0 else mats["parkCream"]
        v3._box(
            fw, root, scene_gate, f"V4AwningValance_{i:02d}",
            (x, valance_y, awning_z - valance_h * 0.58),
            (piece_w * 0.92, 0.10, valance_h), mat, min(0.045, valance_h * 0.28),
            "attraction.ticket_awning_valance",
        )


def _add_queue_finish(root, recipe, mats, fw, scene_gate):
    g = recipe["geometry"]
    base_h = float(g["baseHeight"])
    gx = float(g["gateCenterX"])
    gy = float(g["gateCenterY"])
    clear_w = float(g["gateClearWidth"])
    col_w = float(g["gateColumnWidth"])
    q_right = float(g["queueRightX"])
    q_div = float(g["queueDividerX"])
    q_front = gy - 0.12
    q_back = min(float(g["backY"]) - 0.12, q_front + float(g["queueDepth"]))
    q_left = gx + clear_w * 0.5 + col_w + 0.15
    post_base = float(g.get("queuePostBaseSize", 0.16))

    # Visible feet make the queue fencing look installed rather than floating.
    key_posts = (
        (q_right, q_front), (q_right, q_back), (q_left, q_back),
        (q_left, q_front + 0.35), (q_div, q_front + 0.30), (q_div, q_back - 0.18),
    )
    for i, (x, y) in enumerate(key_posts):
        v3._box(
            fw, root, scene_gate, f"V4QueuePostBase_{i:02d}",
            (x, y, base_h + 0.045),
            (post_base, post_base, 0.09), mats["parkCream"], 0.022,
            "attraction.queue_post_base",
        )

    # Finish the two turnstiles with cream caps and blue shoulders.
    turn_count = max(1, int(g["turnstileCount"]))
    usable = clear_w - 0.14
    th = float(g["turnstileHeight"])
    td = float(g["turnstileDepth"])
    cap_h = float(g.get("turnstileCapHeight", 0.12))
    for i in range(turn_count):
        t = (i + 0.5) / turn_count - 0.5
        x = gx + t * usable
        y = gy - 0.40
        v3._box(
            fw, root, scene_gate, f"V4TurnstileBlueShoulder_{i:02d}",
            (x, y, base_h + th * 0.63),
            (0.24, td * 0.92, 0.28), mats["parkBlue"], 0.035,
            "attraction.entry_turnstile_finish",
        )
        v3._box(
            fw, root, scene_gate, f"V4TurnstileCreamCap_{i:02d}",
            (x, y, base_h + th + cap_h * 0.45),
            (0.28, td * 1.05, cap_h), mats["parkCream"], 0.035,
            "attraction.entry_turnstile_finish",
        )


def apply_style_pass(root, recipe, mats, fw, scene_gate):
    """Apply v3 then the v4 finishing layer and return all newly-authored meshes."""
    before = set(bpy.context.scene.objects)
    v3.apply_style_pass(root, recipe, mats, fw, scene_gate)
    _add_marquee_crown(root, recipe, mats, fw, scene_gate)
    _add_tower_feet(root, recipe, mats, fw, scene_gate)
    _add_kiosk_sales_details(root, recipe, mats, fw, scene_gate)
    _add_queue_finish(root, recipe, mats, fw, scene_gate)
    return [obj for obj in bpy.context.scene.objects if obj not in before and obj.type == "MESH"]
