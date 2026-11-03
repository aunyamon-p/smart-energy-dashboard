# Weather Impact Experiment: Model A vs Model B

## Scope

This is an isolated experiment. It does not change the CU-BEMS raw files,
Step 2 processed outputs, or the anomaly-detection formula. It evaluates
hourly AC power only; Light and Plug are excluded.

## Input and aggregation

- Raw inputs: `backend/data/raw/2018Floor1.csv` and
  `backend/data/raw/2018Floor2.csv`.
- Weather input: `backend/data/external/weather_hourly.csv`.
- AC components are summed once per Floor/Zone/minute, using the existing
  `process_dataset.py` aggregation behavior.
- Partial AC component minutes are excluded rather than filled with zero.
- AC is then aggregated to the hourly mean kW and joined to weather on exact
  `Asia/Bangkok` timestamps.
- Rows with missing target AC, weather, or historical lag features are excluded
  from both models. No value is imputed.

## Models

Both models use the same fixed design and the same training/test rows:

- Historical AC usage: previous valid hourly AC power (`lag_1h_kw`) and
  same-zone AC power 24 hours earlier (`lag_24h_kw`).
- Floor and Zone categorical indicators.
- Cyclic hour-of-day and day-of-week features.
- Model A: the features above.
- Model B: Model A plus Open-Meteo temperature and relative humidity.

The implementation uses ridge regression with a fixed `alpha=1.0`, solved
with numpy. The regularization value is fixed before evaluating the test set;
it is not selected using test data.

## Leakage-safe evaluation

The 4,416 hourly timestamps are ordered chronologically. The first 70% of
timestamps are Train and the final 30% are Test. The split is by timestamp,
not by random row sampling. Lags use only earlier timestamps, so the first
test row may use the immediately preceding training observation, which is
available at prediction time. Weather is joined at the same timestamp and is
used only as an input feature in Model B.

Metrics are calculated on the identical complete Test rows:

- MAE: mean absolute error in kW.
- RMSE: root mean squared error in kW.
- R²: coefficient of determination.

## Results

The exact results are recorded in:

- `backend/data/external/weather_model_comparison.csv`
- `backend/data/external/weather_model_summary.json`

The actual time split was:

- Train: `2018-07-01 00:00` through `2018-11-06 18:00`
- Test: `2018-11-06 19:00` through `2018-12-31 23:00`
- Train rows: `12,193`
- Test rows: `5,300`
- Complete rows used: `17,493`
- Rows excluded because of missing target or historical lag: `171`
- Missing weather rows: `0`

All metrics below are on the same 5,300 complete Test rows.

| Scope | Model | MAE (kW) | RMSE (kW) | R² |
|---|---|---:|---:|---:|
| Overall | A | 2.93698 | 6.40868 | 0.85272 |
| Overall | B | 2.93131 | 6.40698 | 0.85280 |
| Floor1 | A | 6.88393 | 11.32959 | 0.72136 |
| Floor1 | B | 6.87703 | 11.32460 | 0.72161 |
| Floor2 | A | 1.62133 | 3.46049 | 0.84433 |
| Floor2 | B | 1.61607 | 3.46175 | 0.84422 |
| Floor2/z1 | A | 2.38528 | 5.04886 | 0.82347 |
| Floor2/z1 | B | 2.37475 | 5.05045 | 0.82336 |
| Floor2/z2 | A | 1.53811 | 2.77585 | 0.80541 |
| Floor2/z2 | B | 1.53357 | 2.77772 | 0.80515 |
| Floor2/z4 | A | 0.94059 | 1.65185 | 0.82888 |
| Floor2/z4 | B | 0.93989 | 1.65181 | 0.82889 |

Model B's Overall improvement was only `0.193%` in MAE and `0.026%` in
RMSE; R² changed from `0.85272` to `0.85280`. Floor 1 improved slightly in
all three metrics. Floor 2 improved MAE by `0.324%`, but RMSE worsened by
`0.037%` and R² decreased slightly. At Zone level, MAE improved in every
tested Zone, while RMSE and R² were mixed and changes were very small.

The script prints the Overall, Floor, and Zone metrics when run:

```powershell
python backend\experiment_weather_models.py
```

## Interpretation and recommendation

Weather produced a small out-of-sample MAE improvement in this fixed linear
experiment, but the RMSE and R² changes are near zero and are not uniformly
positive across Floors/Zones. The evidence supports keeping Weather API data
as an optional candidate feature for further validation, especially for
Floor 2/Zone-level models, but not replacing Model A or making Weather a
required production dependency yet.

Weather is considered useful only where Model B improves out-of-sample metrics
on the same test rows. An improvement in one Floor or Zone does not establish
a building-wide benefit. The result is predictive association, not proof that
weather causes the load.

## Limitations

- Only one historical six-month period is available.
- Open-Meteo represents Bangkok coordinates, not necessarily the building's
  exact outdoor sensor location.
- Occupancy, schedules, thermostat settings, solar gains, and equipment status
  are unavailable.
- Missing values are excluded, reducing the evaluation sample.
- The experiment uses one fixed linear model and is not a production model
  selection exercise.
