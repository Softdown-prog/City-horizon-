# CH_SERVICE_PRICE_V1

`CH_SERVICE_PRICE_V1` is the data contract for player-controlled product/service prices that need fractional US-dollar values without migrating the whole city treasury away from integer dollars.

## Definition shape

```json
"serviceName": "Sorvete",
"servicePricingContract": {
  "contract": "CH_SERVICE_PRICE_V1",
  "currency": "USD",
  "storageUnit": "cent",
  "initialPrice": 250,
  "minimumPrice": 25,
  "maximumPrice": 5000,
  "priceStep": 25,
  "playerMaySetExtremePrices": true,
  "demandIsAuthoritativeLimit": true
}
```

For `storageUnit: "cent"`, values are integer cents. The example above therefore means `$2.50` initial, `$0.25` minimum, `$50.00` maximum and `$0.25` per UI adjustment.

The runtime stores the per-instance customer price together with its unit scale and step. UI formatting uses the price type, so cent-priced services render decimals while legacy whole-dollar services keep their existing display.

The city treasury, construction costs, maintenance, taxes and other established economy values remain integer dollars. Service sales aggregate their minor-unit price before converting monthly revenue back to treasury dollars.

Legacy definitions that use `defaultServicePrice`, `minimumServicePrice` and `maximumServicePrice` remain whole-dollar contracts with a `$1` step.

Pricing may be exposed before customer-volume balancing is configured. In that state price-demand feedback may be calculated, but customer count and service revenue remain zero until `baseServiceCustomersPerMonth` and `servicePopulationForFullDemand` are defined.

Extreme prices are intentionally allowed inside the declared technical range. Gameplay demand, rather than a hidden acceptable-price cap, is expected to punish unrealistic prices.
