from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd

from ..process_dataset import (
    HIGH_SCORE,
    LOW_SCORE,
    MAD_SCALE,
    MEDIUM_SCORE,
    MIN_ABSOLUTE_SCALE_KW,
    MIN_BASELINE_POINTS,
    MIN_RELATIVE_SCALE,
    add_expected_usage,
    aggregate_power,
    classify_anomaly,
)

TIMEZONE = timezone(timedelta(hours=7))
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def _raw_path(floor: str) -> Path:
    if floor not in {"Floor1", "Floor2"}:
        raise ValueError("floor must be Floor1 or Floor2")
    return RAW_DIR / f"2018{floor}.csv"


def evaluate_observation(timestamp: datetime, floor: str, zone: str, load_type: str, actual_kw: float, interval_minutes: int) -> dict:
    path = _raw_path(floor)
    frame = pd.read_csv(path, parse_dates=["Date"])
    historical = aggregate_power(frame, floor)
    historical = add_expected_usage(historical)
    candidates = historical[
        (historical["zone"] == zone)
        & (historical["load_type"] == load_type)
        & (historical["weekday"] == timestamp.weekday())
        & (historical["minute_of_day"] == timestamp.hour * 60 + timestamp.minute)
    ]
    valid = candidates["actual_kw"].dropna()
    expected = float(valid.median()) if len(valid) >= MIN_BASELINE_POINTS else None
    mad = float((valid - expected).abs().median()) if expected is not None else None
    robust_scale = max(
        MAD_SCALE * mad if mad is not None else 0,
        abs(expected) * MIN_RELATIVE_SCALE if expected is not None else 0,
        MIN_ABSOLUTE_SCALE_KW,
    ) if expected is not None else None
    robust_score = (actual_kw - expected) / robust_scale if expected is not None else None
    actual_kwh = actual_kw * interval_minutes / 60
    expected_kwh = expected * interval_minutes / 60 if expected is not None else None
    row = pd.Series({
        "actual_kw": actual_kw,
        "expected_kw": expected,
        "robust_score": robust_score,
        "partial_component": False,
    })
    classification = classify_anomaly(row) if expected is not None else None
    severity, reason = classification if classification else (None, None)
    return {
        "expected_kw": expected,
        "excess_kw": max(actual_kw - expected, 0) if expected is not None else 0,
        "actual_kwh": actual_kwh,
        "expected_kwh": expected_kwh,
        "robust_score": robust_score,
        "severity": severity,
        "reason": reason,
        "anomaly_detected": classification is not None,
    }


def normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=TIMEZONE)
    return value.astimezone(TIMEZONE)
