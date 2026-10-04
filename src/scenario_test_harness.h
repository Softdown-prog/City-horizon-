#pragma once

#include <functional>
#include <string>
#include <utility>
#include <vector>

inline constexpr const char* kScenarioTestHarnessContract = "CH_SCENARIO_TEST_HARNESS_V1";

struct ScenarioStepResult {
    bool success = false;
    std::string message;
};

struct ScenarioRunResult {
    bool success = true;
    std::string failed_step;
    std::string message;
    std::size_t completed_steps = 0;
};

class ScenarioTestHarness {
public:
    using Step = std::function<ScenarioStepResult()>;

    [[nodiscard]] bool add_step(std::string name, Step step) {
        if (name.empty() || !step) return false;
        for (const Entry& entry : steps_) {
            if (entry.name == name) return false;
        }
        steps_.push_back({std::move(name), std::move(step)});
        return true;
    }

    [[nodiscard]] ScenarioRunResult run() const {
        ScenarioRunResult run;
        for (const Entry& entry : steps_) {
            const ScenarioStepResult result = entry.step();
            if (!result.success) {
                run.success = false;
                run.failed_step = entry.name;
                run.message = result.message;
                return run;
            }
            ++run.completed_steps;
        }
        return run;
    }

    [[nodiscard]] std::size_t step_count() const noexcept { return steps_.size(); }

private:
    struct Entry {
        std::string name;
        Step step;
    };

    std::vector<Entry> steps_;
};
