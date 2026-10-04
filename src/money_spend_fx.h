#pragma once

#include <SDL3/SDL.h>

#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>

// CH_MONEY_SPEND_FX_V1
// Screen-space feedback for successful construction/infrastructure spending.
// The economy remains authoritative; callers spawn an effect only after a
// successful paid action. No economy state is owned or modified here.
class MoneySpendFx {
public:
    void spawn(const std::int64_t amount, const float screen_x, const float screen_y) {
        if (amount <= 0) return;
        entries_.push_back({amount, screen_x, screen_y, SDL_GetTicks()});
        if (entries_.size() > kMaxEntries) entries_.erase(entries_.begin());
    }

    void render(SDL_Renderer* renderer) {
        if (renderer == nullptr) return;
        const Uint64 now = SDL_GetTicks();
        std::erase_if(entries_, [now](const Entry& e) { return now - e.started_ms >= kLifetimeMs; });

        for (const Entry& entry : entries_) {
            const float t = std::clamp(static_cast<float>(now - entry.started_ms) /
                                       static_cast<float>(kLifetimeMs), 0.0F, 1.0F);
            const float eased = 1.0F - (1.0F - t) * (1.0F - t);
            const float y = entry.screen_y - 18.0F - 34.0F * eased;
            const Uint8 alpha = static_cast<Uint8>(255.0F * (1.0F - t));

            const std::string text = "-$" + std::to_string(entry.amount);
            // Tiny dark offset keeps the amount readable over bright terrain.
            SDL_SetRenderDrawColor(renderer, 22, 18, 14, static_cast<Uint8>(alpha * 0.70F));
            SDL_RenderDebugText(renderer, entry.screen_x + 1.0F, y + 1.0F, text.c_str());
            SDL_SetRenderDrawColor(renderer, 255, 214, 92, alpha);
            SDL_RenderDebugText(renderer, entry.screen_x, y, text.c_str());
        }
    }

private:
    struct Entry {
        std::int64_t amount = 0;
        float screen_x = 0.0F;
        float screen_y = 0.0F;
        Uint64 started_ms = 0;
    };

    static constexpr Uint64 kLifetimeMs = 950;
    static constexpr std::size_t kMaxEntries = 24;
    std::vector<Entry> entries_;
};
