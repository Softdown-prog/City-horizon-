#include "road_visual_catalog.h"

#include <array>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace {

void require(const bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << "Test failure: " << message << '\n';
        std::exit(1);
    }
}

}  // namespace

int main(int argc, char** argv) {
    require(argc == 2, "expected the road visual catalog path");

    constexpr std::array<const char*, 16> expected = {
        "premium_01/road_00.png", "premium_01/road_01.png", "premium_01/road_02.png", "premium_01/road_03.png",
        "premium_01/road_04.png", "premium_01/road_05.png", "premium_01/road_06.png", "premium_01/road_07.png",
        "premium_01/road_08.png", "premium_01/road_09.png", "premium_01/road_10.png", "premium_01/road_11.png",
        "premium_01/road_12.png", "premium_01/road_13.png", "premium_01/road_14.png", "premium_01/road_15.png",
    };
    RoadVisualCatalog catalog;
    require(catalog.load_from_file(argv[1]), "valid catalog must load");
    require(catalog.loaded_from_file(), "catalog should report data-driven source");
    for (std::size_t mask = 0; mask < expected.size(); ++mask) {
        const auto connection_mask = static_cast<TileConnectionMask>(mask);
        const RoadVisual* visual = catalog.get_for_mask(connection_mask);
        require(visual != nullptr, "every mask must resolve");
        require(visual->texture_path == "assets/roads/" + std::string(expected[mask]),
                "catalog path differs for mask " + std::to_string(mask));
        require(visual->topology == classify_tile_topology(connection_mask),
                "catalog topology differs for mask " + std::to_string(mask));
        const std::filesystem::path project_root = std::filesystem::path(argv[1]).parent_path().parent_path().parent_path();
        const std::filesystem::path sprite_path = project_root / visual->texture_path;
        require(std::filesystem::is_regular_file(sprite_path), "generated sprite file is present for mask " + std::to_string(mask));
        std::ifstream sprite(sprite_path, std::ios::binary);
        const std::array<unsigned char, 8> png_signature = {137, 80, 78, 71, 13, 10, 26, 10};
        std::array<unsigned char, 8> file_signature{};
        sprite.read(reinterpret_cast<char*>(file_signature.data()), static_cast<std::streamsize>(file_signature.size()));
        require(file_signature == png_signature, "sprite file is a PNG for mask " + std::to_string(mask));
    }

    // Non-topology flag bits must never escape into the 16-entry visual table.
    // This makes the render lookup robust if callers carry unrelated high bits.
    const RoadVisual* normalized = catalog.get_for_mask(static_cast<TileConnectionMask>(0xF3));
    require(normalized != nullptr, "high-bit mask must normalize");
    require(normalized->texture_path == "assets/roads/premium_01/road_03.png",
            "high-bit mask must resolve using the canonical low four topology bits");
    require(normalized->topology == TileTopologyKind::corner,
            "normalized mask 3 must preserve corner semantics");

    RoadVisualCatalog fallback_catalog;
    const std::filesystem::path missing = std::filesystem::path(argv[1]).parent_path() / "missing_road_visual_catalog.json";
    require(!fallback_catalog.load_from_file(missing), "missing catalog must not be accepted");
    require(!fallback_catalog.loaded_from_file(), "fallback catalog must identify itself");
    require(fallback_catalog.get_for_mask(15)->texture_path == "assets/roads/premium_01/road_15.png",
            "fallback must retain expected path");
    require(fallback_catalog.get_for_mask(15)->topology == TileTopologyKind::cross,
            "fallback must expose canonical cross semantics");

    std::cout << "Road visual catalog tests passed.\n";
    return 0;
}
