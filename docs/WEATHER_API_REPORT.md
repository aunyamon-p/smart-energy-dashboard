# Open-Meteo Historical Weather Integration Report

## Scope

This Pre-Step 3.2 task fetches external historical weather data for Bangkok
only. It does not modify CU-BEMS raw files or Step 2 processed outputs, and it
does not perform an energy/weather correlation.

## Source and request

- API: [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- Endpoint: `https://archive-api.open-meteo.com/v1/archive`
- Location: Bangkok, latitude `13.7563`, longitude `100.5018`
- Timezone: `Asia/Bangkok`
- Date range: `2018-07-01` through `2018-12-31`
- Hourly variables:
  - `temperature_2m`
  - `relative_humidity_2m`

The date range was corrected to match the CU-BEMS Dataset. The request
returned HTTP `200`.

## Output

Script: `backend/fetch_weather.py`

Output: `backend/data/external/weather_hourly.csv`

Columns:

| Column | Meaning |
|---|---|
| `timestamp` | ISO-8601 local timestamp including `+07:00` |
| `timezone` | `Asia/Bangkok` |
| `temperature_2m_c` | Open-Meteo temperature at 2 m, degrees Celsius |
| `relative_humidity_2m_pct` | Open-Meteo relative humidity at 2 m, percent |

## Validation results

- Rows: `4,416`
- Expected rows: `184 days x 24 hours = 4,416`
- First timestamp: `2018-07-01T00:00:00+07:00`
- Last timestamp: `2018-12-31T23:00:00+07:00`
- Timestamp interval: exactly `3,600` seconds
- Timezone values: only `Asia/Bangkok`
- Missing temperature values: `0`
- Missing relative humidity values: `0`
- Temperature range: `20.0` to `34.1` °C
- Relative humidity range: `37.0` to `100.0` %

## Repeatability and integrity

The script was run twice with the same date range. The output SHA-256 hash was
identical:

```text
83718B29EF37CF9AF6D5744CFE82079FE67C3D1DAC6BB2FDB308A2CB4CBCA6A4
```

The script writes through a temporary file and replaces the target output,
which prevents duplicate rows when rerun.

The CU-BEMS raw file hashes remain unchanged:

- `2018Floor1.csv`: `875D0EF9B6D80569F38999E7DECB4743718698563E23856755D87187DC9ABE49`
- `2018Floor2.csv`: `610125FEE377CB06D2CE55B2866279F96FCC1396B2FD9052858E946C27EC85DD`

No Step 2 processing output was written by the weather script.

## Tests run

```powershell
python -c "from pathlib import Path; compile(Path('backend/fetch_weather.py').read_text(encoding='utf-8'), 'backend/fetch_weather.py', 'exec')"
python backend\fetch_weather.py --start-date 2018-07-01 --end-date 2018-12-31
```

The direct syntax compilation passed. The normal `py_compile` command was not
used for the final validation because the existing `backend\__pycache__`
directory denied replacement of its bytecode file; this did not affect script
execution or the no-write syntax check.

## Limitations

- The selected coordinates represent Bangkok city, not a sensor installed at
  the CU-BEMS building.
- Weather data is external hourly data and is not an indoor sensor
  measurement.
- No timezone conversion or interpolation was needed because the API returned
  a complete hourly sequence.
- The weather data has not yet been joined to CU-BEMS energy data.
