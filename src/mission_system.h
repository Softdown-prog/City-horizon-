#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include <filesystem>

struct MissionDefinition {
    std::string id;
    std::string display_name;
    std::string description;
    std::string prerequisite_mission;
    std::uint32_t target_population = 0;
    std::size_t target_residences = 0;
    std::size_t target_commercial = 0;
    std::int64_t reactivation_cost = 0;
    std::string required_civic_building_id;
    std::string target_building_id;
};

struct CleanEnergyRequirements {
    std::uint32_t target_population = 40;
    std::size_t target_residences = 2;
    std::size_t target_commercial = 1;
    std::int64_t reactivation_cost = 5000;
};

struct CityWaterRequirements {
    std::uint32_t target_population = 0;
    std::size_t target_residences = 0;
    std::size_t target_commercial = 0;
    std::int64_t reactivation_cost = 0;
    std::string required_civic_building_id = "city_hall_01";
};

class BuildingCatalog;
class BuildingManager;
class CityEconomy;
class PopulationSystem;
class PowerSystem;

// Minimal mission contract required to manage mission registration, completion status,
// JSON configuration loading, and save/load restoration for City Horizon missions.
class MissionManager {
public:
    MissionManager();

    void register_mission(std::string id, std::string display_name);
    bool load_mission_from_file(const std::filesystem::path& json_path);
    std::size_t load_missions_from_directory(const std::filesystem::path& dir_path);

    [[nodiscard]] const MissionDefinition* find_mission(std::string_view mission_id) const;
    [[nodiscard]] bool is_completed(std::string_view mission_id) const;
    bool complete_mission(std::string_view mission_id);
    void reset();

    // Idempotent auto-completion evaluation for "clean_energy". Returns true ONLY on the exact
    // instant the mission is completed and transaction executed (never twice).
    bool check_and_auto_complete_clean_energy(CityEconomy& economy, BuildingManager& buildings,
                                              const BuildingCatalog& catalog,
                                              const PopulationSystem& population, PowerSystem& power,
                                              const CleanEnergyRequirements& reqs = {});

    // Idempotent auto-completion evaluation for "city_water". Returns true ONLY on the exact
    // instant the mission is completed and transaction executed (never twice).
    bool check_and_auto_complete_city_water(CityEconomy& economy, BuildingManager& buildings,
                                            const BuildingCatalog& catalog,
                                            const PopulationSystem& population,
                                            const CityWaterRequirements& reqs = {});

    [[nodiscard]] std::vector<std::string> completed_mission_ids() const;
    void restore_completed_missions(const std::vector<std::string>& mission_ids);
    [[nodiscard]] const std::unordered_map<std::string, MissionDefinition>& definitions() const;

private:
    std::unordered_map<std::string, MissionDefinition> definitions_;
    std::unordered_map<std::string, bool> completion_status_;
};
