# Smart Energy Intelligence System

ระบบวิเคราะห์การใช้พลังงานจาก CU-BEMS Dataset ด้วย React + Vite + TypeScript และ FastAPI + SQLAlchemy + SQLite

## โครงสร้างโปรเจกต์

```text
smart-energy-dashboard/
├── frontend/   # React + Vite + TypeScript
├── backend/    # FastAPI + SQLAlchemy + SQLite และ Dataset
├── docs/       # รายงานและเอกสารการวิเคราะห์
├── backend/.env.example
├── .gitignore
└── README.md
```

ข้อมูล Raw, Processed, Weather และ SQLite อยู่ภายใต้ `backend/data/` และไม่ถูกแก้ไขจากการแยกโครงสร้างนี้

## ติดตั้ง

### Backend

ต้องใช้ Python 3.13 หรือ compatible version:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

### Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
```

แก้ `frontend\.env` เมื่อต้องการเปลี่ยน Backend URL:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## วิธีรัน Local

เปิด Terminal แยกกัน 2 หน้าต่างจาก Project Root

Terminal 1 — Backend:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

For App Runner, build from the repository root using the included
`Dockerfile`. The container listens on port `8000` and binds to `0.0.0.0`.

### PostgreSQL and migrations

Local development defaults to SQLite. For PostgreSQL, install the backend
requirements and set a SQLAlchemy URL such as:

```text
DATABASE_URL=postgresql+psycopg://user:password@host:5432/database
APP_ENV=production
```

Run migrations before starting a production container:

```powershell
alembic upgrade head
```

The application only calls `create_all()` automatically outside production.

### Historical dataset storage

Local development reads `backend\data\raw\2018Floor1.csv` and
`2018Floor2.csv`. To read the same files from S3, set:

```text
HISTORICAL_DATASET_MODE=s3
HISTORICAL_DATASET_S3_BUCKET=your-bucket
HISTORICAL_DATASET_S3_PREFIX=historical/raw
```

The runtime uses the AWS SDK credential chain; no credentials are stored in
the repository.

### IoT Core and Lambda

The Lambda entrypoint is `backend.lambda_adapter.handler.lambda_handler`.
Configure `INGEST_API_URL` to the App Runner `/api/ingest` URL. An optional
`INGEST_API_TOKEN` is forwarded as a Bearer token. The local simulator is
`tools\mqtt_simulator.py`; install its separate dependency file before use.

The MQTT message body must contain the same JSON fields accepted by
`POST /api/ingest`: `source_id`, `timestamp`, `floor`, `zone`, `load_type`,
`actual_kw`, and optionally `interval_minutes`.

The Overview energy chart keeps using `/api/energy` for historical daily
records and polls `/api/energy/realtime` every five seconds for observations
stored by `/api/ingest`. The live observations are rendered alongside the
historical trend without requiring a browser refresh.

Terminal 2 — Frontend:

```powershell
cd frontend
npm run dev
```

เปิด URL ที่ Vite แสดง โดยปกติคือ `http://localhost:5173`

## คำสั่งตรวจสอบ

Frontend:

```powershell
cd frontend
npm run build
```

Backend:

```powershell
python -m pytest backend\tests
```

การเปลี่ยนโครงสร้างนี้ไม่เปลี่ยน API Endpoint, Schema, Anomaly Detection Logic หรือข้อมูล Dataset เดิม
