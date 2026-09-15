#include "studio_content.h"

#include <algorithm>
#include <cctype>
#include <unordered_set>

namespace ch::studio {

namespace {

void addIssue(ValidationReport& report,
              const ValidationSeverity severity,
              std::string code,
              std::string message,
              std::string content_id = {}) {
    report.issues.push_back({severity, std::move(code), std::move(message), std::move(content_id)});
}

bool requiresBehavior(const ContentKind kind) {
    return kind == ContentKind::Building || kind == ContentKind::Actor || kind == ContentKind::Vehicle;
}

} // namespace

bool ValidationReport::ok() const {
    return std::none_of(issues.begin(), issues.end(), [](const ValidationIssue& issue) {
        return issue.severity == ValidationSeverity::Error;
    });
}

std::size_t ValidationReport::errorCount() const {
    return static_cast<std::size_t>(std::count_if(issues.begin(), issues.end(), [](const ValidationIssue& issue) {
        return issue.severity == ValidationSeverity::Error;
    }));
}

std::size_t ValidationReport::warningCount() const {
    return static_cast<std::size_t>(std::count_if(issues.begin(), issues.end(), [](const ValidationIssue& issue) {
        return issue.severity == ValidationSeverity::Warning;
    }));
}

bool isValidContentId(const std::string_view id) {
    if (id.empty()) return false;
    if (!(std::islower(static_cast<unsigned char>(id.front())) || std::isdigit(static_cast<unsigned char>(id.front())))) {
        return false;
    }

    for (const char ch : id) {
        const auto value = static_cast<unsigned char>(ch);
        const bool valid = std::islower(value) || std::isdigit(value) || ch == '.' || ch == '_' || ch == '-';
        if (!valid) return false;
    }
    return true;
}

std::string_view toString(const ContentKind kind) {
    switch (kind) {
    case ContentKind::Terrain: return "terrain";
    case ContentKind::Road: return "road";
    case ContentKind::Sidewalk: return "sidewalk";
    case ContentKind::Building: return "building";
    case ContentKind::Decoration: return "decoration";
    case ContentKind::Actor: return "actor";
    case ContentKind::Vehicle: return "vehicle";
    case ContentKind::UiLayout: return "ui_layout";
    case ContentKind::Scenario: return "scenario";
    case ContentKind::Unknown: break;
    }
    return "unknown";
}

std::string_view toString(const ValidationSeverity severity) {
    switch (severity) {
    case ValidationSeverity::Info: return "INFO";
    case ValidationSeverity::Warning: return "WARNING";
    case ValidationSeverity::Error: return "ERROR";
    }
    return "ERROR";
}

std::optional<ContentKind> contentKindFromString(const std::string_view value) {
    if (value == "terrain") return ContentKind::Terrain;
    if (value == "road") return ContentKind::Road;
    if (value == "sidewalk") return ContentKind::Sidewalk;
    if (value == "building") return ContentKind::Building;
    if (value == "decoration") return ContentKind::Decoration;
    if (value == "actor") return ContentKind::Actor;
    if (value == "vehicle") return ContentKind::Vehicle;
    if (value == "ui_layout") return ContentKind::UiLayout;
    if (value == "scenario") return ContentKind::Scenario;
    return std::nullopt;
}

ValidationReport validatePackage(const ContentPackage& package) {
    ValidationReport report;

    if (package.contract != kContentPackContract) {
        addIssue(report, ValidationSeverity::Error, "CONTRACT_MISMATCH",
                 "Content pack contract must be CH_CONTENT_PACK_V1.");
    }

    if (!isValidContentId(package.package_id)) {
        addIssue(report, ValidationSeverity::Error, "INVALID_PACKAGE_ID",
                 "Package ID must use lowercase letters, digits, '.', '_' or '-'.");
    }

    if (package.display_name.empty()) {
        addIssue(report, ValidationSeverity::Warning, "MISSING_PACKAGE_DISPLAY_NAME",
                 "Package has no display name.");
    }

    if (package.version < 1) {
        addIssue(report, ValidationSeverity::Error, "INVALID_PACKAGE_VERSION",
                 "Package version must be at least 1.");
    }

    std::unordered_set<std::string> ids;
    for (const auto& definition : package.definitions) {
        if (!isValidContentId(definition.id)) {
            addIssue(report, ValidationSeverity::Error, "INVALID_CONTENT_ID",
                     "Content ID must use lowercase letters, digits, '.', '_' or '-'.", definition.id);
        }

        if (!ids.insert(definition.id).second) {
            addIssue(report, ValidationSeverity::Error, "DUPLICATE_CONTENT_ID",
                     "Content ID appears more than once in the same package.", definition.id);
        }

        if (definition.kind == ContentKind::Unknown) {
            addIssue(report, ValidationSeverity::Error, "UNKNOWN_CONTENT_KIND",
                     "Content definition has an unknown kind.", definition.id);
        }

        if (definition.display_name.empty()) {
            addIssue(report, ValidationSeverity::Warning, "MISSING_DISPLAY_NAME",
                     "Content definition has no display name.", definition.id);
        }

        if (requiresBehavior(definition.kind) && definition.behavior_id.empty()) {
            addIssue(report, ValidationSeverity::Warning, "MISSING_BEHAVIOR",
                     "This content kind normally requires a behavior ID.", definition.id);
        }

        if (definition.visual_id.empty() && definition.kind != ContentKind::Scenario) {
            addIssue(report, ValidationSeverity::Warning, "MISSING_VISUAL",
                     "Content definition has no visual ID yet.", definition.id);
        }

        std::unordered_set<std::string> dependencies;
        for (const auto& dependency : definition.dependencies) {
            if (!isValidContentId(dependency)) {
                addIssue(report, ValidationSeverity::Error, "INVALID_DEPENDENCY_ID",
                         "Dependency ID is malformed.", definition.id);
            }
            if (!dependencies.insert(dependency).second) {
                addIssue(report, ValidationSeverity::Warning, "DUPLICATE_DEPENDENCY",
                         "Dependency is listed more than once.", definition.id);
            }
            if (dependency == definition.id) {
                addIssue(report, ValidationSeverity::Error, "SELF_DEPENDENCY",
                         "Content definition cannot depend on itself.", definition.id);
            }
        }
    }

    return report;
}

void ContentCatalog::clear() {
    entries_.clear();
}

ValidationReport ContentCatalog::registerPackage(const ContentPackage& package) {
    ValidationReport report = validatePackage(package);
    if (!report.ok()) return report;

    for (const auto& definition : package.definitions) {
        if (entries_.contains(definition.id)) {
            addIssue(report, ValidationSeverity::Error, "CATALOG_ID_COLLISION",
                     "Content ID is already registered by another package.", definition.id);
        }
    }

    if (!report.ok()) return report;

    for (const auto& definition : package.definitions) {
        entries_.emplace(definition.id, CatalogEntry{package.package_id, definition});
    }

    return report;
}

ValidationReport ContentCatalog::validateReferences() const {
    ValidationReport report;

    for (const auto& [id, entry] : entries_) {
        for (const auto& dependency : entry.definition.dependencies) {
            if (!contains(dependency)) {
                addIssue(report, ValidationSeverity::Error, "UNRESOLVED_DEPENDENCY",
                         "Required content definition is not registered: " + dependency, id);
            }
        }
    }

    return report;
}

const CatalogEntry* ContentCatalog::find(const std::string_view content_id) const {
    const auto it = entries_.find(std::string(content_id));
    return it == entries_.end() ? nullptr : &it->second;
}

bool ContentCatalog::contains(const std::string_view content_id) const {
    return entries_.contains(std::string(content_id));
}

} // namespace ch::studio
