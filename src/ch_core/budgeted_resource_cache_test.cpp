#include "src/ch_core/budgeted_resource_cache.h"

#include <cassert>
#include <optional>
#include <string>

int main() {
    int destroyed = 0;
    ch::BudgetedResourceCache<std::string, int> cache(
        8, [&](int&) { ++destroyed; });

    int loads = 0;
    auto load = [&](const int value) {
        return [&, value]() -> std::optional<int> {
            ++loads;
            return value;
        };
    };

    int* first = cache.get_or_load("a", 4, load(10));
    int* second = cache.get_or_load("b", 4, load(20));
    assert(first != nullptr && *first == 10);
    assert(second != nullptr && *second == 20);
    assert(cache.resident_bytes() == 8);
    assert(loads == 2);

    // Touch A so B becomes the least-recently used entry.
    assert(cache.get("a") != nullptr);
    int* third = cache.get_or_load("c", 4, load(30));
    assert(third != nullptr && *third == 30);
    assert(cache.resident_bytes() == 8);
    assert(cache.get("b") == nullptr);
    assert(destroyed == 1);

    assert(cache.pin("a"));
    cache.set_budget_bytes(4);
    assert(cache.get("a") != nullptr);
    assert(cache.get("c") == nullptr);
    assert(cache.resident_bytes() == 4);
    assert(destroyed == 2);

    // A pinned resource may temporarily keep the cache above budget rather
    // than being destroyed while a renderer could still reference it.
    cache.set_budget_bytes(2);
    const auto over_budget = cache.budget_stats();
    assert(over_budget.resident_bytes == 4);
    assert(over_budget.over_budget_events >= 1);
    assert(cache.unpin("a"));
    cache.set_budget_bytes(2);
    assert(cache.resident_bytes() == 0);
    assert(destroyed == 3);

    return 0;
}
