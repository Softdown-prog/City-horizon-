from pathlib import Path

path = Path("src/economy_system.cpp")
text = path.read_text(encoding="utf-8")

wrong_summary = """        ServicePricingEstimate service = service_pricing_estimate(*definition, instance, population.current_population());
        if (farming != nullptr && !definition->resource_inputs.empty() && definition->default_service_price <= 0) {
            const std::int64_t price = std::clamp("""
right_summary = """        ServicePricingEstimate service = service_pricing_estimate(*definition, instance, population.current_population());
        if (farming != nullptr && !definition->resource_inputs.empty()) {
            const std::int64_t price = std::clamp("""
if wrong_summary not in text:
    raise SystemExit("expected stock summary block was not found")
text = text.replace(wrong_summary, right_summary, 1)

legacy_block = """        if (expense != 0) {
            record(EconomyTransactionType::maintenance, -expense, closing_date, instance.instance_id);
        }
        if (farming != nullptr && !definition->resource_inputs.empty()) {
            bool supplied = true;"""
fixed_legacy_block = """        if (expense != 0) {
            record(EconomyTransactionType::maintenance, -expense, closing_date, instance.instance_id);
        }
        // Service-priced shops consume resource inputs according to the customers
        // actually served above. The legacy bonus path remains for non-service
        // buildings only, preventing a second ingredient charge.
        if (farming != nullptr && !definition->resource_inputs.empty() && definition->default_service_price <= 0) {
            bool supplied = true;"""
if legacy_block not in text:
    raise SystemExit("expected legacy local-supply block was not found")
text = text.replace(legacy_block, fixed_legacy_block, 1)

if text.count("definition->default_service_price <= 0") != 1:
    raise SystemExit("service exclusion must exist only on the legacy local-supply path")

path.write_text(text, encoding="utf-8")
Path("tools/fix_bakery_stock_accounting.py").unlink()
Path(".github/workflows/fix-bakery-stock-accounting-once.yml").unlink()
