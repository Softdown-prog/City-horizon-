#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace ch::studio {

inline constexpr std::string_view kContentPackContract = "CH_CONTENT_PACK_V1";

enum class ContentKind {
    Unknown,
    Terrain,
    Road,
    Sidewalk,
    Building,
    Decoration,
    Actor,
    Vehicle,
    UiLayout,
    Scenario,
};

enum class ValidationSeverity {
    Info,
    Warning,
    Error,
};

struct ContentDefinition {
    std::string id;
    std::string display_name;
    ContentKind kind = ContentKind::Unknown;
    std::string behavior_id;
    std::string visual_id;
    std::string source_path;
    std::vector<std::string> dependencies;
};

struct ContentPackage {
    std::string contract = std::string(kContentPackContract);
    std::string package_id;
    std::string display_name;
    int version = 1;
    std::vector<ContentDefinition> definitions;
};

struct ValidationIssue {
    ValidationSeverity severity = ValidationSeverity::Error;
    std::string code;
    std::string message;
    std::string content_id;
};

struct ValidationReport {
    std::vector<ValidationIssue> issues;

    [[nodiscard]] bool ok() const;
    [[nodiscard]] std::size_t errorCount() const;
    [[nodiscard]] std::size_t warningCount() const;
};

struct CatalogEntry {
    std::string package_id;
    ContentDefinition definition;
};

class ContentCatalog final {
public:
    void clear();

    [[nodiscard]] ValidationReport registerPackage(const ContentPackage& package);
    [[nodiscard]] ValidationReport validateReferences() const;

    [[nodiscard]] const CatalogEntry* find(std::string_view content_id) const;
    [[nodiscard]] bool contains(std::string_view content_id) const;
    [[nodiscard]] std::size_t size() const noexcept { return entries_.size(); }

private:
    std::unordered_map<std::string, CatalogEntry> entries_;
};

[[nodiscard]] bool isValidContentId(std::string_view id);
[[nodiscard]] std::string_view toString(ContentKind kind);
[[nodiscard]] std::string_view toString(ValidationSeverity severity);
[[nodiscard]] std::optional<ContentKind> contentKindFromString(std::string_view value);
[[nodiscard]] ValidationReport validatePackage(const ContentPackage& package);

} // namespace ch::studio
