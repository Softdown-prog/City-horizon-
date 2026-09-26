#include "mission_system.h"

#include <iostream>

namespace {

bool require(const bool condition, const char* description) {
    if (!condition) {
        std::cerr << "FAILED: " << description << '\n';
    }
    return condition;
}

}  // namespace

int main(const int argc, char** argv) {
    MissionManager missions;

    if (!require(missions.definitions().empty(), "mission registry is empty") ||
        !require(missions.completed_mission_ids().empty(), "there are no completed missions") ||
        !require(missions.find_mission("clean_energy") == nullptr, "clean_energy is not registered") ||
        !require(missions.find_mission("city_water") == nullptr, "city_water is not registered") ||
        !require(!missions.is_completed("clean_energy"), "removed missions never report completion") ||
        !require(!missions.complete_mission("clean_energy"), "removed missions cannot be completed")) {
        return 1;
    }

    missions.register_mission("legacy_mission", "Legacy Mission");
    missions.restore_completed_missions({"legacy_mission"});
    if (!require(missions.definitions().empty(), "legacy registration remains disabled") ||
        !require(missions.completed_mission_ids().empty(), "legacy save restoration is ignored")) {
        return 1;
    }

    if (argc > 1 && !require(missions.load_missions_from_directory(argv[1]) == 0,
                             "mission files are not loaded")) {
        return 1;
    }

    std::cout << "mission system disabled\n";
    return 0;
}
