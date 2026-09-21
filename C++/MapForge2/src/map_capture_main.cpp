#include "map_capture_service.h"

#include <QCoreApplication>
#include <QStringList>

#include <iostream>

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    const QStringList args = app.arguments();
    if (args.size() != 4) {
        std::cerr << "usage: MapForge2MapCapture <output.png> <candidate.png> <capture_request.json>\n";
        return 2;
    }

    const ch::studio::MapCaptureResult result = ch::studio::runMapCapture(args.at(1), args.at(2), args.at(3));
    if (!result.ok) {
        std::cerr << result.error.toStdString() << '\n';
        return result.exit_code;
    }

    std::cout << "mapForgeGenericDeterministicCapture: PASS\n";
    std::cout << "output=" << args.at(1).toStdString() << '\n';
    std::cout << "candidate=" << args.at(2).toStdString() << '\n';
    std::cout << "request=" << args.at(3).toStdString() << '\n';
    return 0;
}
