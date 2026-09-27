#include "economy_system.h"
#include "population_system.h"

#include <filesystem>
#include <fstream>
#include <iostream>

namespace {

bool require(const bool condition, const char* description) {
    if (!condition) {
        std::cerr << "FAILED: " << description << '\n';
    }
    return condition;
}

bool test_controlled_exponential_growth() {
    const std::filesystem::path fixture = std::filesystem::temp_directory_path() / "ch_population_growth_fixture";
    std::filesystem::create_directories(fixture);
    {
        std::ofstream out(fixture / "dense_home.json");
        out << R"({"id":"dense_home","name":"Dense Home","category":"residential","texture":"house.png",
            "footprint":{"width":1,"height":1},"residentialCapacity":2000})";
    }
    {
        std::ofstream out(fixture / "apartment_25.json");
        out << R"({"id":"apartment_25","name":"Apartment 25","category":"residential","texture":"apartment.png",
            "footprint":{"width":2,"height":2},"residentialCapacity":25})";
    }

    BuildingCatalog catalog;
    bool ok = require(catalog.load_from_directory(fixture), "growth fixture catalog loads");
    const BuildingDefinition* home = catalog.find("dense_home");
    const BuildingDefinition* apartment = catalog.find("apartment_25");
    ok &= require(home != nullptr && home->residential_capacity == 2000,
                  "growth fixture exposes large residential capacity");
    ok &= require(apartment != nullptr && apartment->residential_capacity == 25,
                  "residential capacity remains authored per building type");
    if (!ok) {
        std::filesystem::remove_all(fixture);
        return false;
    }

    BuildingManager apartment_buildings(-4, 4);
    const auto apartment_id = apartment_buildings.place(*apartment, 0, 0);
    ok &= require(apartment_id.has_value(), "twenty-five resident apartment places");
    PopulationSystem apartment_population;
    apartment_population.rebuild_capacity(apartment_buildings, catalog);
    ok &= require(apartment_population.residential_capacity() == 25,
                  "an apartment contributes all twenty-five authored resident slots");
    apartment_population.restore_current_population(25, apartment_buildings, catalog);
    const BuildingInstance* apartment_instance = apartment_id
        ? apartment_buildings.find_by_id(*apartment_id)
        : nullptr;
    ok &= require(apartment_instance != nullptr &&
                      apartment_population.residents_for(*apartment_instance, apartment_buildings, catalog) == 25,
                  "resident assignment uses the building's authored capacity rather than a hard-coded house size");

    BuildingManager buildings(-4, 4);
    ok &= require(buildings.place(*home, 0, 0).has_value(), "growth fixture residence places");

    PopulationSystem population;
    population.restore_current_population(1000, buildings, catalog);
    const std::int32_t growth = population.advance_month(buildings, catalog);
    ok &= require(growth == 40 && population.current_population() == 1040,
                  "one thousand residents create four-percent monthly organic demand");
    ok &= require(population.last_month_potential_growth() == 40 && population.last_month_growth() == 40,
                  "potential and actual growth are exposed for UI and balancing");

    population.restore_current_population(10, buildings, catalog);
    ok &= require(population.advance_month(buildings, catalog) == 5,
                  "small towns retain the five-resident starter migration floor");

    population.restore_current_population(2000, buildings, catalog);
    ok &= require(population.advance_month(buildings, catalog) == 0,
                  "housing capacity remains a hard upper bound on arrivals");
    ok &= require(population.housing_demand() == 80,
                  "blocked four-percent demand becomes bounded housing pressure");

    std::filesystem::remove_all(fixture);
    return ok;
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
    const BuildingDefinition* house = catalog.find("residential_suburban_cottage_01");
    if (!require(house != nullptr && house->category == "residential" && house->residential_capacity == 5 &&
                     house->tax_revenue_per_month == 0 && house->maintenance_per_month == 0,
                 "production basic house contributes five residents")) {
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
    if (!require(population.residential_capacity() == 5 && population.current_population() == 0,
                 "one basic house contributes five resident slots immediately")) {
        return 1;
    }

    CityEconomy economy;
    if (!require(population.advance_month(buildings, catalog) == 5 && population.current_population() == 5,
                 "starter migration fills the five-person basic house at monthly settlement")) {
        return 1;
    }
    economy.process_month(buildings, catalog, population, {30, 2, 1});
    if (!require(economy.monthly_summary().revenue == 0 && economy.monthly_summary().expenses == 0 &&
                     economy.monthly_summary().balance == 0 && economy.funds() == 50'000,
                 "population occupancy does not invent residential monthly economics")) {
        return 1;
    }

    for (int month = 0; month < 3; ++month) {
        (void)population.advance_month(buildings, catalog);
    }
    if (!require(population.current_population() == 5 && population.advance_month(buildings, catalog) == 0,
                 "population stops exactly at residential capacity")) {
        return 1;
    }
    if (!require(population.housing_demand() > 0,
                 "unhoused migration interest becomes residential demand instead of disappearing")) {
        return 1;
    }

    const auto second_house_id = buildings.place(*house, 3, 0, BuildingRotation::r90);
    if (!require(second_house_id.has_value(), "second house placement succeeds")) {
        return 1;
    }
    population.rebuild_capacity(buildings, catalog);
    const BuildingInstance* first_house = buildings.find_by_id(*first_house_id);
    const BuildingInstance* second_house = buildings.find_by_id(*second_house_id);
    if (!require(population.residential_capacity() == 10 && population.current_population() == 5 &&
                     first_house != nullptr && second_house != nullptr &&
                     population.residents_for(*first_house, buildings, catalog) == 5 &&
                     population.residents_for(*second_house, buildings, catalog) == 0,
                 "a second basic house adds another five slots without duplicating residents")) {
        return 1;
    }
    (void)population.advance_month(buildings, catalog);
    if (!require(population.residents_for(*first_house, buildings, catalog) == 5 &&
                     population.residents_for(*second_house, buildings, catalog) == 5,
                 "residents are deterministically assigned to each home's authored five-person capacity")) {
        return 1;
    }

    if (!test_controlled_exponential_growth()) {
        return 1;
    }

    std::cout << "population system tests passed\n";
    return 0;
}
