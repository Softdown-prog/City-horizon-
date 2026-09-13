#include "src/ch_core/transaction_manager.h"

namespace ch {

TransactionManager::TransactionManager(std::size_t max_depth)
    : max_depth_(max_depth) {}

void TransactionManager::record_command(const CommandRecord& cmd) {
    if (cmd.payloads.empty()) {
        return;
    }

    if (active_batch_.has_value()) {
        for (const auto& payload : cmd.payloads) {
            active_batch_->payloads.push_back(payload);
        }
        return;
    }

    undo_stack_.push_back(cmd);
    redo_stack_.clear();

    if (undo_stack_.size() > max_depth_) {
        undo_stack_.erase(undo_stack_.begin());
    }
}

void TransactionManager::begin_transaction(const std::string& description) {
    if (active_batch_.has_value()) {
        commit_transaction();
    }
    CommandRecord record;
    record.description = description;
    record.action_type = TransactionActionType::batch_transaction;
    active_batch_ = record;
}

void TransactionManager::commit_transaction() {
    if (!active_batch_.has_value()) {
        return;
    }

    CommandRecord batch = std::move(*active_batch_);
    active_batch_.reset();

    if (!batch.payloads.empty()) {
        undo_stack_.push_back(batch);
        redo_stack_.clear();

        if (undo_stack_.size() > max_depth_) {
            undo_stack_.erase(undo_stack_.begin());
        }
    }
}

void TransactionManager::cancel_transaction() {
    active_batch_.reset();
}

bool TransactionManager::can_undo() const {
    return !undo_stack_.empty() && !active_batch_.has_value();
}

bool TransactionManager::can_redo() const {
    return !redo_stack_.empty() && !active_batch_.has_value();
}

std::optional<CommandRecord> TransactionManager::undo() {
    if (!can_undo()) {
        return std::nullopt;
    }

    CommandRecord cmd = std::move(undo_stack_.back());
    undo_stack_.pop_back();

    redo_stack_.push_back(cmd);
    return cmd;
}

std::optional<CommandRecord> TransactionManager::redo() {
    if (!can_redo()) {
        return std::nullopt;
    }

    CommandRecord cmd = std::move(redo_stack_.back());
    redo_stack_.pop_back();

    undo_stack_.push_back(cmd);
    return cmd;
}

void TransactionManager::clear_history() {
    undo_stack_.clear();
    redo_stack_.clear();
    active_batch_.reset();
}

} // namespace ch
