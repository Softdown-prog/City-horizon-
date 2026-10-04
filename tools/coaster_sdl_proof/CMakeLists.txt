cmake_minimum_required(VERSION 3.24)
project(ch_coaster_sdl_visual_proof LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)
set(SDL_SHARED OFF CACHE BOOL "Build SDL shared library" FORCE)
set(SDL_STATIC ON CACHE BOOL "Build SDL static library" FORCE)
set(SDL_TEST_LIBRARY OFF CACHE BOOL "Disable SDL test library" FORCE)
set(SDL_TESTS OFF CACHE BOOL "Disable SDL tests" FORCE)
set(SDL_EXAMPLES OFF CACHE BOOL "Disable SDL examples" FORCE)
# This proof intentionally renders to an SDL software surface in CI. It never
# creates a desktop window, so headless Unix runners must skip the X11/Wayland
# requirement while retaining SDL's dummy/offscreen video and render paths.
set(SDL_UNIX_CONSOLE_BUILD ON CACHE BOOL "Headless console-only SDL proof" FORCE)
FetchContent_Declare(
    SDL3
    GIT_REPOSITORY https://github.com/libsdl-org/SDL.git
    GIT_TAG release-3.4.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(SDL3)

get_filename_component(CH_REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)

add_executable(coaster_sdl_visual_proof
    coaster_sdl_visual_proof.cpp
    "${CH_REPO_ROOT}/src/ch_core/projection.cpp"
)
target_include_directories(coaster_sdl_visual_proof PRIVATE "${CH_REPO_ROOT}")
target_link_libraries(coaster_sdl_visual_proof PRIVATE SDL3::SDL3)

if(MSVC)
    target_compile_options(coaster_sdl_visual_proof PRIVATE /W4)
else()
    target_compile_options(coaster_sdl_visual_proof PRIVATE -Wall -Wextra -Wpedantic)
endif()
