#include "building_urban_integration_validator.h"

#include "building_footprint_model.h"

#include <QJsonArray>

#include <algorithm>
#include <cmath>

namespace ch::studio {
namespace {

bool isAccessModule(const BuildingFacadeModuleKind kind) {
    return kind == BuildingFacadeModuleKind::Door ||
           kind == BuildingFacadeModuleKind::DoubleDoor ||
           kind == BuildingFacadeModuleKind::GarageDoor;
}

float moduleProjectionTiles(const BuildingFacadeModuleKind kind) {
    switch (kind) {
        case BuildingFacadeModuleKind::Awning: return 0.26F;
        case BuildingFacadeModuleKind::Marquee: return 0.34F;
        case BuildingFacadeModuleKind::Balcony: return 0.30F;
        case BuildingFacadeModuleKind::Planter: return 0.08F;
        case BuildingFacadeModuleKind::Hvac: return 0.05F;
        default: return 0.0F;
    }
}

float facadeLengthTiles(const BuildingComposerSpec& spec, const BuildingStreetEdge edge) {
    switch (edge) {
        case BuildingStreetEdge::South:
        case BuildingStreetEdge::North:
            return static_cast<float>(std::max(1, spec.footprint_width_tiles));
        case BuildingStreetEdge::East:
        case BuildingStreetEdge::West:
            return static_cast<float>(std::max(1, spec.footprint_depth_tiles));
    }
    return 1.0F;
}

bool intervalsOverlap(const float a0, const float a1, const float b0, const float b1) {
    return std::max(a0, b0) <= std::min(a1, b1);
}

bool intervalsConnectThroughSidewalk(const float a0, const float a1,
                                     const float b0, const float b1) {
    constexpr float kAccessAlignmentTolerance = 0.12F;
    return intervalsOverlap(a0, a1, b0 - kAccessAlignmentTolerance, b1 + kAccessAlignmentTolerance);
}

bool socketTouchesOccupiedFrontage(const BuildingComposerSpec& spec,
                                   const BuildingFootprintMask& mask,
                                   const float socket_min,
                                   const float socket_max) {
    for (const QPoint& cell : mask.occupied_cells) {
        bool on_edge = false;
        float segment_min = 0.0F;
        float segment_max = 0.0F;
        switch (spec.road_socket_edge) {
            case BuildingStreetEdge::South:
                on_edge = cell.y() == mask.depth - 1;
                segment_min = static_cast<float>(cell.x()) / static_cast<float>(mask.width);
                segment_max = static_cast<float>(cell.x() + 1) / static_cast<float>(mask.width);
                break;
            case BuildingStreetEdge::North:
                on_edge = cell.y() == 0;
                segment_min = static_cast<float>(cell.x()) / static_cast<float>(mask.width);
                segment_max = static_cast<float>(cell.x() + 1) / static_cast<float>(mask.width);
                break;
            case BuildingStreetEdge::East:
                on_edge = cell.x() == mask.width - 1;
                segment_min = static_cast<float>(cell.y()) / static_cast<float>(mask.depth);
                segment_max = static_cast<float>(cell.y() + 1) / static_cast<float>(mask.depth);
                break;
            case BuildingStreetEdge::West:
                on_edge = cell.x() == 0;
                segment_min = static_cast<float>(cell.y()) / static_cast<float>(mask.depth);
                segment_max = static_cast<float>(cell.y() + 1) / static_cast<float>(mask.depth);
                break;
        }
        if (on_edge && intervalsOverlap(segment_min, segment_max, socket_min, socket_max)) return true;
    }
    return false;
}

QJsonArray stringArray(const QStringList& values) {
    QJsonArray result;
    for (const QString& value : values) result.append(value);
    return result;
}

} // namespace

QString BuildingUrbanIntegrationValidation::summary() const {
    if (valid) return QStringLiteral("PASS — sidewalk, road socket, occupied frontage, access alignment and urban clearances passed");
    return issues.isEmpty()
        ? QStringLiteral("FAIL — urban integration validation failed")
        : QStringLiteral("FAIL — %1").arg(issues.join(QStringLiteral("; ")));
}

QJsonObject BuildingUrbanIntegrationValidation::toJson() const {
    return QJsonObject{
        {"version", QStringLiteral("urban_integration_validation_2")},
        {"valid", valid},
        {"sidewalkContactValid", sidewalk_contact_valid},
        {"roadSocketValid", road_socket_valid},
        {"accessAlignmentValid", access_alignment_valid},
        {"facadeClearanceValid", facade_clearance_valid},
        {"visualOutsetValid", visual_outset_valid},
        {"issues", stringArray(issues)},
        {"details", details},
        {"summary", summary()},
    };
}

BuildingUrbanIntegrationValidation BuildingUrbanIntegrationValidator::validate(const BuildingComposerSpec& spec) {
    BuildingUrbanIntegrationValidation result;

    QString footprint_reason;
    const bool footprint_valid = BuildingFootprintModel::isValid(spec, &footprint_reason);
    const BuildingFootprintMask footprint = BuildingFootprintModel::mask(spec);

    result.sidewalk_contact_valid = spec.sidewalk_enabled && spec.sidewalk_depth_tiles > 0.001F && footprint_valid;
    if (!result.sidewalk_contact_valid)
        result.issues << (footprint_valid
            ? QStringLiteral("integrated sidewalk must connect to the authored footprint")
            : QStringLiteral("flexible footprint is invalid: %1").arg(footprint_reason));

    const float facade_length = facadeLengthTiles(spec, spec.road_socket_edge);
    const float socket_width = std::clamp(spec.road_socket_width_tiles, 0.0F, 2.0F);
    const float socket_half_normalized = facade_length > 0.0F ? (socket_width / facade_length) * 0.5F : 1.0F;
    const float socket_center = spec.road_socket_position;
    const float socket_min = socket_center - socket_half_normalized;
    const float socket_max = socket_center + socket_half_normalized;
    const bool occupied_frontage = !spec.road_socket_enabled ||
        socketTouchesOccupiedFrontage(spec, footprint, socket_min, socket_max);

    result.road_socket_valid = !spec.road_socket_enabled ||
        (socket_width >= 0.10F && socket_center >= 0.0F && socket_center <= 1.0F &&
         socket_min >= -0.001F && socket_max <= 1.001F && occupied_frontage);
    if (!result.road_socket_valid) {
        if (!occupied_frontage)
            result.issues << QStringLiteral("road socket must overlap an occupied cell on the selected footprint edge");
        else
            result.issues << QStringLiteral("road socket must fit completely inside its authored facade");
    }

    bool access_found = !spec.road_socket_enabled;
    if (spec.road_socket_enabled) {
        if (spec.facade_editor_enabled) {
            for (const auto& module : spec.facade_modules) {
                if (!module.enabled || module.floor_index != 0 || module.edge != spec.road_socket_edge || !isAccessModule(module.kind))
                    continue;
                const float module_min = module.position - module.width * 0.5F;
                const float module_max = module.position + module.width * 0.5F;
                if (intervalsConnectThroughSidewalk(module_min, module_max, socket_min, socket_max)) {
                    access_found = true;
                    break;
                }
            }
        } else {
            access_found = spec.road_socket_edge == BuildingStreetEdge::South && spec.south_door;
        }
    }
    result.access_alignment_valid = access_found;
    if (!result.access_alignment_valid)
        result.issues << QStringLiteral("ground-floor entrance/garage must align with the road socket on the same facade");

    bool facade_clearance = true;
    float largest_projection = 0.0F;
    for (const auto& module : spec.facade_modules) {
        if (!module.enabled) continue;
        const float min_pos = module.position - module.width * 0.5F;
        const float max_pos = module.position + module.width * 0.5F;
        if (min_pos < -0.001F || max_pos > 1.001F || module.floor_index < 0 || module.floor_index >= std::max(1, spec.floor_count)) {
            facade_clearance = false;
            break;
        }
        if (module.floor_index == 0 && module.edge == spec.road_socket_edge)
            largest_projection = std::max(largest_projection, moduleProjectionTiles(module.kind));
    }
    result.facade_clearance_valid = facade_clearance;
    if (!result.facade_clearance_valid)
        result.issues << QStringLiteral("facade module extends outside its legal facade/floor bounds");

    const float allowed_ground_projection = std::max(0.0F, spec.sidewalk_depth_tiles) + 0.08F;
    const bool projection_ok = largest_projection <= allowed_ground_projection + 0.001F;
    const bool roof_outset_ok = spec.roof_overhang >= 0.0F && spec.roof_overhang <= 0.24F;
    result.visual_outset_valid = projection_ok && roof_outset_ok;
    if (!projection_ok)
        result.issues << QStringLiteral("ground-floor facade projection would intrude into the roadway clearance zone");
    if (!roof_outset_ok)
        result.issues << QStringLiteral("roof overhang exceeds the authored visual-outset allowance");

    result.valid = result.sidewalk_contact_valid && result.road_socket_valid &&
                   result.access_alignment_valid && result.facade_clearance_valid &&
                   result.visual_outset_valid;

    result.details = QJsonObject{
        {"roadSocketEdge", BuildingComposer::streetEdgeName(spec.road_socket_edge)},
        {"roadSocketType", BuildingComposer::roadSocketTypeName(spec.road_socket_type)},
        {"facadeLengthTiles", static_cast<double>(facade_length)},
        {"socketPosition", static_cast<double>(socket_center)},
        {"socketWidthTiles", static_cast<double>(socket_width)},
        {"socketNormalizedMin", static_cast<double>(socket_min)},
        {"socketNormalizedMax", static_cast<double>(socket_max)},
        {"socketTouchesOccupiedFootprintFrontage", occupied_frontage},
        {"accessAlignmentToleranceNormalized", 0.12},
        {"sidewalkDepthTiles", static_cast<double>(spec.sidewalk_depth_tiles)},
        {"footprint", BuildingFootprintModel::manifest(spec)},
        {"largestGroundProjectionTiles", static_cast<double>(largest_projection)},
        {"allowedGroundProjectionTiles", static_cast<double>(allowed_ground_projection)},
        {"roofOverhangTiles", static_cast<double>(spec.roof_overhang)},
        {"runtimePlacementRequirements", QJsonArray{
            QStringLiteral("matching_road_exists_on_rotated_socket_edge"),
            QStringLiteral("road_type_is_compatible"),
            QStringLiteral("occupied_footprint_cells_do_not_overlap_road_or_other_buildings"),
            QStringLiteral("sidewalk_bridges_occupied_frontage_to_road_without_grass_gap"),
            QStringLiteral("entrance_or_garage_faces_matching_road_socket"),
            QStringLiteral("setback_reservation_remains_inside_owned_lot")
        }},
    };

    return result;
}

} // namespace ch::studio
