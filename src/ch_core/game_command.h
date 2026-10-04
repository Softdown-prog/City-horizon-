#pragma once

#include "src/ch_core/transaction_contracts.h"

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace ch {

inline constexpr const char* kGameCommandContract = "CH_GAME_COMMAND_V1";

enum class GameCommandMode : std::uint8_t {
    preview,
    execute,
};

enum class GameCommandFailure : std::uint8_t {
    none,
    invalid_request,
    blocked,
    insufficient_funds,
    out_of_bounds,
    conflicting_state,
    internal_error,
};

struct GameCommandTile {
    int x = 0;
    int y = 0;

    [[nodiscard]] bool operator==(const GameCommandTile&) const = default;
};

// Immutable result of command validation/planning. Preview exposes this object
// directly; execute consumes the same plan so cost and affected tiles cannot
// silently diverge between the two paths.
struct GameCommandPlan {
    bool valid = false;
    GameCommandFailure failure = GameCommandFailure::invalid_request;
    std::string message;
    std::int64_t cost_cents = 0;
    std::vector<GameCommandTile> affected_tiles;
    CommandRecord transaction;
};

struct GameCommandResult {
    bool success = false;
    bool applied = false;
    GameCommandFailure failure = GameCommandFailure::invalid_request;
    std::string message;
    std::int64_t cost_cents = 0;
    std::vector<GameCommandTile> affected_tiles;
    CommandRecord transaction;
};

// Commands own no UI and no renderer state. Implementations inspect the current
// world in prepare(), then mutate only from apply(). This preserves one source
// of truth for validation, preview and execution.
class IGameCommand {
public:
    virtual ~IGameCommand() = default;

    [[nodiscard]] virtual GameCommandPlan prepare() const = 0;
    [[nodiscard]] virtual bool apply(const GameCommandPlan& prepared, std::string& error) = 0;
};

class GameCommandExecutor {
public:
    [[nodiscard]] static GameCommandResult run(IGameCommand& command, const GameCommandMode mode) {
        GameCommandPlan plan = command.prepare();
        GameCommandResult result;
        result.success = plan.valid;
        result.failure = plan.failure;
        result.message = plan.message;
        result.cost_cents = plan.cost_cents;
        result.affected_tiles = plan.affected_tiles;
        result.transaction = plan.transaction;

        if (!plan.valid || mode == GameCommandMode::preview) {
            return result;
        }

        std::string apply_error;
        if (!command.apply(plan, apply_error)) {
            result.success = false;
            result.applied = false;
            result.failure = GameCommandFailure::internal_error;
            result.message = apply_error.empty() ? "command apply failed" : std::move(apply_error);
            return result;
        }

        result.applied = true;
        result.failure = GameCommandFailure::none;
        return result;
    }
};

}  // namespace ch
