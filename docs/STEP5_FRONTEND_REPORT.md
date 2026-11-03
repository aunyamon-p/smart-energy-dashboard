# Step 5 Frontend Development & Backend Integration

## Delivered

- Replaced the prototype's mock-driven UI with typed requests to the FastAPI backend.
- Added `frontend/src/api.ts` as the single API client. The base URL is configurable with `VITE_API_BASE_URL` and defaults to `http://127.0.0.1:8000`.
- Connected Overview to dashboard summary, daily energy, and cached weather/AC data.
- Added live filters for date, floor, zone, load type, severity, and status.
- Connected Alert Events to `/api/alerts`, including search and event navigation.
- Connected Alert Detail to `/api/alerts/{id}`, point evidence, weather context, and status PATCH updates.
- Added `/analytics/weather` for cached Weather & AC Analytics.
- Added loading, empty, and error states throughout the API-backed views.
- Removed all production usage of the mock records in `frontend/src/data.ts`.
- Preserved the light dashboard design and the no-login/no-account UI.

## Files

- `frontend/src/App.tsx`: API-backed pages, filters, charts, alert detail, and status workflow.
- `frontend/src/api.ts`: typed API contract and request helpers.
- `frontend/src/vite-env.d.ts`: Vite environment variable typing.
- `frontend/src/styles.css`: states, filters, weather panels, detail layout, and responsive styles.
- `frontend/.env.example`: `VITE_API_BASE_URL` configuration.

## Verification

### Frontend build

`npm run build` passed successfully with TypeScript checking and Vite production bundling.

### Backend integration smoke tests

With the existing FastAPI service at `127.0.0.1:8000`:

- `GET /api/dashboard/summary`: HTTP 200.
- `GET /api/energy`: HTTP 200 and returned database rows.
- `GET /api/alerts`: HTTP 200 and returned alert events.
- `GET /api/analytics/weather-ac`: HTTP 200 and returned cached weather/AC rows.
- `GET /api/alerts/CU-EVENT-000001`: HTTP 200 with 43 evidence points.
- `PATCH /api/alerts/CU-EVENT-000001` to `Acknowledged`, then back to `New`: both updates succeeded.

No raw dataset, Step 2 output, weather CSV, anomaly formula, database schema, or AWS resource was changed.

## Run locally

1. Start the backend from the project root:

   `python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`

2. Start the frontend in another terminal:

   `cd frontend; npm run dev`

3. Open the Vite URL shown in the terminal. Copy `frontend/.env.example` to `frontend/.env` if a different API base URL is needed.

## Remaining limitations

- The production bundle reports the existing Recharts chunk-size warning; it is not a build failure.
- Browser automation was not required for the API contract smoke tests; visual browser testing should be done when the local Vite server is available.
- Weather remains contextual information and does not alter anomaly detection severity.
