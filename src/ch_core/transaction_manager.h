#ifndef CITY_HORIZON_CH_CORE_TRANSACTION_MANAGER_H
#define CITY_HORIZON_CH_CORE_TRANSACTION_MANAGER_H

#include "src/ch_core/transaction_contracts.h"
#include <vector>
#include <string>
#include <optional>

namespace ch {

class TransactionManager {
public:
    explicit TransactionManager(std::size_t max_depth = 100);

    void record_command(const CommandRecord& cmd);

    void begin_transaction(const std::string& description);
    void commit_transaction();
    void cancel_transaction();

    [[nodiscard]] bool can_undo() const;
    [[nodiscard]] bool can_redo() const;

    std::optional<CommandRecord> undo();
    std::optional<CommandRecord> redo();

    void clear_history();

    [[nodiscard]] std::size_t undo_stack_size() const { return undo_stack_.size(); }
    [[nodiscard]] std::size_t redo_stack_size() const { return redo_stack_.size(); }
    [[nodiscard]] bool is_in_batch() const { return active_batch_.has_value(); }

private:
    std::size_t max_depth_;
    std::vector<CommandRecord> undo_stack_;
    std::vector<CommandRecord> redo_stack_;
    std::optional<CommandRecord> active_batch_;
};

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_TRANSACTION_MANAGER_H
