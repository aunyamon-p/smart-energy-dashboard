# Step 4 Backend Development Report

## Status

Step 4 Backend Development is complete for the local environment. The
implementation uses FastAPI, SQLAlchemy, and SQLite. The SQLAlchemy data
access layer is database-agnostic so the same models and API can be used with
Amazon RDS by changing `DATABASE_URL`; no AWS resources were created.

Raw CU-BEMS files, Step 2 outputs, Weather CSVs, and experiment artifacts were
read only and were not modified.

## Files created

### Application

- `backend/app/config.py` — environment configuration and CORS origins.
- `backend/app/db.py` — SQLAlchemy engine, session, and declarative base.
- `backend/app/models.py` — relational database models and indexes.
- `backend/app/schemas.py` — API response/request validation.
- `backend/app/routes.py` — API endpoints, filters, status update, and cached
  Weather context.
- `backend/app/main.py` — FastAPI application and CORS setup.
- `backend/seed_database.py` — idempotent import of approved real outputs.

### Configuration and tests

- `backend/requirements.txt`
- `backend/.env.example`
- `backend/tests/test_api.py`

## Database schema

SQLite database: `backend/data/smart_energy.db`

The default SQLite URL is resolved from the project root as an absolute path,
so running the importer or API from either the project root or the `backend`
directory uses the same database file. The parent directory is created before
SQLAlchemy opens SQLite. A `DATABASE_URL` environment value remains supported;
non-SQLite URLs, including a future RDS URL, are passed through unchanged.

| Table | Rows loaded | Source |
|---|---:|---|
| `energy_daily` | 3,496 | `processed_energy_daily.csv` |
| `alert_events` | 23,123 | `alert_events.csv` |
| `anomaly_evidence` | 262,890 | `anomalies.csv` |
| `weather_hourly` | 4,416 | `weather_hourly.csv` |
| `weather_ac_hourly` | 26,496 | `weather_energy_hourly.csv` |

Important design rules:

- Daily Energy is the source for Dashboard Energy totals.
- Alert Events are the source for the Alert List.
- Point evidence is separate and returned only in Alert Detail.
- Event energy is never added to daily Energy totals.
- Missing values remain `NULL`; they are not converted to zero.
- Alert status is stored independently from detection fields.
- Alert classification remains `Potential Anomaly`.
- Weather is cached locally and is never fetched from Open-Meteo on each
  dashboard request.

The importer computes a dataset version from the SHA-256 values of the
approved Step 2 and Weather output files. The current imported version is
`e4979c92753a7cde`.

## API endpoints

### `GET /api/dashboard/summary`

Supports `start_date`, `end_date`, `floor`, `zone`, `load_type`, and
`include_weather`. Returns actual, expected, and excess kWh; event counts by
severity; quality counts; and cached Weather metadata.

### `GET /api/energy`

Supports date, Floor, Zone, load type, `page`, and `page_size`. Returns daily
Energy records with pagination.

### `GET /api/alerts`

Supports date, Floor, Zone, load type, severity, status, `page`, `page_size`,
and `sort`. The default `sort=event_time` orders `start_timestamp` descending;
`sort=recently_added` orders `created_at` descending. Sorting is applied before
pagination. Returns event-level alerts, not point-level evidence.

### `GET /api/alerts/{id}`

Returns an Alert Event, all matching point evidence, and cached Weather
context when the event is an AC event with a matching hourly observation.
Non-AC events correctly return no AC Weather context.

### `PATCH /api/alerts/{id}`

Accepts only `New`, `Acknowledged`, or `Resolved`. It changes workflow
metadata only and cannot change detection metrics, severity, timestamps,
classification, or evidence.

### `GET /api/analytics/weather-ac`

Returns cached hourly AC/Weather joined records with date, Floor, and Zone
filters, pagination, coverage fields, and a note that Weather is contextual.

## Validation and error handling

- Invalid `load_type`, severity, status, date range, or pagination returns
  HTTP `422`.
- Unknown Alert IDs return HTTP `404`.
- CORS is configured from `CORS_ORIGINS`.
- Database URL, environment, and page-size limits are configurable through
  environment variables.
- API timestamps are serialized with the dataset timezone offset
  (`+07:00`), even though SQLite stores the local timestamp representation.
- Numeric API values are JSON numbers rather than source CSV strings.

## Installation and run

From the project root:

```powershell
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
python backend\seed_database.py
python -m uvicorn backend.app.main:app --reload
```

The API is then available at `http://localhost:8000`.

For Amazon RDS later, set a SQLAlchemy-compatible `DATABASE_URL` in the
environment and run the same schema/migration strategy. The application code
does not need to be rewritten; production should add formal migrations before
deployment.

## Tests executed

### Automated API tests

```powershell
pytest -q backend\tests
```

Result: **7 passed**.

Covered cases:

- Dashboard summary with real Energy values and cached Weather state.
- Energy filtering and pagination.
- Alert severity filtering.
- Alert Detail evidence linkage and AC Weather context.
- Weather & AC Analytics cached rows.
- Alert status update without changing detection fields.
- Invalid filters, unknown IDs, and missing resources.

### Additional validation

- `python backend\seed_database.py` completed successfully.
- Reseeding is idempotent and loaded the same counts:
  - Energy daily: `3,496`
  - Alert Events: `23,123`
  - Evidence: `262,890`
  - Weather hourly: `4,416`
  - Weather/AC hourly: `26,496`
- Python `compileall` passed for application, importer, and tests.
- Direct smoke calls returned HTTP `200` for Summary, Energy, Alerts, Alert
  Detail, and Weather Analytics.
- PATCH smoke call returned HTTP `200` and changed status to `Resolved`.
- Raw/Step 2/Weather source files retained their existing SHA-256 hashes.
- Seed was run successfully from both the project root and `backend`
  directory; both resolved to `backend/data/smart_energy.db` in the project.

One non-blocking warning was emitted by the installed FastAPI/Starlette test
stack about a future `httpx` compatibility change. It did not affect test
results or endpoint behavior.

## Known limitations before deployment

1. `anomaly_evidence` is linked to an event at read time by matching
   Floor/Zone/load and the event time range. A future production migration
   should add an explicit immutable event-membership table or event ID
   column.
2. SQLite stores timestamps without preserving the timezone type; the API
   serializer restores the documented `Asia/Bangkok` offset. PostgreSQL/RDS
   should use an explicit timezone-aware timestamp policy.
3. There is no tariff, so cost is returned as `null` with
   `cost_status=not_configured`.
4. No authentication was added, consistent with the current local prototype
   scope. Production access control must be decided before public deployment.
5. Formal Alembic migrations should be added before moving to RDS.

## Out of scope and unchanged

- No Frontend integration was started.
- No AWS resource was created or deployed.
- No anomaly formula or Step 2 output was changed.
- No Open-Meteo request is made by API reads.
- No mock Energy, Alert, or Weather data is used.
