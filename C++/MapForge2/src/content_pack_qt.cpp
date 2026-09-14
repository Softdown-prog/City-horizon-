#include "content_pack_qt.h"

#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>

namespace ch::studio {

namespace {

std::string stringField(const QJsonObject& object, const char* key) {
    return object.value(QString::fromUtf8(key)).toString().toStdString();
}

} // namespace

ContentPackLoadResult loadContentPackFromJsonFile(const QString& path) {
    ContentPackLoadResult result;

    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        result.error = QString("Unable to open content pack: %1").arg(path);
        return result;
    }

    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(file.readAll(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        result.error = QString("Invalid JSON: %1").arg(parseError.errorString());
        return result;
    }

    const QJsonObject root = document.object();
    ContentPackage package;
    package.contract = stringField(root, "contract");
    package.package_id = stringField(root, "packageId");
    package.display_name = stringField(root, "displayName");
    package.version = root.value("version").toInt(1);

    const QJsonValue definitionsValue = root.value("definitions");
    if (!definitionsValue.isArray()) {
        result.error = "Content pack must contain a definitions array.";
        return result;
    }

    const QJsonArray definitions = definitionsValue.toArray();
    package.definitions.reserve(static_cast<std::size_t>(definitions.size()));

    for (qsizetype index = 0; index < definitions.size(); ++index) {
        const QJsonValue value = definitions.at(index);
        if (!value.isObject()) {
            result.error = QString("definitions[%1] must be an object.").arg(index);
            return result;
        }

        const QJsonObject object = value.toObject();
        ContentDefinition definition;
        definition.id = stringField(object, "id");
        definition.display_name = stringField(object, "displayName");
        definition.behavior_id = stringField(object, "behaviorId");
        definition.visual_id = stringField(object, "visualId");
        definition.source_path = stringField(object, "sourcePath");

        const std::string kindText = stringField(object, "kind");
        definition.kind = contentKindFromString(kindText).value_or(ContentKind::Unknown);

        const QJsonValue dependenciesValue = object.value("dependencies");
        if (!dependenciesValue.isUndefined()) {
            if (!dependenciesValue.isArray()) {
                result.error = QString("definitions[%1].dependencies must be an array.").arg(index);
                return result;
            }
            const QJsonArray dependencies = dependenciesValue.toArray();
            definition.dependencies.reserve(static_cast<std::size_t>(dependencies.size()));
            for (const QJsonValue dependency : dependencies) {
                if (!dependency.isString()) {
                    result.error = QString("definitions[%1].dependencies must contain only strings.").arg(index);
                    return result;
                }
                definition.dependencies.push_back(dependency.toString().toStdString());
            }
        }

        package.definitions.push_back(std::move(definition));
    }

    result.success = true;
    result.package = std::move(package);
    return result;
}

} // namespace ch::studio
