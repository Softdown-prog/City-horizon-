#include "asset_history.h"

namespace ch::studio {

bool AssetHistory::commit(const QString& label,
                          const AssetDocumentSnapshot& before,
                          const AssetDocumentSnapshot& after) {
    if (before == after) return false;

    while (entries_.size() > cursor_) entries_.removeLast();
    entries_.push_back(AssetHistoryEntry{label, before, after});
    cursor_ = entries_.size();
    return true;
}

bool AssetHistory::undo(AssetDocument& document, QString* label) {
    if (!canUndo()) return false;
    --cursor_;
    const AssetHistoryEntry& entry = entries_[cursor_];
    document.restore(entry.before);
    if (label) *label = entry.label;
    return true;
}

bool AssetHistory::redo(AssetDocument& document, QString* label) {
    if (!canRedo()) return false;
    const AssetHistoryEntry& entry = entries_[cursor_];
    document.restore(entry.after);
    ++cursor_;
    if (label) *label = entry.label;
    return true;
}

void AssetHistory::clear() {
    entries_.clear();
    cursor_ = 0;
}

AssetEditTransaction::AssetEditTransaction(AssetDocument& document,
                                           AssetHistory& history,
                                           QString label)
    : document_(document),
      history_(history),
      label_(std::move(label)),
      before_(document.snapshot()) {}

bool AssetEditTransaction::commit() {
    if (finished_) return false;
    finished_ = true;
    return history_.commit(label_, before_, document_.snapshot());
}

void AssetEditTransaction::rollback() {
    if (finished_) return;
    document_.restore(before_);
    finished_ = true;
}

} // namespace ch::studio
