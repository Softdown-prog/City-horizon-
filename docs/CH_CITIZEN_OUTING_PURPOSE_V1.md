# CH_CITIZEN_OUTING_PURPOSE_V1

City Horizon keeps citizen wellbeing needs separate from the reason a citizen leaves home.

## Wellbeing needs

The compact need model remains unchanged:

- `hunger`
- `thirst`
- `fun`

These values decay over time and can be restored by destinations with `needsEffect`.

## Outing purposes

`PedestrianOutingPurpose` defines why the citizen is making the trip:

- `need` — satisfy the currently weakest wellbeing need.
- `shopping` — discretionary purchase at commercial destinations. This is intentionally independent from hunger/thirst/fun, so future shoe, clothing, hardware and similar shops do not need fake wellbeing effects.
- `service` — use an essential or non-retail service. Existing essential food commerce can serve as a fallback; future clinic/health and similar authored services fit here.
- `leisure_activity` — visit an activity destination or a ticketed attraction. `fun` remains a wellbeing need, while this purpose describes the trip itself.

## Current decision policy

When a citizen is comfortable (`min(hunger, thirst, fun) > 70`), weather currently provides a deterministic first-pass discretionary purpose:

- sunny -> `leisure_activity`
- overcast -> `shopping`
- rain/thunderstorm -> `service`

When any wellbeing value reaches 70 or below, `need` is authoritative.

This is tuning, not a permanent design restriction. Purpose selection can later become weighted by personality, income, district, age, schedule or authored city policy without adding more need bars.

## Destination policy

- `need`: destination must satisfy the selected `PedestrianNeed`.
- `shopping`: current V1 accepts accessible priced `commercial` definitions with a non-empty `serviceName`.
- `service`: current V1 accepts essential services and non-commercial definitions with a non-empty `serviceName`.
- `leisure_activity`: current V1 accepts activity-overlay/fun destinations and ticketed attractions.

All destinations still obey accessibility, navigation and the citizen's remaining monthly budget. If a discretionary purpose has no reachable valid destination, the runtime falls back to the citizen's weakest wellbeing need instead of inventing a new need.

## Spending

Existing service/ticket charges continue to debit `monthly_budget_cents`. The separate aggregate monthly city economy is unchanged by this contract.

Shopping-specific spend bands (for example a future mall purchase range) are deliberately deferred until authored destination spending metadata exists.

## Deferred examples

- Shoe/clothing/hardware stores: `shopping`.
- Clinic/health provider: `service`.
- Mall: normally `shopping`; it may also expose leisure/activity behavior later if authored.
- Church/religious venue: visit/donation behavior is deferred. No donation percentage is hard-coded by V1.
- Education: deferred.

The key invariant is that new destination families should normally be modeled as outing purposes/service metadata, not as additional hunger/thirst/fun-style bars.
