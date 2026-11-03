# CU-BEMS Dataset Analysis

## Scope

This document records the observed structure and data-quality checks for the two
CU-BEMS CSV files currently staged under `backend/data/raw/`. The source files
were copied without modifying their contents. No preprocessing or anomaly
detection has been applied.

## Raw files

| File | Rows | Columns | Time range | Sampling interval |
|---|---:|---:|---|---|
| `2018Floor1.csv` | 264,960 | 12 | 2018-07-01 00:00:00 to 2018-12-31 23:59:00 | 1 minute |
| `2018Floor2.csv` | 264,960 | 37 | 2018-07-01 00:00:00 to 2018-12-31 23:59:00 | 1 minute |

Both files use comma-separated values and have a header row. The timestamp
column is `Date` with format `YYYY-MM-DD HH:mm:ss`.

## Column structure and units

### Common naming pattern

- `z1` through `z4`: zone identifiers encoded in the source column names. The
  exact physical room or area mapping is not available in these CSV files.
- `AC`: air-conditioning power, labelled by the source as `kW`.
- `Light`: lighting power, labelled by the source as `kW`.
- `Plug`: plug-load power, labelled by the source as `kW`.
- `S1(degC)`: temperature, labelled as degrees Celsius.
- `S1(RH%)`: relative humidity, labelled as percent.
- `S1(lux)`: illuminance, labelled as lux.

The source files do not provide a data dictionary. The descriptions above are
based only on the column names; the physical zone mapping and sensor semantics
must be confirmed before production calculations.

### `2018Floor1.csv`

```text
Date
z1_Light(kW)
z1_Plug(kW)
z2_AC1(kW)
z2_AC2(kW)
z2_AC3(kW)
z2_AC4(kW)
z2_Light(kW)
z2_Plug(kW)
z3_Light(kW)
z3_Plug(kW)
z4_Light(kW)
```

### `2018Floor2.csv`

```text
Date, z1_AC1(kW), z1_Light(kW), z1_Plug(kW), z1_S1(degC), z1_S1(RH%), z1_S1(lux),
z2_AC1(kW), z2_AC2(kW), z2_AC3(kW), z2_AC4(kW), z2_AC5(kW), z2_AC6(kW),
z2_AC7(kW), z2_AC8(kW), z2_AC9(kW), z2_AC10(kW), z2_AC11(kW), z2_AC12(kW),
z2_AC13(kW), z2_AC14(kW), z2_Light(kW), z2_Plug(kW), z2_S1(degC),
z2_S1(RH%), z2_S1(lux), z3_Light(kW), z3_Plug(kW), z3_S1(degC),
z3_S1(RH%), z3_S1(lux), z4_AC1(kW), z4_Light(kW), z4_Plug(kW),
z4_S1(degC), z4_S1(RH%), z4_S1(lux)
```

The CSV header remains the authoritative source if a future data delivery
changes the available sensors.

## Missing data

### Floor 1

- `Date`: 0 missing values.
- Most power columns: approximately 0.18% to 0.57% missing.
- `z2_Plug(kW)`: 29,835 missing values (11.260%).
- No column is completely empty.

### Floor 2

- `Date`: 0 missing values.
- Power columns: approximately 0.16% to 0.22% missing.
- Zone 1 to Zone 3 environmental sensors: approximately 61% to 62% missing.
- `z4_S1(degC)`, `z4_S1(RH%)`, `z4_S1(lux)`: 264,960 missing values each (100%).
- `z2_AC11(kW)` and `z4_Plug(kW)` contain observed zero values only when
  present; this has not been interpreted as a faulty sensor.

Missing values are retained as empty fields in the raw files. They have not
been converted to zero, interpolated, or imputed.

## Integrity and timestamp checks

- Both files contain 264,960 data rows.
- No malformed rows were found.
- No duplicate timestamps were found.
- Timestamps are continuous at one-minute intervals.
- No negative numeric values were found.
- The copied files have the same SHA-256 hashes as their source files:
  - `2018Floor1.csv`: `875D0EF9B6D80569F38999E7DECB4743718698563E23856755D87187DC9ABE49`
  - `2018Floor2.csv`: `610125FEE377CB06D2CE55B2866279F96FCC1396B2FD9052858E946C27EC85DD`

## Precautions for later processing

1. Treat the raw files as immutable input.
2. Parse `Date` explicitly and confirm timezone assumptions before aggregation.
3. Keep missing values as null/missing in processed data; do not silently replace
   them with zero.
4. Exclude or explicitly flag sensors that are 100% missing.
5. Confirm whether the `kW` values are instantaneous power readings before
   converting them to energy (`kWh`).
6. Confirm the physical mapping of `z1` to `z4` and the electricity tariff
   before producing dashboard labels or cost estimates.
7. Investigate extreme values as possible sensor/data-quality issues before
   treating them as behavioural anomalies.

## Step 1 status

Dataset staging and read verification are complete. Processing and anomaly
detection are implemented separately in `backend/process_dataset.py`; this
document remains the raw-dataset analysis and does not describe derived
results.
