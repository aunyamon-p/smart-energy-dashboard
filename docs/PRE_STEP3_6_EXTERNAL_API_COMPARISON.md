# Pre-Step 3.6: External Data API Comparison

## Scope

This is a research and feasibility comparison only. It does not modify the
Open-Meteo integration, CU-BEMS Raw Dataset, Step 2 outputs, anomaly logic,
Backend API, Database, or Frontend.

The project already has a verified Open-Meteo historical weather integration:

- Bangkok coordinates: `13.7563, 100.5018`
- Timezone: `Asia/Bangkok`
- Period: `2018-07-01` through `2018-12-31`
- Frequency: hourly
- Rows: `4,416`
- Missing temperature/humidity: `0`
- No API key was required

The existing Weather Model experiment found only a small predictive
improvement from weather: Overall MAE improved by `0.193%`, RMSE by `0.026%`,
and R² changed from `0.85272` to `0.85280`. This is the baseline for the
comparison; it does not prove causation.

## Important distinction

None of the external APIs reviewed here is a replacement for the CU-BEMS
building meter. Grid, generation, and carbon data describe an electricity
system at national or grid-zone level. They can provide context or cost/carbon
factors, but actual building consumption must continue to come from BMS/AMI
measurements.

## Comparison summary

| API | Group | Thailand | Jul-Dec 2018 coverage | Key/cost | Resolution | Value for this system | Integration impact |
|---|---|---|---|---|---|---|---|
| Open-Meteo Historical | Weather | Yes | Verified: complete hourly data | No key; free public access for this use | Hourly | Useful explanatory feature for AC; small measured forecasting gain | Low; already integrated |
| Electricity Maps | Carbon intensity / electricity mix/load | Yes, official zone `TH` | Current product has trailing history; 2018 requires paid/custom historical access | Trial available; production signals require authentication and commercial plan | Hourly standard; finer intervals may be available by plan | Strong live grid carbon/mix context; not building fault evidence | Low-medium; add auth, rate limits, cache, source/version fields |
| WattTime | Marginal carbon intensity | Thailand must be confirmed from an account | Historical access and 2018 availability require subscriber verification | Account and bearer token required; plan-based | Real-time, forecast, historical signals | Potentially useful for carbon-aware operation, not direct anomaly detection | Medium; region lookup, auth, quota and model-version handling |
| Ember Data API | Carbon intensity / electricity generation | Country data uses ISO-3; verify `THA` options | Yearly carbon intensity; monthly generation may cover 2018 if `THA` is available | API key required; CC-BY-4.0 attribution | Monthly/yearly | Good national context and emissions reporting; too coarse for minute/hour alerts | Low-medium; key, attribution, monthly join and coverage validation |
| U.S. EIA International | Electricity/energy statistics | Thailand exists as `THA` | Historical monthly national series exist, but electricity product/frequency must be selected and verified | Free key registration; `DEMO_KEY` supports limited testing | Usually monthly/yearly | Useful national benchmark, weak direct value for building anomalies | Low-medium; product mapping and unit normalization required |

Ratings are feasibility judgments for this project, not vendor guarantees.
“Thailand” means the API has an identifiable country/grid entry, not that it
has building-level CU-BEMS data.

## 1. Carbon emission and carbon-intensity APIs

### Electricity Maps

The official zones endpoint lists:

```json
{
  "zoneName": "Thailand",
  "zoneKey": "TH",
  "countryCode": "TH",
  "isCommerciallyAvailable": true,
  "tier": "TIER_C"
}
```

The metadata request succeeded without a key. The actual request
`/v3/carbon-intensity/latest?zone=TH` returned HTTP `401` with an invalid
authentication-token message. Therefore, Thailand support is verified, but
data access is not keyless.

The official pricing information describes a trial and paid country signals.
The current product information provides recent trailing history; Jul-Dec 2018
should not be assumed available without a paid/custom historical arrangement.
The API is operationally attractive for live carbon context because its grid
zone is explicit and its standard signal is hourly. It is not a suitable
replacement for CU-BEMS anomaly evidence.

Official references:

- [Electricity Maps API documentation](https://docs.electricitymaps.com/api-reference/)
- [Electricity Maps zones endpoint](https://api.electricitymaps.com/v3/zones)
- [Electricity Maps pricing](https://www.electricitymaps.com/pricing)

### WattTime

WattTime documents real-time, forecast, and historical marginal-emissions
signals and a location-to-grid lookup. Thailand coverage and the exact grid
region must be confirmed after account access; the public documentation does
not justify assuming that the CU-BEMS location has 2018 history. Historical
and other data endpoints require authenticated subscriber access.

This could be valuable for future carbon-aware control or reporting, but
marginal emissions are not the same as building power and should not alter the
existing anomaly baseline without a separate validated experiment.

Official reference:

- [WattTime API documentation](https://docs.watttime.org/)

### Ember Data API

Ember provides open electricity data, including generation, demand, power
sector emissions, and carbon intensity. Its API documentation describes
country filtering and ISO-3 country codes; Thailand should be checked as
`THA` through the authenticated options/data response.

The carbon-intensity dataset is documented at yearly grain, so it cannot
directly explain hourly or monthly anomalies in Jul-Dec 2018. Ember's monthly
generation/fuel-mix data may be useful for national context if the requested
Thailand dates are present. An API key is required and CC-BY-4.0 attribution
must be retained.

Official references:

- [Ember API](https://ember-energy.org/data/api/)
- [Ember API OpenAPI specification](https://api.ember-energy.org/v1/openapi.json)

## 2. Electricity and energy-data APIs

### U.S. EIA International API

The API has an official Thailand country identifier `THA` and supports
frequency/date/product filters. A live test using `DEMO_KEY` returned HTTP
`200` for a monthly Thailand query covering `2018-07` to `2018-12`.
However, the intentionally broad query returned 42 national energy rows,
with the first records being petroleum products such as “Total petroleum and
other liquids.” This proves reachability and date filtering, not that the
requested electricity series is available.

To use EIA, a future implementation must explicitly select an electricity
product and verify its unit, activity, frequency, and date coverage. EIA data
is national statistics, not a local building meter, so its direct anomaly
detection value is low.

Official references:

- [EIA API technical documentation](https://www.eia.gov/opendata/documentation.php)
- [EIA International data API](https://api.eia.gov/v2/international/data/)

### Ember monthly electricity data

Ember is also an electricity/energy-data candidate. Monthly generation and
fuel-mix context could support explanations such as grid mix changes or
national demand conditions. It cannot explain a specific CU-BEMS Zone's
minute-level event, and it requires authentication plus attribution.

Use it only as a monthly context feature after validating the exact `THA`
date/product response. Do not treat national generation as site consumption.

### Electricity Maps electricity mix/load

Electricity Maps also exposes grid mix/load context for supported zones,
including Thailand metadata. It is more operationally aligned than EIA for
live use, but current access and long historical coverage are commercial.
Its `TH` zone is a grid-zone signal, not the building's meter.

## 3. Live tests performed

### Electricity Maps metadata

Request:

```text
GET https://api.electricitymaps.com/v3/zones
```

Result: HTTP success; `TH` was present with `zoneName=Thailand`,
`countryCode=TH`, and `isCommerciallyAvailable=true`.

### Electricity Maps data endpoint without key

Request:

```text
GET https://api.electricitymaps.com/v3/carbon-intensity/latest?zone=TH
```

Result: HTTP `401`, invalid authentication token. No secret was created or
stored.

### EIA International with Demo key

Request used the official International endpoint, Thailand `THA`, monthly
frequency, and Jul-Dec 2018 dates with `DEMO_KEY`.

Result: HTTP `200`, `total=42` for the broad query. Returned records included
petroleum products, so no claim of an electricity-series match is made. A
future test must add the documented electricity product/activity filters.

### Open-Meteo reference

The existing project test already verified HTTP `200`, 4,416 complete hourly
rows, Bangkok timezone, and no missing temperature/humidity. The existing
weather files and scripts were not changed in this step.

## 4. Usefulness for anomaly detection

| Data | Helps detect a building anomaly? | Helps explain an alert? | Safe role |
|---|---:|---:|---|
| Temperature/humidity | Sometimes, especially AC and Floor 2 patterns | Yes, as external context | Candidate expected-usage feature; retain as optional |
| Grid carbon intensity | Usually no for power anomaly detection | Yes, for carbon impact/cost context | Separate carbon-impact annotation |
| Grid mix/load | Rarely directly | Sometimes, for system-wide context | Context only, with timezone/coverage metadata |
| National generation/fuel mix | No at minute/Zone scale | Limited monthly explanation | Reporting/benchmark context only |
| National energy statistics | No | Limited macro context | Do not join directly to building anomaly rows |

The current anomaly detector should not be changed based on any API in this
comparison. A future API feature must be evaluated using time-based
holdouts, missing-data behavior, and false-negative/false-positive proxies.

## 5. Ranking and recommendation

This ranking is provided for review; it is not a final decision:

1. **Open-Meteo** — best immediate fit and lowest integration risk. It is
   already verified for the dataset period, requires no key, and has complete
   hourly data. The measured forecasting improvement is small, so it should
   remain optional rather than mandatory.
2. **Electricity Maps** — best candidate for a future live Thailand grid
   carbon/mix context feature if the project accepts authentication and
   commercial/historical constraints. It is not a replacement for Weather or
   CU-BEMS meter data.
3. **Ember Data API** — best candidate for monthly/yearly national
   generation/emissions reporting after key and `THA` coverage validation.
   It is too coarse for the current anomaly detector.
4. **WattTime** — potentially valuable for marginal-emissions optimization,
   but Thailand coverage, historical 2018 access, account requirements, and
   model/version behavior need provider confirmation.
5. **EIA International** — easiest broad national-data test, but the live
   test did not yet identify a suitable electricity series and the data is
   not building-level.

## 6. Answers to the requested questions

### 1. Which API is most suitable?

For the current Smart Energy Intelligence System, Open-Meteo is the most
appropriate primary external API because it has verified historical coverage,
simple Python integration, no key, and a direct relationship to AC demand.
For a different goal—live carbon reporting—Electricity Maps is the strongest
candidate, subject to authentication, cost, and historical-access approval.

### 2. Should Weather API continue?

Yes, as an optional context/feature. The project has complete data for the
target period and Model B showed a small out-of-sample improvement, but the
effect is not large or uniformly positive. It should not replace the existing
baseline or be required for anomaly operation.

### 3. Should Open-Meteo be the primary External Data API?

It is the recommended primary external API for the current scope unless the
user prioritizes carbon accounting over load explanation. This recommendation
is based on verified coverage and low operational risk, not merely successful
HTTP calls.

### 4. Expected system changes

| API | Main changes if adopted |
|---|---|
| Open-Meteo | Already integrated; preserve source metadata, retries, validation, and optional feature flag |
| Electricity Maps | New authenticated client, secret management, rate-limit/cache handling, grid-zone mapping, historical-coverage checks, and separate carbon-context schema |
| WattTime | Account/token flow, location-to-region mapping, quota handling, model-version metadata, and historical availability checks |
| Ember | API-key configuration, CC-BY attribution, monthly/yearly schema, country/product validation, and separate reporting table |
| EIA | API-key configuration, explicit electricity product mapping, unit conversion, pagination, and separate national-statistics schema |

## Limitations

- External API documentation and pricing/coverage can change.
- “Thailand supported” does not guarantee CU-BEMS building coverage.
- No unauthenticated live test can prove historical 2018 availability.
- National/grid data cannot validate a specific Zone's equipment fault.
- No additional API was integrated or used to change anomaly results.
- Nager.Date was not considered a viable energy-context API because the
  previous feasibility test returned no usable Thailand 2018 holiday data.

## Status

Pre-Step 3.6 is complete. Only the comparison report was added; existing
Weather integration, experiment artifacts, Raw Dataset, Step 2 outputs,
anomaly logic, and application code remain unchanged.
