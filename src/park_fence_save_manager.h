#pragma once

#include "park_fence_runtime.h"
#include "save_manager.h"

#include <fstream>
#include <sstream>
#include <string>

// Fence persistence is layered over the existing city save contract so old
// saveVersion 1..11 files remain readable without rewriting SaveManager's JSON
// parser. Each city save owns one small deterministic sidecar next to it.
class ParkFenceSaveManager : public SaveManager {
public:
    [[nodiscard]] SaveOperationResult save(const std::filesystem::path& path,
                                           const CityEconomy& economy, const SimulationClock& clock,
                                           const BuildingManager& buildings, const RoadManager& roads,
                                           const SidewalkManager& sidewalks, const FarmingSystem& farming,
                                           const LandManager& lands, const PopulationSystem& population,
                                           const ServiceVehicleManager* vehicles = nullptr,
                                           const MissionManager* missions = nullptr,
                                           const std::vector<TerrainPaintTile>* terrain_paint = nullptr,
                                           const std::vector<ch::TerrainHeightSample>* terrain_heights = nullptr) const {
        SaveOperationResult result = SaveManager::save(path, economy, clock, buildings, roads,
                                                       sidewalks, farming, lands, population,
                                                       vehicles, missions, terrain_paint, terrain_heights);
        if (!result.success) return result;

        const std::filesystem::path fence_path = sidecar_path(path);
        std::ofstream output(fence_path, std::ios::binary | std::ios::trunc);
        if (!output) {
            result.success = false;
            result.message = "city saved but Park fences could not be written";
            return result;
        }

        output << "CH_PARK_FENCE_V2\n";
        for (const FenceNode& node : park_fence_runtime::fences().nodes()) {
            output << "N " << node.vertex_x << ' ' << node.vertex_y << ' '
                   << static_cast<int>(node.orientation_hint) << '\n';
        }
        for (const FenceSegment& segment : park_fence_runtime::fences().segments()) {
            output << "S " << segment.from.x << ' ' << segment.from.y << ' '
                   << segment.to.x << ' ' << segment.to.y << ' '
                   << std::string(park_fence_runtime::fence_style_id(
                          park_fence_runtime::segment_style(segment.from, segment.to))) << '\n';
            if (!segment.open_gate) continue;
            output << "G " << segment.from.x << ' ' << segment.from.y << ' '
                   << segment.to.x << ' ' << segment.to.y << '\n';
        }
        if (!output) {
            result.success = false;
            result.message = "city saved but Park fence data could not be completed";
            return result;
        }

        result.message += " + Park fences";
        return result;
    }

    [[nodiscard]] SaveOperationResult load(const std::filesystem::path& path,
                                           const BuildingCatalog& catalog, CityEconomy& economy,
                                           SimulationClock& clock, BuildingManager& buildings,
                                           RoadManager& roads, SidewalkManager& sidewalks, FarmingSystem& farming,
                                           LandManager& lands, PopulationSystem& population,
                                           const ServiceVehicleCatalog* vehicle_catalog = nullptr,
                                           ServiceVehicleManager* vehicles = nullptr,
                                           MissionManager* missions = nullptr,
                                           std::vector<TerrainPaintTile>* terrain_paint = nullptr,
                                           std::vector<ch::TerrainHeightSample>* terrain_heights = nullptr) const {
        SaveOperationResult result = SaveManager::load(path, catalog, economy, clock, buildings, roads,
                                                       sidewalks, farming, lands, population,
                                                       vehicle_catalog, vehicles, missions, terrain_paint, terrain_heights);
        if (!result.success) return result;

        park_fence_runtime::clear();
        const std::filesystem::path fence_path = sidecar_path(path);
        std::ifstream input(fence_path, std::ios::binary);
        if (!input) {
            // Existing saves predate fence persistence. An absent sidecar is a
            // valid empty fence network, not a load failure.
            return result;
        }

        std::string header;
        std::getline(input, header);
        const bool legacy_v1 = header == "CH_PARK_FENCE_V1";
        if (!legacy_v1 && header != "CH_PARK_FENCE_V2") {
            result.message += " | Park fence sidecar ignored: unsupported format";
            return result;
        }

        struct PendingGate { FenceVertex from; FenceVertex to; };
        struct PendingStyle {
            FenceVertex from;
            FenceVertex to;
            park_fence_runtime::ParkFenceStyle style = park_fence_runtime::ParkFenceStyle::classic_iron;
        };
        std::vector<PendingGate> gates;
        std::vector<PendingStyle> styles;
        std::size_t restored_nodes = 0;
        std::size_t skipped_entries = 0;
        std::string line;
        while (std::getline(input, line)) {
            if (line.empty()) continue;
            std::istringstream row(line);
            char kind = '\0';
            row >> kind;
            if (kind == 'N') {
                int x = 0, y = 0, rotation = 0;
                if (!(row >> x >> y >> rotation) || rotation < 0 || rotation > 3 ||
                    !park_fence_runtime::fences().place_node(x, y, static_cast<FenceRotation>(rotation))) {
                    ++skipped_entries;
                } else {
                    ++restored_nodes;
                }
            } else if (kind == 'S' && !legacy_v1) {
                PendingStyle pending{};
                std::string style_id;
                if (!(row >> pending.from.x >> pending.from.y >> pending.to.x >> pending.to.y >> style_id)) {
                    ++skipped_entries;
                    continue;
                }
                const std::optional<park_fence_runtime::ParkFenceStyle> style =
                    park_fence_runtime::fence_style_from_id(style_id);
                if (!style) {
                    ++skipped_entries;
                } else {
                    pending.style = *style;
                    styles.push_back(pending);
                }
            } else if (kind == 'G') {
                PendingGate gate{};
                if (!(row >> gate.from.x >> gate.from.y >> gate.to.x >> gate.to.y)) {
                    ++skipped_entries;
                } else {
                    gates.push_back(gate);
                }
            } else {
                ++skipped_entries;
            }
        }

        std::size_t restored_styles = 0;
        for (const PendingStyle& pending : styles) {
            if (park_fence_runtime::set_segment_style(pending.from, pending.to, pending.style)) ++restored_styles;
            else ++skipped_entries;
        }

        std::size_t restored_gates = 0;
        for (const PendingGate& gate : gates) {
            if (park_fence_runtime::fences().set_open_gate(gate.from, gate.to, true)) ++restored_gates;
            else ++skipped_entries;
        }

        result.message += " | Park fences " + std::to_string(restored_nodes) +
                          " nodes, " + std::to_string(restored_gates) + " open gates";
        if (!legacy_v1) result.message += ", " + std::to_string(restored_styles) + " styled segments";
        if (skipped_entries != 0) {
            result.message += " (" + std::to_string(skipped_entries) + " invalid fence entries skipped)";
        }
        return result;
    }

private:
    [[nodiscard]] static std::filesystem::path sidecar_path(const std::filesystem::path& city_path) {
        std::filesystem::path result = city_path;
        result += ".park_fences";
        return result;
    }
};
