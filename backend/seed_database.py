
"""Load approved Step 2 and Weather outputs into the SQLAlchemy database.

Supports:
- Local CSV files (default)
- S3 objects (SEED_SOURCE=s3)
- Additive and idempotent imports
- Existing records are never updated or deleted
- Conflicting records abort the entire transaction
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
from sqlalchemy import Numeric, select, tuple_

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.db import Base, SessionLocal, engine
from backend.app.models import (
    AlertEvent,
    AnomalyEvidence,
    EnergyDaily,
    WeatherAcHourly,
    WeatherHourly,
)


ROOT = Path(__file__).resolve().parents[1]
TIMEZONE = "Asia/Bangkok"

# Exact object keys relative to the dataset bucket root.
DATASET_FILES = {
    "processed_energy_daily": "processed/processed_energy_daily.csv",
    "anomalies": "processed/anomalies.csv",
    "alert_events": "processed/alert_events.csv",
    "processing_summary": "processed/processing_summary.json",
    "weather_hourly": "external/weather_hourly.csv",
    "weather_energy_hourly": "external/weather_energy_hourly.csv",
}

# Natural keys used to identify the same logical record.
NATURAL_KEYS = {
    EnergyDaily: ("floor", "zone", "load_type", "date"),
    AlertEvent: ("alert_id",),
    AnomalyEvidence: ("point_alert_id",),
    WeatherHourly: ("timestamp",),
    WeatherAcHourly: ("floor", "zone", "timestamp"),
}

# These fields describe the dataset/import operation, not the
# underlying business record. They are not used for conflict checks.
VERSION_FIELDS = {
    "dataset_version",
    "source_version",
}

OPERATIONAL_FIELDS = {
    AlertEvent: {"status", "status_updated_at"},
}


def timestamp_series(values: pd.Series) -> pd.Series:
    return (
        pd.to_datetime(values, utc=True)
        .dt.tz_convert(TIMEZONE)
        .dt.tz_localize(None)
    )


def clean_value(value):
    """Convert pandas missing values into Python None."""
    if value is None:
        return None

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.to_pydatetime() if isinstance(value, pd.Timestamp) else value

    if isinstance(value, date):
        return value

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return value


def comparable_value(value, column=None):
    """Normalize database and CSV values for safe equality checks."""
    value = clean_value(value)

    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float, Decimal)):
        value = Decimal(str(value))
        if (
            column is not None
            and isinstance(column.type, Numeric)
            and column.type.scale is not None
        ):
            quantum = Decimal(1).scaleb(-column.type.scale)
            value = value.quantize(quantum, rounding=ROUND_HALF_UP)
        return value

    return value


def read_dataset() -> tuple[dict[str, bytes], dict[str, pd.DataFrame]]:
    """Read the same dataset from Local or S3."""

    source = os.getenv("SEED_SOURCE", "local").strip().lower()

    if source == "local":
        contents = {
            name: (
                ROOT / "backend" / "data" / Path(*object_key.split("/"))
            ).read_bytes()
            for name, object_key in DATASET_FILES.items()
        }

    elif source == "s3":
        import boto3

        bucket = os.getenv("HISTORICAL_DATASET_S3_BUCKET")

        if not bucket:
            raise RuntimeError(
                "HISTORICAL_DATASET_S3_BUCKET is required when SEED_SOURCE=s3"
            )

        s3 = boto3.client("s3")

        contents = {}

        for name, object_key in DATASET_FILES.items():
            response = s3.get_object(
                Bucket=bucket,
                Key=object_key,
            )

            contents[name] = response["Body"].read()

    else:
        raise ValueError(
            f"Unsupported SEED_SOURCE: {source}. Use local or s3."
        )

    hashes = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in contents.items()
    }

    digest = hashlib.sha256()

    for name, value in sorted(hashes.items()):
        digest.update(name.encode())
        digest.update(value.encode())

    dataset_version = digest.hexdigest()[:16]

    frames = {
        name: pd.read_csv(io.BytesIO(contents[name]))
        for name in (
            "processed_energy_daily",
            "anomalies",
            "alert_events",
            "weather_hourly",
            "weather_energy_hourly",
        )
    }

    return {
        "dataset_version": dataset_version,
    }, frames


def prepare_records(
    dataset_version: str,
    frames: dict[str, pd.DataFrame],
) -> dict[type, list[dict]]:
    """Convert CSV rows into SQLAlchemy insert mappings."""

    daily = frames["processed_energy_daily"].copy()
    events = frames["alert_events"].copy()
    evidence = frames["anomalies"].copy()
    weather = frames["weather_hourly"].copy()
    weather_ac = frames["weather_energy_hourly"].copy()

    events["start_timestamp"] = timestamp_series(
        events["start_timestamp"]
    )
    events["end_timestamp"] = timestamp_series(
        events["end_timestamp"]
    )
    evidence["timestamp"] = timestamp_series(evidence["timestamp"])
    weather["timestamp"] = timestamp_series(weather["timestamp"])
    weather_ac["timestamp"] = timestamp_series(weather_ac["timestamp"])

    # Never import realtime-generated records through the historical seed.
    if events["alert_id"].astype(str).str.startswith("INGEST-").any():
        raise RuntimeError(
            "Historical Dataset contains an INGEST-* Alert ID. "
            "Import aborted to protect realtime records."
        )

    if evidence["alert_id"].astype(str).str.startswith("INGEST-").any():
        raise RuntimeError(
            "Historical Dataset contains an INGEST-* Evidence ID. "
            "Import aborted to protect realtime records."
        )

    daily_rows = []

    for row in daily.to_dict("records"):
        row["date"] = pd.to_datetime(row["date"]).date()
        row["dataset_version"] = dataset_version
        daily_rows.append(row)

    event_rows = []

    for row in events.to_dict("records"):
        row["dataset_version"] = dataset_version
        row["status_updated_at"] = None
        event_rows.append(row)

    evidence_rows = []

    for row in evidence.to_dict("records"):
        evidence_rows.append({
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
        })

    weather_rows = []

    for row in weather.to_dict("records"):
        weather_rows.append({
            "timestamp": row["timestamp"],
            "timezone": row["timezone"],
            "temperature_2m_c": row["temperature_2m_c"],
            "relative_humidity_2m_pct": row["relative_humidity_2m_pct"],
            "source": "Open-Meteo",
            "source_version": dataset_version,
        })

    weather_ac_rows = []

    for row in weather_ac.to_dict("records"):
        weather_ac_rows.append({
            "floor": row["floor"],
            "zone": row["zone"],
            "timestamp": row["timestamp"],
            "ac_power_kw": row["ac_power_kw"],
            "valid_minute_count": row["valid_minute_count"],
            "expected_minute_count": row["expected_minute_count"],
            "missing_minute_count": row["missing_minute_count"],
            "temperature_2m_c": row["temperature_2m_c"],
            "relative_humidity_2m_pct": row["relative_humidity_2m_pct"],
            "join_status": (
                "complete"
                if pd.notna(row["ac_power_kw"])
                and pd.notna(row["temperature_2m_c"])
                else "missing_ac"
                if pd.isna(row["ac_power_kw"])
                else "missing_weather"
            ),
            "dataset_version": dataset_version,
        })

    mappings = {
        EnergyDaily: daily_rows,
        AlertEvent: event_rows,
        AnomalyEvidence: evidence_rows,
        WeatherHourly: weather_rows,
        WeatherAcHourly: weather_ac_rows,
    }

    # Normalize NaN/NaT to None in every insert mapping.
    for model, rows in mappings.items():
        mappings[model] = [
            {
                key: clean_value(value)
                for key, value in row.items()
            }
            for row in rows
        ]

    return mappings


def find_existing_rows(db, model, keys, chunk_size=400):
    """Load existing records matching incoming natural keys."""

    if not keys:
        return {}

    key_columns = NATURAL_KEYS[model]
    columns = [getattr(model, name) for name in key_columns]

    existing = {}

    for start in range(0, len(keys), chunk_size):
        chunk = keys[start:start + chunk_size]

        if len(key_columns) == 1:
            condition = columns[0].in_([key[0] for key in chunk])
        else:
            condition = tuple_(*columns).in_(chunk)

        rows = db.execute(
            select(model).where(condition)
        ).scalars().all()

        for row in rows:
            key = tuple(
                getattr(row, name)
                for name in key_columns
            )
            existing[key] = row

    return existing


def check_same_record(model, existing, incoming):
    """Compare imported fields without changing existing records."""

    ignored_fields = VERSION_FIELDS | OPERATIONAL_FIELDS.get(model, set())

    for field, incoming_value in incoming.items():
        if field in ignored_fields:
            continue

        existing_value = (
            existing[field]
            if isinstance(existing, dict)
            else getattr(existing, field)
        )
        column = getattr(model, field).property.columns[0]

        if comparable_value(existing_value, column) != comparable_value(
            incoming_value,
            column,
        ):
            return False, field

    return True, None


def import_model(db, model, incoming_rows):
    """Insert missing records, skip identical records, reject conflicts."""

    key_columns = NATURAL_KEYS[model]
    incoming_by_key = {}
    duplicate_count = 0

    for row in incoming_rows:
        key = tuple(row[name] for name in key_columns)

        if any(value is None for value in key):
            raise RuntimeError(
                f"{model.__name__}: Natural Key contains NULL: {key}"
            )

        if key in incoming_by_key:
            same, conflict_field = check_same_record(
                model,
                incoming_by_key[key],
                row,
            )
            if not same:
                raise RuntimeError(
                    f"Conflicting duplicate in {model.__tablename__}: "
                    f"Natural Key={key}, field={conflict_field}."
                )
            duplicate_count += 1
            continue

        incoming_by_key[key] = row

    keys = list(incoming_by_key.keys())

    existing_rows = find_existing_rows(
        db,
        model,
        keys,
    )

    pending = []
    skipped = duplicate_count

    for key, incoming in incoming_by_key.items():
        existing = existing_rows.get(key)

        if existing is None:
            pending.append(incoming)
            continue

        same, conflict_field = check_same_record(
            model,
            existing,
            incoming,
        )

        if not same:
            raise RuntimeError(
                f"Conflict in {model.__tablename__}: "
                f"Natural Key={key}, field={conflict_field}. "
                "Existing data was not modified."
            )

        skipped += 1

    if pending:
        db.bulk_insert_mappings(model, pending)

    return {
        "inserted": len(pending),
        "skipped": skipped,
    }


def seed(dry_run: bool = False) -> dict:
    # Keep the original local schema initialization behavior.
    # Production schema changes should be managed separately.
    Base.metadata.create_all(bind=engine)

    metadata, frames = read_dataset()
    dataset_version = metadata["dataset_version"]

    mappings = prepare_records(
        dataset_version,
        frames,
    )

    results = {}

    db = SessionLocal()

    try:
        for model, rows in mappings.items():
            results[model.__tablename__] = import_model(
                db,
                model,
                rows,
            )

        if dry_run:
            db.rollback()
        else:
            db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    return {
        "dataset_version": dataset_version,
        "mode": "dry-run" if dry_run else "committed",
        "tables": results,
        "ingested_energy": "untouched",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check import and roll back without saving changes.",
    )

    args = parser.parse_args()

    result = seed(dry_run=args.dry_run)

    print("\nSeed result")
    print("=" * 50)
    print(f"Dataset Version: {result['dataset_version']}")
    print(f"Mode: {result['mode']}")

    for table, counts in result["tables"].items():
        print(
            f"{table}: "
            f"inserted={counts['inserted']}, "
            f"skipped={counts['skipped']}"
        )

    print("ingested_energy: untouched")
