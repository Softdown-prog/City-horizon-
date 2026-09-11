#include "road_visual_catalog.h"

#include <fstream>
#include <iostream>
#include <iterator>
#include <string_view>
#include <utility>

namespace {

constexpr std::array<std::string_view, 16> kDefaultSpriteNames = {
    "premium_01/road_00.png", "premium_01/road_01.png", "premium_01/road_02.png", "premium_01/road_03.png",
    "premium_01/road_04.png", "premium_01/road_05.png", "premium_01/road_06.png", "premium_01/road_07.png",
    "premium_01/road_08.png", "premium_01/road_09.png", "premium_01/road_10.png", "premium_01/road_11.png",
    "premium_01/road_12.png", "premium_01/road_13.png", "premium_01/road_14.png", "premium_01/road_15.png",
};

[[nodiscard]] std::string read_text_file(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return {};
    }
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

[[nodiscard]] std::string sprite_path_for_mask(const std::string_view json, const std::uint8_t mask) {
    const std::string key = '"' + std::to_string(mask) + '"';
    const std::size_t key_position = json.find(key);
    if (key_position == std::string_view::npos) {
        return {};
    }
    const std::size_t colon = json.find(':', key_position + key.size());
    const std::size_t opening_quote = colon == std::string_view::npos ? std::string_view::npos : json.find('"', colon);
    const std::size_t closing_quote = opening_quote == std::string_view::npos ? std::string_view::npos :
        json.find('"', opening_quote + 1);
    if (closing_quote == std::string_view::npos) {
        return {};
    }
    return std::string(json.substr(opening_quote + 1, closing_quote - opening_quote - 1));
}

}  // namespace

RoadVisualCatalog::RoadVisualCatalog() {
    set_default_paths();
}

bool RoadVisualCatalog::load_from_file(const std::filesystem::path& path) {
    set_default_paths();
    loaded_from_file_ = false;
    const std::string json = read_text_file(path);
    if (json.empty()) {
        std::cerr << "Road visual catalog unavailable; using expected default paths: " << path << '\n';
        return false;
    }

    std::array<RoadVisual, 16> loaded;
    for (std::uint8_t mask = 0; mask < loaded.size(); ++mask) {
        const std::string texture_path = sprite_path_for_mask(json, mask);
        if (texture_path.empty()) {
            std::cerr << "Road visual catalog is missing mask " << static_cast<int>(mask)
                      << "; using expected default paths.\n";
            return false;
        }
        loaded[mask].texture_path = texture_path;
    }
    visuals_ = std::move(loaded);
    loaded_from_file_ = true;
    return true;
}

const RoadVisual* RoadVisualCatalog::get_for_mask(const std::uint8_t mask) const {
    return &visuals_[static_cast<std::size_t>(mask & 0x0F)];
}

bool RoadVisualCatalog::loaded_from_file() const {
    return loaded_from_file_;
}

void RoadVisualCatalog::set_default_paths() {
    for (std::size_t mask = 0; mask < visuals_.size(); ++mask) {
        visuals_[mask].texture_path = "assets/roads/" + std::string(kDefaultSpriteNames[mask]);
    }
}
