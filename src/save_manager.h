#pragma once

#include <cstddef>
#include <filesystem>
#include <string>

class BuildingCatalog;
class BuildingManager;
class RoadManager;
class LandManager;
class CityEconomy;
class SimulationClock;
class PopulationSystem;
class SidewalkManager;
class FarmingSystem;
class ServiceVehicleCatalog;
class ServiceVehicleManager;

struct SaveOperationResult {
    bool success = false;
    std::string message;
    std::size_t skipped_buildings = 0;
    std::size_t skipped_roads = 0;
    std::size_t skipped_sidewalks = 0;
    std::size_t skipped_farming_tiles = 0;
    std::size_t unknown_parcels = 0;
};

class MissionManager;

// JSON save-game boundary. Gameplay systems expose narrow restore APIs, while
// file format, version checks and user-data paths remain centralized here.
class SaveManager {
public:
    static constexpr int kSaveVersion = 10;

    [[nodiscard]] static std::filesystem::path default_save_path();
    // Reserved path for a later timer-driven autosave; no automatic writes yet.
    [[nodiscard]] static std::filesystem::path autosave_path();

    [[nodiscard]] SaveOperationResult save(const std::filesystem::path& path,
                                           const CityEconomy& economy, const SimulationClock& clock,
                                           const BuildingManager& buildings, const RoadManager& roads,
                                           const SidewalkManager& sidewalks, const FarmingSystem& farming,
                                           const LandManager& lands, const PopulationSystem& population,
                                           const ServiceVehicleManager* vehicles = nullptr,
                                           const MissionManager* missions = nullptr) const;
    [[nodiscard]] SaveOperationResult load(const std::filesystem::path& path,
                                           const BuildingCatalog& catalog, CityEconomy& economy,
                                           SimulationClock& clock, BuildingManager& buildings,
                                           RoadManager& roads, SidewalkManager& sidewalks, FarmingSystem& farming,
                                           LandManager& lands, PopulationSystem& population,
                                           const ServiceVehicleCatalog* vehicle_catalog = nullptr,
                                           ServiceVehicleManager* vehicles = nullptr,
                                           MissionManager* missions = nullptr) const;
};
