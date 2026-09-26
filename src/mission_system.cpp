#include "mission_system.h"

MissionManager::MissionManager() = default;

void MissionManager::register_mission(std::string id, std::string display_name) {
    (void)id;
    (void)display_name;
}

bool MissionManager::load_mission_from_file(const std::filesystem::path& json_path) {
    (void)json_path;
    return false;
}

std::size_t MissionManager::load_missions_from_directory(const std::filesystem::path& dir_path) {
    (void)dir_path;
    return 0;
}

const MissionDefinition* MissionManager::find_mission(const std::string_view mission_id) const {
    (void)mission_id;
    return nullptr;
}

bool MissionManager::is_completed(const std::string_view mission_id) const {
    (void)mission_id;
    return false;
}

bool MissionManager::complete_mission(const std::string_view mission_id) {
    (void)mission_id;
    return false;
}

void MissionManager::reset() {}

bool MissionManager::check_and_auto_complete_clean_energy(CityEconomy& economy, BuildingManager& buildings,
                                                          const BuildingCatalog& catalog,
                                                          const PopulationSystem& population, PowerSystem& power,
                                                          const CleanEnergyRequirements& reqs) {
    (void)economy;
    (void)buildings;
    (void)catalog;
    (void)population;
    (void)power;
    (void)reqs;
    return false;
}

bool MissionManager::check_and_auto_complete_city_water(CityEconomy& economy, BuildingManager& buildings,
                                                         const BuildingCatalog& catalog,
                                                         const PopulationSystem& population,
                                                         const CityWaterRequirements& reqs) {
    (void)economy;
    (void)buildings;
    (void)catalog;
    (void)population;
    (void)reqs;
    return false;
}

std::vector<std::string> MissionManager::completed_mission_ids() const {
    return {};
}

void MissionManager::restore_completed_missions(const std::vector<std::string>& mission_ids) {
    (void)mission_ids;
}

const std::unordered_map<std::string, MissionDefinition>& MissionManager::definitions() const {
    static const std::unordered_map<std::string, MissionDefinition> kNoMissions;
    return kNoMissions;
}
