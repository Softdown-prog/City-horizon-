#pragma once

#include "simulation_clock.h"

#include <cstdint>
#include <utility>
#include <vector>

class CityEconomy;

struct LandParcel {
    std::uint32_t id = 0;
    int origin_x = 0;
    int origin_y = 0;
    int width = 1;
    int height = 1;
    std::int64_t purchase_cost = 0;
    bool owned = false;
};

// Owns the city-boundary rules, not the map itself. Tiles can exist visually
// without being owned; placement systems query this class before using them.
class LandManager {
public:
    LandManager(int map_min, int map_max, int parcel_width = 32, int parcel_height = 32);

    [[nodiscard]] const LandParcel* parcel_at(int tile_x, int tile_y) const;
    [[nodiscard]] const LandParcel* parcel_by_id(std::uint32_t parcel_id) const;
    [[nodiscard]] bool is_tile_owned(int tile_x, int tile_y) const;
    [[nodiscard]] bool is_area_owned(int tile_x, int tile_y, int width, int height) const;
    [[nodiscard]] bool are_tiles_owned(const std::vector<std::pair<int, int>>& tiles) const;
    [[nodiscard]] bool can_purchase_parcel(std::uint32_t parcel_id) const;
    [[nodiscard]] bool is_adjacent_to_owned(const LandParcel& parcel) const;
    [[nodiscard]] bool purchase_parcel(std::uint32_t parcel_id, CityEconomy& economy, const GameDate& date);
    // Load-only restoration stores ownership ids, not parcel geometry or prices.
    [[nodiscard]] std::size_t restore_owned_parcels(const std::vector<std::uint32_t>& owned_parcel_ids);
    [[nodiscard]] int owned_parcel_count() const;
    [[nodiscard]] const std::vector<LandParcel>& parcels() const;

    [[nodiscard]] int parcel_width() const;
    [[nodiscard]] int parcel_height() const;

private:
    [[nodiscard]] bool is_inside_map(int tile_x, int tile_y) const;
    [[nodiscard]] static bool shares_orthogonal_edge(const LandParcel& left, const LandParcel& right);

    int map_min_ = 0;
    int map_max_ = 0;
    int parcel_width_ = 32;
    int parcel_height_ = 32;
    std::vector<LandParcel> parcels_;
};
