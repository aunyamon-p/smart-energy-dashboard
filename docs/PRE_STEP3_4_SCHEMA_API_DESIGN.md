# Pre-Step 3.4: Data Schema and Backend API Design

## Scope and source validation

This document defines the data contract for the future backend. It is a
design-only deliverable: no API, database, frontend, or AWS integration is
implemented in this step.

The design was checked against the current generated outputs:

- `backend/data/processed/processed_energy_daily.csv`: 3,496 daily
  Floor/Zone/load records.
- `backend/data/processed/anomalies.csv`: 262,890 point-level evidence rows.
- `backend/data/processed/alert_events.csv`: 23,123 contiguous potential
  anomaly events.
- `backend/data/processed/data_quality_report.csv`: 49 raw-column quality
  records.
- `backend/data/processed/processing_summary.json`: 5,034,240 processed
  series rows, 42,111 missing power observations, and 2,107 partial-component
  observations.
- `backend/data/external/weather_hourly.csv`: 4,416 hourly Bangkok weather
  rows.
- `backend/data/external/weather_energy_hourly.csv`: 26,496 hourly AC/weather
  join rows, with 26,439 complete temperature/AC pairs.
- `backend/data/external/weather_energy_correlations.csv`: 9 overall,
  Floor-level, and Zone-level correlation records.

The source data covers `Floor1` and `Floor2`, zones `z1` through `z4` where
available, and load types `AC`, `Light`, and `Plug`. AC, Light, and Plug are
instantaneous power in kW. They are not cumulative energy meters.

## Common contract conventions

| Convention | Contract |
|---|---|
| Timestamp | API responses use ISO-8601 with the dataset timezone offset, for example `2018-07-01T00:00:00+07:00`. |
| Date | `YYYY-MM-DD`, interpreted in `Asia/Bangkok`. |
| Floor | String identifier such as `Floor1`; no building identity is invented because the source contains floors only. |
| Zone | String identifier such as `z2`; only zones present in the source are returned. |
| Load type | Enum: `AC`, `Light`, `Plug`. |
| Power | Number in instantaneous kW. |
| Energy | Number in kWh for the stated interval or day. |
| Missing numeric value | JSON `null`; never silently converted to `0`. |
| Status | `New` is currently present in Step 2. Future workflow values may be `Acknowledged` and `Resolved`. |
| Anomaly meaning | `Potential Anomaly`; it is statistical evidence, not a confirmed equipment fault. |
| Cost | `null` until an approved tariff and tariff version are configured. |

The backend should validate query dates, dimensions, enum values, pagination,
and status transitions. Invalid input should return a clear `4xx` response;
the API must not return a success-shaped empty result for invalid input.

## 1. Energy Usage schema

The canonical energy record is derived from
`processed_energy_daily.csv`. It is one record per
`floor + zone + load_type + date`.

| Field | Type | Unit | Meaning | Source/derivation |
|---|---|---|---|---|
| `date` | string | date | Local calendar date | `date` |
| `floor` | string | - | Floor identifier | `floor` |
| `zone` | string | - | Zone identifier | `zone` |
| `load_type` | enum | - | `AC`, `Light`, or `Plug` | `load_type` |
| `actual_energy_kwh` | number or null | kWh | Energy from valid actual power observations | `actual_kwh` summed using `kW * interval_hours` |
| `expected_energy_kwh` | number or null | kWh | Baseline energy over the same valid observations | `expected_kwh` summed; null for missing actual rows |
| `excess_energy_kwh` | number or null | kWh | Positive excess above the baseline | `excess_kwh` summed |
| `observations` | integer | rows | Count of non-missing actual power observations | `actual_kw.count` |
| `missing_observations` | integer | rows | Count of missing aggregated power observations | `actual_kw.isna().sum()` |
| `partial_component_observations` | integer | rows | Rows with incomplete multi-component AC data | `partial_component.sum()` |

`actual_energy_kwh`, `expected_energy_kwh`, and `excess_energy_kwh` must not be
added again from alert records. Alert event energy is evidence for that event,
not an additional building-energy total.

### Energy response example

```json
{
  "data": [
    {
      "date": "2018-07-01",
      "floor": "Floor1",
      "zone": "z1",
      "load_type": "Light",
      "actual_energy_kwh": 165.085,
      "expected_energy_kwh": 155.753,
      "excess_energy_kwh": 10.1694166667,
      "observations": 1440,
      "missing_observations": 0,
      "partial_component_observations": 0
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 1,
    "total": 3496
  },
  "timezone": "Asia/Bangkok"
}
```

## 2. Potential Anomaly / Alert schema

### Alert event (user-facing canonical record)

The API alert list and detail endpoints use
`backend/data/processed/alert_events.csv`. A contiguous run of point
anomalies in one Floor/Zone/load series is one event.

| Field | Type | Unit | Meaning |
|---|---|---|---|
| `alert_id` | string | - | Stable event ID, format currently `CU-EVENT-######` |
| `floor` | string | - | Affected floor |
| `zone` | string | - | Affected zone |
| `load_type` | enum | - | Affected load |
| `start_timestamp` | string | timestamp | First anomalous minute |
| `end_timestamp` | string | timestamp | Last anomalous minute |
| `duration_minutes` | integer | minutes | Inclusive event duration |
| `evidence_points` | integer | rows | Number of point anomalies grouped into the event |
| `actual_kw_peak` | number | kW | Highest actual power excess point in the event |
| `expected_kw_at_peak` | number | kW | Baseline at the selected peak point |
| `excess_kw_peak` | number | kW | `actual_kw_peak - expected_kw_at_peak` |
| `excess_energy_kwh` | number | kWh | Sum of point-level excess energy for this event |
| `severity` | enum | - | `Low`, `Medium`, or `High` |
| `reason` | string | - | Human-readable statistical explanation |
| `status` | enum | - | Current workflow status; currently `New` |
| `classification` | enum | - | Always `Potential Anomaly` for this dataset |

`classification` is an API-level explicit guard against presenting a
statistical alert as a confirmed fault. A confirmed fault requires external
inspection or an approved operational workflow and is not supported by the
current dataset.

### Point evidence (detail-only, not the alert list)

`anomalies.csv` may be exposed under alert detail as `evidence`, or kept
internal. Its `alert_id` is a point-level ID (`CU-######`) and must not be
confused with the event ID. The fields are
`timestamp`, `actual_kw`, `expected_kw`, `excess_kw`, `actual_kwh`,
`expected_kwh`, `excess_kwh`, `severity`, `reason`, `status`, and
`robust_score`, plus Floor/Zone/load dimensions.

### Alert list response example

```json
{
  "data": [
    {
      "alert_id": "CU-EVENT-000001",
      "floor": "Floor1",
      "zone": "z1",
      "load_type": "Plug",
      "start_timestamp": "2018-07-01T00:00:00+07:00",
      "end_timestamp": "2018-07-01T00:42:00+07:00",
      "duration_minutes": 43,
      "evidence_points": 43,
      "actual_kw_peak": 19.34,
      "expected_kw_at_peak": 1.18,
      "excess_kw_peak": 18.16,
      "excess_energy_kwh": 12.665,
      "severity": "High",
      "reason": "Plug usage remained above the weekday/time baseline for 43 consecutive minute(s); peak excess was 18.160 kW.",
      "status": "New",
      "classification": "Potential Anomaly"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 1,
    "total": 23123
  }
}
```

### Alert detail response example

```json
{
  "data": {
    "alert_id": "CU-EVENT-000001",
    "floor": "Floor1",
    "zone": "z1",
    "load_type": "Plug",
    "start_timestamp": "2018-07-01T00:00:00+07:00",
    "end_timestamp": "2018-07-01T00:42:00+07:00",
    "duration_minutes": 43,
    "evidence_points": 43,
    "actual_kw_peak": 19.34,
    "expected_kw_at_peak": 1.18,
    "excess_kw_peak": 18.16,
    "excess_energy_kwh": 12.665,
    "severity": "High",
    "reason": "Plug usage remained above the weekday/time baseline for 43 consecutive minute(s); peak excess was 18.160 kW.",
    "status": "New",
    "classification": "Potential Anomaly",
    "evidence": [
      {
        "timestamp": "2018-07-01T00:00:00+07:00",
        "actual_kw": 18.56,
        "expected_kw": 1.26,
        "excess_kw": 17.3,
        "actual_kwh": 0.3093333333,
        "expected_kwh": 0.021,
        "excess_kwh": 0.2883333333,
        "severity": "High",
        "robust_score": 19.4478168982
      }
    ]
  }
}
```

## 3. Weather Context schema

Weather is an external context dataset and is joined by exact
`Asia/Bangkok` hourly timestamp. It is not an indoor measurement and does not
replace energy usage.

| Field | Type | Unit | Meaning |
|---|---|---|---|
| `timestamp` | string | timestamp | Local hourly weather timestamp |
| `timezone` | string | IANA timezone | Currently `Asia/Bangkok` |
| `temperature_2m_c` | number or null | °C | Open-Meteo temperature at 2 m |
| `relative_humidity_2m_pct` | number or null | %RH | Open-Meteo relative humidity at 2 m |
| `ac_power_kw` | number or null | kW | Hourly mean AC power for the selected Floor/Zone |
| `valid_minute_count` | integer | rows | Complete AC minutes included |
| `expected_minute_count` | integer | rows | Expected minutes, normally 60 |
| `missing_minute_count` | integer | rows | Missing AC minutes |

The `ac_power_kw` and quality fields are present only in the joined
weather-energy dataset. They are not weather observations.

## 4. Dashboard Summary schema

The summary is an API projection, not a new source dataset. It should be
computed from daily energy rows and event rows using the requested date and
dimension filters.

| Field | Type | Unit | Meaning |
|---|---|---|---|
| `period.start` / `period.end` | string | date | Inclusive local reporting period |
| `actual_energy_kwh` | number or null | kWh | Sum of selected daily actual energy |
| `expected_energy_kwh` | number or null | kWh | Sum of selected daily expected energy |
| `excess_energy_kwh` | number or null | kWh | Sum of selected daily excess energy |
| `potential_anomaly_event_count` | integer | events | Count of distinct alert event IDs |
| `severity_counts` | object | events | Counts by Low/Medium/High |
| `missing_observations` | integer | rows | Selected daily missing observations |
| `partial_component_observations` | integer | rows | Selected daily partial AC observations |
| `estimated_cost` | number or null | currency | Null until tariff configuration exists |
| `cost_status` | enum | - | `not_configured` for the current dataset |
| `weather_context` | object or null | - | Coverage metadata, not a causal adjustment |

### Dashboard response example

```json
{
  "data": {
    "period": {
      "start": "2018-07-01",
      "end": "2018-07-01"
    },
    "timezone": "Asia/Bangkok",
    "actual_energy_kwh": 165.085,
    "expected_energy_kwh": 155.753,
    "excess_energy_kwh": 10.1694166667,
    "potential_anomaly_event_count": 2,
    "severity_counts": {
      "High": 2,
      "Medium": 0,
      "Low": 0
    },
    "missing_observations": 0,
    "partial_component_observations": 0,
    "estimated_cost": null,
    "cost_status": "not_configured",
    "weather_context": null
  }
}
```

The example is intentionally a filtered `Floor1/z1/Light` projection for
2018-07-01. It must not be interpreted as the total for all Floors, Zones, or
load types. Weather context is null because this projection is for Light and
the weather join is defined for AC.

## 5. Proposed API endpoints

### `GET /api/dashboard/summary`

Returns the summary projection.

Suggested query parameters:

- `start_date`, `end_date` (required or server-defined reporting default)
- `floor`
- `zone`
- `load_type`
- `include_weather=true|false`

Energy totals come from daily records. Event counts come from distinct event
IDs. The endpoint must not sum `excess_energy_kwh` from both daily and alert
tables.

### `GET /api/energy`

Returns daily Energy Usage records with pagination.

Suggested query parameters:

- `start_date`, `end_date`
- `floor`, `zone`, `load_type`
- `page`, `page_size`

### `GET /api/alerts`

Returns event-level Potential Anomalies from `alert_events.csv`, not every
point in `anomalies.csv`.

Suggested query parameters:

- `start_date`, `end_date`
- `floor`, `zone`, `load_type`
- `severity=High|Medium|Low`
- `status=New|Acknowledged|Resolved`
- `page`, `page_size`
- `sort=start_timestamp|severity|excess_energy_kwh`

### `GET /api/alerts/{id}`

Returns one event record and optional point evidence. `{id}` refers to the
event `alert_id` (`CU-EVENT-######`), never a point-level `CU-######` ID.

### `PATCH /api/alerts/{id}`

Updates workflow metadata only, for example:

```json
{
  "status": "Acknowledged"
}
```

This endpoint must not change actual power, expected power, excess energy,
severity, timestamps, or the anomaly classification. The initial import has
only `New` status; `Acknowledged` and `Resolved` require persistence in the
future backend.

## 6. Data availability and future system fields

### Present in source or generated outputs

- Raw timestamp, Floor, Zone, load columns, and instantaneous kW.
- Daily actual/expected/excess kWh and data-quality counts.
- Point anomaly evidence and grouped event records.
- Robust score, MAD-derived scale, severity, reason, and current `New` status.
- Open-Meteo hourly temperature and relative humidity.
- Hourly AC/weather join quality counts and correlation summaries.

### Must be created by the backend/application

- Stable API serialization and pagination metadata.
- Event detail lookup and relationship from an event to its point evidence.
- Persisted alert workflow status and status-change audit metadata.
- Request validation and consistent error responses.
- Optional tariff configuration and cost calculation, after an approved tariff
  is supplied.
- Database keys/indexes and source-data version metadata.

### Not available in the current dataset

- Electricity tariff, currency cost, demand charges, or billing period rules.
- Occupancy, thermostat settings, operating schedules, equipment status, and
  maintenance confirmation.
- Building-specific outdoor weather sensor measurements.
- A confirmed-fault label or a human verification outcome.
- Authentication/Account data; this project intentionally has no login system.

## 7. Integrity and non-duplication rules

1. Keep raw CSVs immutable and preserve the existing Step 2 formulas.
2. Sum AC components once per Floor/Zone/minute; never sum both component rows
   and an already aggregated AC row.
3. Use daily energy rows as the dashboard energy-total source.
4. Use event rows as the alert source; point anomalies are evidence only.
5. Do not convert missing or partial component readings to zero.
6. Preserve `Potential Anomaly` in every alert response; do not expose
   `Confirmed Fault` without an external verification workflow.
7. Keep weather context separate from energy totals and do not infer causation
   from the reported correlations.
8. Return `null` for cost until a tariff is explicitly configured.

## Example consistency test

The JSON examples in this document were parsed and checked for valid JSON,
required fields, enum values, numeric fields, and the event/energy field names
against the CSV headers. The check passed without modifying any source or
processed output.

## Status

Pre-Step 3.4 is complete. The files are ready as the contract reference for
Step 3 backend implementation. No backend API has been started.
