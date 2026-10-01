cmake_minimum_required(VERSION 3.24)

project(CHRailMapForgeProof LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

get_filename_component(CH_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)

# Import the real MapForge project so this proof links the exact canonical
# CH_CAMERA_V1 projection library instead of reproducing projection math here.
add_subdirectory("${CH_ROOT}/C++/MapForge2" mapforge2 EXCLUDE_FROM_ALL)

add_executable(CHRailMapForgeProof
    "${CH_ROOT}/C++/MapForge2/src/procedural_rail_preview_main.cpp"
    "${CH_ROOT}/src/rail_system.cpp"
)
target_include_directories(CHRailMapForgeProof PRIVATE "${CH_ROOT}")
target_link_libraries(CHRailMapForgeProof PRIVATE mapforge2_canonical Qt6::Gui)

if(MSVC)
    target_compile_options(CHRailMapForgeProof PRIVATE /W4 /permissive- /utf-8)
else()
    target_compile_options(CHRailMapForgeProof PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
