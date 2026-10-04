#pragma once

#include <SDL3/SDL.h>

#include <array>
#include <algorithm>
#include <cstdint>

// CH_TOOL_CURSOR_V1
// Small procedural cursors keep editing tools readable without adding another
// binary-asset pipeline. The click hotspot is always the lower-left action tip
// at (5, 27); decoration stays above/right of that point so grid picking does
// not shift when a tool becomes active.
enum class ToolCursorKind : std::uint8_t {
    pointer = 0,
    build,
    floor,
    raise_terrain,
    lower_terrain,
    smooth_terrain,
    demolish,
    road,
    water,
    land,
    count,
};

class ToolCursorManager {
public:
    ToolCursorManager() = default;
    ToolCursorManager(const ToolCursorManager&) = delete;
    ToolCursorManager& operator=(const ToolCursorManager&) = delete;

    ~ToolCursorManager() {
        for (SDL_Cursor* cursor : cursors_) {
            if (cursor != nullptr) SDL_DestroyCursor(cursor);
        }
    }

    void set(const ToolCursorKind kind) {
        if (kind == active_) return;
        active_ = kind;
        if (kind == ToolCursorKind::pointer) {
            SDL_SetCursor(SDL_GetDefaultCursor());
            return;
        }
        const std::size_t index = static_cast<std::size_t>(kind);
        if (cursors_[index] == nullptr) cursors_[index] = make_cursor(kind);
        if (cursors_[index] != nullptr) SDL_SetCursor(cursors_[index]);
        else SDL_SetCursor(SDL_GetDefaultCursor());
    }

    [[nodiscard]] ToolCursorKind active() const noexcept { return active_; }

private:
    static constexpr int kSize = 32;
    static constexpr int kHotX = 5;
    static constexpr int kHotY = 27;

    struct Rgba { Uint8 r, g, b, a; };
    static constexpr Rgba kInk{27, 32, 36, 255};
    static constexpr Rgba kLight{246, 244, 232, 255};
    static constexpr Rgba kAccent{245, 188, 66, 255};
    static constexpr Rgba kGood{92, 184, 92, 255};
    static constexpr Rgba kBad{214, 72, 72, 255};
    static constexpr Rgba kWater{79, 154, 211, 255};

    static void pixel(SDL_Surface* surface, const int x, const int y, const Rgba c) {
        if (surface == nullptr || x < 0 || y < 0 || x >= kSize || y >= kSize) return;
        (void)SDL_WriteSurfacePixel(surface, x, y, c.r, c.g, c.b, c.a);
    }

    static void line(SDL_Surface* surface, int x0, int y0, const int x1, const int y1, const Rgba c, const int thickness = 1) {
        const int dx = std::abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
        const int dy = -std::abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
        int err = dx + dy;
        for (;;) {
            for (int oy = -thickness / 2; oy <= thickness / 2; ++oy)
                for (int ox = -thickness / 2; ox <= thickness / 2; ++ox)
                    pixel(surface, x0 + ox, y0 + oy, c);
            if (x0 == x1 && y0 == y1) break;
            const int e2 = 2 * err;
            if (e2 >= dy) { err += dy; x0 += sx; }
            if (e2 <= dx) { err += dx; y0 += sy; }
        }
    }

    static void diamond(SDL_Surface* s, const int cx, const int cy, const int rx, const int ry, const Rgba fill, const Rgba outline) {
        for (int y = -ry; y <= ry; ++y) {
            const float t = 1.0F - static_cast<float>(std::abs(y)) / static_cast<float>(std::max(1, ry));
            const int span = static_cast<int>(t * static_cast<float>(rx));
            for (int x = -span; x <= span; ++x) pixel(s, cx + x, cy + y, fill);
        }
        line(s, cx, cy - ry, cx + rx, cy, outline);
        line(s, cx + rx, cy, cx, cy + ry, outline);
        line(s, cx, cy + ry, cx - rx, cy, outline);
        line(s, cx - rx, cy, cx, cy - ry, outline);
    }

    static void plus(SDL_Surface* s, const int cx, const int cy, const Rgba c) {
        line(s, cx - 4, cy, cx + 4, cy, kInk, 3);
        line(s, cx, cy - 4, cx, cy + 4, kInk, 3);
        line(s, cx - 3, cy, cx + 3, cy, c);
        line(s, cx, cy - 3, cx, cy + 3, c);
    }

    static void minus(SDL_Surface* s, const int cx, const int cy, const Rgba c) {
        line(s, cx - 4, cy, cx + 4, cy, kInk, 3);
        line(s, cx - 3, cy, cx + 3, cy, c);
    }

    static void arrow_vertical(SDL_Surface* s, const int cx, const int y0, const int y1, const bool up, const Rgba c) {
        line(s, cx, y0, cx, y1, kInk, 3);
        line(s, cx, y0, cx, y1, c);
        const int tip = up ? y0 : y1;
        const int wing = up ? tip + 4 : tip - 4;
        line(s, cx, tip, cx - 4, wing, kInk, 3);
        line(s, cx, tip, cx + 4, wing, kInk, 3);
        line(s, cx, tip, cx - 3, up ? tip + 3 : tip - 3, c);
        line(s, cx, tip, cx + 3, up ? tip + 3 : tip - 3, c);
    }

    static void action_tip(SDL_Surface* s) {
        // Tiny neutral pointer to preserve an obvious exact click point.
        line(s, kHotX, kHotY, 10, 21, kInk, 3);
        line(s, kHotX, kHotY, 10, 21, kLight);
        pixel(s, kHotX, kHotY, kInk);
    }

    static SDL_Cursor* make_cursor(const ToolCursorKind kind) {
        SDL_Surface* s = SDL_CreateSurface(kSize, kSize, SDL_PIXELFORMAT_RGBA32);
        if (s == nullptr) return nullptr;
        for (int y = 0; y < kSize; ++y)
            for (int x = 0; x < kSize; ++x)
                (void)SDL_WriteSurfacePixel(s, x, y, 0, 0, 0, 0);

        action_tip(s);
        switch (kind) {
            case ToolCursorKind::build:
                // Hammer silhouette + construction plus.
                line(s, 13, 18, 24, 7, kInk, 5);
                line(s, 13, 18, 24, 7, kLight, 2);
                line(s, 19, 6, 27, 10, kInk, 5);
                line(s, 20, 7, 26, 10, kAccent, 2);
                plus(s, 25, 20, kGood);
                break;
            case ToolCursorKind::floor:
                diamond(s, 20, 14, 9, 5, kAccent, kInk);
                plus(s, 24, 23, kGood);
                break;
            case ToolCursorKind::raise_terrain:
                diamond(s, 19, 20, 10, 5, kGood, kInk);
                arrow_vertical(s, 19, 5, 15, true, kLight);
                break;
            case ToolCursorKind::lower_terrain:
                diamond(s, 19, 11, 10, 5, kAccent, kInk);
                arrow_vertical(s, 19, 15, 27, false, kLight);
                break;
            case ToolCursorKind::smooth_terrain:
                diamond(s, 19, 18, 10, 5, kLight, kInk);
                line(s, 10, 11, 28, 11, kInk, 3);
                line(s, 11, 11, 27, 11, kGood);
                break;
            case ToolCursorKind::demolish:
                line(s, 12, 8, 27, 23, kInk, 5);
                line(s, 27, 8, 12, 23, kInk, 5);
                line(s, 13, 9, 26, 22, kBad, 2);
                line(s, 26, 9, 13, 22, kBad, 2);
                break;
            case ToolCursorKind::road:
                diamond(s, 20, 15, 10, 6, Rgba{100, 104, 107, 255}, kInk);
                line(s, 13, 15, 27, 15, kLight, 2);
                break;
            case ToolCursorKind::water:
                diamond(s, 20, 16, 10, 5, kWater, kInk);
                line(s, 13, 16, 18, 14, kLight);
                line(s, 18, 14, 24, 16, kLight);
                break;
            case ToolCursorKind::land:
                diamond(s, 20, 17, 10, 5, kGood, kInk);
                line(s, 20, 16, 20, 6, kInk, 3);
                line(s, 20, 6, 27, 9, kInk, 3);
                line(s, 21, 7, 26, 9, kAccent);
                break;
            case ToolCursorKind::pointer:
            case ToolCursorKind::count:
                break;
        }

        SDL_Cursor* cursor = SDL_CreateColorCursor(s, kHotX, kHotY);
        SDL_DestroySurface(s);
        return cursor;
    }

    std::array<SDL_Cursor*, static_cast<std::size_t>(ToolCursorKind::count)> cursors_{};
    ToolCursorKind active_ = ToolCursorKind::pointer;
};
