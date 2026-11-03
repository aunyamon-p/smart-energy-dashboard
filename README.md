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
