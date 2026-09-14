#include "main_window.h"

#include <QApplication>
#include <QCoreApplication>
#include <QString>

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    QCoreApplication::setApplicationName("MapForge2");
    QCoreApplication::setOrganizationName("City Horizon");

    ch::editor::MainWindow window;
    if (argc > 1) {
        window.loadScenario(QString::fromLocal8Bit(argv[1]));
    }
    window.show();
    return app.exec();
}
