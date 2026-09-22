#include "economy_system.h"
#include "population_system.h"

#include <algorithm>
#include <iostream>

namespace {

bool require(const bool condition, const char* description) {
    if (!condition) {
        std::cerr << "FAILED: " << description << '\n';
        return false;
    }
    return true;
}

bool contains_transaction(const CityEconomy& economy, const EconomyTransactionType type) {
    for (const EconomyTransaction& transaction : economy.ledger()) {
        if (transaction.type == type) {
            return true;
        }
    }
    return false;
}

std::int64_t tax_for_building(const CityEconomy& economy, const std::uint64_t building_instance_id) {
    const auto transaction = std::find_if(economy.ledger().begin(), economy.ledger().end(),
        [building_instance_id](const EconomyTransaction& item) {
            return item.type == EconomyTransactionType::tax_revenue && item.building_instance_id == building_instance_id;
        });
    return transaction == economy.ledger().end() ? 0 : transaction->amount;
}

}  // namespace

int main(int argc, char** argv) {
    if (!require(argc == 2, "definitions directory argument")) {
        return 1;
    }

    BuildingCatalog catalog;
    if (!require(catalog.load_from_directory(argv[1]), "catalog loads economic building data")) {
        return 1;
    }
    const BuildingDefinition* cafe = catalog.find("cafe_01");
    const BuildingDefinition* house = catalog.find("house_suburban_01");
    const BuildingDefinition* bakery = catalog.find("bakery_01");
    if (!require(cafe != nullptr, "cafe definition exists") || !require(house != nullptr, "house definition exists") ||
        !require(bakery != nullptr, "bakery definition exists") ||
        !require(cafe->build_cost == 2'500 && cafe->maintenance_per_month == 80 && cafe->tax_revenue_per_month == 220 &&
                     cafe->required_population_for_full_revenue == 20,
                 "cafe economics come from JSON") ||
        !require(bakery->build_cost == 2'500 && bakery->default_service_price == 3 &&
                     bakery->base_service_customers_per_month == 120 &&
                     bakery->service_population_for_full_demand == 60,
                 "bakery pricing economy comes from JSON")) {
        return 1;
    }

    BuildingInstance bakery_instance;
    bakery_instance.definition_id = bakery->id;
    bakery_instance.service_price = 3;
    const ServicePricingEstimate bakery_default = CityEconomy::service_pricing_estimate(*bakery, bakery_instance, 60);
    bakery_instance.service_price = 2;
    const ServicePricingEstimate bakery_discount = CityEconomy::service_pricing_estimate(*bakery, bakery_instance, 60);
    bakery_instance.service_price = 5;
    const ServicePricingEstimate bakery_expensive = CityEconomy::service_pricing_estimate(*bakery, bakery_instance, 60);
    bakery_instance.service_price = 3;
    const ServicePricingEstimate bakery_half_population = CityEconomy::service_pricing_estimate(*bakery, bakery_instance, 30);
    if (!require(bakery_default.price_demand_percent == 100 && bakery_default.customers_per_month == 120 &&
                     bakery_default.revenue_per_month == 360,
                 "bakery default price produces reference demand and revenue") ||
        !require(bakery_discount.price_demand_percent == 120 && bakery_discount.customers_per_month == 144 &&
                     bakery_discount.revenue_per_month == 288,
                 "bakery discount increases customers but lowers total sales revenue") ||
        !require(bakery_expensive.price_demand_percent == 36 && bakery_expensive.customers_per_month == 43 &&
                     bakery_expensive.revenue_per_month == 215,
                 "bakery high price reduces demand and revenue") ||
        !require(bakery_half_population.population_demand_percent == 50 &&
                     bakery_half_population.customers_per_month == 60 && bakery_half_population.revenue_per_month == 180,
                 "bakery customer volume is limited by local population")) {
        return 1;
    }

    SimulationClock clock(1.0);
    if (!require(clock.advance_seconds(0.9).days_advanced == 0, "clock does not depend on frames below a game day") ||
        !require(clock.advance_seconds(0.1).days_advanced == 1 && clock.date().day == 2,
                 "clock advances a deterministic game day") ) {
        return 1;
    }
    clock.set_speed(SimulationSpeed::paused);
    if (!require(clock.advance_seconds(100.0).days_advanced == 0 && clock.date().day == 2,
                 "pause freezes simulated time")) {
        return 1;
    }
    clock.set_speed(SimulationSpeed::speed2);
    if (!require(clock.advance_seconds(1.0).days_advanced == 4, "speed 2 advances four game days per configured second")) {
        return 1;
    }
    clock.set_speed(SimulationSpeed::speed3);
    if (!require(clock.advance_seconds(1.0).days_advanced == 12, "speed 3 advances twelve game days per configured second")) {
        return 1;
    }

    BuildingManager buildings(-6, 6);
    PopulationSystem population;
    const auto first_id = buildings.place(*cafe, 0, 0);
    if (!require(first_id.has_value(), "first cafe placement succeeds")) {
        return 1;
    }

    CityEconomy economy;
    const GameDate purchase_date = {1, 1, 1};
    if (!require(economy.funds() == 50'000, "economy starts with 50000") ||
        !require(economy.spend_for_building(cafe->build_cost, purchase_date, *first_id), "building cost is affordable") ||
        !require(economy.funds() == 47'500, "building purchase deducts its cost") ||
        !require(!economy.spend_for_building(50'000, purchase_date, *first_id), "construction cannot create negative funds") ||
        !require(contains_transaction(economy, EconomyTransactionType::building_construction), "ledger records construction")) {
        return 1;
    }

    economy.process_month(buildings, catalog, population, {30, 1, 1});
    if (!require(economy.monthly_summary().revenue == 22 && economy.monthly_summary().expenses == 80 &&
                 economy.monthly_summary().balance == -58,
                 "zero population leaves one cafe at minimum demand") ||
        !require(economy.funds() == 47'442, "low-demand cafe changes funds by its monthly net") ||
        !require(contains_transaction(economy, EconomyTransactionType::tax_revenue) &&
                 contains_transaction(economy, EconomyTransactionType::maintenance) &&
                 contains_transaction(economy, EconomyTransactionType::monthly_closure),
                 "ledger records monthly income expenses and close")) {
        return 1;
    }

    const auto second_id = buildings.place(*cafe, 3, 0);
    if (!require(second_id.has_value(), "second cafe placement succeeds") ||
        !require(economy.spend_for_building(cafe->build_cost, {1, 2, 1}, *second_id), "second build cost is deducted")) {
        return 1;
    }
    economy.process_month(buildings, catalog, population, {30, 2, 1});
    if (!require(economy.monthly_summary().revenue == 44 && economy.monthly_summary().expenses == 160 &&
                 economy.monthly_summary().balance == -116,
                 "two cafes share the same low population demand") ||
        !require(economy.funds() == 44'826, "funds change exactly after low-demand two-cafe monthly close")) {
        return 1;
    }

    const auto house_id = buildings.place(*house, 0, 3, BuildingRotation::r270);
    if (!require(house_id.has_value(), "house placement succeeds") ||
        !require(economy.spend_for_building(house->build_cost, {1, 3, 1}, *house_id), "house build cost is deducted")) {
        return 1;
    }
    const std::uint32_t arrivals_after_first_house = population.advance_month(buildings, catalog);
    if (!require(arrivals_after_first_house == 4 && population.current_population() == 4,
                 "first occupied residence fills up to powered capacity")) {
        return 1;
    }
    economy.process_month(buildings, catalog, population, {30, 3, 1});
    if (!require(economy.monthly_summary().revenue == 88 && economy.monthly_summary().expenses == 160 &&
                 economy.monthly_summary().balance == -72,
                 "residences scale commercial demand according to population") ||
        !require(economy.funds() == 42'954, "mixed building monthly balance changes funds exactly")) {
        return 1;
    }

    BuildingManager demand_buildings(-16, 16);
    PopulationSystem demand_population;
    const auto demand_cafe_id = demand_buildings.place(*cafe, 0, 0);
    if (!require(demand_cafe_id.has_value(), "commercial demand test cafe placement succeeds")) {
        return 1;
    }
    for (int x = 0; x < 5; ++x) {
        if (!require(demand_buildings.place(*house, x * 3, 3).has_value(), "demand test residence placement succeeds")) {
            return 1;
        }
    }
    demand_population.rebuild_capacity(demand_buildings, catalog);
    if (!require(demand_population.residential_capacity() == 20, "five residences provide population for full commercial demand")) {
        return 1;
    }

    const auto cafe_month_at_population = [&](const std::uint32_t residents) {
        demand_population.restore_current_population(residents, demand_buildings, catalog);
        CityEconomy demand_economy;
        demand_economy.process_month(demand_buildings, catalog, demand_population, {30, 4, 1});
        return std::pair<std::int64_t, std::int64_t>{
            tax_for_building(demand_economy, *demand_cafe_id),
            demand_economy.monthly_summary().expenses};
    };
    const auto no_residents = cafe_month_at_population(0);
    const auto low_population = cafe_month_at_population(5);
    const auto medium_population = cafe_month_at_population(10);
    const auto full_population = cafe_month_at_population(20);
    if (!require(no_residents.first == 22, "commercial revenue is 10 percent at zero population") ||
        !require(low_population.first == 55, "commercial revenue is 25 percent at low population") ||
        !require(medium_population.first == 110, "commercial revenue is 50 percent at medium population") ||
        !require(full_population.first == 220, "commercial revenue reaches 100 percent at required population") ||
        !require(no_residents.second == 80 && low_population.second == 80 &&
                     medium_population.second == 80 && full_population.second == 80,
                 "commercial maintenance stays integral at every demand level") ||
        !require(CityEconomy::commercial_demand_percent(*cafe, 0) == 10 &&
                     CityEconomy::commercial_demand_percent(*cafe, 20) == 100 &&
                     CityEconomy::commercial_demand_percent(*cafe, 21) == 100,
                 "commercial demand percentage is clamped between the minimum and maximum")) {
        return 1;
    }

    BuildingDefinition demand_driven_definition = *cafe;
    demand_driven_definition.category = "other";
    if (!require(CityEconomy::commercial_demand_percent(demand_driven_definition, 0) == 10,
                 "population demand is enabled by its definition property, not category")) {
        return 1;
    }

    SimulationClock monthly_clock(1.0);
    monthly_clock.set_speed(SimulationSpeed::speed1);
    const SimulationAdvance nearly_a_month = monthly_clock.advance_seconds(29.0);
    const SimulationAdvance month_close = monthly_clock.advance_seconds(1.0);
    if (!require(nearly_a_month.closed_months.empty() && month_close.closed_months.size() == 1 &&
                 month_close.closed_months.front().month == 1 && monthly_clock.date().month == 2,
                 "month close is deterministic and reports its closing date")) {
        return 1;
    }

    std::cout << "Economy and simulation checks passed.\n";
    return 0;
}
