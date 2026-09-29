#ifndef CITY_HORIZON_CH_CORE_TERRAIN_HEIGHTFIELD_H
#define CITY_HORIZON_CH_CORE_TERRAIN_HEIGHTFIELD_H

#include <cstdint>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace ch {

inline constexpr std::string_view kTerrainHeightfieldContract = "CH_TERRAIN_HEIGHTFIELD_V1";
inline constexpr float kTerrainHeightMin = -3.0F;
inline constexpr float kTerrainHeightMax = 3.0F;

struct TerrainHeightSample {
    int x = 0;
    int y = 0;
    float height = 0.0F;
};

enum class TerrainBrushMode {
    raise,
    lower,
    smooth
};

// Sparse, shared-vertex height data for the isometric ground grid. A missing
// sample is the canonical zero level, so old maps remain perfectly flat.
class TerrainHeightField {
public:
    [[nodiscard]] float height_at(int x, int y) const noexcept;
    [[nodiscard]] float sample(float x, float y) const noexcept;

    void set_height(int x, int y, float height) noexcept;
    void apply_brush(float center_x, float center_y, float radius, float strength,
                     TerrainBrushMode mode) noexcept;

    [[nodiscard]] std::vector<TerrainHeightSample> samples() const;
    [[nodiscard]] bool empty() const noexcept { return samples_.empty(); }
    void clear() noexcept { samples_.clear(); }

private:
    static std::uint64_t pack_key(int x, int y) noexcept;
    static int unpack_x(std::uint64_t key) noexcept;
    static int unpack_y(std::uint64_t key) noexcept;

    std::unordered_map<std::uint64_t, float> samples_;
};

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_TERRAIN_HEIGHTFIELD_H
