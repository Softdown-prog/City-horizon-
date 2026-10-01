#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

// main.cpp temporarily aliases CityEconomy to the runtime bridge class before
// including main_runtime_impl.cpp. MissionManager, however, is implemented in
// mission_system.cpp against the canonical CityEconomy type. Keep this header's
// ABI canonical even when it is reached from inside that compatibility wrapper;
// otherwise the declaration is macro-rewritten to ChCityEconomy& while the
// separately compiled definition still exports CityEconomy&, causing LNK2019.
#if defined(CityEconomy)
#pragma push_macro("CityEconomy")
#undef CityEconomy
#define CH_MISSION_RESTORE_CITY_ECONOMY_MACRO 1
#endif

// Legacy mission data types are kept only so old saves and call sites continue
// to compile while missions are no longer part of the active game loop.
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

// Compatibility shell. Mission progression, unlocks and mission transactions
// are intentionally disabled. The API remains temporarily so SaveManager and
// older runtime call sites can migrate without destabilising unrelated systems.
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

    bool check_and_auto_complete_clean_energy(CityEconomy& economy, BuildingManager& buildings,
                                              const BuildingCatalog& catalog,
                                              const PopulationSystem& population, PowerSystem& power,
                                              const CleanEnergyRequirements& reqs = {});

    bool check_and_auto_complete_city_water(CityEconomy& economy, BuildingManager& buildings,
                                            const BuildingCatalog& catalog,
                                            const PopulationSystem& population,
                                            const CityWaterRequirements& reqs = {});

    [[nodiscard]] std::vector<std::string> completed_mission_ids() const;
    void restore_completed_missions(const std::vector<std::string>& mission_ids);
    [[nodiscard]] const std::unordered_map<std::string, MissionDefinition>& definitions() const;
};

#if defined(CH_MISSION_RESTORE_CITY_ECONOMY_MACRO)
#pragma pop_macro("CityEconomy")
#undef CH_MISSION_RESTORE_CITY_ECONOMY_MACRO
#endif
