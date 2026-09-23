#include "asset_project_editor_window.h"
#include "sprite_workshop_launcher.h"

#include <QApplication>
#include <QFormLayout>
#include <QMessageBox>
#include <QPushButton>
#include <QTabWidget>

namespace {

void installSpriteWorkshopButton(ch::studio::AssetProjectEditorWindow& window) {
    for (QTabWidget* tabs : window.findChildren<QTabWidget*>()) {
        for (int index = 0; index < tabs->count(); ++index) {
            if (tabs->tabText(index) != QStringLiteral("4 Directions")) continue;

            QWidget* tab = tabs->widget(index);
            auto* form = qobject_cast<QFormLayout*>(tab != nullptr ? tab->layout() : nullptr);
            if (form == nullptr) return;

            auto* button = new QPushButton(QStringLiteral("Edit selected direction in Sprite Workshop"), tab);
            button->setObjectName(QStringLiteral("edit_selected_direction_in_sprite_workshop"));
            button->setToolTip(QStringLiteral("Open the currently selected SOUTH/EAST/WEST/NORTH sprite with its .chasset anchor, animation and activity overlay metadata."));
            form->addRow(button);

            QObject::connect(button, &QPushButton::clicked, &window, [&window]() {
                QString reason;
                if (!ch::studio::launchSpriteWorkshop(window.document(), window.currentPath(), window.previewDirection(), &reason)) {
                    QMessageBox::warning(&window, QStringLiteral("Sprite Workshop"), reason);
                }
            });
            return;
        }
    }
}

} // namespace

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("City Horizon Asset Editor"));
    app.setOrganizationName(QStringLiteral("City Horizon"));

    ch::studio::AssetProjectEditorWindow window;
    installSpriteWorkshopButton(window);
    window.show();
    return app.exec();
}
