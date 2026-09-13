#include "economy_system.h"
#include "population_system.h"

#include <algorithm>
#include <iostream>

namespace {

bool require(const bool condition, const char* description) {
    if (!condition) {
        std::cerr << "FAILED: " << description << '\n';
    }
    return condition;
}

std::size_t property_tax_transaction_count(const CityEconomy& economy) {
    return static_cast<std::size_t>(std::count_if(economy.ledger().begin(), economy.ledger().end(),
        [](const EconomyTransaction& transaction) {
            return transaction.type == EconomyTransactionType::property_tax;
        }));
}

}  // namespace

int main(const int argc, char** argv) {
    if (!require(argc == 2, "definitions directory argument")) {
        return 1;
    }

    BuildingCatalog catalog;
    if (!require(catalog.load_from_directory(argv[1]), "catalog loads")) {
        return 1;
    }
    const BuildingDefinition* house = catalog.find("house_suburban_01");
    if (!require(house != nullptr && house->category == "residential" && house->residential_capacity == 4 &&
                     house->property_tax_per_year == 240 && house->tax_revenue_per_month == 0 &&
                     house->maintenance_per_month == 0,
                 "residential capacity and annual property tax come from the house definition")) {
        return 1;
    }

    BuildingManager buildings(-8, 8);
    PopulationSystem population;
    population.rebuild_capacity(buildings, catalog);
    if (!require(population.current_population() == 0 && population.residential_capacity() == 0,
                 "city starts with no residential population or capacity")) {
        return 1;
    }

    const auto first_house_id = buildings.place(*house, 0, 0, BuildingRotation::r0);
    if (!require(first_house_id.has_value(), "first house placement succeeds")) {
        return 1;
    }
    population.rebuild_capacity(buildings, catalog);
    if (!require(population.residential_capacity() == 4 && population.current_population() == 0,
                 "one house contributes its full capacity immediately")) {
        return 1;
    }

    CityEconomy economy;
    if (!require(population.advance_month(buildings, catalog) == 4 && population.current_population() == 4,
                 "population grows up to available powered capacity in monthly settlement")) {
        return 1;
    }
    economy.process_month(buildings, catalog, population, {30, 2, 1});
    if (!require(economy.monthly_summary().revenue == 0 && economy.monthly_summary().expenses == 0 &&
                     economy.monthly_summary().balance == 0 && economy.funds() == 50'000,
                 "residences have neither monthly revenue nor monthly maintenance")) {
        return 1;
    }

    for (int month = 0; month < 3; ++month) {
        (void)population.advance_month(buildings, catalog);
    }
    if (!require(population.current_population() == 4 && population.advance_month(buildings, catalog) == 0,
                 "population stops exactly at residential capacity")) {
        return 1;
    }
    economy.process_month(buildings, catalog, population, {30, 3, 1});
    if (!require(economy.monthly_summary().balance == 0 && economy.funds() == 50'000,
                 "occupancy does not change residential monthly economics")) {
        return 1;
    }

    economy.process_month(buildings, catalog, population, {30, 1, 1});
    if (!require(economy.monthly_summary().revenue == 240 && economy.monthly_summary().expenses == 0 &&
                     economy.monthly_summary().balance == 240 && economy.funds() == 50'240 &&
                     economy.last_property_tax_year() == 1 && property_tax_transaction_count(economy) == 1,
                 "one residence pays its full IPTU once in the fiscal month regardless of occupancy")) {
        return 1;
    }
    economy.process_month(buildings, catalog, population, {30, 1, 1});
    if (!require(economy.monthly_summary().balance == 0 && economy.funds() == 50'240 &&
                     property_tax_transaction_count(economy) == 1,
                 "the same fiscal year cannot charge IPTU twice")) {
        return 1;
    }
    economy.process_month(buildings, catalog, population, {30, 1, 2});
    if (!require(economy.monthly_summary().balance == 240 && economy.funds() == 50'480 &&
                     economy.last_property_tax_year() == 2 && property_tax_transaction_count(economy) == 2,
                 "the next fiscal year charges the residence again")) {
        return 1;
    }

    const auto second_house_id = buildings.place(*house, 3, 0, BuildingRotation::r90);
    if (!require(second_house_id.has_value(), "second house placement succeeds")) {
        return 1;
    }
    population.rebuild_capacity(buildings, catalog);
    const BuildingInstance* first_house = buildings.find_by_id(*first_house_id);
    const BuildingInstance* second_house = buildings.find_by_id(*second_house_id);
    if (!require(population.residential_capacity() == 8 && population.current_population() == 4 &&
                     first_house != nullptr && second_house != nullptr &&
                     population.residents_for(*first_house, buildings, catalog) == 4 &&
                     population.residents_for(*second_house, buildings, catalog) == 0,
                 "capacity grows without duplicating existing residents")) {
        return 1;
    }
    (void)population.advance_month(buildings, catalog);
    if (!require(population.residents_for(*first_house, buildings, catalog) == 4 &&
                     population.residents_for(*second_house, buildings, catalog) == 4,
                 "residents are deterministically assigned to newly available homes")) {
        return 1;
    }
    economy.process_month(buildings, catalog, population, {30, 1, 3});
    if (!require(economy.monthly_summary().revenue == 480 && economy.monthly_summary().expenses == 0 &&
                     economy.monthly_summary().balance == 480 && economy.funds() == 50'960,
                 "two residences pay twice the annual IPTU base")) {
        return 1;
    }

    std::cout << "population system tests passed\n";
    return 0;
}
