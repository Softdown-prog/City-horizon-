#pragma once

#include "src/ch_core/resource_cache.h"

#include <cstddef>
#include <functional>
#include <limits>
#include <optional>
#include <utility>

namespace ch {

// Budget/accounting layer for resources whose residency has a meaningful byte
// cost (textures, decoded images, audio buffers). It reuses ResourceCache for
// lookup/load telemetry and adds LRU eviction plus explicit pinning.
template <typename Key, typename Value, typename Hash = std::hash<Key>, typename KeyEqual = std::equal_to<Key>>
class BudgetedResourceCache {
public:
    struct Entry {
        Value value;
        std::size_t resident_bytes = 0;
        std::size_t pin_count = 0;
        std::size_t last_touch = 0;
    };

    struct BudgetStats {
        std::size_t resident_bytes = 0;
        std::size_t budget_bytes = 0;
        std::size_t evictions = 0;
        std::size_t evicted_bytes = 0;
        std::size_t over_budget_events = 0;
    };

    using Evictor = std::function<void(Value&)>;

    explicit BudgetedResourceCache(const std::size_t budget_bytes = 0, Evictor evictor = {})
        : budget_bytes_(budget_bytes), evictor_(std::move(evictor)) {}

    void set_budget_bytes(const std::size_t budget_bytes) {
        budget_bytes_ = budget_bytes;
        enforce_budget(nullptr);
    }

    [[nodiscard]] std::size_t budget_bytes() const noexcept { return budget_bytes_; }
    [[nodiscard]] std::size_t resident_bytes() const noexcept { return resident_bytes_; }
    [[nodiscard]] std::size_t size() const noexcept { return cache_.size(); }

    template <typename Loader>
    [[nodiscard]] Value* get_or_load(const Key& key, const std::size_t resident_bytes, Loader&& loader) {
        if (auto existing = cache_.find(key); existing != cache_.end()) {
            existing->second.last_touch = ++touch_serial_;
            return &existing->second.value;
        }

        auto loaded = std::invoke(std::forward<Loader>(loader));
        if (!loaded.has_value()) return nullptr;

        Entry entry{std::move(*loaded), resident_bytes, 0, ++touch_serial_};
        auto [inserted, was_inserted] = cache_.emplace(key, std::move(entry));
        if (!was_inserted) return &inserted->second.value;

        resident_bytes_ += inserted->second.resident_bytes;
        enforce_budget(&key);
        return &inserted->second.value;
    }

    [[nodiscard]] Value* get(const Key& key) {
        auto found = cache_.find(key);
        if (found == cache_.end()) return nullptr;
        found->second.last_touch = ++touch_serial_;
        return &found->second.value;
    }

    [[nodiscard]] bool pin(const Key& key) {
        auto found = cache_.peek(key);
        if (found == cache_.end()) return false;
        ++found->second.pin_count;
        found->second.last_touch = ++touch_serial_;
        return true;
    }

    [[nodiscard]] bool unpin(const Key& key) {
        auto found = cache_.peek(key);
        if (found == cache_.end() || found->second.pin_count == 0) return false;
        --found->second.pin_count;
        return true;
    }

    [[nodiscard]] bool erase(const Key& key) {
        auto found = cache_.peek(key);
        if (found == cache_.end() || found->second.pin_count != 0) return false;
        destroy_and_erase(found);
        return true;
    }

    void clear_unpinned() {
        for (auto it = cache_.begin(); it != cache_.end();) {
            if (it->second.pin_count != 0) {
                ++it;
                continue;
            }
            auto victim = it++;
            destroy_and_erase(victim);
        }
    }

    [[nodiscard]] BudgetStats budget_stats() const noexcept {
        return {resident_bytes_, budget_bytes_, evictions_, evicted_bytes_, over_budget_events_};
    }

    [[nodiscard]] const typename ResourceCache<Key, Entry, Hash, KeyEqual>::Stats& cache_stats() const noexcept {
        return cache_.stats();
    }

private:
    using Cache = ResourceCache<Key, Entry, Hash, KeyEqual>;
    using Iterator = typename Cache::iterator;

    void destroy_and_erase(const Iterator victim) {
        const std::size_t bytes = victim->second.resident_bytes;
        if (evictor_) evictor_(victim->second.value);
        const Key key = victim->first;
        cache_.erase(key);
        resident_bytes_ = bytes > resident_bytes_ ? 0 : resident_bytes_ - bytes;
        ++evictions_;
        evicted_bytes_ += bytes;
    }

    void enforce_budget(const Key* protected_key) {
        if (budget_bytes_ == 0) return;  // zero means unlimited during bring-up.

        while (resident_bytes_ > budget_bytes_) {
            Iterator victim = cache_.end();
            std::size_t oldest = std::numeric_limits<std::size_t>::max();
            for (auto it = cache_.begin(); it != cache_.end(); ++it) {
                if (it->second.pin_count != 0) continue;
                if (protected_key != nullptr && KeyEqual{}(it->first, *protected_key)) continue;
                if (it->second.last_touch < oldest) {
                    oldest = it->second.last_touch;
                    victim = it;
                }
            }
            if (victim == cache_.end()) {
                ++over_budget_events_;
                return;
            }
            destroy_and_erase(victim);
        }
    }

    Cache cache_;
    std::size_t budget_bytes_ = 0;
    std::size_t resident_bytes_ = 0;
    std::size_t touch_serial_ = 0;
    std::size_t evictions_ = 0;
    std::size_t evicted_bytes_ = 0;
    std::size_t over_budget_events_ = 0;
    Evictor evictor_;
};

}  // namespace ch
