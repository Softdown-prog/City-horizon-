#ifndef CITY_HORIZON_CH_CORE_VALIDATION_H
#define CITY_HORIZON_CH_CORE_VALIDATION_H

#include "src/ch_core/map_document.h"
#include <vector>
#include <string>

namespace ch {

struct MapValidationReport {
    bool valid = true;
    std::vector<std::string> errors;
    std::vector<std::string> warnings;
    std::vector<std::string> legacy_debt;
};

[[nodiscard]] MapValidationReport validate_map_document(const MapDocument& document);

} // namespace ch

#endif // CITY_HORIZON_CH_CORE_VALIDATION_H
