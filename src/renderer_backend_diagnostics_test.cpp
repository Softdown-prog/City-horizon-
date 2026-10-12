#include "renderer_backend_diagnostics.h"

#include <SDL3/SDL.h>
#include <cassert>
#include <iostream>
#include <sstream>
#include <string>

int main() {
    // Test exact renderer detection independently of the machine's default.
    if (!SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software")) {
        std::cerr << "Cannot select SDL software renderer for smoke test\n";
        return 1;
    }
    if (!SDL_Init(SDL_INIT_VIDEO)) {
        std::cerr << SDL_GetError() << '\n';
        return 2;
    }
    SDL_Window* window = SDL_CreateWindow("CH SDL backend smoke", 320, 240, SDL_WINDOW_HIDDEN);
    SDL_Renderer* renderer = window != nullptr ? SDL_CreateRenderer(window, nullptr) : nullptr;
    if (renderer == nullptr) {
        std::cerr << "Cannot create SDL renderer: " << SDL_GetError() << '\n';
        if (window != nullptr) SDL_DestroyWindow(window);
        SDL_Quit();
        return 3;
    }
    std::ostringstream diagnostic;
    ch::renderer_backend::report(renderer, diagnostic);
    const std::string lines = diagnostic.str();
    std::cout << lines;
    const bool ok =
        ch::renderer_backend::is_software(renderer) &&
        ch::renderer_backend::selected(renderer) == "software" &&
        lines.find("selected=software") != std::string::npos &&
        lines.find("requested=software") != std::string::npos &&
        lines.find("WARNING: software renderer") != std::string::npos &&
        lines.find("available=") != std::string::npos;
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
    if (!ok) {
        std::cerr << "CH_RENDER_BACKEND_V1 smoke validation failed\n";
        return 4;
    }
    std::cout << "CH_RENDER_BACKEND_V1 PASS: selected backend is accurately reported\n";
    return 0;
}
