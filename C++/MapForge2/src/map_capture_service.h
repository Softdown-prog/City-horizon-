#ifndef CITY_HORIZON_MAPFORGE2_MAP_CAPTURE_SERVICE_H
#define CITY_HORIZON_MAPFORGE2_MAP_CAPTURE_SERVICE_H

#include <QString>

namespace ch::studio {

struct MapCaptureResult {
    bool ok = false;
    int exit_code = 1;
    QString error;
};

[[nodiscard]] MapCaptureResult runMapCapture(const QString& output_path,
                                             const QString& candidate_path,
                                             const QString& request_path);

} // namespace ch::studio

#endif // CITY_HORIZON_MAPFORGE2_MAP_CAPTURE_SERVICE_H
