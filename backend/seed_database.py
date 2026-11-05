"""Load approved Step 2 and Weather outputs into the local SQLAlchemy database."""

from __future__ import annotations

import hashlib
import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.db import Base, SessionLocal, engine
from backend.app.models import AlertEvent, AnomalyEvidence, EnergyDaily, WeatherAcHourly, WeatherHourly


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "backend" / "data" / "processed"
EXTERNAL = ROOT / "backend" / "data" / "external"
TIMEZONE = "Asia/Bangkok"


def file_hashes() -> dict[str, str]:
    paths = [
        PROCESSED / "processed_energy_daily.csv",
        PROCESSED / "anomalies.csv",
        PROCESSED / "alert_events.csv",
        PROCESSED / "processing_summary.json",
        EXTERNAL / "weather_hourly.csv",
        EXTERNAL / "weather_energy_hourly.csv",
    ]
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def version() -> str:
    digest = hashlib.sha256()
    for name, value in sorted(file_hashes().items()):
        digest.update(name.encode())
        digest.update(value.encode())
    return digest.hexdigest()[:16]


def timestamp_series(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, utc=True).dt.tz_convert(TIMEZONE).dt.tz_localize(None)


def decimal_value(value):
    return None if pd.isna(value) else value


def seed(replace: bool = False) -> dict[str, int | str]:
    Base.metadata.create_all(bind=engine)
    dataset_version = version()
    daily = pd.read_csv(PROCESSED / "processed_energy_daily.csv")
    events = pd.read_csv(PROCESSED / "alert_events.csv")
    evidence = pd.read_csv(PROCESSED / "anomalies.csv")
    weather = pd.read_csv(EXTERNAL / "weather_hourly.csv")
    weather_ac = pd.read_csv(EXTERNAL / "weather_energy_hourly.csv")
    events["start_timestamp"] = timestamp_series(events["start_timestamp"])
    events["end_timestamp"] = timestamp_series(events["end_timestamp"])
    evidence["timestamp"] = timestamp_series(evidence["timestamp"])
    weather["timestamp"] = timestamp_series(weather["timestamp"])
    weather_ac["timestamp"] = timestamp_series(weather_ac["timestamp"])

    with SessionLocal.begin() as db:
        existing_version = db.scalar(
            select(EnergyDaily.dataset_version)
            .where(EnergyDaily.dataset_version.is_not(None))
            .limit(1)
        )
        if existing_version and existing_version != dataset_version and not replace:
            raise RuntimeError(
                "Database already contains a different dataset version; "
                "rerun with --replace only after taking a backup"
            )
        if existing_version == dataset_version and not replace:
            return {
                "dataset_version": dataset_version,
                "energy_daily": db.query(EnergyDaily).count(),
                "alert_events": db.query(AlertEvent).count(),
                "anomaly_evidence": db.query(AnomalyEvidence).count(),
                "weather_hourly": db.query(WeatherHourly).count(),
                "weather_ac_hourly": db.query(WeatherAcHourly).count(),
            }
        if replace:
            db.query(AnomalyEvidence).delete()
            db.query(AlertEvent).delete()
            db.query(EnergyDaily).delete()
            db.query(WeatherAcHourly).delete()
            db.query(WeatherHourly).delete()
        db.bulk_insert_mappings(
            EnergyDaily,
            [
                {
                    **row,
                    "date": pd.to_datetime(row["date"]).date(),
                    "dataset_version": dataset_version,
                    "actual_energy_kwh": decimal_value(row["actual_energy_kwh"]),
                    "expected_energy_kwh": decimal_value(row["expected_energy_kwh"]),
                    "excess_energy_kwh": decimal_value(row["excess_energy_kwh"]),
                }
                for row in daily.to_dict("records")
            ],
        )
        db.bulk_insert_mappings(
            AlertEvent,
            [
                {
                    **row,
                    "dataset_version": dataset_version,
                    "status_updated_at": None,
                }
                for row in events.to_dict("records")
            ],
        )
        db.bulk_insert_mappings(
            AnomalyEvidence,
            [
                {
                    "point_alert_id": row["alert_id"],
                    "floor": row["floor"],
                    "zone": row["zone"],
                    "load_type": row["load_type"],
                    "timestamp": row["timestamp"],
                    "actual_kw": row["actual_kw"],
                    "expected_kw": row["expected_kw"],
                    "excess_kw": row["excess_kw"],
                    "actual_kwh": row["actual_kwh"],
                    "expected_kwh": row["expected_kwh"],
                    "excess_kwh": row["excess_kwh"],
                    "severity": row["severity"],
                    "reason": row["reason"],
                    "status": row["status"],
                    "robust_score": row["robust_score"],
                    "dataset_version": dataset_version,
                }
                for row in evidence.to_dict("records")
            ],
        )
        db.bulk_insert_mappings(
            WeatherHourly,
            [
                {
                    "timestamp": row["timestamp"],
                    "timezone": row["timezone"],
                    "temperature_2m_c": decimal_value(row["temperature_2m_c"]),
                    "relative_humidity_2m_pct": decimal_value(row["relative_humidity_2m_pct"]),
                    "source": "Open-Meteo",
                    "source_version": dataset_version,
                }
                for row in weather.to_dict("records")
            ],
        )
        db.bulk_insert_mappings(
            WeatherAcHourly,
            [
                {
                    "floor": row["floor"],
                    "zone": row["zone"],
                    "timestamp": row["timestamp"],
                    "ac_power_kw": decimal_value(row["ac_power_kw"]),
                    "valid_minute_count": decimal_value(row["valid_minute_count"]),
                    "expected_minute_count": decimal_value(row["expected_minute_count"]),
                    "missing_minute_count": decimal_value(row["missing_minute_count"]),
                    "temperature_2m_c": decimal_value(row["temperature_2m_c"]),
                    "relative_humidity_2m_pct": decimal_value(row["relative_humidity_2m_pct"]),
                    "join_status": (
                        "complete"
                        if pd.notna(row["ac_power_kw"])
                        and pd.notna(row["temperature_2m_c"])
                        else "missing_ac"
                        if pd.isna(row["ac_power_kw"])
                        else "missing_weather"
                    ),
                    "dataset_version": dataset_version,
                }
                for row in weather_ac.to_dict("records")
            ],
        )
    return {
        "dataset_version": dataset_version,
        "energy_daily": len(daily),
        "alert_events": len(events),
        "anomaly_evidence": len(evidence),
        "weather_hourly": len(weather),
        "weather_ac_hourly": len(weather_ac),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace imported historical tables after a backup; never affects ingested_energy",
    )
    print(seed(replace=parser.parse_args().replace))
