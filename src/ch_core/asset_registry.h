#pragma once

#include <algorithm>
#include <cstddef>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace ch {

enum class AssetKind {
    Sprite,
    Animation,
    Actor,
    Ride,
    Building,
    Terrain,
    Overlay,
    Audio,
    Other
};

struct AssetDescriptor {
    std::string id;
    AssetKind kind = AssetKind::Other;
    std::string logical_path;
    std::string source_group;
    std::string contract;
};

enum class AssetRegistrationResult {
    Inserted,
    DuplicateId,
    InvalidId,
    InvalidPath
};

class AssetRegistry {
public:
    [[nodiscard]] AssetRegistrationResult register_asset(AssetDescriptor descriptor) {
        if (descriptor.id.empty()) return AssetRegistrationResult::InvalidId;
        if (descriptor.logical_path.empty()) return AssetRegistrationResult::InvalidPath;
        if (assets_.contains(descriptor.id)) return AssetRegistrationResult::DuplicateId;
        assets_.emplace(descriptor.id, std::move(descriptor));
        return AssetRegistrationResult::Inserted;
    }

    [[nodiscard]] const AssetDescriptor* find(std::string_view id) const {
        const auto found = assets_.find(std::string(id));
        return found == assets_.end() ? nullptr : &found->second;
    }

    [[nodiscard]] bool contains(std::string_view id) const {
        return find(id) != nullptr;
    }

    [[nodiscard]] std::size_t size() const noexcept {
        return assets_.size();
    }

    [[nodiscard]] std::vector<std::string> ids(AssetKind kind) const {
        std::vector<std::string> result;
        result.reserve(assets_.size());
        for (const auto& [id, descriptor] : assets_) {
            if (descriptor.kind == kind) result.push_back(id);
        }
        std::sort(result.begin(), result.end());
        return result;
    }

    void clear() noexcept {
        assets_.clear();
    }

private:
    std::unordered_map<std::string, AssetDescriptor> assets_;
};

}  // namespace ch
