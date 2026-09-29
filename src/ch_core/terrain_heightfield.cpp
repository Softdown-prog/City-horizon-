#include "src/ch_core/terrain_heightfield.h"

#include <algorithm>
#include <cmath>

namespace ch {

namespace {

constexpr float kZeroEpsilon = 0.0001F;

[[nodiscard]] float smooth_falloff(const float normalized_distance) noexcept {
    const float t = std::clamp(normalized_distance, 0.0F, 1.0F);
    const float smooth_step = t * t * (3.0F - 2.0F * t);
    return 1.0F - smooth_step;
}

} // namespace

std::uint64_t TerrainHeightField::pack_key(const int x, const int y) noexcept {
    return (static_cast<std::uint64_t>(static_cast<std::uint32_t>(x)) << 32) |
           static_cast<std::uint32_t>(y);
}

int TerrainHeightField::unpack_x(const std::uint64_t key) noexcept {
    return static_cast<int>(static_cast<std::int32_t>(key >> 32));
}

int TerrainHeightField::unpack_y(const std::uint64_t key) noexcept {
    return static_cast<int>(static_cast<std::int32_t>(key & 0xFFFFFFFFULL));
}

float TerrainHeightField::height_at(const int x, const int y) const noexcept {
    const auto it = samples_.find(pack_key(x, y));
    return it == samples_.end() ? 0.0F : it->second;
}

float TerrainHeightField::sample(const float x, const float y) const noexcept {
    const int x0 = static_cast<int>(std::floor(x));
    const int y0 = static_cast<int>(std::floor(y));
    const int x1 = x0 + 1;
    const int y1 = y0 + 1;
    const float tx = x - static_cast<float>(x0);
    const float ty = y - static_cast<float>(y0);

    const float top = height_at(x0, y0) + (height_at(x1, y0) - height_at(x0, y0)) * tx;
    const float bottom = height_at(x0, y1) + (height_at(x1, y1) - height_at(x0, y1)) * tx;
    return top + (bottom - top) * ty;
}

void TerrainHeightField::set_height(const int x, const int y, const float height) noexcept {
    if (!std::isfinite(height)) {
        return;
    }

    const float clamped = std::clamp(height, kTerrainHeightMin, kTerrainHeightMax);
    const std::uint64_t key = pack_key(x, y);
    if (std::abs(clamped) <= kZeroEpsilon) {
        samples_.erase(key);
    } else {
        samples_[key] = clamped;
    }
}

void TerrainHeightField::apply_brush(const float center_x, const float center_y, const float radius,
                                     const float strength, const TerrainBrushMode mode) noexcept {
    if (!std::isfinite(center_x) || !std::isfinite(center_y) ||
        !std::isfinite(radius) || !std::isfinite(strength) ||
        radius <= 0.0F || std::abs(strength) <= kZeroEpsilon) {
        return;
    }

    const float magnitude = std::abs(strength);
    const int min_x = static_cast<int>(std::floor(center_x - radius));
    const int max_x = static_cast<int>(std::ceil(center_x + radius));
    const int min_y = static_cast<int>(std::floor(center_y - radius));
    const int max_y = static_cast<int>(std::ceil(center_y + radius));

    // Smoothing must read a stable source field. Otherwise the order in which
    // vertices are visited would make the result visibly directional.
    const std::unordered_map<std::uint64_t, float> source = mode == TerrainBrushMode::smooth
        ? samples_ : std::unordered_map<std::uint64_t, float>{};
    const auto source_height_at = [&](const int x, const int y) {
        if (mode != TerrainBrushMode::smooth) {
            return height_at(x, y);
        }
        const auto it = source.find(pack_key(x, y));
        return it == source.end() ? 0.0F : it->second;
    };

    for (int y = min_y; y <= max_y; ++y) {
        for (int x = min_x; x <= max_x; ++x) {
            const float dx = static_cast<float>(x) - center_x;
            const float dy = static_cast<float>(y) - center_y;
            const float distance = std::sqrt(dx * dx + dy * dy);
            if (distance > radius) {
                continue;
            }

            const float falloff = smooth_falloff(distance / radius);
            const float current = source_height_at(x, y);
            if (mode == TerrainBrushMode::smooth) {
                const float neighbour_average = (
                    source_height_at(x - 1, y) + source_height_at(x + 1, y) +
                    source_height_at(x, y - 1) + source_height_at(x, y + 1)) * 0.25F;
                const float blend = std::clamp(magnitude * falloff, 0.0F, 1.0F);
                set_height(x, y, current + (neighbour_average - current) * blend);
            } else {
                const float direction = mode == TerrainBrushMode::lower ? -1.0F : 1.0F;
                set_height(x, y, current + direction * magnitude * falloff);
            }
        }
    }
}

std::vector<TerrainHeightSample> TerrainHeightField::samples() const {
    std::vector<TerrainHeightSample> result;
    result.reserve(samples_.size());
    for (const auto& [key, height] : samples_) {
        result.push_back({unpack_x(key), unpack_y(key), height});
    }
    std::sort(result.begin(), result.end(), [](const TerrainHeightSample& left, const TerrainHeightSample& right) {
        return left.y == right.y ? left.x < right.x : left.y < right.y;
    });
    return result;
}

} // namespace ch
