# CU-BEMS Anomaly Detection

## Scope

`process_dataset.py` reads the immutable CSV files in `backend/data/raw/` and
writes derived results to `backend/data/processed/`. It does not modify raw
files and does not calculate cost because no electricity tariff was supplied.

## Processing model

1. Parse `Date` as a timestamp and validate uniqueness and interval continuity.
2. Select only columns whose source names match `zN_ACN(kW)`, `zN_Light(kW)`,
   or `zN_Plug(kW)`. Environmental columns are retained in the quality report
   but are not used as power inputs.
3. Group measurements by Floor, Zone, and load type. Multiple AC channels in
   one Zone are summed once. A sum is missing only when every component is
   missing; partial component readings are marked with `partial_component`.
4. Do not replace missing values with zero.
5. Convert power to energy using the measured timestamp interval:

   `kWh = kW * interval_hours`

   With the source's one-minute interval, this is `kW * 1/60`.
   Expected energy is kept missing when the corresponding actual power is
   missing, so daily actual and expected totals use the same valid observations.
6. Produce daily energy aggregates, minute-level anomaly evidence, and
   contiguous alert events.

## Expected usage and detection

Expected power is the historical median for the same Floor, Zone, load type,
weekday, and minute of day. This accounts for recurring weekday/time patterns
and is robust to isolated spikes.

The deviation is scored with a robust z-score:

```text
robust_scale = max(1.4826 * MAD, 10% of |expected_kW|, 0.05 kW)
score = (actual_kW - expected_kW) / robust_scale
```

Only high-side deviations (`actual_kW > expected_kW`) are alerts. A baseline
requires at least three non-missing observations. A zero MAD is handled
without changing data: the score uses a minimum 10% relative or 0.05 kW
scale. This avoids treating harmless changes caused by two-decimal rounding as
infinite anomalies.

Severity:

- Low: score >= 3.5 and < 5
- Medium: score >= 5 and < 8
- High: score >= 8

Point anomalies contain timestamp, Floor, Zone, load type, actual/expected
power, excess power, actual/expected/excess energy, severity, reason, and
`New` status. Consecutive point anomalies in one Floor/Zone/load series are
combined into one alert event. An event contains start/end time, duration,
evidence count, peak values, total excess energy, severity, reason, and `New`
status. Partial-component rows are retained for quality reporting but excluded
from alert creation because the aggregated power is incomplete. Cost is
intentionally absent until a tariff is configured.

## Outputs

- `processed_energy_daily.csv`: daily actual, expected, and excess kWh.
- `anomalies.csv`: high-side anomaly records.
- `alert_events.csv`: contiguous anomaly records grouped into user-facing
  alert events.
- `data_quality_report.csv`: missing, range, negative-value, and all-missing
  checks for every raw column.
- `processing_summary.json`: counts, source checks, thresholds, and limitations.

Run from the project root:

```powershell
python backend\process_dataset.py --self-test
python backend\process_dataset.py
```

The current implementation is historical batch analysis, not real-time
monitoring. Extreme values are flagged by the statistical method but are not
deleted or capped. Physical sensor validation remains necessary before using
alerts as operational decisions.
