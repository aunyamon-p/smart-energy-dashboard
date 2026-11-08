"""Import approved historical and weather outputs from S3 without changing existing rows."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.db import SessionLocal
from backend.app.models import AlertEvent, AnomalyEvidence, EnergyDaily, WeatherAcHourly, WeatherHourly


TIMEZONE = "Asia/Bangkok"
REQUIRED_FILES = (
    "processed/processed_energy_daily.csv",
    "processed/anomalies.csv",
    "processed/alert_events.csv",
    "external/weather_hourly.csv",
    "external/weather_energy_hourly.csv",
    "processed/processing_summary.json",
)


def s3_settings() -> tuple[str, str]:
    bucket = os.environ.get("SEED_S3_BUCKET") or os.environ.get("HISTORICAL_DATASET_S3_BUCKET")
    if not bucket:
        raise RuntimeError("SEED_S3_BUCKET is required")
    prefix = os.environ.get("SEED_S3_PREFIX", "").strip("/")
    return bucket, prefix


def object_key(prefix: str, relative_key: str) -> str:
    return f"{prefix}/{relative_key}" if prefix else relative_key


def read_objects(bucket: str, prefix: str) -> dict[str, bytes]:
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError as error:
        raise RuntimeError("boto3 is required to read S3") from error

    try:
        client = boto3.client("s3")
    except (BotoCoreError, ClientError) as error:
        raise RuntimeError("Unable to create the S3 client") from error
    objects: dict[str, bytes] = {}
    for relative_key in REQUIRED_FILES:
        key = object_key(prefix, relative_key)
        try:
            response = client.get_object(Bucket=bucket, Key=key)
        except (BotoCoreError, ClientError) as error:
            raise RuntimeError(f"Unable to read required S3 object: {relative_key}") from error
        try:
            objects[relative_key] = response["Body"].read()
        except (BotoCoreError, ClientError, KeyError) as error:
            raise RuntimeError(f"Unable to read required S3 object: {relative_key}") from error
    return objects


def timestamp_series(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, utc=True).dt.tz_convert(TIMEZONE).dt.tz_localize(None)


def required_columns(frame: pd.DataFrame, columns: set[str], filename: str) -> None:
    missing = columns.difference(frame.columns)
    if missing:
        raise ValueError(f"{filename} is missing columns: {sorted(missing)}")


def parse_objects(objects: dict[str, bytes]) -> tuple[dict[str, pd.DataFrame], str]:
    frames = {
        key: pd.read_csv(io.BytesIO(value))
        for key, value in objects.items()
        if key.endswith(".csv")
    }
    required_columns(
        frames["processed/processed_energy_daily.csv"],
        {
            "floor", "zone", "load_type", "date", "actual_energy_kwh",
            "expected_energy_kwh", "excess_energy_kwh", "observations",
            "missing_observations", "partial_component_observations",
        },
        "processed_energy_daily.csv",
    )
    required_columns(
        frames["processed/anomalies.csv"],
        {
            "alert_id", "timestamp", "floor", "zone", "load_type", "actual_kw",
            "expected_kw", "excess_kw", "actual_kwh", "expected_kwh",
            "excess_kwh", "severity", "reason", "status", "robust_score",
        },
        "anomalies.csv",
    )
    required_columns(
        frames["processed/alert_events.csv"],
        {
            "alert_id", "floor", "zone", "load_type", "start_timestamp",
            "end_timestamp", "duration_minutes", "evidence_points",
            "actual_kw_peak", "expected_kw_at_peak", "excess_kw_peak",
            "excess_energy_kwh", "severity", "reason", "status",
        },
        "alert_events.csv",
    )
    required_columns(
        frames["external/weather_hourly.csv"],
        {"timestamp", "timezone", "temperature_2m_c", "relative_humidity_2m_pct"},
        "weather_hourly.csv",
    )
    required_columns(
        frames["external/weather_energy_hourly.csv"],
        {
            "floor", "zone", "timestamp", "ac_power_kw", "valid_minute_count",
            "expected_minute_count", "missing_minute_count", "temperature_2m_c",
            "relative_humidity_2m_pct",
        },
        "weather_energy_hourly.csv",
    )
    summary = json.loads(objects["processed/processing_summary.json"].decode("utf-8"))
    if not isinstance(summary, dict):
        raise ValueError("processing_summary.json must contain a JSON object")
    digest = hashlib.sha256()
    for key in sorted(objects):
        digest.update(key.encode())
        digest.update(hashlib.sha256(objects[key]).hexdigest().encode())
    return frames, digest.hexdigest()[:16]


def clean(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().replace(tzinfo=None)
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return value
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (float, int)):
        return Decimal(str(value))
    return value


def same_value(left: Any, right: Any) -> bool:
    left = clean(left)
    right = clean(right)
    if left is None or right is None:
        return left is right
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        return abs(Decimal(str(left)) - Decimal(str(right))) <= Decimal("0.00000001")
    return left == right


def validate_source_keys(frame: pd.DataFrame, key_fields: tuple[str, ...], filename: str) -> None:
    keys = frame.loc[:, list(key_fields)].astype(str)
    duplicates = keys[keys.duplicated(keep=False)]
    if not duplicates.empty:
        sample = duplicates.iloc[0].to_dict()
        raise ValueError(f"{filename} contains duplicate unique key: {sample}")


def insert_if_missing(
    db,
    model,
    values: dict[str, Any],
    key_fields: tuple[str, ...],
    protected_prefix: str | None = None,
) -> str:
    identifier = values.get(key_fields[0])
    if protected_prefix and isinstance(identifier, str) and identifier.startswith(protected_prefix):
        raise ValueError(f"Refusing to import protected realtime identifier: {identifier}")
    conditions = [getattr(model, field) == values[field] for field in key_fields]
    existing = db.scalar(select(model).where(and_(*conditions)))
    if existing is None:
        db.add(model(**values))
        return "insert"
    for field, value in values.items():
        if not same_value(getattr(existing, field), value):
            raise RuntimeError(
                f"Conflict in {model.__tablename__} key {identifier!r}: field {field!r} differs"
            )
    return "skip"


def source_rows(frames: dict[str, pd.DataFrame], dataset_version: str) -> list[tuple[str, Any, tuple[str, ...], dict[str, Any]]]:
    daily = frames["processed/processed_energy_daily.csv"]
    events = frames["processed/alert_events.csv"].copy()
    evidence = frames["processed/anomalies.csv"].copy()
    weather = frames["external/weather_hourly.csv"].copy()
    weather_ac = frames["external/weather_energy_hourly.csv"].copy()
    events[["start_timestamp", "end_timestamp"]] = events[["start_timestamp", "end_timestamp"]].apply(timestamp_series)
    evidence["timestamp"] = timestamp_series(evidence["timestamp"])
    weather["timestamp"] = timestamp_series(weather["timestamp"])
    weather_ac["timestamp"] = timestamp_series(weather_ac["timestamp"])
    validate_source_keys(daily, ("floor", "zone", "load_type", "date"), "processed_energy_daily.csv")
    validate_source_keys(events, ("alert_id",), "alert_events.csv")
    validate_source_keys(evidence, ("alert_id",), "anomalies.csv")
    validate_source_keys(weather, ("timestamp",), "weather_hourly.csv")
    validate_source_keys(weather_ac, ("floor", "zone", "timestamp"), "weather_energy_hourly.csv")
    rows: list[tuple[str, Any, tuple[str, ...], dict[str, Any]]] = []

    for row in daily.to_dict("records"):
        rows.append(("energy_daily", EnergyDaily, ("floor", "zone", "load_type", "date"), {
            "floor": row["floor"], "zone": row["zone"], "load_type": row["load_type"],
            "date": pd.to_datetime(row["date"]).date(), "actual_energy_kwh": row["actual_energy_kwh"],
            "expected_energy_kwh": row["expected_energy_kwh"], "excess_energy_kwh": row["excess_energy_kwh"],
            "observations": row["observations"], "missing_observations": row["missing_observations"],
            "partial_component_observations": row["partial_component_observations"],
            "dataset_version": dataset_version,
        }))
    for row in events.to_dict("records"):
        rows.append(("alert_events", AlertEvent, ("alert_id",), {
            "alert_id": row["alert_id"], "floor": row["floor"], "zone": row["zone"], "load_type": row["load_type"],
            "start_timestamp": row["start_timestamp"], "end_timestamp": row["end_timestamp"],
            "duration_minutes": row["duration_minutes"], "evidence_points": row["evidence_points"],
            "actual_kw_peak": row["actual_kw_peak"], "expected_kw_at_peak": row["expected_kw_at_peak"],
            "excess_kw_peak": row["excess_kw_peak"], "excess_energy_kwh": row["excess_energy_kwh"],
            "severity": row["severity"], "reason": row["reason"], "status": row["status"],
            "dataset_version": dataset_version, "status_updated_at": None,
        }))
    for row in evidence.to_dict("records"):
        rows.append(("anomaly_evidence", AnomalyEvidence, ("point_alert_id",), {
            "point_alert_id": row["alert_id"], "floor": row["floor"], "zone": row["zone"],
            "load_type": row["load_type"], "timestamp": row["timestamp"], "actual_kw": row["actual_kw"],
            "expected_kw": row["expected_kw"], "excess_kw": row["excess_kw"], "actual_kwh": row["actual_kwh"],
            "expected_kwh": row["expected_kwh"], "excess_kwh": row["excess_kwh"], "severity": row["severity"],
            "reason": row["reason"], "status": row["status"], "robust_score": row["robust_score"],
            "dataset_version": dataset_version,
        }))
    for row in weather.to_dict("records"):
        rows.append(("weather_hourly", WeatherHourly, ("timestamp",), {
            "timestamp": row["timestamp"], "timezone": row["timezone"],
            "temperature_2m_c": row["temperature_2m_c"],
            "relative_humidity_2m_pct": row["relative_humidity_2m_pct"],
            "source": "Open-Meteo", "source_version": dataset_version,
        }))
    for row in weather_ac.to_dict("records"):
        rows.append(("weather_ac_hourly", WeatherAcHourly, ("floor", "zone", "timestamp"), {
            "floor": row["floor"], "zone": row["zone"], "timestamp": row["timestamp"],
            "ac_power_kw": row["ac_power_kw"], "valid_minute_count": row["valid_minute_count"],
            "expected_minute_count": row["expected_minute_count"], "missing_minute_count": row["missing_minute_count"],
            "temperature_2m_c": row["temperature_2m_c"],
            "relative_humidity_2m_pct": row["relative_humidity_2m_pct"],
            "join_status": (
                "complete" if pd.notna(row["ac_power_kw"]) and pd.notna(row["temperature_2m_c"])
                else "missing_ac" if pd.isna(row["ac_power_kw"]) else "missing_weather"
            ),
            "dataset_version": dataset_version,
        }))
    return rows


def preflight(db, rows: list[tuple[str, Any, tuple[str, ...], dict[str, Any]]]) -> dict[str, int]:
    counts = {
        f"{name}_{action}": 0
        for name in ("energy_daily", "alert_events", "anomaly_evidence", "weather_hourly", "weather_ac_hourly")
        for action in ("inserted", "skipped")
    }
    for table, model, key_fields, values in rows:
        protected = "INGEST-" if table in {"alert_events", "anomaly_evidence"} else None
        action = insert_if_missing(db, model, values, key_fields, protected_prefix=protected)
        counts[f"{table}_{'inserted' if action == 'insert' else 'skipped'}"] += 1
    db.rollback()
    return counts


def import_frames(db, frames: dict[str, pd.DataFrame], dataset_version: str) -> dict[str, int]:
    rows = source_rows(frames, dataset_version)
    counts = preflight(db, rows)
    for table, model, key_fields, values in rows:
        protected = "INGEST-" if table in {"alert_events", "anomaly_evidence"} else None
        if insert_if_missing(db, model, values, key_fields, protected_prefix=protected) == "insert":
            db.flush()
    return counts


def run(dry_run: bool) -> dict[str, Any]:
    bucket, prefix = s3_settings()
    objects = read_objects(bucket, prefix)
    frames, dataset_version = parse_objects(objects)
    try:
        with SessionLocal() as db:
            counts = import_frames(db, frames, dataset_version)
            if dry_run:
                db.rollback()
            else:
                db.commit()
    except SQLAlchemyError as error:
        raise RuntimeError("Database operation failed; no import was committed") from error
    return {"dataset_version": dataset_version, "dry_run": dry_run, "inserted": counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate and report inserts without committing")
    args = parser.parse_args()
    try:
        print(json.dumps(run(dry_run=args.dry_run), indent=2))
    except (RuntimeError, ValueError) as error:
        print(f"Import failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
