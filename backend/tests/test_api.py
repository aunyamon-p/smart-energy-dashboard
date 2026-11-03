import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./backend/data/smart_energy.db"

from fastapi.testclient import TestClient

from backend.app.main import app


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
