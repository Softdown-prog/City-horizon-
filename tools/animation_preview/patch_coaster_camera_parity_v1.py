from pathlib import Path

# Verification trigger only: keep the regressor-approved CH_CAMERA_V1 constants
# frozen while the full-lap proof validates the newly wired V2 pose continuity.
PATH = Path("C++/MapForge2/src/coaster_project_video_main.cpp")
text = PATH.read_text(encoding="utf-8")

# These values are derived from the approved CH Blender final bake, not tuned
# against the proof image. CH_CAMERA_V1 is orthographic yaw 45 / elevation 30.
# The final calibrated ortho scale is reconstructed from the final preflight
# projected bounds: 6.512514321292677 m. The common rail anchor baked into all
# 192 occupied frames is local (0, 0, 0.48), while camera target Z is 1.25 m.
BAKED_ORTHO_SCALE = 6.512514321292677
RAIL_ANCHOR_SOURCE_X = 128.0
RAIL_ANCHOR_SOURCE_Y = 154.21275273604374
SPRITE_SCALE_COEFF = 0.035976898743441864  # orthoScale*sqrt(2)/256

# Once a successful proof promotes the same code into the live renderer this
# helper becomes an invariant checker. Match stable significant digits instead
# of the final decimal emitted by Python formatting: the promoted C++ literal
# may round the last representable decimal without changing the double value.
already_promoted = (
    "kSpriteScaleCoefficient = 0.035976898743442" in text
    and "kRailAnchorSourceX = 128.0" in text
    and "kRailAnchorSourceY = 154.212752736043" in text
    and text.count("1.224744871391589") >= 2
    and "pose.world_x - pose.world_y + pose.world_z * 0.816496580927726" in text
)
if already_promoted:
    for legacy in (
        "const double u = x - y",
        "constexpr double zFactor = 3.2",
        "projection.scale / 14.0",
        "world_z + 0.12",
        "size.height()*0.62",
    ):
        if legacy in text:
            raise SystemExit(f"promoted renderer still contains legacy placement: {legacy}")
    print("CH_CAMERA_V1 + occupied V2 rail-anchor/scale already promoted")
    raise SystemExit(0)

replacements = [
    (
        "    double zFactor = 3.2;\n\n    [[nodiscard]] QPointF map(double x, double y, double z) const {\n        const double u = x - y;\n        const double v = 0.5 * (x + y) - z * zFactor;",
        "    // CH_CAMERA_V1: orthographic, yaw 45 degrees, elevation 30 degrees.\n    // With the 2:1 ground diamond normalized to u=x+y, the world-Z screen\n    // coefficient is sqrt(3/2). Keep this identical to fit_projection().\n    double zFactor = 1.224744871391589;\n\n    [[nodiscard]] QPointF map(double x, double y, double z) const {\n        const double u = x + y;\n        const double v = 0.5 * (x - y) - z * zFactor;"
    ),
    (
        "    constexpr double zFactor = 3.2;\n    for (const auto& s : samples) {\n        const double u = s.x - s.y;\n        const double v = 0.5 * (s.x + s.y) - s.z * zFactor;",
        "    // Must match the frozen CH_CAMERA_V1 used by CH Blender. The prior\n    // 3.2 coefficient and x-y horizontal basis described a different camera,\n    // so correctly selected car sprites could never sit visually on the rail.\n    constexpr double zFactor = 1.224744871391589;\n    for (const auto& s : samples) {\n        const double u = s.x + s.y;\n        const double v = 0.5 * (s.x - s.y) - s.z * zFactor;"
    ),
    (
        "        cars.push_back({pose, pose.world_x + pose.world_y + pose.world_z * 0.25});",
        "        // Camera is at +X/-Y and 30 degrees elevation. Draw farther cars\n        // first using the same view basis as CH_CAMERA_V1. sqrt(2/3) is the\n        // world-Z depth coefficient after normalizing the X/Y terms to +/-1.\n        cars.push_back({pose, pose.world_x - pose.world_y + pose.world_z * 0.816496580927726});"
    ),
    (
        "        const QPointF anchor = projection.map(car.pose.world_x, car.pose.world_y, car.pose.world_z + 0.12);\n        const double spriteScale = std::clamp(projection.scale / 14.0, 0.34, 0.68);\n        const QSizeF size(r.w * spriteScale, r.h * spriteScale);\n        const QRectF dst(anchor.x() - size.width()*0.5, anchor.y() - size.height()*0.62,\n                         size.width(), size.height());",
        f"        // The route sample itself is the rail centerline. Never add a screen-space\n        // or world-Z fudge here: all occupied V2 frames were baked around the same\n        // physical local rail anchor (0,0,0.48 m).\n        const QPointF anchor = projection.map(car.pose.world_x, car.pose.world_y, car.pose.world_z);\n\n        // Preserve CH Blender world scale exactly. For CH_CAMERA_V1, the source\n        // horizontal coordinate is (x+y)/sqrt(2), so source pixels per normalized\n        // MapForge u unit are 256/(orthoScale*sqrt(2)).\n        constexpr double kBakedOrthoScale = {BAKED_ORTHO_SCALE:.15f};\n        constexpr double kSpriteScaleCoefficient = {SPRITE_SCALE_COEFF:.15f};\n        constexpr double kRailAnchorSourceX = {RAIL_ANCHOR_SOURCE_X:.1f};\n        constexpr double kRailAnchorSourceY = {RAIL_ANCHOR_SOURCE_Y:.15f};\n        static_assert(kBakedOrthoScale > 6.5 && kBakedOrthoScale < 6.53);\n        const double spriteScale = projection.scale * kSpriteScaleCoefficient;\n        const QSizeF size(r.w * spriteScale, r.h * spriteScale);\n        const QRectF dst(anchor.x() - kRailAnchorSourceX * spriteScale,\n                         anchor.y() - kRailAnchorSourceY * spriteScale,\n                         size.width(), size.height());"
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"camera/anchor parity patch anchor count changed: expected 1, got {count}: {old[:100]!r}")
    text = text.replace(old, new)

for legacy in (
    "const double u = x - y",
    "constexpr double zFactor = 3.2",
    "projection.scale / 14.0",
    "world_z + 0.12",
    "size.height()*0.62",
):
    if legacy in text:
        raise SystemExit(f"legacy MapForge placement survived parity patch: {legacy}")
if text.count("1.224744871391589") < 2:
    raise SystemExit("CH_CAMERA_V1 z projection factor not installed consistently")
if "kRailAnchorSourceY" not in text or "kSpriteScaleCoefficient" not in text:
    raise SystemExit("V2 physical rail-anchor/scale contract was not installed")

PATH.write_text(text, encoding="utf-8")
print("CH_CAMERA_V1 + occupied V2 rail-anchor/scale proof placement installed")
