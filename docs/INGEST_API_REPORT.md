# Energy Ingest API Report

## Endpoint

`POST /api/ingest`

The endpoint accepts one timestamped energy observation:

- `source_id`: unique source identifier
- `timestamp`: ISO timestamp; naive timestamps are interpreted as `Asia/Bangkok`
- `floor`: `Floor1` or `Floor2`
- `zone`: a CU-BEMS zone
- `load_type`: `AC`, `Light`, or `Plug`
- `actual_kw`: non-negative instantaneous power
- `interval_minutes`: 1–60, default 1

Each observation is stored in the separate `ingested_energy` table. Historical
CSV data and historical Step 2 tables are not modified.

## Detection behavior

The endpoint reuses `backend/process_dataset.py`:

- the existing CU-BEMS raw file for the submitted floor is read;
- the existing `aggregate_power` behavior is used;
- the existing weekday/minute-of-day median baseline is used;
- the existing MAD scale, minimum scale, robust score, and
  `classify_anomaly` severity thresholds are used;
- a detected point creates one evidence row and one `Potential Anomaly` event;
- a normal point creates no alert.

No new severity rule or threshold was introduced.

## Real test payload

```json
{
  "source_id": "TEST-INGEST-20261103-001",
  "timestamp": "2018-07-01T10:00:00+07:00",
  "floor": "Floor1",
  "zone": "z2",
  "load_type": "AC",
  "actual_kw": 457.3,
  "interval_minutes": 1
}
```

The selected CU-BEMS dimension has a historical baseline of `45.73 kW`.
The existing logic calculated:

- Actual energy: `7.6216666667 kWh`
- Expected power: `45.73 kW`
- Excess power: `411.57 kW`
- Robust score: `90.00`
- Severity: `High`
- Alert ID: `INGEST-EVENT-TEST-INGEST-20261103-001`
- Evidence points: `1`

## Verification

- POST returned HTTP `201`.
- Alert detail returned HTTP `200` and one evidence point.
- Alert list returned the new alert.
- Dashboard summary included the new event and High count.
- Negative `actual_kw` returned HTTP `422`.
- Frontend production build passed.
- Frontend Overview and Alerts now poll the backend every 15 seconds, so new
  ingest results appear without a browser refresh.
