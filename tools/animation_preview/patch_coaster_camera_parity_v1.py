from pathlib import Path

PATH = Path("C++/MapForge2/src/coaster_project_video_main.cpp")
text = PATH.read_text(encoding="utf-8")

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
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"camera parity patch anchor count changed: expected 1, got {count}: {old[:80]!r}")
    text = text.replace(old, new)

# Proof-time invariants: fail instead of silently rendering with a mixed camera.
if "const double u = x - y" in text or "constexpr double zFactor = 3.2" in text:
    raise SystemExit("legacy MapForge projection survived CH_CAMERA_V1 patch")
if text.count("1.224744871391589") < 2:
    raise SystemExit("CH_CAMERA_V1 z projection factor not installed consistently")

PATH.write_text(text, encoding="utf-8")
print("CH_CAMERA_V1 MapForge proof projection installed")
