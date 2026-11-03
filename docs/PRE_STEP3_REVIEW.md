# Pre-Step 3 Review

Review date: 2026-11-03

This review checks the Step 2 processor and generated outputs before backend
development. Raw CSV files were not modified. The only correction made during
this review was to the derived daily Expected Energy calculation described
below.

## Files reviewed

- `backend/process_dataset.py`
- `backend/ANOMALY_DETECTION.md`
- `backend/data/processed/processed_energy_daily.csv`
- `backend/data/processed/anomalies.csv`
- `backend/data/processed/alert_events.csv`
- `backend/data/processed/data_quality_report.csv`
- `backend/data/processed/processing_summary.json`

## 1. Counts and Missing Values

Both source files were read successfully:

| Source | Rows | Columns | Interval |
|---|---:|---:|---:|
| `2018Floor1.csv` | 264,960 | 12 | 60 seconds |
| `2018Floor2.csv` | 264,960 | 37 | 60 seconds |

Derived output counts:

- Processed Floor/Zone/load series rows: 5,034,240
- Daily rows: 3,496
- Point anomaly evidence rows: 262,890
- Grouped alert events: 23,123
- Missing aggregated power observations: 42,111
- Partial-component observations: 2,107
- Partial-component anomaly candidates excluded: 7

The quality report contains 49 raw columns. The three Floor 2 Zone 4
environmental columns are 100% missing. Missing values were not converted to
zero. The derived daily, point-anomaly, and event outputs contain no nulls in
their exported fields.

## 2. kWh Calculation

The processor uses:

```text
kWh = kW * interval_hours
```

The source timestamps are continuous at one-minute intervals, so the normal
interval is `1/60` hour. The first row in each series receives the series
median interval, which is also one minute for these files.

Independent recomputation matched the generated daily output exactly:

- Actual Energy maximum absolute difference: `0.0 kWh`
- Expected Energy maximum absolute difference: `0.0 kWh`
- Excess Energy maximum absolute difference: `0.0 kWh`
- Observation counts and missing counts matched exactly

The row-level identity
`excess_kwh = max(actual_kwh - expected_kwh, 0)` passed within floating-point
precision (`1.42e-14` maximum difference).

## 3. Missing Data and Partial AC Components

AC channels are aggregated by Floor, Zone, and load type. Multiple AC channels
within one Zone are summed once. `sum(min_count=1)` preserves a fully missing
aggregate as missing; it does not turn missing values into zero.

If only some AC components are present, the aggregate is marked
`partial_component=True`. Such observations remain available for quality
reporting and energy totals, but are excluded from anomaly alert creation
because the total load is incomplete.

No evidence was found that Missing Data created ordinary false alerts. The
seven partial-component anomaly candidates were excluded after the prior Step 2
review.

## 4. Anomaly Detection and Event Grouping

Expected Power is the historical median for the same:

- Floor
- Zone
- Load type
- Weekday
- Minute of day

The robust scale is:

```text
max(1.4826 * MAD, 10% * abs(Expected kW), 0.05 kW)
```

Severity is derived from the robust score:

- Low: `>= 3.5` and `< 5`
- Medium: `>= 5` and `< 8`
- High: `>= 8`

Independent checks confirmed that every point anomaly has Actual Power above
Expected Power and meets the Low threshold. Counts are consistent:

| Severity | Point evidence | Alert events |
|---|---:|---:|
| High | 188,300 | 10,310 |
| Medium | 39,702 | 4,639 |
| Low | 34,888 | 8,174 |

The event grouping uses the same Floor/Zone/load series and joins timestamps
only when they are exactly one minute apart. The sum of event evidence points
equals the point anomaly count: `262,890`.

## 5. Expected Power, Excess Energy, and Severity

Point-level checks passed:

- `excess_kw = max(actual_kw - expected_kw, 0)`
- Actual, Expected, and Excess kWh equal their kW values multiplied by the
  interval duration
- No negative energy values were found
- Severity boundaries match the documented robust-score thresholds
- No point anomaly or event has missing exported values

Daily Excess Energy is the sum of row-level Excess Energy. It must not be
calculated as `max(sum(Actual) - sum(Expected), 0)` because individual
minute-level positive and negative deviations can cancel. The generated
output uses the correct row-level sum.

## 6. Long Event Review: 2,281 Minutes

The longest event is:

- Event: `CU-EVENT-021607`
- Floor/Zone/load: `Floor2 / z1 / Light`
- Start: `2018-12-15 16:06`
- End: `2018-12-17 06:06`
- Duration: 2,281 minutes
- Evidence points: 2,281
- Peak Actual: `1.18 kW`
- Peak Expected: `0.01 kW`
- Peak Excess: `1.17 kW`
- Excess Energy: `30.21375 kWh`

Independent inspection of the raw aggregate found exactly 2,281 rows, no
missing values, continuous one-minute timestamps, and Actual Power between
`0.26` and `1.18 kW`. Therefore, the duration is not caused by a timestamp
grouping bug or Missing Data. It represents a persistent deviation from the
weekday/minute baseline. It should be treated as a potential persistent
operational or sensor/channel issue and reviewed with domain context before
being treated as a confirmed fault.

## Issue found and correction

The initial implementation calculated Expected Energy for a row even when the
corresponding Actual Power was missing. This could make daily Actual and
Expected totals use different valid observation counts and produced an
inconsistent comparison in a diagnostic check.

The processor was corrected so Expected Energy is missing whenever Actual Power
is missing. This correction:

- Does not modify raw data
- Does not change anomaly thresholds
- Does not change point anomaly or event counts
- Makes daily Actual and Expected totals comparable
- Makes the daily output match an independent row-level recomputation

## Tests run

Passed:

```powershell
python backend\process_dataset.py --self-test
python -m py_compile backend\process_dataset.py
python backend\process_dataset.py
```

Additional audit checks passed:

- Source row/column counts and one-minute intervals
- Raw SHA-256 hashes unchanged
- Daily output recomputation
- kWh formulas
- Missing and partial-component handling
- Severity boundaries
- Point-to-event evidence totals
- Event duration calculation
- Longest event timestamp continuity

## Files ready for Step 3

The following derived files are ready as inputs for future Backend API work:

- `backend/data/processed/processed_energy_daily.csv`
- `backend/data/processed/anomalies.csv`
- `backend/data/processed/alert_events.csv`
- `backend/data/processed/data_quality_report.csv`
- `backend/data/processed/processing_summary.json`

The processing implementation and its documentation are:

- `backend/process_dataset.py`
- `backend/ANOMALY_DETECTION.md`

No Backend, Frontend, Database, or AWS work was started in this review.
