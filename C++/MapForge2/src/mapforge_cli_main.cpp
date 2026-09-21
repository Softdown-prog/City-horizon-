#include "map_capture_service.h"
#include "src/ch_core/map_document.h"
#include "src/ch_core/validation.h"

#include <QCoreApplication>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>

#include <iostream>
#include <string>

namespace {

QJsonArray toJsonArray(const std::vector<std::string>& values) {
    QJsonArray array;
    for (const std::string& value : values) array.append(QString::fromStdString(value));
    return array;
}

QJsonObject inspectDocument(const ch::MapDocument& document, const QString& path) {
    QJsonObject result;
    result.insert(QStringLiteral("contract"), QStringLiteral("MAPFORGE_CLI_RESULT_V1"));
    result.insert(QStringLiteral("command"), QStringLiteral("inspect"));
    result.insert(QStringLiteral("path"), QFileInfo(path).absoluteFilePath());
    result.insert(QStringLiteral("terrainTiles"), static_cast<qint64>(document.terrain_tiles().size()));
    result.insert(QStringLiteral("buildings"), static_cast<qint64>(document.buildings().size()));
    result.insert(QStringLiteral("roads"), static_cast<qint64>(document.roads().size()));
    result.insert(QStringLiteral("ok"), true);
    return result;
}

QJsonObject validateDocument(const ch::MapDocument& document, const QString& path) {
    const ch::MapValidationReport report = ch::validate_map_document(document);
    QJsonObject result;
    result.insert(QStringLiteral("contract"), QStringLiteral("MAPFORGE_CLI_RESULT_V1"));
    result.insert(QStringLiteral("command"), QStringLiteral("validate"));
    result.insert(QStringLiteral("path"), QFileInfo(path).absoluteFilePath());
    result.insert(QStringLiteral("ok"), report.valid);
    result.insert(QStringLiteral("errors"), toJsonArray(report.errors));
    result.insert(QStringLiteral("warnings"), toJsonArray(report.warnings));
    result.insert(QStringLiteral("legacyDebt"), toJsonArray(report.legacy_debt));
    return result;
}

void printJson(const QJsonObject& object) {
    const QByteArray json = QJsonDocument(object).toJson(QJsonDocument::Compact);
    std::cout << json.constData() << '\n';
}

void printUsage() {
    std::cerr << "MapForge2CLI usage:\n"
              << "  MapForge2CLI inspect <map.json>\n"
              << "  MapForge2CLI validate <map.json>\n"
              << "  MapForge2CLI capture <output.png> <candidate.png> <capture_request.json>\n";
}

} // namespace

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    const QStringList args = app.arguments();
    if (args.size() < 2) {
        printUsage();
        return 2;
    }

    const QString command = args.at(1).trimmed().toLower();

    if (command == QStringLiteral("capture")) {
        if (args.size() != 5) {
            printUsage();
            return 2;
        }

        const ch::studio::MapCaptureResult capture = ch::studio::runMapCapture(args.at(2), args.at(3), args.at(4));
        QJsonObject result;
        result.insert(QStringLiteral("contract"), QStringLiteral("MAPFORGE_CLI_RESULT_V1"));
        result.insert(QStringLiteral("command"), QStringLiteral("capture"));
        result.insert(QStringLiteral("ok"), capture.ok);
        result.insert(QStringLiteral("output"), QFileInfo(args.at(2)).absoluteFilePath());
        result.insert(QStringLiteral("candidate"), QFileInfo(args.at(3)).absoluteFilePath());
        result.insert(QStringLiteral("request"), QFileInfo(args.at(4)).absoluteFilePath());
        if (!capture.ok) result.insert(QStringLiteral("error"), capture.error);
        printJson(result);
        return capture.ok ? 0 : capture.exit_code;
    }

    if ((command == QStringLiteral("inspect") || command == QStringLiteral("validate")) && args.size() == 3) {
        const QString path = args.at(2);
        const auto document = ch::MapDocument::load_from_file(path.toStdString());
        if (!document) {
            QJsonObject result;
            result.insert(QStringLiteral("contract"), QStringLiteral("MAPFORGE_CLI_RESULT_V1"));
            result.insert(QStringLiteral("command"), command);
            result.insert(QStringLiteral("path"), QFileInfo(path).absoluteFilePath());
            result.insert(QStringLiteral("ok"), false);
            result.insert(QStringLiteral("error"), QStringLiteral("unable to load map document"));
            printJson(result);
            return 4;
        }

        if (command == QStringLiteral("inspect")) {
            printJson(inspectDocument(*document, path));
            return 0;
        }

        const QJsonObject result = validateDocument(*document, path);
        printJson(result);
        return result.value(QStringLiteral("ok")).toBool() ? 0 : 5;
    }

    printUsage();
    return 2;
}
