import os
from pathlib import Path

import shutil
import tempfile
import atexit
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PRODUCTION_DATABASE = Path(__file__).resolve().parents[1] / "data" / "smart_energy.db"
TEST_DIRECTORY = Path(tempfile.mkdtemp(prefix="smart-energy-tests-"))
TEST_DATABASE = TEST_DIRECTORY / "smart_energy_test.db"
shutil.copy2(PRODUCTION_DATABASE, TEST_DATABASE)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"

from backend.app import ingestion
from backend.app.db import get_db
from backend.app.main import app


test_engine = create_engine(
    f"sqlite:///{TEST_DATABASE.as_posix()}",
    connect_args={"check_same_thread": False},
    future=True,
)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


@atexit.register
def cleanup_test_database():
    app.dependency_overrides.clear()
    test_engine.dispose()
    shutil.rmtree(TEST_DIRECTORY, ignore_errors=True)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_summary_uses_real_counts_and_weather_cache():
    response = client.get("/api/dashboard/summary", params={"start_date": "2018-07-01", "end_date": "2018-07-01", "floor": "Floor1", "zone": "z1", "load_type": "Light"})
    assert response.status_code == 200
    body = response.json()
    assert body["actual_energy_kwh"] == 165.085
    assert body["weather_context"]["status"] == "cached"
    assert body["cost_status"] == "not_configured"


def test_energy_filters_and_pagination():
    response = client.get("/api/energy", params={"floor": "Floor1", "zone": "z1", "load_type": "Light", "page_size": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 184
    assert len(body["data"]) == 1


def test_alert_list_filters():
    response = client.get("/api/alerts", params={"severity": "High", "page_size": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 10310
    assert all(row["severity"] == "High" for row in body["data"])


def test_alert_sorting_happens_before_pagination():
    event_time_page = client.get("/api/alerts", params={"sort": "event_time", "page": 1, "page_size": 2})
    recently_added_page = client.get("/api/alerts", params={"sort": "recently_added", "page": 1, "page_size": 2})
    assert event_time_page.status_code == 200
    assert recently_added_page.status_code == 200
    event_time_rows = event_time_page.json()["data"]
    recently_added_rows = recently_added_page.json()["data"]
    assert event_time_rows[0]["start_timestamp"] >= event_time_rows[1]["start_timestamp"]
    assert recently_added_rows[0]["created_at"] >= recently_added_rows[1]["created_at"]

    second_page = client.get("/api/alerts", params={"sort": "event_time", "page": 2, "page_size": 2})
    assert second_page.status_code == 200
    assert not {row["alert_id"] for row in event_time_rows}.intersection(
        row["alert_id"] for row in second_page.json()["data"]
    )


def test_ingest_normal_observation_creates_no_alert():
    response = client.post(
        "/api/ingest",
        json={
            "source_id": "AUTOMATED-TEST-NORMAL-001",
            "timestamp": "2026-11-01T10:01:00+07:00",
            "floor": "Floor1",
            "zone": "z2",
            "load_type": "AC",
            "actual_kw": 45.73,
            "interval_minutes": 1,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["anomaly_detected"] is False
    assert body["alert_id"] is None


def test_realtime_energy_includes_ingested_observation():
    source_id = "AUTOMATED-TEST-REALTIME-001"
    response = client.post(
        "/api/ingest",
        json={
            "source_id": source_id,
            "timestamp": "2026-11-07T22:07:00+07:00",
            "floor": "Floor1",
            "zone": "z2",
            "load_type": "AC",
            "actual_kw": 90.0,
            "interval_minutes": 1,
        },
    )
    assert response.status_code == 201
    realtime = client.get(
        "/api/energy/realtime",
        params={"floor": "Floor1", "zone": "z2", "load_type": "AC"},
    )
    assert realtime.status_code == 200
    body = realtime.json()
    row = next(item for item in body["data"] if item["source_id"] == source_id)
    assert row["actual_kw"] == 90.0
    assert row["actual_kwh"] == 1.5
    assert row["anomaly_detected"] is True


def test_ingest_reuses_prepared_floor_baseline(monkeypatch):
    ingestion._historical_baseline.cache_clear()
    original_read_csv = ingestion.pd.read_csv
    reads = []

    def tracked_read_csv(*args, **kwargs):
        reads.append(args[0])
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(ingestion.pd, "read_csv", tracked_read_csv)
    ingestion.evaluate_observation(
        datetime.fromisoformat("2026-11-01T10:01:00+07:00"),
        "Floor1",
        "z2",
        "AC",
        45.73,
        1,
    )
    ingestion.evaluate_observation(
        datetime.fromisoformat("2026-11-01T10:02:00+07:00"),
        "Floor1",
        "z2",
        "AC",
        45.73,
        1,
    )
    assert reads == [ingestion.RAW_DIR / "2018Floor1.csv"]


def test_ingest_anomaly_creates_alert_and_evidence():
    response = client.post(
        "/api/ingest",
        json={
            "source_id": "AUTOMATED-TEST-ANOMALY-001",
            "timestamp": "2026-11-02T10:00:00+07:00",
            "floor": "Floor1",
            "zone": "z2",
            "load_type": "AC",
            "actual_kw": 457.3,
            "interval_minutes": 1,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["anomaly_detected"] is True
    assert body["alert_id"] == "INGEST-EVENT-AUTOMATED-TEST-ANOMALY-001"
    detail = client.get(f"/api/alerts/{body['alert_id']}")
    assert detail.status_code == 200
    assert len(detail.json()["data"]["evidence"]) == 1
    assert detail.json()["data"]["created_at"] is not None


def test_ingest_duplicate_source_id_returns_conflict():
    response = client.post(
        "/api/ingest",
        json={
            "source_id": "AUTOMATED-TEST-DUPLICATE-001",
            "timestamp": "2026-11-01T10:01:00+07:00",
            "floor": "Floor1",
            "zone": "z2",
            "load_type": "AC",
            "actual_kw": 45.73,
            "interval_minutes": 1,
        },
    )
    assert response.status_code == 201
    duplicate = client.post(
        "/api/ingest",
        json={
            "source_id": "AUTOMATED-TEST-DUPLICATE-001",
            "timestamp": "2026-11-01T10:01:00+07:00",
            "floor": "Floor1",
            "zone": "z2",
            "load_type": "AC",
            "actual_kw": 45.73,
            "interval_minutes": 1,
        },
    )
    assert duplicate.status_code == 409


def test_ingest_negative_actual_returns_unprocessable_entity():
    response = client.post(
        "/api/ingest",
        json={
            "source_id": "AUTOMATED-TEST-NEGATIVE-001",
            "timestamp": "2026-11-03T10:00:00+07:00",
            "floor": "Floor1",
            "zone": "z2",
            "load_type": "AC",
            "actual_kw": -1,
            "interval_minutes": 1,
        },
    )
    assert response.status_code == 422


def test_alert_detail_contains_evidence_and_weather_for_ac():
    response = client.get("/api/alerts/CU-EVENT-000012")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["classification"] == "Potential Anomaly"
    assert len(body["evidence"]) == body["evidence_points"]
    assert body["weather_context"]["source"] == "Open-Meteo"


def test_weather_analytics_uses_cached_rows():
    response = client.get("/api/analytics/weather-ac", params={"floor": "Floor2", "zone": "z2", "page_size": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "Open-Meteo"
    assert body["pagination"]["total"] == 4416
    assert body["data"][0]["temperature_2m_c"] == 27.1


def test_patch_status_does_not_change_detection_fields():
    before = client.get("/api/alerts/CU-EVENT-000001").json()["data"]
    response = client.patch("/api/alerts/CU-EVENT-000001", json={"status": "Acknowledged"})
    assert response.status_code == 200
    assert response.json()["status"] == "Acknowledged"
    after = client.get("/api/alerts/CU-EVENT-000001").json()["data"]
    assert after["status"] == "Acknowledged"
    for field in ("actual_kw_peak", "expected_kw_at_peak", "severity", "classification", "evidence_points"):
        assert after[field] == before[field]


def test_validation_and_not_found_errors():
    assert client.get("/api/energy", params={"load_type": "Unknown"}).status_code == 422
    assert client.get("/api/alerts", params={"severity": "Unknown"}).status_code == 422
    assert client.get("/api/alerts/not-found").status_code == 404
    assert client.patch("/api/alerts/not-found", json={"status": "Resolved"}).status_code == 404
