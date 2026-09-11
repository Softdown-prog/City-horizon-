#include "land_system.h"

#include "economy_system.h"

#include <algorithm>
#include <cstdlib>

LandManager::LandManager(const int map_min, const int map_max, const int parcel_width, const int parcel_height)
    : map_min_(map_min), map_max_(map_max), parcel_width_(std::max(1, parcel_width)), parcel_height_(std::max(1, parcel_height)) {
    // The central parcel is centered around the world origin, so data-defined
    // initial building placements near the origin remain inside owned land.
    const int center_origin_x = -(parcel_width_ / 2);
    const int center_origin_y = -(parcel_height_ / 2);
    std::uint32_t next_id = 1;
    for (int parcel_y = -1; parcel_y <= 1; ++parcel_y) {
        for (int parcel_x = -1; parcel_x <= 1; ++parcel_x) {
            const bool initial = parcel_x == 0 && parcel_y == 0;
            const bool orthogonal_neighbor = std::abs(parcel_x) + std::abs(parcel_y) == 1;
            parcels_.push_back({
                next_id++,
                center_origin_x + parcel_x * parcel_width_,
                center_origin_y + parcel_y * parcel_height_,
                parcel_width_,
                parcel_height_,
                initial ? 0 : (orthogonal_neighbor ? 5'000 : 10'000),
                initial,
            });
        }
    }
}

const LandParcel* LandManager::parcel_at(const int tile_x, const int tile_y) const {
    if (!is_inside_map(tile_x, tile_y)) {
        return nullptr;
    }
    const auto found = std::find_if(parcels_.begin(), parcels_.end(), [tile_x, tile_y](const LandParcel& parcel) {
        return tile_x >= parcel.origin_x && tile_x < parcel.origin_x + parcel.width &&
               tile_y >= parcel.origin_y && tile_y < parcel.origin_y + parcel.height;
    });
    return found == parcels_.end() ? nullptr : &*found;
}

const LandParcel* LandManager::parcel_by_id(const std::uint32_t parcel_id) const {
    const auto found = std::find_if(parcels_.begin(), parcels_.end(), [parcel_id](const LandParcel& parcel) {
        return parcel.id == parcel_id;
    });
    return found == parcels_.end() ? nullptr : &*found;
}

bool LandManager::is_tile_owned(const int tile_x, const int tile_y) const {
    const LandParcel* parcel = parcel_at(tile_x, tile_y);
    return parcel != nullptr && parcel->owned;
}

bool LandManager::is_area_owned(const int tile_x, const int tile_y, const int width, const int height) const {
    if (width <= 0 || height <= 0) {
        return false;
    }
    for (int offset_y = 0; offset_y < height; ++offset_y) {
        for (int offset_x = 0; offset_x < width; ++offset_x) {
            if (!is_tile_owned(tile_x + offset_x, tile_y + offset_y)) {
                return false;
            }
        }
    }
    return true;
}

bool LandManager::are_tiles_owned(const std::vector<std::pair<int, int>>& tiles) const {
    return !tiles.empty() && std::all_of(tiles.begin(), tiles.end(), [this](const auto& tile) {
        return is_tile_owned(tile.first, tile.second);
    });
}

bool LandManager::can_purchase_parcel(const std::uint32_t parcel_id) const {
    const LandParcel* parcel = parcel_by_id(parcel_id);
    return parcel != nullptr && !parcel->owned && is_adjacent_to_owned(*parcel);
}

bool LandManager::is_adjacent_to_owned(const LandParcel& parcel) const {
    return std::any_of(parcels_.begin(), parcels_.end(), [&parcel](const LandParcel& candidate) {
        return candidate.owned && shares_orthogonal_edge(parcel, candidate);
    });
}

bool LandManager::purchase_parcel(const std::uint32_t parcel_id, CityEconomy& economy, const GameDate& date) {
    if (!can_purchase_parcel(parcel_id)) {
        return false;
    }
    auto found = std::find_if(parcels_.begin(), parcels_.end(), [parcel_id](const LandParcel& parcel) {
        return parcel.id == parcel_id;
    });
    if (found == parcels_.end() || !economy.spend_for_land(found->purchase_cost, date, found->id)) {
        return false;
    }
    found->owned = true;
    return true;
}

std::size_t LandManager::restore_owned_parcels(const std::vector<std::uint32_t>& owned_parcel_ids) {
    for (LandParcel& parcel : parcels_) {
        parcel.owned = false;
    }
    std::size_t missing = 0;
    for (const std::uint32_t parcel_id : owned_parcel_ids) {
        auto found = std::find_if(parcels_.begin(), parcels_.end(), [parcel_id](const LandParcel& parcel) {
            return parcel.id == parcel_id;
        });
        if (found == parcels_.end()) {
            ++missing;
        } else {
            found->owned = true;
        }
    }
    return missing;
}

int LandManager::owned_parcel_count() const {
    return static_cast<int>(std::count_if(parcels_.begin(), parcels_.end(), [](const LandParcel& parcel) {
        return parcel.owned;
    }));
}

const std::vector<LandParcel>& LandManager::parcels() const {
    return parcels_;
}

int LandManager::parcel_width() const {
    return parcel_width_;
}

int LandManager::parcel_height() const {
    return parcel_height_;
}

bool LandManager::is_inside_map(const int tile_x, const int tile_y) const {
    return tile_x >= map_min_ && tile_x <= map_max_ && tile_y >= map_min_ && tile_y <= map_max_;
}

bool LandManager::shares_orthogonal_edge(const LandParcel& left, const LandParcel& right) {
    const int left_right = left.origin_x + left.width;
    const int right_right = right.origin_x + right.width;
    const int left_bottom = left.origin_y + left.height;
    const int right_bottom = right.origin_y + right.height;
    const bool vertical_overlap = std::max(left.origin_y, right.origin_y) < std::min(left_bottom, right_bottom);
    const bool horizontal_overlap = std::max(left.origin_x, right.origin_x) < std::min(left_right, right_right);
    return ((left_right == right.origin_x || right_right == left.origin_x) && vertical_overlap) ||
           ((left_bottom == right.origin_y || right_bottom == left.origin_y) && horizontal_overlap);
}
