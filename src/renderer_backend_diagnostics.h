#pragma once

#include <SDL3/SDL.h>

#include <ostream>
#include <string>

// CH_RENDER_BACKEND_DIAGNOSTICS_V1
// Observe SDL3's ACTUAL selected backend, not what the video CI requested.
// Never force OpenGL: let SDL choose the platform-appropriate renderer, and
// allow the normal SDL_RENDER_DRIVER environment setting for troubleshooting.
namespace ch::renderer_backend {

[[nodiscard]] inline std::string selected(SDL_Renderer* renderer) {
    if (renderer == nullptr) return "unavailable";
    const char* name = SDL_GetRendererName(renderer);
    return name != nullptr && name[0] != '\0' ? name : "unknown";
}

[[nodiscard]] inline bool is_software(SDL_Renderer* renderer) {
    return selected(renderer) == "software";
}

inline void report(SDL_Renderer* renderer, std::ostream& output) {
    output << "[CH_RENDER_BACKEND_V1] selected=" << selected(renderer);
    const char* video = SDL_GetCurrentVideoDriver();
    output << " video=" << (video != nullptr ? video : "unknown");
    const char* requested = SDL_GetHint(SDL_HINT_RENDER_DRIVER);
    output << " requested=" << (requested != nullptr && requested[0] ? requested : "auto");
    output << " available=";
    const int count = SDL_GetNumRenderDrivers();
    for (int i = 0; i < count; ++i) {
        if (i != 0) output << ',';
        const char* name = SDL_GetRenderDriver(i);
        output << (name != nullptr ? name : "unknown");
    }
    output << '\n';
    if (is_software(renderer))
        output << "[CH_RENDER_BACKEND_V1] WARNING: software renderer in use. "
                  "Rail sprite alpha behavior requires additional validation "
                  "(see GitHub issue #76).\n";
}

} // namespace ch::renderer_backend
