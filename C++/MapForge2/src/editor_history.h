#pragma once

#include "editor_document.h"

#include <cstddef>
#include <vector>

namespace ch::editor {

struct TileChange {
    int x = 0;
    int y = 0;
    TileState before;
    TileState after;
};

class EditorHistory {
public:
    void commit(std::vector<TileChange> changes);
    bool undo(EditorDocument& document);
    bool redo(EditorDocument& document);
    void clear();

    [[nodiscard]] bool canUndo() const { return cursor_ > 0; }
    [[nodiscard]] bool canRedo() const { return cursor_ < entries_.size(); }
    [[nodiscard]] std::size_t size() const { return entries_.size(); }

private:
    std::vector<std::vector<TileChange>> entries_;
    std::size_t cursor_ = 0;
};

} // namespace ch::editor
