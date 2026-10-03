cmake_minimum_required(VERSION 3.24)
project(CHMapForgeCoasterVideoProof LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Qt6 6.5 REQUIRED COMPONENTS Core Gui)

get_filename_component(CH_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)

add_executable(MapForge2CoasterVideoProof
    "${CH_ROOT}/C++/MapForge2/src/coaster_project_video_main.cpp"
)
target_include_directories(MapForge2CoasterVideoProof PRIVATE "${CH_ROOT}")
target_link_libraries(MapForge2CoasterVideoProof PRIVATE Qt6::Core Qt6::Gui)

if(MSVC)
    target_compile_options(MapForge2CoasterVideoProof PRIVATE /W4 /permissive- /utf-8)
else()
    target_compile_options(MapForge2CoasterVideoProof PRIVATE -Wall -Wextra -Wpedantic)
endif()
