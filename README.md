# 1. Smart Energy Intelligence System

## 2. ภาพรวมโครงการ (Project Overview)

เว็บแอปสำหรับติดตามและวิเคราะห์การใช้พลังงานจากข้อมูล CU-BEMS แสดงพลังงานจริงเทียบกับค่าคาดหมาย เหตุการณ์การใช้พลังงานผิดปกติ และข้อมูลสภาพอากาศที่เกี่ยวข้องกับการใช้เครื่องปรับอากาศ

ระบบประกอบด้วย Frontend สำหรับแสดงผล, Backend API สำหรับอ่านและบันทึกข้อมูล และฐานข้อมูลสำหรับข้อมูลวิเคราะห์กับข้อมูล Realtime

## 3. ประโยชน์ของแอปพลิเคชัน (Benefits of the Application)

- เห็นภาพรวมการใช้พลังงานและแนวโน้มรายวัน เพื่อช่วยสังเกตช่วงที่ใช้พลังงานสูง
- ค้นหาและติดตาม Alert ตามวัน อาคาร/ชั้น Zone ประเภทโหลด Severity และ Status ได้
- เปิดดูรายละเอียด Alert พร้อมหลักฐานรายจุดและบริบทสภาพอากาศ เพื่อช่วยตรวจสอบเหตุการณ์
- รับข้อมูลมิเตอร์ Realtime ผ่าน API และแสดงร่วมกับข้อมูล Historical
- ตรวจสอบข้อมูลที่ขาดหายและข้อมูล AC ที่มีองค์ประกอบไม่ครบ โดยไม่แทนค่าข้อมูลที่ไม่มี

ผลวิเคราะห์เป็นข้อมูลประกอบการติดตาม ไม่ใช่หลักฐานยืนยันสาเหตุของการใช้พลังงาน

## 4. คุณสมบัติของระบบ (System Features)

- **Energy Overview:** แสดง Actual Energy, Expected Energy, Potential Events และ Excess Energy พร้อมกราฟแนวโน้ม
- **Historical และ Realtime:** แสดงยอด Historical รายวันและข้อมูลจากมิเตอร์ที่ส่งผ่าน `/api/ingest`
- **Alert Monitoring:** กรอง Severity/Status/ช่วงวัน เรียงตามเวลาเหตุการณ์หรือเวลาที่เพิ่ม และแบ่งหน้า
- **Alert Details:** แสดงช่วงเวลา ระยะเวลา Severity เหตุผล หลักฐานรายจุด และ Weather Context
- **Weather & AC Analytics:** แสดงข้อมูลสภาพอากาศและการใช้ AC เพื่อประกอบการวิเคราะห์
- **Data Quality:** แสดงจำนวนการสังเกตที่ขาดหายและข้อมูล AC ที่ไม่สมบูรณ์
- **Additive Seed:** `backend/seed_database.py` นำเข้าข้อมูลที่ขาด ข้ามข้อมูลซ้ำที่ตรงกัน และยกเลิก Transaction เมื่อพบ Conflict
- **Runtime API Configuration:** Frontend อ่าน Backend URL จาก `frontend/public/config.js` ก่อน แล้วจึงใช้ `VITE_API_BASE_URL` เป็น fallback

## 5. เทคโนโลยีที่ใช้ (Tech Stack)

- **Frontend:** React 18, TypeScript, Vite, React Router, Recharts และ Lucide
- **Backend:** Python, FastAPI, Pydantic และ Uvicorn
- **Data & Database:** Pandas, NumPy, SQLAlchemy และ Alembic; Local ใช้ SQLite และรองรับ PostgreSQL ผ่าน `DATABASE_URL`
- **AWS integrations ที่มีโค้ดรองรับ:**
  - **Amazon S3:** Backend อ่าน Raw CSV ผ่าน `HISTORICAL_DATASET_MODE=s3`, `HISTORICAL_DATASET_S3_BUCKET` และ `HISTORICAL_DATASET_S3_PREFIX`; Seed อ่าน Processed/Weather CSV เมื่อกำหนด `SEED_SOURCE=s3` และ `HISTORICAL_DATASET_S3_BUCKET`
  - **AWS Lambda และ AWS IoT Core:** `backend/lambda_adapter/handler.py` รองรับการรับ IoT event แล้วส่งต่อไปยัง Backend `/api/ingest`

## 6. โครงสร้างโปรเจกต์ (Project Structure)

```text
smart-energy-dashboard/
├── backend/
│   ├── app/                 # FastAPI routes, models, schemas, database และ ingestion
│   ├── alembic/             # Database migrations
│   ├── .env.example         # ตัวอย่าง Backend configuration
│   ├── data/
│   │   ├── raw/             # CU-BEMS source CSV
│   │   ├── processed/       # Daily energy, anomalies, alert events และ quality report
│   │   ├── external/        # Weather และผลวิเคราะห์ที่เกี่ยวข้อง
│   │   └── smart_energy.db  # Local SQLite database
│   ├── lambda_adapter/      # Lambda handler สำหรับส่ง IoT event เข้า API
│   ├── tests/               # Backend API tests
│   ├── seed_database.py     # นำเข้าข้อมูล Processed และ Weather
│   └── requirements.txt
├── frontend/
│   ├── public/config.js     # Runtime Backend API URL
│   ├── src/                 # React UI และ API client
│   ├── .env.example         # Vite API URL fallback
│   ├── index.html
│   └── package.json
├── tools/
│   ├── mqtt_simulator.py    # เครื่องมือจำลองการส่งข้อมูลผ่าน MQTT
│   └── requirements-simulator.txt
├── docs/                    # เอกสารประกอบและรายงานวิเคราะห์
├── Dockerfile
├── alembic.ini
└── README.md
```

## 7. Dataset และแหล่งข้อมูล (Dataset & Data Sources)

- **CU-BEMS Raw:** `backend/data/raw/2018Floor1.csv` และ `2018Floor2.csv` เป็นข้อมูลต้นทางสำหรับสร้างผลวิเคราะห์
- **Processed:** `backend/data/processed/` มี `processed_energy_daily.csv`, `anomalies.csv`, `alert_events.csv`, `data_quality_report.csv` และ `processing_summary.json`
- **Weather:** `backend/data/external/` มีข้อมูลรายชั่วโมง `weather_hourly.csv` และข้อมูลจับคู่ Weather กับพลังงาน AC ใน `weather_energy_hourly.csv` รวมถึงไฟล์ผลวิเคราะห์
- **Local Seed:** อ่าน Processed และ Weather CSV ข้างต้นจากเครื่อง แล้วเพิ่มข้อมูลลงตาราง `energy_daily`, `alert_events`, `anomaly_evidence`, `weather_hourly` และ `weather_ac_hourly`
- **Realtime:** รับข้อมูลที่ `POST /api/ingest` และบันทึกลง `ingested_energy`; ตาราง Realtime ไม่ได้ถูกเติมจาก Historical Seed

ข้อมูล CU-BEMS ครอบคลุม Floor1/Floor2, Zone ตามข้อมูลต้นทาง และโหลด AC, Light, Plug ค่าพลังงานรายวันและข้อมูล AC แสดงตามหน่วยที่ API ส่งกลับ

## 8. ติดตั้งและเริ่มใช้งาน Local (Installation & Local Setup)

คำสั่งต่อไปนี้ใช้ PowerShell จาก Project Root และต้องติดตั้ง Python กับ Node.js/npm ไว้แล้ว

### ติดตั้ง Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

ค่าเริ่มต้นใน `backend/.env.example` ใช้ SQLite ที่ `backend/data/smart_energy.db` และอ่าน Historical Dataset จากไฟล์ Local

### นำเข้าข้อมูลเริ่มต้น

```powershell
python backend\seed_database.py
```

ตรวจผลโดยไม่บันทึกข้อมูล:

```powershell
python backend\seed_database.py --dry-run
```

### เริ่ม Backend

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

เอกสาร API อยู่ที่ `http://127.0.0.1:8000/docs` และ Health Check ที่ `http://127.0.0.1:8000/health`

### เริ่ม Frontend

เปิด Terminal อีกหน้าต่าง:

```powershell
cd frontend
npm install
npm run dev
```

Frontend ใช้ URL จาก `frontend/public/config.js` เป็นหลัก หากต้องการชี้ไป Backend Local ให้กำหนด `window.APP_CONFIG.API_BASE_URL` เป็น `http://127.0.0.1:8000` ในไฟล์นี้ หรือปล่อย URL ว่างเพื่อนำค่า `VITE_API_BASE_URL` มาใช้เป็น fallback จากนั้นเปิด URL ที่ Vite แสดง โดยปกติคือ `http://localhost:5173`

### ตรวจสอบและทดสอบ

```powershell
# จาก Project Root
python -m pytest backend\tests

# จาก frontend
npm run build
```

### การตั้งค่าฐานข้อมูลและ Historical Dataset

- กำหนด `DATABASE_URL` ใน `backend/.env` เมื่อต้องการใช้ฐานข้อมูลอื่น; ค่า Local เริ่มต้นเป็น SQLite
- ใน Production ให้ตั้ง `APP_ENV=production` และใช้ `alembic upgrade head` จาก Project Root เพื่อจัดการ Schema ก่อนใช้งาน แอปจะไม่เรียก `create_all()` อัตโนมัติเมื่ออยู่ใน Production

## 9. API Endpoints

Base URL สำหรับ Local คือ `http://127.0.0.1:8000` ทุก Endpoint ของแอปอยู่ใต้ `/api` ยกเว้น Health Check

| Method | Endpoint | รายละเอียด |
|---|---|---|
| `GET` | `/health` | ตรวจสถานะ Backend |
| `GET` | `/api/dashboard/summary` | สรุปพลังงาน เหตุการณ์ และคุณภาพข้อมูลตามช่วงวันที่/มิติที่เลือก |
| `GET` | `/api/energy` | ข้อมูลพลังงาน Historical รายวัน รองรับ `start_date`, `end_date`, `floor`, `zone`, `load_type`, `page`, `page_size` |
| `GET` | `/api/energy/realtime` | ข้อมูลมิเตอร์ Realtime รองรับ `since`, `floor`, `zone`, `load_type`, `page`, `page_size` |
| `GET` | `/api/alerts` | รายการ Alert รองรับช่วงวันที่ มิติ `severity`, `status`, `sort`, `page`, `page_size` |
| `GET` | `/api/alerts/{alert_id}` | รายละเอียด Alert, หลักฐานรายจุด และ Weather Context |
| `PATCH` | `/api/alerts/{alert_id}` | เปลี่ยน Status โดยส่ง JSON เช่น `{"status":"Acknowledged"}` |
| `POST` | `/api/ingest` | รับข้อมูล Realtime โดยส่ง `source_id`, `timestamp`, `floor`, `zone`, `load_type`, `actual_kw` และ `interval_minutes` (ไม่บังคับ) |
| `GET` | `/api/analytics/weather-ac` | ข้อมูล Weather และ AC ตามช่วงวันที่/มิติ รองรับ Pagination |

Endpoint ที่แบ่งหน้ารายการส่ง `page` เริ่มที่ `1` และ `page_size` ได้สูงสุด `200` โดยค่าตอบกลับมี `pagination` ระบุ `page`, `page_size` และ `total` ค่า timestamp ของ Realtime ส่งเป็น ISO 8601 พร้อม offset เวลาไทย `+07:00`
