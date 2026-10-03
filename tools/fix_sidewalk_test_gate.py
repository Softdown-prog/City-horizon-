from pathlib import Path

cmake = Path("CMakeLists.txt")
text = cmake.read_text(encoding="utf-8")
old = '''    add_executable(sidewalk_topology_test
        src/sidewalk_topology_test.cpp
        src/building_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/mobile_animation.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/sidewalk_system.cpp
        src/vehicle_system.cpp
    )'''
new = '''    add_executable(sidewalk_topology_test
        src/sidewalk_topology_test.cpp
        src/building_system.cpp
        src/crosswalk_system.cpp
        src/economy_system.cpp
        src/farming_system.cpp
        src/mobile_animation.cpp
        src/population_system.cpp
        src/power_system.cpp
        src/resource_system.cpp
        src/road_system.cpp
        src/sidewalk_system.cpp
        src/vehicle_system.cpp
    )'''
count = text.count(old)
assert count == 1, f"sidewalk_topology_test target drifted: expected 1, found {count}"
cmake.write_text(text.replace(old, new, 1), encoding="utf-8")
