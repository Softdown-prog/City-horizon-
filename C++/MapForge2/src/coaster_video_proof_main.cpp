// Compatibility launcher for the established CH MapForge coaster video workflow.
// The workflow historically passes only <output-dir> <atlas>. Keep that stable,
// but render CH_MAPFORGE_COASTER_PROJECT_V1 with the promoted occupied V2 atlas.
#include <QCryptographicHash>
#include <QFileInfo>

#define main mapforge_coaster_project_legacy_main
#include "coaster_project_video_main.cpp"
#undef main

namespace {

bool validate_promoted_v2_atlas(const QString& atlasPath, const QImage& atlas) {
    const QSize expectedSize(
        ch::coaster::kCarPoseAtlasColumns * ch::coaster::kCarPoseFrameWidth,
        ch::coaster::kCarPoseAtlasRows * ch::coaster::kCarPoseFrameHeight);
    if (atlas.isNull() || atlas.size() != expectedSize) {
        std::fprintf(stderr, "invalid Flame V2 atlas size: got %dx%d expected %dx%d\n",
                     atlas.width(), atlas.height(), expectedSize.width(), expectedSize.height());
        return false;
    }

    QFile manifestFile(QString::fromUtf8(ch::coaster::kFlameCarPoseAtlasManifestPath));
    if (!manifestFile.open(QIODevice::ReadOnly)) {
        std::fprintf(stderr, "missing Flame V2 atlas manifest\n");
        return false;
    }
    const auto document = QJsonDocument::fromJson(manifestFile.readAll());
    if (!document.isObject()) return false;
    const auto manifest = document.object();
    if (manifest.value(QStringLiteral("contract")).toString() !=
            QString::fromUtf8(ch::coaster::kCoasterCarAtlasContract) ||
        manifest.value(QStringLiteral("poseContract")).toString() !=
            QString::fromUtf8(ch::coaster::kCoasterCarOrientationContract) ||
        manifest.value(QStringLiteral("frameCount")).toInt() != ch::coaster::kCarPoseFrameCount ||
        manifest.value(QStringLiteral("columns")).toInt() != ch::coaster::kCarPoseAtlasColumns ||
        manifest.value(QStringLiteral("rows")).toInt() != ch::coaster::kCarPoseAtlasRows ||
        manifest.value(QStringLiteral("frameWidth")).toInt() != ch::coaster::kCarPoseFrameWidth ||
        manifest.value(QStringLiteral("frameHeight")).toInt() != ch::coaster::kCarPoseFrameHeight ||
        manifest.value(QStringLiteral("spriteSheet")).toString() != QFileInfo(atlasPath).fileName()) {
        std::fprintf(stderr, "Flame V2 atlas manifest contract/layout mismatch\n");
        return false;
    }

    QFile atlasFile(atlasPath);
    if (!atlasFile.open(QIODevice::ReadOnly)) return false;
    const auto actualSha = QCryptographicHash::hash(
        atlasFile.readAll(), QCryptographicHash::Sha256).toHex();
    const auto expectedSha = manifest.value(QStringLiteral("spriteSheetSha256"))
                                 .toString().toLatin1().toLower();
    if (actualSha != expectedSha) {
        std::fprintf(stderr, "Flame V2 atlas SHA-256 does not match runtime manifest\n");
        return false;
    }
    return true;
}

bool validate_route_pose_coverage(
    const std::vector<ch::coaster::CenterlineSample>& samples) {
    for (const auto& sample : samples) {
        const auto pose = ch::coaster::select_car_pose_from_frame(
            sample.tangent_x, sample.tangent_y, sample.tangent_z,
            sample.up_x, sample.up_y, sample.up_z, 0);
        if (!pose.requires_extended_orientation) continue;
        std::fprintf(stderr,
                     "route requests pose outside promoted V2 coverage at %.3fm: pitch=%.3f roll=%.3f snappedPitch=%.3f snappedRoll=%.3f\n",
                     sample.distance_m, pose.sampled_pitch_degrees, pose.sampled_roll_degrees,
                     pose.snapped_pitch_degrees, pose.snapped_roll_degrees);
        return false;
    }
    return true;
}

bool write_capture_metadata(const QString& outputDir,
                            const ch::coaster::CenterlineRoute& route,
                            const int frameCount,
                            const double lapSeconds) {
    QJsonObject meta;
    meta.insert(QStringLiteral("contract"), QStringLiteral("CH_COASTER_FULL_LAP_CAPTURE_V1"));
    meta.insert(QStringLiteral("fullLap"), true);
    meta.insert(QStringLiteral("routeMeters"), route.length_m());
    meta.insert(QStringLiteral("trainSpeedMps"), kTrainSpeedMps);
    meta.insert(QStringLiteral("fps"), kFps);
    meta.insert(QStringLiteral("frameCount"), frameCount);
    meta.insert(QStringLiteral("lapSeconds"), lapSeconds);
    meta.insert(QStringLiteral("firstLeadDistanceMeters"), 0.0);
    meta.insert(QStringLiteral("lastLeadDistanceMeters"), 0.0);
    QFile file(QStringLiteral("%1/capture_meta.json").arg(outputDir));
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) return false;
    return file.write(QJsonDocument(meta).toJson(QJsonDocument::Indented)) > 0;
}

} // namespace

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    if (argc < 3 || argc > 4) {
        std::fprintf(stderr, "usage: MapForge2CoasterVideoProof <output-dir> <atlas> [mapforge-project]\n");
        return 2;
    }

    const QString outputDir = QString::fromLocal8Bit(argv[1]);
    const QString atlasPath = QString::fromLocal8Bit(argv[2]);
    const QString projectPath = argc == 4
        ? QString::fromLocal8Bit(argv[3])
        : QStringLiteral("C++/MapForge2/projects/coaster_flame_01.mapforge.json");
    QDir().mkpath(outputDir);

    QImage atlas(atlasPath);
    if (!validate_promoted_v2_atlas(atlasPath, atlas)) return 3;

    ch::coaster::CenterlineRoute route;
    QJsonObject project;
    if (!load_project_route(projectPath, route, project) || !route.valid()) {
        std::fprintf(stderr, "failed to construct CH_MAPFORGE_COASTER_PROJECT_V1\n");
        return 4;
    }
    const auto samples = sample_track(route);
    if (!validate_route_pose_coverage(samples)) return 6;
    const Projection projection = fit_projection(samples);

    // A proof is only valid after the lead car has traversed the entire closed
    // route and returned exactly to its starting distance.  The previous fixed
    // 360-frame/12-second capture could end mid-lap on larger coasters.
    const double lapSeconds = route.length_m() / kTrainSpeedMps;
    const int frameCount = std::max(2, static_cast<int>(std::ceil(lapSeconds * kFps)) + 1);
    if (!write_capture_metadata(outputDir, route, frameCount, lapSeconds)) return 7;

    for (int frame = 0; frame < frameCount; ++frame) {
        QImage image(kWidth, kHeight, QImage::Format_ARGB32_Premultiplied);
        image.fill(Qt::transparent);
        QPainter painter(&image);
        painter.setRenderHint(QPainter::Antialiasing, true);
        painter.setRenderHint(QPainter::SmoothPixmapTransform, true);
        draw_ground(painter, projection, project);
        draw_station(painter, projection);
        draw_supports(painter, projection, route);
        draw_track(painter, projection, samples);

        const double lapProgress = static_cast<double>(frame) /
                                   static_cast<double>(frameCount - 1);
        const double lead = ch::coaster::normalize_route_distance(
            lapProgress * route.length_m(), route.length_m(), true);
        draw_train(painter, projection, atlas, route, lead);
        painter.end();
        const QString path = QStringLiteral("%1/frame_%2.png")
                                 .arg(outputDir).arg(frame, 4, 10, QLatin1Char('0'));
        if (!image.save(path, "PNG")) return 5;
    }

    std::printf("CH_MAPFORGE_COASTER_PROJECT_V1 atlas=%s full_lap=1 frames=%d fps=%d lap_s=%.3f cars=%d route_m=%.3f points=%zu\n",
                ch::coaster::kCoasterCarAtlasContract, frameCount, kFps, lapSeconds,
                ch::coaster::kCoasterTrainCarCount, route.length_m(), route.point_count());
    return 0;
}
