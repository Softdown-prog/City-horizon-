#pragma once

#include "asset_document.h"

#include <QString>
#include <QVector>

#include <cstddef>
#include <utility>

namespace ch::studio {

struct AssetHistoryEntry {
    QString label;
    AssetDocumentSnapshot before;
    AssetDocumentSnapshot after;
};

class AssetHistory final {
public:
    bool commit(const QString& label,
                const AssetDocumentSnapshot& before,
                const AssetDocumentSnapshot& after);
    bool undo(AssetDocument& document, QString* label = nullptr);
    bool redo(AssetDocument& document, QString* label = nullptr);
    void clear();

    [[nodiscard]] bool canUndo() const { return cursor_ > 0; }
    [[nodiscard]] bool canRedo() const { return cursor_ < entries_.size(); }
    [[nodiscard]] std::size_t size() const { return static_cast<std::size_t>(entries_.size()); }
    [[nodiscard]] int cursor() const { return cursor_; }

private:
    QVector<AssetHistoryEntry> entries_;
    int cursor_ = 0;
};

class AssetEditTransaction final {
public:
    AssetEditTransaction(AssetDocument& document, AssetHistory& history, QString label);

    AssetEditTransaction(const AssetEditTransaction&) = delete;
    AssetEditTransaction& operator=(const AssetEditTransaction&) = delete;

    bool commit();
    void rollback();
    [[nodiscard]] bool finished() const { return finished_; }

private:
    AssetDocument& document_;
    AssetHistory& history_;
    QString label_;
    AssetDocumentSnapshot before_;
    bool finished_ = false;
};

} // namespace ch::studio
