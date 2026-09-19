#include "building_composer_widget.h"

#include <QApplication>
#include <QCoreApplication>
#include <QEvent>
#include <QHBoxLayout>
#include <QPushButton>
#include <QVBoxLayout>

#include <algorithm>

namespace ch::studio {
namespace {

class AssetBrowserUiExtension final : public QObject {
public:
    explicit AssetBrowserUiExtension(QObject* parent = nullptr) : QObject(parent) {}

protected:
    bool eventFilter(QObject* watched, QEvent* event) override {
        if (event->type() != QEvent::Polish && event->type() != QEvent::Show) return false;
        auto* composer = dynamic_cast<BuildingComposerWidget*>(watched);
        if (!composer || composer->property("ch_asset_browser_attached").toBool()) return false;
        auto* layout = qobject_cast<QVBoxLayout*>(composer->layout());
        if (!layout) return false;

        composer->setProperty("ch_asset_browser_attached", true);
        auto* row = new QHBoxLayout();
        auto* browser_button = new QPushButton(QStringLiteral("Asset Browser / Library…"), composer);
        browser_button->setToolTip(QStringLiteral(
            "Index exported building packages, filter them, inspect validation metadata and reopen authoring snapshots for editing."));
        row->addWidget(browser_button);
        row->addStretch(1);
        layout->insertLayout(std::max(0, layout->count() - 1), row);
        QObject::connect(browser_button, &QPushButton::clicked, composer, [composer]() {
            composer->openAssetBrowser();
        });
        return false;
    }
};

} // namespace

void installAssetBrowserUiExtension() {
    if (qApp) qApp->installEventFilter(new AssetBrowserUiExtension(qApp));
}

} // namespace ch::studio

Q_COREAPP_STARTUP_FUNCTION(ch::studio::installAssetBrowserUiExtension)
