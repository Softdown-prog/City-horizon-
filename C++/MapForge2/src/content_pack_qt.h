#pragma once

#include "studio_content.h"

#include <QString>

namespace ch::studio {

struct ContentPackLoadResult {
    bool success = false;
    ContentPackage package;
    QString error;
};

[[nodiscard]] ContentPackLoadResult loadContentPackFromJsonFile(const QString& path);

} // namespace ch::studio
