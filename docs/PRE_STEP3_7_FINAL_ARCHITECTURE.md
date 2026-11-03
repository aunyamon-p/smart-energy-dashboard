# Pre-Step 3.7: Final Project Architecture

## 1. Purpose and decision record

This document is the final architecture proposal before Step 3 backend
implementation. It is design-only. No Backend, Database, Frontend, or AWS
resource was created or changed in this step.

The architecture follows these decisions:

1. CU-BEMS remains the authoritative source for building Energy Analysis and
   Anomaly Detection.
2. The existing Step 2 formula and derived outputs remain unchanged.
3. Open-Meteo remains the selected external API.
4. Weather is contextual information, not an anomaly-detector input in the
   first production backend.
5. Weather context is exposed on the Dashboard, Weather & AC Analytics, and
   Alert Detail pages where an alert has a relevant AC/time context.
6. Alerts remain `Potential Anomaly`; the system does not claim `Confirmed
   Fault` without external verification.
7. The initial AWS design prioritizes AWS Learner Lab cost control and avoids
   always-on infrastructure.

## 2. Verified baseline and consistency

The design was checked against:

- `backend/process_dataset.py` and `backend/ANOMALY_DETECTION.md`
- `PRE_STEP3_REVIEW.md`
- `PRE_STEP3_4_SCHEMA_API_DESIGN.md`
- `WEATHER_API_REPORT.md`
- `WEATHER_ENERGY_ANALYSIS.md`
- `WEATHER_MODEL_EXPERIMENT.md`
- `PRE_STEP3_5_HOLIDAY_API_REPORT.md`
- `PRE_STEP3_6_EXTERNAL_API_COMPARISON.md`
- Step 2 processed CSV/JSON outputs and Weather outputs

Verified facts:

- Raw files: two CU-BEMS files, each with `264,960` one-minute rows.
- Time range: `2018-07-01` through `2018-12-31`, local Bangkok time.
- Power columns are instantaneous `kW`; energy is derived as `kW *
  interval_hours`.
- Processed series rows: `5,034,240`.
- Daily Energy rows: `3,496`.
- Point anomaly evidence rows: `262,890`.
- Alert Events: `23,123`.
- Missing aggregated power observations: `42,111`.
- Partial-component observations: `2,107`.
- Weather rows: `4,416` complete hourly Bangkok observations.
- Weather/AC joined rows: `26,496`; complete correlation pairs: `26,439`.
- Open-Meteo Model B improved Overall MAE by only `0.193%`; it does not
  justify changing the anomaly formula.
- Nager.Date returned no usable Thailand 2018 holiday calendar and is not part
  of this architecture.

No raw, Step 2, Weather, or experiment output is changed by this document.

## 3. Target system boundary

### In scope

- Read-only ingestion of CU-BEMS raw files.
- Reproducible Step 2 batch processing.
- Serving daily Energy, Potential Anomaly Events, and data-quality metadata.
- Fetching and caching Open-Meteo historical/current context with validation.
- Weather/AC hourly analytics and correlation results.
- Dashboard, Alert List, Alert Detail, and Weather Analytics API responses.
- Alert workflow status such as `New`, `Acknowledged`, and `Resolved`.

### Out of scope for the first implementation

- Re-training or changing the anomaly formula.
- Automatic fault confirmation.
- Electricity tariff or cost calculation until an approved tariff is supplied.
- Holiday feature integration.
- Carbon-intensity integration.
- Occupancy, thermostat, schedule, or equipment-status inference.
- AWS deployment in this Pre-Step.

## 4. Logical data flow

```text
CU-BEMS Raw CSV (immutable)
        |
        v
Step 2 Processor (pandas, reproducible batch)
        |
        +--> daily Energy aggregates
        +--> point anomaly evidence (internal/detail)
        +--> contiguous Potential Anomaly Events (alert source)
        +--> data quality + processing metadata
        |
        v
Object storage / database read model
        |
        v
Serverless Backend API
        |
        +--> Dashboard Summary + Energy trend
        +--> Energy records
        +--> Alert List
        +--> Alert Detail + evidence + Weather context
        +--> Weather & AC Analytics
        |
        v
Existing React dashboard

Open-Meteo API
        |
        v
Validated Weather cache (separate source and schema)
        |
        +--> hourly Weather context
        +--> Weather/AC analytics
        +--> optional Alert Detail context
```

### Data ownership rules

- CU-BEMS owns actual power and the derived Energy totals.
- Step 2 owns Expected Power, MAD/robust score, severity, and event grouping.
- Open-Meteo owns external temperature and humidity observations.
- The backend owns API serialization, filters, pagination, and alert workflow
  status.
- The UI never calculates Energy, Expected Usage, Severity, or cost.

## 5. Recommended AWS Learner Lab architecture

### 5.1 Low-cost initial services

| Concern | Recommended service | Role |
|---|---|---|
| Raw and derived file storage | Amazon S3 | Separate prefixes for raw, processed, external, and reports |
| API compute | AWS Lambda | Python handlers for read APIs and status updates |
| HTTP interface | Amazon API Gateway HTTP API | REST-style routes with lower overhead than a full always-on server |
| Query/read model | Amazon DynamoDB | Energy daily records, alert events, alert status, and metadata |
| Frontend hosting | S3 static website or existing local Vite host | Host built React assets only when needed |
| Secrets | AWS Secrets Manager only if a future API requires a key | No secret is needed for current Open-Meteo use |
| Logs | CloudWatch Logs | Lambda/API errors and ingestion summaries with retention |

This is a cost-conscious proposal, not a claim that the Learner Lab account
has every service enabled. Availability, quotas, credits, and region
restrictions must be checked before deployment.

### 5.2 Services intentionally not selected initially

- **RDS/Aurora:** unnecessary for the current read-heavy, batch-derived
  records and creates instance/storage cost.
- **ECS/EC2:** always-on compute is unnecessary for this prototype and risks
  consuming Learner Lab credits.
- **OpenSearch:** unnecessary for the current alert volume and query patterns.
- **Step Functions/Glue/EMR:** defer until ingestion frequency or data size
  justifies orchestration/ETL services.
- **CloudFront:** optional for a public production UI, but not required for
  local testing or a minimal Learner Lab demonstration.

### 5.3 S3 layout

```text
s3://<project-bucket>/
  raw/cubems/2018Floor1.csv
  raw/cubems/2018Floor2.csv
  processed/energy_daily/...
  processed/anomaly_evidence/...
  processed/alert_events/...
  processed/quality/...
  external/open_meteo/weather_hourly/...
  external/open_meteo/weather_energy_hourly/...
  analytics/weather_ac/...
  manifests/processing_runs/...
```

Raw prefixes must be write-protected after upload. Each processing run should
write a versioned output or manifest rather than silently overwrite an
approved result.

## 6. Processing and ingestion architecture

### Initial batch flow

1. Upload immutable CU-BEMS CSVs to the controlled raw prefix.
2. Run the existing processor in a local or one-off Lambda/container-compatible
   batch environment.
3. Validate source row counts, timestamps, power columns, missing values, and
   SHA-256/source manifest.
4. Write processed outputs to versioned S3 prefixes.
5. Load only approved read-model records into DynamoDB.
6. Fetch Open-Meteo data for the required date range using the existing
   validation behavior.
7. Store Weather separately and generate the hourly AC join/analytics outputs.
8. Publish a processing-run manifest with source versions, row counts, and
   status.

The existing `process_dataset.py` should be reused as the calculation source
in Step 3. It should not be rewritten as part of this architecture step.

### Weather refresh flow

- Historical data: one controlled backfill for the CU-BEMS period.
- Current/future data: optional scheduled refresh only after a live-data
  requirement is defined.
- Validate HTTP response, schema, timezone, duplicate timestamps, expected
  range, and missing values.
- Use a temporary object/version and publish only after validation.
- Preserve `source=Open-Meteo`, request period, coordinates, timezone, and
  retrieval time.

Weather failures must not erase the last valid Weather cache or make Energy API
responses fail. The API should return `weather_context.status` such as
`available`, `stale`, or `unavailable`.

## 7. Database/read-model schema

The database is a serving projection of immutable files, not a replacement for
the raw or processed artifacts.

### 7.1 `energy_daily`

One row per `floor + zone + load_type + date`.

| Field | Type | Notes |
|---|---|---|
| `pk` | string | `ENERGY#Floor1#z1#Light` |
| `sk` | string | `DATE#2018-07-01` |
| `date` | date string | `Asia/Bangkok` local date |
| `floor` | string | `Floor1`, `Floor2` |
| `zone` | string | Source zone only |
| `load_type` | string | `AC`, `Light`, `Plug` |
| `actual_energy_kwh` | decimal/null | Source processed output |
| `expected_energy_kwh` | decimal/null | Same valid observations as actual |
| `excess_energy_kwh` | decimal/null | Positive row-level excess sum |
| `observations` | integer | Non-missing actual observations |
| `missing_observations` | integer | Missing aggregated power observations |
| `partial_component_observations` | integer | Incomplete component rows |
| `dataset_version` | string | Processing manifest/version |

### 7.2 `alert_events`

One row per contiguous Potential Anomaly Event. Point evidence is not a second
alert source.

| Field | Type | Notes |
|---|---|---|
| `pk` | string | `ALERT#CU-EVENT-000001` |
| `sk` | string | `EVENT` |
| `alert_id` | string | Stable event ID |
| `floor`, `zone`, `load_type` | string | Event dimensions |
| `start_timestamp`, `end_timestamp` | timestamp | ISO-8601 with `+07:00` |
| `duration_minutes` | integer | Inclusive duration |
| `evidence_points` | integer | Point evidence count |
| `actual_kw_peak` | decimal | Event peak |
| `expected_kw_at_peak` | decimal | Baseline at peak |
| `excess_kw_peak` | decimal | Peak excess |
| `excess_energy_kwh` | decimal | Event evidence energy |
| `severity` | string | `Low`, `Medium`, `High` |
| `classification` | string | Always `Potential Anomaly` |
| `status` | string | `New`, `Acknowledged`, `Resolved` |
| `reason` | string | Statistical explanation |
| `dataset_version` | string | Source processing version |
| `status_updated_at` | timestamp/null | Backend workflow metadata |

Recommended indexes:

- GSI by `start_timestamp` for recent/list queries.
- GSI by `floor + zone + load_type + start_timestamp`.
- Filterable severity/status fields.

### 7.3 `anomaly_evidence`

Point records from `anomalies.csv` are detail evidence, not dashboard alert
rows. They should be stored in S3 and optionally indexed in DynamoDB only if
the Alert Detail page requires point-level retrieval.

Required relationship:

```text
alert_events.alert_id
  -> anomaly_evidence.event_id or derived event membership
```

The current CSV has point IDs but does not export the grouped event ID.
Before production Alert Detail implementation, the backend must either:

1. create a versioned event-to-point membership projection during ingestion,
   or
2. query evidence by the event's dimensions and contiguous time range with
   strict dataset-version matching.

This is a necessary design issue to resolve before Step 3 implementation.

### 7.4 `weather_hourly`

One row per validated external hourly observation.

| Field | Type | Notes |
|---|---|---|
| `pk` | string | `WEATHER#Asia/Bangkok` |
| `sk` | string | `2018-07-01T00:00:00+07:00` |
| `timestamp` | timestamp | Local timezone-aware timestamp |
| `timezone` | string | `Asia/Bangkok` |
| `temperature_2m_c` | decimal/null | Open-Meteo |
| `relative_humidity_2m_pct` | decimal/null | Open-Meteo |
| `source` | string | `Open-Meteo` |
| `latitude`, `longitude` | decimal | Request coordinates |
| `retrieved_at` | timestamp | Fetch metadata |
| `source_version` | string/null | API/report metadata |

### 7.5 `weather_ac_hourly`

Separate joined context, never a replacement for Energy totals.

| Field | Type | Notes |
|---|---|---|
| `floor`, `zone`, `timestamp` | key fields | AC scope and hour |
| `ac_power_kw` | decimal/null | Hourly mean AC power |
| `valid_minute_count` | integer | Complete source minutes |
| `expected_minute_count` | integer | Normally 60 |
| `missing_minute_count` | integer | Missing minutes |
| `temperature_2m_c` | decimal/null | Joined Weather |
| `relative_humidity_2m_pct` | decimal/null | Joined Weather |
| `join_status` | string | `complete`, `missing_ac`, `missing_weather` |
| `dataset_version` | string | Energy/Weather versions |

### 7.6 `processing_runs`

Stores provenance and validation results:

- run ID, source file hashes, source row counts
- processor version and configuration
- output row counts
- missing/partial counts
- Weather request period and response status
- validation status and error message
- created timestamp

## 8. Backend API contract

The API should use JSON, ISO-8601 timestamps, `Asia/Bangkok`, `null` for
unknown numeric values, pagination, and explicit validation errors.

### Energy and dashboard

- `GET /api/dashboard/summary`
  - Filters: `start_date`, `end_date`, `floor`, `zone`, `load_type`,
    `include_weather`
  - Uses `energy_daily` for Energy totals and distinct event IDs for alert
    counts.
  - Never adds alert event energy to daily Energy totals.
- `GET /api/energy`
  - Returns daily records with filters and pagination.
- `GET /api/analytics/weather-ac`
  - Returns hourly AC/Weather context, correlation summaries, coverage, and
    missing-value metadata.
  - Does not change anomaly outputs.

### Alerts

- `GET /api/alerts`
  - Reads event-level `alert_events`, not every point in
    `anomaly_evidence`.
  - Filters: date, floor, zone, load type, severity, status, pagination,
    sort.
- `GET /api/alerts/{id}`
  - Returns one event, evidence, and optional Weather context.
  - Weather context is returned only when the event has a supported AC scope
    and matching hourly observations; otherwise it is `null` with a reason.
- `PATCH /api/alerts/{id}`
  - Changes workflow status only.
  - Cannot change actual/expected power, severity, timestamps, event energy,
    classification, or source dataset.

### Weather response shape

```json
{
  "status": "available",
  "source": "Open-Meteo",
  "timezone": "Asia/Bangkok",
  "timestamp": "2018-07-01T00:00:00+07:00",
  "temperature_2m_c": 27.1,
  "relative_humidity_2m_pct": 88.0,
  "ac_context": {
    "floor": "Floor2",
    "zone": "z1",
    "ac_power_kw": 45.47,
    "valid_minute_count": 60,
    "missing_minute_count": 0
  }
}
```

The frontend should label this as Weather Context, not as measured indoor
temperature or proof of causation.

## 9. Frontend integration contract

The existing light dashboard structure can remain:

- **Dashboard:** show Energy actual/expected/excess from API; show a compact
  Weather Context card/trend for the selected period and AC scope.
- **Weather & AC Analytics:** show hourly temperature, humidity, AC power,
  correlation values, coverage, and missing-data notes from the analytics API.
- **Alert List:** show event-level Potential Anomalies and status.
- **Alert Detail:** show event metrics, point evidence, and matching Weather
  context with a note that Weather does not alter severity.
- **No Login/Account UI:** preserve the existing no-auth prototype decision
  for local Learner Lab development; add authentication only if deployment
  requirements later demand it.

The frontend must not retain mock Energy/Alert values after API integration.
Loading, empty, stale-weather, and API-error states must be explicit.

## 10. Security, reliability, and cost controls

### Security

- Keep S3 buckets private; expose data through API Gateway/Lambda.
- Use least-privilege IAM for ingestion, API read, and status update paths.
- Do not put API keys in the frontend or repository.
- Current Open-Meteo flow needs no secret; future keyed APIs use Secrets
  Manager or learner-lab-approved environment configuration.
- Validate IDs, dates, enums, page sizes, and status transitions.
- Keep audit fields for status changes.

### Reliability

- Treat Raw and approved processed outputs as immutable/versioned.
- Use idempotent ingestion keyed by dataset version and primary keys.
- Validate Weather timezone, duplicate timestamps, HTTP status, schema, date
  range, and missing values before publishing.
- Use retry with bounded backoff for transient Open-Meteo failures.
- Keep the last valid Weather cache and report `stale` instead of deleting it.
- Return clear `4xx` validation errors and `5xx` request IDs; do not silently
  return success-shaped fallback data.

### Learner Lab cost controls

- Prefer Lambda + API Gateway HTTP API over EC2/ECS/RDS.
- Use S3 lifecycle rules for temporary files and old experiment artifacts.
- Set CloudWatch log retention and avoid verbose per-row logs.
- Use DynamoDB on-demand only for the small serving projection; review usage
  before enabling production-like traffic.
- Avoid frequent Weather polling; cache hourly observations and request only
  missing ranges.
- Add AWS Budgets/alerts if available in the lab account.
- Delete test stacks and temporary buckets after validation.

## 11. Pre-Step 3.7 readiness review

### Ready for Step 3

- CU-BEMS raw and processed data contracts are defined.
- Step 2 formula, severity, and event grouping are stable.
- Alert list source is clearly `alert_events.csv`.
- Weather source, timezone, schema, coverage, and limitations are known.
- Weather API can be exposed as context without changing anomaly logic.
- API endpoints and core response fields are defined.
- AWS services are selected with a low-cost serverless default.

### Must be resolved before or during Backend implementation

1. **Point-to-event relationship:** add a versioned event membership projection
   or implement strict range-based evidence lookup.
2. **Dataset versioning:** define a manifest ID and immutable output path for
   each approved processing run.
3. **Alert status persistence:** decide the allowed transition graph and audit
   retention for `New`, `Acknowledged`, and `Resolved`.
4. **Weather freshness policy:** define how long a failed fetch can leave
   context marked `stale`.
5. **Current vs historical operation:** confirm whether Step 3 serves only the
   2018 dataset or also accepts future live BMS data.
6. **Tariff policy:** keep cost fields null until an approved tariff,
   currency, and billing rule are supplied.
7. **Authentication scope:** confirm whether the local/Learner Lab deployment
   remains intentionally unauthenticated or needs an AWS identity layer.
8. **Exact AWS region and quotas:** verify Learner Lab permissions, supported
   services, and budget before provisioning.

## 12. Final recommendation

Proceed to Step 3 with a read-only Energy/Alert serving API backed by
versioned S3 artifacts and a small DynamoDB read model, using Lambda and API
Gateway HTTP API. Keep Open-Meteo as a separately versioned Weather context
source and expose it in the Dashboard, Weather & AC Analytics, and relevant
Alert Detail responses.

Do not merge Weather into the existing anomaly formula, do not aggregate Alert
event energy into Dashboard Energy totals, and do not label statistical
evidence as a confirmed fault. Resolve the eight readiness items above during
the Step 3 design/implementation review before deploying to AWS.

## Status

Pre-Step 3.7 is complete. This document is the architecture reference for
Step 3. No Backend, Frontend, Database, or AWS implementation was started.
