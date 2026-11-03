"""Analyze hourly CU-BEMS AC power against Open-Meteo weather."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from process_dataset import RAW_DIR, aggregate_power, load_raw_file


ROOT = Path(__file__).resolve().parent
EXTERNAL_DIR = ROOT / "data" / "external"
WEATHER_FILE = EXTERNAL_DIR / "weather_hourly.csv"
HOURLY_OUTPUT = EXTERNAL_DIR / "weather_energy_hourly.csv"
CORRELATION_OUTPUT = EXTERNAL_DIR / "weather_energy_correlations.csv"
SUMMARY_OUTPUT = EXTERNAL_DIR / "weather_energy_summary.json"
SCATTER_OUTPUT = EXTERNAL_DIR / "weather_ac_scatter.png"
TREND_OUTPUT = EXTERNAL_DIR / "weather_ac_trend.png"
TIMEZONE = "Asia/Bangkok"
FLOOR_FILES = (RAW_DIR / "2018Floor1.csv", RAW_DIR / "2018Floor2.csv")


def load_hourly_ac() -> tuple[pd.DataFrame, dict]:
    hourly_frames = []
    source_summary = {}
    for path in FLOOR_FILES:
        frame, check = load_raw_file(path)
        floor = path.stem.replace("2018", "")
        ac = aggregate_power(frame, floor)
        ac = ac[ac["load_type"].eq("AC")].copy()
        ac.loc[ac["partial_component"], "actual_kw"] = pd.NA
        ac["timestamp"] = pd.to_datetime(ac["timestamp"]).dt.tz_localize(TIMEZONE)
        ac = ac.set_index("timestamp")
        grouped = (
            ac.groupby(["floor", "zone"])["actual_kw"]
            .resample("1h")
            .agg(["mean", "count"])
            .rename(columns={"mean": "ac_power_kw", "count": "valid_minute_count"})
            .reset_index()
        )
        grouped["expected_minute_count"] = 60
        grouped["missing_minute_count"] = (
            grouped["expected_minute_count"] - grouped["valid_minute_count"]
        )
        grouped.loc[grouped["valid_minute_count"].eq(0), "ac_power_kw"] = pd.NA
        grouped["valid_zone_count"] = 1
        grouped["zone_count"] = 1
        hourly_frames.append(grouped)
        source_summary[f"{floor}.csv"] = {
            "rows": check["rows"],
            "ac_zones": int(ac["zone"].nunique()),
            "partial_ac_rows_excluded": int(ac["partial_component"].sum()),
        }

    zone_hourly = pd.concat(hourly_frames, ignore_index=True)
    floor_hourly = (
        zone_hourly.groupby(["floor", "timestamp"], as_index=False)
        .agg(
            ac_power_kw=("ac_power_kw", lambda values: values.sum(min_count=1)),
            valid_zone_count=("ac_power_kw", "count"),
            zone_count=("zone", "nunique"),
            missing_minute_count=("missing_minute_count", "sum"),
        )
    )
    floor_hourly["zone"] = "ALL"
    floor_hourly["valid_minute_count"] = pd.NA
    floor_hourly["expected_minute_count"] = pd.NA
    columns = [
        "floor", "zone", "timestamp", "ac_power_kw", "valid_minute_count",
        "expected_minute_count", "missing_minute_count", "valid_zone_count",
        "zone_count",
    ]
    return pd.concat([zone_hourly[columns], floor_hourly[columns]], ignore_index=True), source_summary


def load_weather() -> pd.DataFrame:
    weather = pd.read_csv(WEATHER_FILE)
    required = {
        "timestamp",
        "timezone",
        "temperature_2m_c",
        "relative_humidity_2m_pct",
    }
    missing_columns = required.difference(weather.columns)
    if missing_columns:
        raise ValueError(f"Weather file is missing columns: {sorted(missing_columns)}")
    if set(weather["timezone"].dropna()) != {TIMEZONE}:
        raise ValueError("Weather file contains unexpected timezone values")
    weather["timestamp"] = pd.to_datetime(weather["timestamp"], utc=True).dt.tz_convert(TIMEZONE)
    if weather["timestamp"].duplicated().any():
        raise ValueError("Weather file contains duplicate timestamps")
    return weather[["timestamp", "temperature_2m_c", "relative_humidity_2m_pct"]]


def correlation_rows(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scope, group_columns in [
        ("overall", []),
        ("floor", ["floor"]),
        ("zone", ["floor", "zone"]),
    ]:
        groups = [((), joined)] if not group_columns else joined.groupby(group_columns, dropna=False)
        for keys, group in groups:
            pair = group.dropna(subset=["temperature_2m_c", "ac_power_kw"])
            if len(pair) < 3:
                continue
            if not isinstance(keys, tuple):
                keys = (keys,)
            row = {
                "scope": scope,
                "floor": keys[0] if group_columns else "ALL",
                "zone": keys[1] if len(group_columns) == 2 else "ALL",
                "pair_rows": len(pair),
                "temperature_missing": int(group["temperature_2m_c"].isna().sum()),
                "ac_power_missing": int(group["ac_power_kw"].isna().sum()),
                "pearson_temperature_ac": pair["temperature_2m_c"].corr(pair["ac_power_kw"], method="pearson"),
                "spearman_temperature_ac": pair["temperature_2m_c"].corr(pair["ac_power_kw"], method="spearman"),
                "temperature_min_c": pair["temperature_2m_c"].min(),
                "temperature_max_c": pair["temperature_2m_c"].max(),
                "ac_power_min_kw": pair["ac_power_kw"].min(),
                "ac_power_max_kw": pair["ac_power_kw"].max(),
            }
            rows.append(row)
    return pd.DataFrame(rows)


def create_charts(joined: pd.DataFrame) -> None:
    pair = joined.dropna(subset=["temperature_2m_c", "ac_power_kw"])
    fig, axis = plt.subplots(figsize=(9, 6))
    for label, group in pair.groupby("floor"):
        axis.scatter(group["temperature_2m_c"], group["ac_power_kw"], s=7, alpha=0.25, label=label)
    axis.set_title("Hourly outdoor temperature vs AC power")
    axis.set_xlabel("Temperature at 2 m (°C)")
    axis.set_ylabel("AC power (kW)")
    axis.grid(alpha=0.2)
    axis.legend()
    fig.tight_layout()
    fig.savefig(SCATTER_OUTPUT, dpi=150)
    plt.close(fig)

    daily = (
        pair.set_index("timestamp")
        .resample("1D")
        .agg(temperature_2m_c=("temperature_2m_c", "mean"), ac_power_kw=("ac_power_kw", "mean"))
    )
    fig, axis_left = plt.subplots(figsize=(11, 5))
    axis_left.plot(daily.index, daily["temperature_2m_c"], color="#d97706", label="Mean temperature")
    axis_left.set_ylabel("Temperature (°C)", color="#d97706")
    axis_right = axis_left.twinx()
    axis_right.plot(daily.index, daily["ac_power_kw"], color="#159a8a", label="Mean AC power")
    axis_right.set_ylabel("AC power (kW)", color="#159a8a")
    axis_left.set_title("Daily mean temperature and AC power")
    axis_left.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(TREND_OUTPUT, dpi=150)
    plt.close(fig)


def main() -> None:
    hourly_ac, source_summary = load_hourly_ac()
    weather = load_weather()
    joined = hourly_ac.merge(weather, on="timestamp", how="inner", validate="many_to_one")
    joined.to_csv(HOURLY_OUTPUT, index=False, date_format="%Y-%m-%dT%H:%M:%S%z")
    correlations = correlation_rows(joined)
    correlations.to_csv(CORRELATION_OUTPUT, index=False)
    create_charts(joined[joined["zone"].eq("ALL")])
    summary = {
        "timezone": TIMEZONE,
        "weather_rows": len(weather),
        "hourly_ac_rows_before_join": len(hourly_ac),
        "joined_rows": len(joined),
        "joined_pair_rows": int(joined[["temperature_2m_c", "ac_power_kw"]].dropna().shape[0]),
        "joined_missing_temperature": int(joined["temperature_2m_c"].isna().sum()),
        "joined_missing_ac_power": int(joined["ac_power_kw"].isna().sum()),
        "source_summary": source_summary,
        "correlation_rows": len(correlations),
        "outputs": {
            "hourly_join": str(HOURLY_OUTPUT),
            "correlations": str(CORRELATION_OUTPUT),
            "scatter": str(SCATTER_OUTPUT),
            "trend": str(TREND_OUTPUT),
        },
        "limitations": [
            "Pearson and Spearman correlation do not establish causation.",
            "Open-Meteo Bangkok weather is not an indoor sensor measurement at the building.",
            "Occupancy, thermostat settings, schedules, and solar/internal gains are unavailable.",
            "Partial AC component rows are excluded instead of imputed.",
        ],
    }
    SUMMARY_OUTPUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
