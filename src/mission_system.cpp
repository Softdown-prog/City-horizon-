#include "mission_system.h"
#include "building_system.h"
#include "economy_system.h"
#include "population_system.h"
#include "power_system.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <iostream>
#include <optional>
#include <sstream>

namespace {

[[nodiscard]] std::string read_mission_file(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return {};
    }
    std::ostringstream contents;
    contents << input.rdbuf();
    return contents.str();
}

[[nodiscard]] std::size_t skip_whitespace(const std::string& text, std::size_t position) {
    while (position < text.size() && std::isspace(static_cast<unsigned char>(text[position])) != 0) {
        ++position;
    }
    return position;
}

[[nodiscard]] std::optional<std::size_t> value_position(const std::string& json, std::string_view key) {
    const std::string quoted_key = std::string("\"") + std::string(key) + "\"";
    const std::size_t key_position = json.find(quoted_key);
    if (key_position == std::string::npos) {
        return std::nullopt;
    }
    const std::size_t colon = json.find(':', key_position + quoted_key.size());
    if (colon == std::string::npos) {
        return std::nullopt;
    }
    return skip_whitespace(json, colon + 1);
}

[[nodiscard]] std::optional<std::string> json_string(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position || *position >= json.size() || json[*position] != '"') {
        return std::nullopt;
    }
    const std::size_t end = json.find('"', *position + 1);
    if (end == std::string::npos) {
        return std::nullopt;
    }
    return json.substr(*position + 1, end - *position - 1);
}

template <typename Number>
[[nodiscard]] std::optional<Number> json_number(const std::string& json, std::string_view key) {
    const auto position = value_position(json, key);
    if (!position) {
        return std::nullopt;
    }
    std::size_t parsed = 0;
    try {
        if constexpr (std::is_same_v<Number, int>) {
            const int value = std::stoi(json.substr(*position), &parsed);
            return parsed == 0 ? std::nullopt : std::optional<int>(value);
        } else if constexpr (std::is_same_v<Number, std::uint32_t>) {
            const unsigned long value = std::stoul(json.substr(*position), &parsed);
            return parsed == 0 ? std::nullopt : std::optional<std::uint32_t>(static_cast<std::uint32_t>(value));
        } else if constexpr (std::is_same_v<Number, std::size_t>) {
            const unsigned long long value = std::stoull(json.substr(*position), &parsed);
            return parsed == 0 ? std::nullopt : std::optional<std::size_t>(static_cast<std::size_t>(value));
        } else if constexpr (std::is_same_v<Number, std::int64_t>) {
            const long long value = std::stoll(json.substr(*position), &parsed);
            return parsed == 0 ? std::nullopt : std::optional<std::int64_t>(static_cast<std::int64_t>(value));
        }
    } catch (...) {
        return std::nullopt;
    }
    return std::nullopt;
}

}  // namespace

MissionManager::MissionManager() {
    register_mission("clean_energy", "Energia Limpa");
    register_mission("city_water", "Água para a Cidade");
}

void MissionManager::register_mission(std::string id, std::string display_name) {
    if (id.empty()) return;
    const std::string mission_id = id;
    definitions_[mission_id] = MissionDefinition{std::move(id), std::move(display_name)};
    if (completion_status_.find(mission_id) == completion_status_.end()) {
        completion_status_[mission_id] = false;
    }
}

bool MissionManager::load_mission_from_file(const std::filesystem::path& json_path) {
    const std::string contents = read_mission_file(json_path);
    if (contents.empty()) return false;
    const auto id = json_string(contents, "id");
    const auto name = json_string(contents, "name");
    if (!id || id->empty() || !name || name->empty()) return false;

    MissionDefinition def;
    def.id = *id;
    def.display_name = *name;
    def.description = json_string(contents, "description").value_or("");
    def.prerequisite_mission = json_string(contents, "prerequisiteMission").value_or("");
    def.target_population = json_number<std::uint32_t>(contents, "targetPopulation").value_or(0);
    def.target_residences = json_number<std::size_t>(contents, "targetResidences").value_or(0);
    def.target_commercial = json_number<std::size_t>(contents, "targetCommercial").value_or(0);
    def.reactivation_cost = json_number<std::int64_t>(contents, "reactivationCost").value_or(0);
    def.required_civic_building_id = json_string(contents, "requiredCivicBuildingId").value_or("");
    def.target_building_id = json_string(contents, "targetBuildingId").value_or("");

    definitions_[def.id] = def;
    if (completion_status_.find(def.id) == completion_status_.end()) {
        completion_status_[def.id] = false;
    }
    return true;
}

std::size_t MissionManager::load_missions_from_directory(const std::filesystem::path& dir_path) {
    if (!std::filesystem::exists(dir_path) || !std::filesystem::is_directory(dir_path)) {
        return 0;
    }
    std::size_t loaded = 0;
    for (const auto& entry : std::filesystem::directory_iterator(dir_path)) {
        if (entry.is_regular_file() && entry.path().extension() == ".json") {
            if (load_mission_from_file(entry.path())) {
                loaded++;
            }
        }
    }
    return loaded;
}

const MissionDefinition* MissionManager::find_mission(const std::string_view mission_id) const {
    const auto it = definitions_.find(std::string(mission_id));
    if (it != definitions_.end()) {
        return &it->second;
    }
    return nullptr;
}

bool MissionManager::is_completed(const std::string_view mission_id) const {
    const auto it = completion_status_.find(std::string(mission_id));
    if (it != completion_status_.end()) {
        return it->second;
    }
    return false;
}

bool MissionManager::complete_mission(const std::string_view mission_id) {
    const std::string key(mission_id);
    auto it = completion_status_.find(key);
    if (it != completion_status_.end()) {
        it->second = true;
        return true;
    }
    completion_status_[key] = true;
    return true;
}

void MissionManager::reset() {
    for (auto& [id, completed] : completion_status_) {
        completed = false;
    }
}

bool MissionManager::check_and_auto_complete_clean_energy(CityEconomy& economy, BuildingManager& buildings,
                                                          const BuildingCatalog& catalog,
                                                          const PopulationSystem& population, PowerSystem& power,
                                                          const CleanEnergyRequirements& reqs) {
    // Idempotent guard: if already completed, do nothing and return false immediately
    if (is_completed("clean_energy")) {
        return false;
    }

    if (population.current_population() < reqs.target_population) {
        return false;
    }

    if (economy.funds() < reqs.reactivation_cost) {
        return false;
    }

    std::size_t residential_count = 0;
    std::size_t commercial_count = 0;

    for (const BuildingInstance& instance : buildings.instances()) {
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr) {
            continue;
        }
        if (definition->category == "residential") {
            residential_count++;
        } else if (definition->category == "commercial") {
            commercial_count++;
        }
    }

    if (residential_count < reqs.target_residences || commercial_count < reqs.target_commercial) {
        return false;
    }

    // Execute exact instant auto-completion transaction
    if (reqs.reactivation_cost > 0) {
        economy.restore_funds(economy.funds() - reqs.reactivation_cost);
    }

    complete_mission("clean_energy");

    // Decoupled infrastructure unlock: update Hydroelectric Dam instance state
    buildings.set_operational_by_definition("hydroelectric_01", true);
    power.rebuild(buildings, catalog);

    return true;
}

bool MissionManager::check_and_auto_complete_city_water(CityEconomy& economy, BuildingManager& buildings,
                                                         const BuildingCatalog& catalog,
                                                         const PopulationSystem& population,
                                                         const CityWaterRequirements& reqs) {
    // 1. Idempotent guard: if already completed, do nothing and return false immediately
    if (is_completed("city_water")) {
        return false;
    }

    // Read data-driven requirements from loaded JSON definition if present
    const MissionDefinition* def = find_mission("city_water");
    const std::string prerequisite = (def != nullptr && !def->prerequisite_mission.empty()) ? def->prerequisite_mission : "clean_energy";
    const std::uint32_t target_pop = (def != nullptr && def->target_population > 0) ? def->target_population : reqs.target_population;
    const std::size_t target_res = (def != nullptr && def->target_residences > 0) ? def->target_residences : reqs.target_residences;
    const std::size_t target_com = (def != nullptr && def->target_commercial > 0) ? def->target_commercial : reqs.target_commercial;
    const std::int64_t cost = (def != nullptr && def->reactivation_cost > 0) ? def->reactivation_cost : reqs.reactivation_cost;
    const std::string required_civic = (def != nullptr && !def->required_civic_building_id.empty()) ? def->required_civic_building_id : reqs.required_civic_building_id;

    // 2. Mandatory prerequisite check
    if (!prerequisite.empty() && !is_completed(prerequisite)) {
        return false;
    }

    // Pending balancing guard: if numerical requirements are 0 (unconfigured/pending), do not auto-complete
    if (target_pop == 0 && target_res == 0 && target_com == 0 && cost == 0) {
        return false;
    }

    // 3. Data-driven requirements evaluation
    if (population.current_population() < target_pop) {
        return false;
    }

    if (economy.funds() < cost) {
        return false;
    }

    std::size_t residential_count = 0;
    std::size_t commercial_count = 0;
    bool has_required_civic = required_civic.empty();

    for (const BuildingInstance& instance : buildings.instances()) {
        if (!has_required_civic && instance.definition_id == required_civic) {
            has_required_civic = true;
        }
        const BuildingDefinition* definition = catalog.find(instance.definition_id);
        if (definition == nullptr) {
            continue;
        }
        if (definition->category == "residential") {
            residential_count++;
        } else if (definition->category == "commercial") {
            commercial_count++;
        }
    }

    if (!has_required_civic || residential_count < target_res || commercial_count < target_com) {
        return false;
    }

    // 4. Single-transaction execution
    if (cost > 0) {
        economy.restore_funds(economy.funds() - cost);
    }

    complete_mission("city_water");

    // 5. Decoupled infrastructure unlock: update Water Intake Station (water_intake_01) instance state
    const std::string target_building = (def != nullptr && !def->target_building_id.empty()) ? def->target_building_id : "water_intake_01";
    buildings.set_operational_by_definition(target_building, true);

    return true;
}

std::vector<std::string> MissionManager::completed_mission_ids() const {
    std::vector<std::string> completed;
    for (const auto& [id, is_done] : completion_status_) {
        if (is_done) {
            completed.push_back(id);
        }
    }
    return completed;
}

void MissionManager::restore_completed_missions(const std::vector<std::string>& mission_ids) {
    reset();
    for (const std::string& id : mission_ids) {
        completion_status_[id] = true;
    }
}

const std::unordered_map<std::string, MissionDefinition>& MissionManager::definitions() const {
    return definitions_;
}
