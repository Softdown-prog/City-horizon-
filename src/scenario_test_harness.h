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
    std::string scenario_name;
    std::string failed_step;
    std::string message;
    std::size_t completed_steps = 0;
};

class ScenarioTestHarness {
public:
    using Step = std::function<ScenarioStepResult()>;

    explicit ScenarioTestHarness(std::string name = {}) : name_(std::move(name)) {}

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
        run.scenario_name = name_;
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

    [[nodiscard]] const std::string& name() const noexcept { return name_; }
    [[nodiscard]] std::size_t step_count() const noexcept { return steps_.size(); }

private:
    struct Entry {
        std::string name;
        Step step;
    };

    std::string name_;
    std::vector<Entry> steps_;
};

struct ScenarioSuiteRunResult {
    bool success = true;
    std::size_t completed_scenarios = 0;
    std::vector<ScenarioRunResult> results;
};

class ScenarioTestSuite {
public:
    [[nodiscard]] bool add(ScenarioTestHarness scenario) {
        if (scenario.name().empty()) return false;
        for (const ScenarioTestHarness& existing : scenarios_) {
            if (existing.name() == scenario.name()) return false;
        }
        scenarios_.push_back(std::move(scenario));
        return true;
    }

    [[nodiscard]] ScenarioSuiteRunResult run() const {
        ScenarioSuiteRunResult suite;
        suite.results.reserve(scenarios_.size());
        for (const ScenarioTestHarness& scenario : scenarios_) {
            ScenarioRunResult result = scenario.run();
            suite.results.push_back(result);
            if (!result.success) {
                suite.success = false;
                return suite;
            }
            ++suite.completed_scenarios;
        }
        return suite;
    }

    [[nodiscard]] std::size_t scenario_count() const noexcept { return scenarios_.size(); }

private:
    std::vector<ScenarioTestHarness> scenarios_;
};
