#include "asset_project_editor_window.h"

#include <QApplication>

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("City Horizon Asset Editor"));
    app.setOrganizationName(QStringLiteral("City Horizon"));

    ch::studio::AssetProjectEditorWindow window;
    window.show();
    return app.exec();
}
