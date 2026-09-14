#include "editor_history.h"

#include <algorithm>
#include <utility>

namespace ch::editor {

void EditorHistory::commit(std::vector<TileChange> changes) {
    changes.erase(
        std::remove_if(changes.begin(), changes.end(), [](const TileChange& change) {
            return change.before == change.after;
        }),
        changes.end());

    if (changes.empty()) {
        return;
    }

    if (cursor_ < entries_.size()) {
        entries_.erase(entries_.begin() + static_cast<std::ptrdiff_t>(cursor_), entries_.end());
    }

    entries_.push_back(std::move(changes));
    cursor_ = entries_.size();
}

bool EditorHistory::undo(EditorDocument& document) {
    if (!canUndo()) {
        return false;
    }

    --cursor_;
    const auto& changes = entries_[cursor_];
    for (auto it = changes.rbegin(); it != changes.rend(); ++it) {
        document.setTile(it->x, it->y, it->before);
    }
    return true;
}

bool EditorHistory::redo(EditorDocument& document) {
    if (!canRedo()) {
        return false;
    }

    const auto& changes = entries_[cursor_];
    for (const auto& change : changes) {
        document.setTile(change.x, change.y, change.after);
    }
    ++cursor_;
    return true;
}

void EditorHistory::clear() {
    entries_.clear();
    cursor_ = 0;
}

} // namespace ch::editor
