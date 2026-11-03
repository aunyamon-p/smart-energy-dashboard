# Weather & AC Energy Analysis

## Scope

This Pre-Step 3.3 analysis compares hourly Open-Meteo weather with AC power
from the CU-BEMS Floor 1 and Floor 2 raw files. It does not modify Raw
Dataset, Step 2 outputs, or the existing anomaly-detection formula.

## Method

1. Read `backend/data/external/weather_hourly.csv`.
2. Read both CU-BEMS raw CSV files using the same AC parsing and aggregation
   helpers as `backend/process_dataset.py`.
3. Keep only `AC` columns. `Light` and `Plug` are not included.
4. Sum multiple AC channels inside the same Zone.
5. Exclude minutes where an AC Zone has partial component data rather than
   filling the missing component with zero.
6. Aggregate instantaneous AC power to hourly mean `kW`.
7. Parse both datasets as timezone-aware `Asia/Bangkok` timestamps and perform
   an exact hourly inner join.
8. Calculate Pearson and Spearman correlations using only complete
   temperature/AC pairs.

The Floor `ALL` rows are the sum of available Zone hourly means. They are
provided for Floor-level comparison; Zone rows remain available for the
per-Zone results.

## Data coverage

| Item | Result |
|---|---:|
| Weather rows | 4,416 |
| AC hourly rows before join | 26,496 |
| Joined rows | 26,496 |
| Complete temperature/AC pairs | 26,439 |
| Missing temperature after join | 0 |
| Missing AC hourly values after join | 57 |
| Timestamp range | 2018-07-01 00:00 to 2018-12-31 23:00 |
| Timestamp interval | 1 hour |

AC source details:

- Floor 1: one supported AC Zone (`z2`), 1,518 partial AC minutes excluded.
- Floor 2: three supported AC Zones (`z1`, `z2`, `z4`), 589 partial AC
  minutes excluded.

No values were imputed. A missing hourly AC value means no complete AC minute
was available for that hourly aggregate.

## Correlation results

| Scope | Pair rows | Pearson | Spearman |
|---|---:|---:|---:|
| Overall | 26,439 | 0.142 | 0.190 |
| Floor 1 | 8,796 | -0.156 | -0.089 |
| Floor 1 / z2 | 4,398 | -0.156 | -0.089 |
| Floor 2 | 17,643 | 0.378 | 0.410 |
| Floor 2 / z1 | 4,411 | 0.504 | 0.494 |
| Floor 2 / z2 | 4,410 | 0.443 | 0.413 |
| Floor 2 / z4 | 4,411 | 0.504 | 0.492 |

Pearson measures linear association; Spearman measures monotonic rank
association. Neither establishes causation. The overall association is weakly
positive; Floor 1 is weak/near-zero and negative; Floor 2 is moderate positive.
Floor-level differences indicate that one building-wide temperature coefficient
would hide important operating differences.

## Outputs

- `backend/analyze_weather_energy.py`
- `backend/data/external/weather_energy_hourly.csv`
- `backend/data/external/weather_energy_correlations.csv`
- `backend/data/external/weather_energy_summary.json`
- `backend/data/external/weather_ac_scatter.png`
- `backend/data/external/weather_ac_trend.png`

## Recommendation

Weather should be retained as a candidate feature for a future Expected Usage
model, especially for Floor 2 and its individual Zones. It should not replace
the current baseline or be interpreted as causal without additional features.
Before production use, validate the relationship over time-based holdout
periods and include occupancy, schedules, thermostat settings, and equipment
status if available.

## Limitations

- Open-Meteo data represents Bangkok at the requested coordinates, not an
  indoor sensor at the CU-BEMS building.
- Occupancy, thermostat settings, operating schedules, solar gains, and other
  internal loads are not available.
- Correlation is not causation.
- No missing values were imputed.
- This step does not modify or replace the existing anomaly detector.
