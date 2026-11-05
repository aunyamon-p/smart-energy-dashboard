from __future__ import annotations

from datetime import datetime, timezone, timedelta
from functools import lru_cache
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
    aggregate_power,
    classify_anomaly,
)
from .config import get_settings

TIMEZONE = timezone(timedelta(hours=7))
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def _raw_path(floor: str) -> Path:
    if floor not in {"Floor1", "Floor2"}:
        raise ValueError("floor must be Floor1 or Floor2")
    return RAW_DIR / f"2018{floor}.csv"


def _historical_frame(floor: str) -> pd.DataFrame:
    settings = get_settings()
    if not settings.historical_dataset_is_s3:
        return pd.read_csv(_raw_path(floor), parse_dates=["Date"])
    if not settings.historical_dataset_s3_bucket:
        raise ValueError("HISTORICAL_DATASET_S3_BUCKET is required in S3 mode")
    try:
        import boto3
    except ImportError as error:
        raise ValueError("boto3 is required in S3 mode") from error
    key = f"{settings.historical_dataset_s3_prefix.rstrip('/')}/2018{floor}.csv"
    response = boto3.client("s3").get_object(Bucket=settings.historical_dataset_s3_bucket, Key=key)
    return pd.read_csv(response["Body"], parse_dates=["Date"])


@lru_cache(maxsize=2)
def _historical_baseline(floor: str) -> pd.DataFrame:
    """Load one floor and prepare only the statistics required by ingestion."""
    frame = _historical_frame(floor)
    historical = aggregate_power(frame, floor)
    historical["weekday"] = historical["timestamp"].dt.day_of_week
    historical["minute_of_day"] = (
        historical["timestamp"].dt.hour * 60 + historical["timestamp"].dt.minute
    )
    group_columns = ["zone", "load_type", "weekday", "minute_of_day"]
    grouped = historical.groupby(group_columns, dropna=False)["actual_kw"]
    statistics = grouped.agg(["count", "median"]).reset_index()
    historical = historical.merge(
        statistics[group_columns + ["median"]],
        on=group_columns,
        how="left",
    )
    historical["absolute_deviation"] = (
        historical["actual_kw"] - historical["median"]
    ).abs()
    mad = (
        historical.groupby(group_columns, dropna=False)["absolute_deviation"]
        .median()
        .rename("mad")
        .reset_index()
    )
    statistics = statistics.merge(mad, on=group_columns, how="left")
    insufficient = statistics["count"] < MIN_BASELINE_POINTS
    statistics.loc[insufficient, ["median", "mad"]] = pd.NA
    return statistics.rename(columns={"median": "expected_kw", "mad": "mad_kw"})[
        group_columns + ["expected_kw", "mad_kw"]
    ]


def evaluate_observation(timestamp: datetime, floor: str, zone: str, load_type: str, actual_kw: float, interval_minutes: int) -> dict:
    historical = _historical_baseline(floor)
    candidates = historical[
        (historical["zone"] == zone)
        & (historical["load_type"] == load_type)
        & (historical["weekday"] == timestamp.weekday())
        & (historical["minute_of_day"] == timestamp.hour * 60 + timestamp.minute)
    ]
    baseline = candidates.iloc[0] if not candidates.empty else None
    expected = float(baseline["expected_kw"]) if baseline is not None and pd.notna(baseline["expected_kw"]) else None
    mad = float(baseline["mad_kw"]) if baseline is not None and pd.notna(baseline["mad_kw"]) else None
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
