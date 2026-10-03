#pragma once

#include "park_fence_runtime.h"
#include "save_manager.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <optional>
#include <sstream>
#include <string>

// Fence persistence is layered over the existing city save contract so old
// saveVersion 1..12 files remain readable without rewriting SaveManager's JSON
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
        const std::filesystem::path fence_path = sidecar_path(path);
        const std::filesystem::path staged_city = staging_path(path);
        const std::filesystem::path staged_fence = staging_path(fence_path);
        const std::filesystem::path backup_city = backup_path(path);
        const std::filesystem::path backup_fence = backup_path(fence_path);

        cleanup_file(staged_city);
        cleanup_file(staged_fence);
        cleanup_file(backup_city);
        cleanup_file(backup_fence);

        SaveOperationResult result = SaveManager::save(staged_city, economy, clock, buildings, roads,
                                                       sidewalks, farming, lands, population,
                                                       vehicles, missions, terrain_paint, terrain_heights);
        if (!result.success) {
            cleanup_file(staged_city);
            return result;
        }

        const std::optional<std::uint64_t> city_digest = file_digest(staged_city);
        if (!city_digest.has_value()) {
            cleanup_file(staged_city);
            result.success = false;
            result.message = "city save staging could not be verified";
            return result;
        }

        if (!write_fence_sidecar(staged_fence, *city_digest)) {
            cleanup_file(staged_city);
            cleanup_file(staged_fence);
            result.success = false;
            result.message = "city and Park fences were not committed because fence staging failed";
            return result;
        }

        const bool had_city = std::filesystem::exists(path);
        const bool had_fence = std::filesystem::exists(fence_path);
        std::error_code error;
        if (had_city) {
            std::filesystem::rename(path, backup_city, error);
            if (error) return staging_failure(result, staged_city, staged_fence,
                                              "existing city save could not be staged for replacement");
        }
        if (had_fence) {
            error.clear();
            std::filesystem::rename(fence_path, backup_fence, error);
            if (error) {
                restore_backup(backup_city, path);
                return staging_failure(result, staged_city, staged_fence,
                                       "existing Park fence sidecar could not be staged for replacement");
            }
        }

        error.clear();
        std::filesystem::rename(staged_city, path, error);
        if (error) {
            restore_backup(backup_city, path);
            restore_backup(backup_fence, fence_path);
            return staging_failure(result, staged_city, staged_fence,
                                   "staged city save could not be committed");
        }

        error.clear();
        std::filesystem::rename(staged_fence, fence_path, error);
        if (error) {
            cleanup_file(path);
            restore_backup(backup_city, path);
            restore_backup(backup_fence, fence_path);
            return staging_failure(result, staged_city, staged_fence,
                                   "staged Park fence sidecar could not be committed; previous save restored");
        }

        cleanup_file(backup_city);
        cleanup_file(backup_fence);
        result.message += " + Park fences (transactional V3)";
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
                                                       vehicle_catalog, vehicles, missions, terrain_paint,
                                                       terrain_heights);
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
        const bool legacy_v2 = header == "CH_PARK_FENCE_V2";
        const bool bound_v3 = header == "CH_PARK_FENCE_V3";
        if (!legacy_v1 && !legacy_v2 && !bound_v3) {
            result.message += " | Park fence sidecar ignored: unsupported format";
            return result;
        }

        if (bound_v3) {
            std::string digest_line;
            if (!std::getline(input, digest_line)) {
                result.message += " | Park fence sidecar ignored: missing city digest";
                return result;
            }
            std::istringstream digest_row(digest_line);
            std::string marker;
            std::string expected_hex;
            digest_row >> marker >> expected_hex;
            const std::optional<std::uint64_t> current_digest = file_digest(path);
            if (marker != "D" || !current_digest.has_value() || digest_hex(*current_digest) != expected_hex) {
                result.message += " | Park fence sidecar ignored: it belongs to a different city-save state";
                return result;
            }
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

    [[nodiscard]] static std::filesystem::path staging_path(const std::filesystem::path& path) {
        std::filesystem::path result = path;
        result += ".staging";
        return result;
    }

    [[nodiscard]] static std::filesystem::path backup_path(const std::filesystem::path& path) {
        std::filesystem::path result = path;
        result += ".previous";
        return result;
    }

    static void cleanup_file(const std::filesystem::path& path) {
        std::error_code ignored;
        std::filesystem::remove(path, ignored);
    }

    static void restore_backup(const std::filesystem::path& backup,
                               const std::filesystem::path& destination) {
        if (!std::filesystem::exists(backup)) return;
        cleanup_file(destination);
        std::error_code ignored;
        std::filesystem::rename(backup, destination, ignored);
    }

    [[nodiscard]] static SaveOperationResult staging_failure(SaveOperationResult result,
                                                             const std::filesystem::path& staged_city,
                                                             const std::filesystem::path& staged_fence,
                                                             const std::string& message) {
        cleanup_file(staged_city);
        cleanup_file(staged_fence);
        result.success = false;
        result.message = message;
        return result;
    }

    [[nodiscard]] static std::optional<std::uint64_t> file_digest(const std::filesystem::path& path) {
        std::ifstream input(path, std::ios::binary);
        if (!input) return std::nullopt;
        // FNV-1a is used as a deterministic identity checksum, not for security.
        std::uint64_t digest = 14695981039346656037ULL;
        char buffer[4096];
        while (input) {
            input.read(buffer, sizeof(buffer));
            const std::streamsize count = input.gcount();
            for (std::streamsize index = 0; index < count; ++index) {
                digest ^= static_cast<unsigned char>(buffer[index]);
                digest *= 1099511628211ULL;
            }
        }
        if (!input.eof()) return std::nullopt;
        return digest;
    }

    [[nodiscard]] static std::string digest_hex(const std::uint64_t digest) {
        std::ostringstream stream;
        stream << std::hex << std::setw(16) << std::setfill('0') << digest;
        return stream.str();
    }

    [[nodiscard]] static bool write_fence_sidecar(const std::filesystem::path& path,
                                                  const std::uint64_t city_digest) {
        std::ofstream output(path, std::ios::binary | std::ios::trunc);
        if (!output) return false;

        output << "CH_PARK_FENCE_V3\n";
        output << "D " << digest_hex(city_digest) << '\n';
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
        output.flush();
        return static_cast<bool>(output);
    }
};
