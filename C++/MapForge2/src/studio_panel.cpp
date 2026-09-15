#include "studio_panel.h"

#include "content_pack_qt.h"

#include <QFileDialog>
#include <QHBoxLayout>
#include <QLabel>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QVBoxLayout>

namespace ch::studio {

StudioPanel::StudioPanel(QWidget* parent)
    : QWidget(parent) {
    auto* layout = new QVBoxLayout(this);

    auto* intro = new QLabel(
        "City Horizon Studio foundation\n\n"
        "Content is authored as deterministic data. C++ defines capabilities; content packs combine them. "
        "This first layer validates CH_CONTENT_PACK_V1 IDs, kinds, dependencies and catalog collisions before any runtime integration.",
        this);
    intro->setWordWrap(true);
    layout->addWidget(intro);

    auto* buttons = new QHBoxLayout();
    auto* loadButton = new QPushButton("Load Content Pack…", this);
    auto* clearButton = new QPushButton("Clear Catalog", this);
    buttons->addWidget(loadButton);
    buttons->addWidget(clearButton);
    buttons->addStretch(1);
    layout->addLayout(buttons);

    summary_ = new QLabel(this);
    layout->addWidget(summary_);

    report_ = new QPlainTextEdit(this);
    report_->setReadOnly(true);
    report_->setPlaceholderText("Validation diagnostics will appear here.");
    layout->addWidget(report_, 1);

    connect(loadButton, &QPushButton::clicked, this, [this]() { loadPack(); });
    connect(clearButton, &QPushButton::clicked, this, [this]() { clearCatalog(); });

    refreshSummary();
}

void StudioPanel::loadPack() {
    const QString path = QFileDialog::getOpenFileName(
        this,
        "Open City Horizon content pack",
        {},
        "City Horizon Content Pack (*.json);;All files (*.*)");
    if (path.isEmpty()) return;

    const ContentPackLoadResult loaded = loadContentPackFromJsonFile(path);
    report_->appendPlainText(QString("\n=== %1 ===").arg(path));

    if (!loaded.success) {
        report_->appendPlainText(QString("[ERROR] JSON_LOAD_FAILED: %1").arg(loaded.error));
        return;
    }

    const ValidationReport packageReport = validatePackage(loaded.package);
    appendReport("Package validation", packageReport);
    if (!packageReport.ok()) return;

    const ValidationReport registrationReport = catalog_.registerPackage(loaded.package);
    appendReport("Catalog registration", registrationReport);
    if (!registrationReport.ok()) return;

    const ValidationReport referenceReport = catalog_.validateReferences();
    appendReport("Catalog dependency validation", referenceReport);
    refreshSummary();

    report_->appendPlainText(QString("Loaded %1 (%2 definitions).")
                                 .arg(QString::fromStdString(loaded.package.package_id))
                                 .arg(loaded.package.definitions.size()));
}

void StudioPanel::clearCatalog() {
    catalog_.clear();
    report_->clear();
    refreshSummary();
}

void StudioPanel::appendReport(const QString& title, const ValidationReport& report) {
    report_->appendPlainText(QString("-- %1: %2 error(s), %3 warning(s)")
                                 .arg(title)
                                 .arg(report.errorCount())
                                 .arg(report.warningCount()));

    if (report.issues.empty()) {
        report_->appendPlainText("[OK] No validation issues.");
        return;
    }

    for (const auto& issue : report.issues) {
        QString line = QString("[%1] %2")
                           .arg(QString::fromUtf8(toString(issue.severity).data(), static_cast<qsizetype>(toString(issue.severity).size())))
                           .arg(QString::fromStdString(issue.code));
        if (!issue.content_id.empty()) {
            line += QString(" (%1)").arg(QString::fromStdString(issue.content_id));
        }
        line += QString(": %1").arg(QString::fromStdString(issue.message));
        report_->appendPlainText(line);
    }
}

void StudioPanel::refreshSummary() {
    summary_->setText(QString("Contract: CH_CONTENT_PACK_V1   |   Registered definitions: %1")
                          .arg(catalog_.size()));
}

} // namespace ch::studio
