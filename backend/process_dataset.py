"""Process CU-BEMS raw CSV files and detect high-power anomalies.

Raw files are read-only inputs. Results are written to backend/data/processed.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "data" / "processed"
POWER_PATTERN = re.compile(r"^(z\d+)_(AC\d*|Light|Plug)\(kW\)$")
SUPPORTED_LOADS = ("AC", "Light", "Plug")
MIN_BASELINE_POINTS = 3
MAD_SCALE = 1.4826
MIN_RELATIVE_SCALE = 0.10
MIN_ABSOLUTE_SCALE_KW = 0.05
LOW_SCORE = 3.5
MEDIUM_SCORE = 5.0
HIGH_SCORE = 8.0


def parse_power_column(column: str) -> tuple[str, str] | None:
    match = POWER_PATTERN.match(column)
    if not match:
        return None
    zone, component = match.groups()
    load_type = "AC" if component.startswith("AC") else component
    return zone, load_type


def power_columns(columns: Iterable[str]) -> list[str]:
    return [column for column in columns if parse_power_column(column) is not None]


def load_raw_file(path: Path) -> tuple[pd.DataFrame, dict]:
    frame = pd.read_csv(path, parse_dates=["Date"])
    if frame["Date"].isna().any():
        raise ValueError(f"{path.name}: Date contains invalid or missing timestamps")
    if frame["Date"].duplicated().any():
        raise ValueError(f"{path.name}: duplicate timestamps found")
    ordered = frame["Date"].sort_values()
    intervals = ordered.diff().dropna().dt.total_seconds()
    power = power_columns(frame.columns)
    non_numeric = [column for column in power if not pd.api.types.is_numeric_dtype(frame[column])]
    if non_numeric:
        raise ValueError(f"{path.name}: non-numeric power columns: {non_numeric}")
    return frame, {
        "file": path.name,
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "power_columns": int(len(power)),
        "first_timestamp": frame["Date"].min().isoformat(),
        "last_timestamp": frame["Date"].max().isoformat(),
        "interval_seconds": sorted(intervals.unique().tolist()),
        "irregular_intervals": int((intervals != 60).sum()),
    }


def aggregate_power(frame: pd.DataFrame, floor: str) -> pd.DataFrame:
    records: list[pd.DataFrame] = []
    for zone, load_type in sorted(
        {parse_power_column(column) for column in power_columns(frame.columns)}
    ):
        columns = [
            column
            for column in power_columns(frame.columns)
            if parse_power_column(column) == (zone, load_type)
        ]
        values = frame[columns]
        aggregate = values.sum(axis=1, min_count=1)
        partial = values.isna().any(axis=1) if len(columns) > 1 else pd.Series(False, index=frame.index)
        records.append(
            pd.DataFrame(
                {
                    "timestamp": frame["Date"],
                    "floor": floor,
                    "zone": zone,
                    "load_type": load_type,
                    "actual_kw": aggregate,
                    "missing_component": aggregate.isna(),
                    "partial_component": partial,
                    "component_count": len(columns),
                }
            )
        )
    if not records:
        raise ValueError(f"{floor}: no supported kW columns found")
    return pd.concat(records, ignore_index=True)


def add_expected_usage(series: pd.DataFrame) -> pd.DataFrame:
    result = series.sort_values(["floor", "zone", "load_type", "timestamp"]).copy()
    result["weekday"] = result["timestamp"].dt.day_of_week
    result["minute_of_day"] = result["timestamp"].dt.hour * 60 + result["timestamp"].dt.minute
    group_columns = ["floor", "zone", "load_type", "weekday", "minute_of_day"]
    grouped = result.groupby(group_columns, dropna=False)["actual_kw"]
    result["expected_kw"] = grouped.transform(
        lambda values: values.median() if values.notna().sum() >= MIN_BASELINE_POINTS else np.nan
    )
    result["mad_kw"] = grouped.transform(
        lambda values: (values - values.median()).abs().median()
        if values.notna().sum() >= MIN_BASELINE_POINTS
        else np.nan
    )
    mad_scale = result["mad_kw"] * MAD_SCALE
    relative_scale = result["expected_kw"].abs() * MIN_RELATIVE_SCALE
    result["robust_scale_kw"] = pd.concat(
        [mad_scale, relative_scale, pd.Series(MIN_ABSOLUTE_SCALE_KW, index=result.index)],
        axis=1,
    ).max(axis=1, skipna=False)
    result["robust_score"] = (result["actual_kw"] - result["expected_kw"]) / result["robust_scale_kw"]
    result["excess_kw"] = (result["actual_kw"] - result["expected_kw"]).clip(lower=0)
    result["interval_hours"] = result.groupby(["floor", "zone", "load_type"])["timestamp"].diff().dt.total_seconds().div(3600)
    interval_medians = result.groupby(["floor", "zone", "load_type"])["interval_hours"].transform("median")
    result["interval_hours"] = result["interval_hours"].fillna(interval_medians)
    result["actual_kwh"] = result["actual_kw"] * result["interval_hours"]
    result["expected_kwh"] = (
        result["expected_kw"] * result["interval_hours"]
    ).where(result["actual_kw"].notna())
    result["excess_kwh"] = result["excess_kw"] * result["interval_hours"]
    return result


def classify_anomaly(row: pd.Series) -> tuple[str, str] | None:
    if (
        pd.isna(row["actual_kw"])
        or pd.isna(row["expected_kw"])
        or pd.isna(row["robust_score"])
        or row["partial_component"]
    ):
        return None
    if row["actual_kw"] <= row["expected_kw"] or row["robust_score"] < LOW_SCORE:
        return None
    score = row["robust_score"]
    severity = "High" if score >= HIGH_SCORE else "Medium" if score >= MEDIUM_SCORE else "Low"
    reason = (
        f"Observed {row['actual_kw']:.3f} kW exceeded the weekday/time baseline "
        f"of {row['expected_kw']:.3f} kW; robust score {score:.2f}."
    )
    return severity, reason


def detect_anomalies(processed: pd.DataFrame) -> pd.DataFrame:
    classified = processed.apply(classify_anomaly, axis=1)
    mask = classified.notna()
    anomalies = processed.loc[mask].copy()
    if anomalies.empty:
        return pd.DataFrame(
            columns=[
                "alert_id", "timestamp", "floor", "zone", "load_type", "actual_kw",
                "expected_kw", "excess_kw", "actual_kwh", "expected_kwh", "excess_kwh",
                "severity", "reason", "status", "robust_score",
            ]
        )
    values = classified[mask].tolist()
    anomalies["severity"] = [value[0] for value in values]
    anomalies["reason"] = [value[1] for value in values]
    anomalies["status"] = "New"
    anomalies = anomalies.sort_values("timestamp")
    anomalies.insert(0, "alert_id", [f"CU-{index:06d}" for index in range(1, len(anomalies) + 1)])
    return anomalies[
        [
            "alert_id", "timestamp", "floor", "zone", "load_type", "actual_kw",
            "expected_kw", "excess_kw", "actual_kwh", "expected_kwh", "excess_kwh",
            "severity", "reason", "status", "robust_score",
        ]
    ]


def detect_alert_events(anomalies: pd.DataFrame) -> pd.DataFrame:
    event_columns = [
        "alert_id", "floor", "zone", "load_type", "start_timestamp", "end_timestamp",
        "duration_minutes", "evidence_points", "actual_kw_peak", "expected_kw_at_peak",
        "excess_kw_peak", "excess_energy_kwh", "severity", "reason", "status",
    ]
    if anomalies.empty:
        return pd.DataFrame(columns=event_columns)

    ordered = anomalies.sort_values(
        ["floor", "zone", "load_type", "timestamp"]
    ).copy()
    series_columns = ["floor", "zone", "load_type"]
    ordered["previous_timestamp"] = ordered.groupby(series_columns)["timestamp"].shift()
    ordered["new_event"] = (
        ordered["previous_timestamp"].isna()
        | (ordered["timestamp"] - ordered["previous_timestamp"] != pd.Timedelta(minutes=1))
    )
    ordered["event_number"] = ordered.groupby(series_columns)["new_event"].cumsum()
    grouped = ordered.groupby(series_columns + ["event_number"], sort=False)
    severity_rank = {"Low": 1, "Medium": 2, "High": 3}
    rows = []
    for (floor, zone, load_type, _), group in grouped:
        peak = group.loc[group["excess_kw"].idxmax()]
        severity = max(group["severity"], key=lambda value: severity_rank[value])
        rows.append(
            {
                "floor": floor,
                "zone": zone,
                "load_type": load_type,
                "start_timestamp": group["timestamp"].min(),
                "end_timestamp": group["timestamp"].max(),
                "duration_minutes": int(
                    (group["timestamp"].max() - group["timestamp"].min()).total_seconds() / 60
                )
                + 1,
                "evidence_points": int(len(group)),
                "actual_kw_peak": peak["actual_kw"],
                "expected_kw_at_peak": peak["expected_kw"],
                "excess_kw_peak": peak["excess_kw"],
                "excess_energy_kwh": group["excess_kwh"].sum(),
                "severity": severity,
                "reason": (
                    f"{load_type} usage remained above the weekday/time baseline for "
                    f"{len(group)} consecutive minute(s); peak excess was "
                    f"{peak['excess_kw']:.3f} kW."
                ),
                "status": "New",
            }
        )
    events = pd.DataFrame(rows).sort_values("start_timestamp").reset_index(drop=True)
    events.insert(0, "alert_id", [f"CU-EVENT-{index:06d}" for index in range(1, len(events) + 1)])
    return events[event_columns]


def build_quality_report(raw_frames: list[tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    rows = []
    for floor, frame in raw_frames:
        for column in frame.columns:
            missing = int(frame[column].isna().sum())
            numeric = pd.to_numeric(frame[column], errors="coerce")
            rows.append(
                {
                    "floor": floor,
                    "column": column,
                    "missing_count": missing,
                    "missing_pct": missing / len(frame) * 100,
                    "min_value": numeric.min() if column != "Date" else np.nan,
                    "max_value": numeric.max() if column != "Date" else np.nan,
                    "negative_count": int((numeric < 0).sum()) if column != "Date" else 0,
                    "all_missing": missing == len(frame),
                }
            )
    return pd.DataFrame(rows)


def write_results() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_frames = []
    all_series = []
    file_checks = []
    for path in [RAW_DIR / "2018Floor1.csv", RAW_DIR / "2018Floor2.csv"]:
        floor = path.stem.replace("2018", "")
        frame, check = load_raw_file(path)
        raw_frames.append((floor, frame))
        file_checks.append(check)
        all_series.append(aggregate_power(frame, floor))

    series = add_expected_usage(pd.concat(all_series, ignore_index=True))
    partial_component_anomalies = int(
        (
            series["partial_component"]
            & series["actual_kw"].gt(series["expected_kw"])
            & series["robust_score"].ge(LOW_SCORE)
        ).sum()
    )
    anomalies = detect_anomalies(series)
    alert_events = detect_alert_events(anomalies)
    daily = (
        series.assign(date=series["timestamp"].dt.date)
        .groupby(["floor", "zone", "load_type", "date"], as_index=False)
        .agg(
            actual_energy_kwh=("actual_kwh", "sum"),
            expected_energy_kwh=("expected_kwh", "sum"),
            excess_energy_kwh=("excess_kwh", "sum"),
            observations=("actual_kw", "count"),
            missing_observations=("actual_kw", lambda values: int(values.isna().sum())),
            partial_component_observations=("partial_component", "sum"),
        )
    )
    daily.to_csv(OUTPUT_DIR / "processed_energy_daily.csv", index=False)
    anomalies.to_csv(OUTPUT_DIR / "anomalies.csv", index=False, date_format="%Y-%m-%dT%H:%M:%S")
    alert_events.to_csv(OUTPUT_DIR / "alert_events.csv", index=False, date_format="%Y-%m-%dT%H:%M:%S")
    quality = build_quality_report(raw_frames)
    quality.to_csv(OUTPUT_DIR / "data_quality_report.csv", index=False)
    summary = {
        "source_files": file_checks,
        "processed_series_rows": int(len(series)),
        "daily_rows": int(len(daily)),
        "point_anomaly_rows": int(len(anomalies)),
        "alert_event_rows": int(len(alert_events)),
        "anomalies_by_severity": anomalies["severity"].value_counts().reindex(["High", "Medium", "Low"], fill_value=0).astype(int).to_dict(),
        "alert_events_by_severity": alert_events["severity"].value_counts().reindex(["High", "Medium", "Low"], fill_value=0).astype(int).to_dict(),
        "missing_power_observations": int(series["actual_kw"].isna().sum()),
        "partial_component_observations": int(series["partial_component"].sum()),
        "partial_component_anomalies_excluded": partial_component_anomalies,
        "cost_estimation": "not calculated: electricity tariff was not provided",
        "method": "weekday and minute-of-day median baseline with MAD-scaled robust score",
        "thresholds": {
            "low": LOW_SCORE,
            "medium": MEDIUM_SCORE,
            "high": HIGH_SCORE,
            "minimum_scale_kw": MIN_ABSOLUTE_SCALE_KW,
            "minimum_relative_scale": MIN_RELATIVE_SCALE,
        },
    }
    (OUTPUT_DIR / "processing_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run_self_tests() -> None:
    index = pd.to_datetime(
        ["2020-01-06 00:00", "2020-01-13 00:00", "2020-01-20 00:00", "2020-01-27 00:00"]
    )
    sample = pd.DataFrame(
        {
            "timestamp": index,
            "floor": ["Floor1"] * 4,
            "zone": ["z1"] * 4,
            "load_type": ["Light"] * 4,
            "actual_kw": [10.0, np.nan, 10.0, 100.0],
            "missing_component": [False, True, False, False],
            "partial_component": [False] * 4,
            "component_count": [1] * 4,
        }
    )
    result = add_expected_usage(sample)
    assert result.loc[0, "actual_kwh"] == 10 * 168
    assert pd.isna(result.loc[1, "actual_kwh"])
    assert result.loc[3, "excess_kwh"] > 0
    assert parse_power_column("z2_AC14(kW)") == ("z2", "AC")
    assert parse_power_column("z1_S1(lux)") is None
    raw_sample = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2020-01-01 00:00"]),
            "z1_AC1(kW)": [2.0],
            "z1_AC2(kW)": [3.0],
            "z1_Plug(kW)": [np.nan],
        }
    )
    aggregated = aggregate_power(raw_sample, "Floor1")
    ac = aggregated[aggregated["load_type"].eq("AC")].iloc[0]
    plug = aggregated[aggregated["load_type"].eq("Plug")].iloc[0]
    assert ac["actual_kw"] == 5.0
    assert pd.isna(plug["actual_kw"])
    sample_anomalies = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2020-01-01 00:00", "2020-01-01 00:01", "2020-01-01 00:03"]),
            "floor": ["Floor1"] * 3,
            "zone": ["z1"] * 3,
            "load_type": ["Light"] * 3,
            "actual_kw": [10.0, 11.0, 12.0],
            "expected_kw": [1.0] * 3,
            "excess_kw": [9.0, 10.0, 11.0],
            "excess_kwh": [0.15, 0.1666667, 0.1833333],
            "severity": ["High", "Medium", "Low"],
        }
    )
    events = detect_alert_events(sample_anomalies)
    assert len(events) == 2
    assert events.iloc[0]["evidence_points"] == 2
    assert events.iloc[0]["severity"] == "High"
    print("Self-tests passed: kWh conversion, missing preservation, excess calculation, parsing")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        run_self_tests()
        return
    summary = write_results()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
