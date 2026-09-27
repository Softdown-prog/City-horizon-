#pragma once

#include "crosswalk_system.h"
#include "src/ch_core/contracts.h"

namespace crosswalk_runtime {

[[nodiscard]] inline CrosswalkManager& crosswalks() {
    static CrosswalkManager manager(ch::contracts::kMapMin, ch::contracts::kMapMax);
    return manager;
}

inline void clear() {
    crosswalks().clear();
}

}  // namespace crosswalk_runtime
