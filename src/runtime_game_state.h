#pragma once

namespace ch::runtime_game_state {

// Runtime-only presentation bridge. The canonical economy remains authoritative;
// this state simply lets the UI and clock react without duplicating the main loop.
inline bool game_over = false;
inline int consecutive_negative_months = 0;

inline void reset() {
    game_over = false;
    consecutive_negative_months = 0;
}

inline void update(const bool bankrupt, const int negative_months) {
    game_over = bankrupt;
    consecutive_negative_months = negative_months;
}

}  // namespace ch::runtime_game_state
