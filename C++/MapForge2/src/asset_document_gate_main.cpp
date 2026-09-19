#include "asset_document.h"
#include "asset_history.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QJsonDocument>

using namespace ch::studio;

namespace {

bool add(AssetDocument& document, const AssetLayer& layer, QString* reason) {
    return document.addLayer(layer, -1, reason);
}

} // namespace

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    const QString output_directory = argc > 1
        ? QString::fromLocal8Bit(argv[1])
        : QDir::current().filePath(QStringLiteral("asset_document_tests"));

    if (!QDir().mkpath(output_directory)) return 2;
    QDir output(output_directory);

    QString reason;
    AssetDocument document;
    document.newDocument(QStringLiteral("asset.foundation.gate"),
                         QStringLiteral("Asset Editor Foundation Gate"),
                         QSize(640, 480));
    document.setCategory(QStringLiteral("amusement_ride"));
    document.setMetadata(QJsonObject{
        {"authoringMode", QStringLiteral("deterministic")},
        {"aiDirectPixelOutput", false},
        {"rendererOwnsFinalOutput", true},
    });

    AssetLayer root;
    root.id = QStringLiteral("root.art");
    root.name = QStringLiteral("Artwork");
    root.type = AssetLayerType::Group;
    if (!add(document, root, &reason)) return 3;

    AssetLayer raster;
    raster.id = QStringLiteral("body.raster");
    raster.name = QStringLiteral("Raster body");
    raster.type = AssetLayerType::Raster;
    raster.parent_id = root.id;
    raster.source_path = QStringLiteral("assets/amusement/carousel/classic/platform.png.b64");
    if (!add(document, raster, &reason)) return 4;

    AssetLayer vector;
    vector.id = QStringLiteral("trim.vector");
    vector.name = QStringLiteral("Vector trim");
    vector.type = AssetLayerType::Vector;
    vector.parent_id = root.id;
    vector.payload = QJsonObject{
        {"primitive", QStringLiteral("rounded_rect")},
        {"fill", QStringLiteral("#b4534c")},
        {"stroke", QStringLiteral("#433b37")},
    };
    if (!add(document, vector, &reason)) return 5;

    AssetLayer mask;
    mask.id = QStringLiteral("body.mask");
    mask.name = QStringLiteral("Body mask");
    mask.type = AssetLayerType::Mask;
    mask.parent_id = raster.id;
    mask.payload = QJsonObject{{"mode", QStringLiteral("alpha")}};
    if (!add(document, mask, &reason)) return 6;

    AssetLayer adjustment;
    adjustment.id = QStringLiteral("grade.adjustment");
    adjustment.name = QStringLiteral("Classic Tycoon grade");
    adjustment.type = AssetLayerType::Adjustment;
    adjustment.parent_id = root.id;
    adjustment.payload = QJsonObject{
        {"operation", QStringLiteral("levels")},
        {"contrast", 1.08},
        {"saturation", 0.94},
    };
    if (!add(document, adjustment, &reason)) return 7;

    AssetLayer reference;
    reference.id = QStringLiteral("design.reference");
    reference.name = QStringLiteral("Design reference");
    reference.type = AssetLayerType::Reference;
    reference.visible = false;
    reference.source_path = QStringLiteral("references/not_exported.png");
    if (!add(document, reference, &reason)) return 8;

    AssetLayer object;
    object.id = QStringLiteral("scene.object");
    object.name = QStringLiteral("2.5D object placeholder");
    object.type = AssetLayerType::Object2_5D;
    object.parent_id = root.id;
    object.payload = QJsonObject{
        {"worldX", 1.25},
        {"worldY", -0.5},
        {"height", 0.75},
        {"cameraContract", QStringLiteral("CH_CAMERA_V1")},
    };
    if (!add(document, object, &reason)) return 9;

    if (!document.validate(&reason)) return 10;

    AssetHistory history;
    const AssetTransform2D original_transform = document.layer(QStringLiteral("scene.object"))->transform;
    {
        AssetEditTransaction transaction(document, history, QStringLiteral("Move 2.5D object"));
        AssetTransform2D moved = original_transform;
        moved.position_px = QPointF(42.0, -18.0);
        moved.rotation_degrees = 12.5;
        if (!document.setLayerTransform(QStringLiteral("scene.object"), moved, &reason)) return 11;
        if (!transaction.commit()) return 12;
    }

    const AssetDocumentSnapshot authored_snapshot = document.snapshot();
    const QString asset_path = output.filePath(QStringLiteral("foundation_sample.chasset"));
    if (!document.save(asset_path, &reason)) return 13;

    AssetDocument loaded;
    if (!AssetDocument::load(asset_path, &loaded, &reason)) return 14;
    const bool round_trip_exact = loaded.snapshot() == authored_snapshot;

    QString undo_label;
    const bool undo_called = history.undo(document, &undo_label);
    const AssetLayer* undone_object = document.layer(QStringLiteral("scene.object"));
    const bool undo_pass = undo_called && undone_object
        && undone_object->transform == original_transform
        && undo_label == QStringLiteral("Move 2.5D object");

    QString redo_label;
    const bool redo_called = history.redo(document, &redo_label);
    const AssetLayer* redone_object = document.layer(QStringLiteral("scene.object"));
    const bool redo_pass = redo_called && redone_object
        && redone_object->transform == loaded.layer(QStringLiteral("scene.object"))->transform
        && redo_label == QStringLiteral("Move 2.5D object");

    const bool contract_pass = loaded.cameraContract() == QLatin1String("CH_CAMERA_V1")
        && loaded.stylePreset() == QLatin1String("CH_CLASSIC_TYCOON_STYLE_V1")
        && loaded.layers().size() == 7;
    const bool pass = round_trip_exact && undo_pass && redo_pass && contract_pass;

    const QJsonObject report{
        {"gate", QStringLiteral("asset_document_foundation_1")},
        {"contract", QString::fromLatin1(AssetDocument::kContractVersion)},
        {"pass", pass},
        {"roundTripExact", round_trip_exact},
        {"undoPass", undo_pass},
        {"redoPass", redo_pass},
        {"contractPass", contract_pass},
        {"cameraContract", loaded.cameraContract()},
        {"stylePreset", loaded.stylePreset()},
        {"layerCount", loaded.layers().size()},
        {"historyEntries", static_cast<int>(history.size())},
        {"aiWritesDocumentNotFinalPixels", true},
    };

    QFile report_file(output.filePath(QStringLiteral("asset_document_gate.json")));
    if (!report_file.open(QIODevice::WriteOnly | QIODevice::Truncate)) return 15;
    report_file.write(QJsonDocument(report).toJson(QJsonDocument::Indented));
    report_file.close();

    return pass ? 0 : 16;
}
