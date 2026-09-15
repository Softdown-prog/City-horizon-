#pragma once

#include "studio_content.h"

#include <QWidget>

class QLabel;
class QPlainTextEdit;

namespace ch::studio {

class StudioPanel final : public QWidget {
public:
    explicit StudioPanel(QWidget* parent = nullptr);

private:
    void loadPack();
    void clearCatalog();
    void appendReport(const QString& title, const ValidationReport& report);
    void refreshSummary();

    ContentCatalog catalog_;
    QLabel* summary_ = nullptr;
    QPlainTextEdit* report_ = nullptr;
};

} // namespace ch::studio
