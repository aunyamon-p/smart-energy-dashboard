# Alert Event Sorting

The Alerts page sends sorting to `GET /api/alerts` before pagination:

- `sort=event_time` (default): `start_timestamp DESC`, then `alert_id DESC`
- `sort=recently_added`: `created_at DESC`, then `alert_id DESC`

`created_at` was added with an additive SQLite schema migration. Existing rows
are preserved; newly ingested events receive the database creation timestamp.
The anomaly detection logic and source data are unchanged.

Verification with the existing test ingest event:

- Event Time top row: `CU-EVENT-023123`, with the latest event timestamp.
- Recently Added top row: `INGEST-EVENT-TEST-INGEST-20261103-001`, with its
  latest `created_at` timestamp.
- Invalid sort returns HTTP 422.
- Backend tests: 7 passed.
- Frontend production build: passed.

## Post-migration verification

- Before this verification, the database contained `23,124` Alert Events and
  every existing row had a non-null `created_at`.
- Two new High anomalies were submitted through `POST /api/ingest` during
  verification (`...-002` and `...-003`). No SQL was used to set their
  timestamps.
- After verification, the database contains `23,126` Alert Events and
  `created_at` NULL count remains `0`.
- The latest ingest event appears first with `sort=recently_added`, including
  `page_size=1`.
- Event Time ordering, filters, and multi-page pagination return the expected
  rows. The frontend keeps the existing 15-second Alerts polling and filter
  state.
