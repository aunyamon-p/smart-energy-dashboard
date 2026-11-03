"""Compare AC forecasting with and without Open-Meteo weather features.

This experiment is isolated from Step 2 outputs. It uses a chronological
train/test split and does not impute missing energy or weather values.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_weather_energy import load_hourly_ac, load_weather


ROOT = Path(__file__).resolve().parent
EXTERNAL_DIR = ROOT / "data" / "external"
OUTPUT_METRICS = EXTERNAL_DIR / "weather_model_comparison.csv"
OUTPUT_SUMMARY = EXTERNAL_DIR / "weather_model_summary.json"
TIMEZONE = "Asia/Bangkok"
TEST_FRACTION = 0.30
RIDGE_ALPHA = 1.0
LAG_COLUMNS = ("lag_1h_kw", "lag_24h_kw")


def build_experiment_frame() -> tuple[pd.DataFrame, dict]:
    hourly, source_summary = load_hourly_ac()
    hourly = hourly[hourly["zone"].ne("ALL")].copy()
    weather = load_weather()
    joined = hourly.merge(weather, on="timestamp", how="left", validate="many_to_one")
    if joined["timestamp"].dt.tz is None:
        raise ValueError("AC timestamps must be timezone-aware")
    if str(joined["timestamp"].dt.tz) != TIMEZONE:
        raise ValueError("AC timestamps are not in Asia/Bangkok")
    joined = joined.sort_values(["floor", "zone", "timestamp"]).reset_index(drop=True)
    series = joined.set_index("timestamp")
    for lag, periods in (("lag_1h_kw", 1), ("lag_24h_kw", 24)):
        joined[lag] = (
            series.groupby(["floor", "zone"])["ac_power_kw"]
            .shift(periods)
            .to_numpy()
        )
    joined["hour"] = joined["timestamp"].dt.hour
    joined["weekday"] = joined["timestamp"].dt.day_of_week
    joined["time_index"] = joined["timestamp"].astype("int64") // 10**9
    timestamps = joined["timestamp"].drop_duplicates().sort_values().tolist()
    split_index = int(len(timestamps) * (1 - TEST_FRACTION))
    if split_index <= 0 or split_index >= len(timestamps):
        raise ValueError("Time split did not produce both train and test periods")
    split_timestamp = timestamps[split_index]
    joined["split"] = np.where(joined["timestamp"] < split_timestamp, "train", "test")
    required = [
        "ac_power_kw",
        "temperature_2m_c",
        "relative_humidity_2m_pct",
        *LAG_COLUMNS,
    ]
    complete = joined.dropna(subset=required).copy()
    if complete.empty:
        raise ValueError("No complete rows remain after excluding missing values")
    metadata = {
        "timezone": TIMEZONE,
        "hourly_zone_rows_before_features": int(len(joined)),
        "complete_rows_used": int(len(complete)),
        "excluded_rows_missing_target_weather_or_lag": int(len(joined) - len(complete)),
        "train_start": joined.loc[joined["split"].eq("train"), "timestamp"].min().isoformat(),
        "train_end": joined.loc[joined["split"].eq("train"), "timestamp"].max().isoformat(),
        "test_start": joined.loc[joined["split"].eq("test"), "timestamp"].min().isoformat(),
        "test_end": joined.loc[joined["split"].eq("test"), "timestamp"].max().isoformat(),
        "split_timestamp": pd.Timestamp(split_timestamp).isoformat(),
        "train_rows": int((complete["split"] == "train").sum()),
        "test_rows": int((complete["split"] == "test").sum()),
        "source_summary": source_summary,
        "missing_weather_rows": int(joined[["temperature_2m_c", "relative_humidity_2m_pct"]].isna().any(axis=1).sum()),
        "missing_ac_rows": int(joined["ac_power_kw"].isna().sum()),
    }
    return complete, metadata


def feature_matrix(frame: pd.DataFrame, include_weather: bool, categories: dict | None = None) -> tuple[np.ndarray, dict]:
    if categories is None:
        categories = {
            "floor": sorted(frame["floor"].unique().tolist()),
            "zone": sorted(frame["zone"].unique().tolist()),
        }
    numeric = pd.DataFrame(
        {
            "lag_1h_kw": frame["lag_1h_kw"],
            "lag_24h_kw": frame["lag_24h_kw"],
            "hour_sin": np.sin(2 * np.pi * frame["hour"] / 24),
            "hour_cos": np.cos(2 * np.pi * frame["hour"] / 24),
            "weekday_sin": np.sin(2 * np.pi * frame["weekday"] / 7),
            "weekday_cos": np.cos(2 * np.pi * frame["weekday"] / 7),
        },
        index=frame.index,
    )
    if include_weather:
        numeric["temperature_2m_c"] = frame["temperature_2m_c"]
        numeric["relative_humidity_2m_pct"] = frame["relative_humidity_2m_pct"]
    categorical = pd.get_dummies(
        frame[["floor", "zone"]],
        columns=["floor", "zone"],
        dtype=float,
    )
    expected_columns = [
        *(f"floor_{value}" for value in categories["floor"]),
        *(f"zone_{value}" for value in categories["zone"]),
    ]
    categorical = categorical.reindex(columns=expected_columns, fill_value=0.0)
    matrix = pd.concat([numeric, categorical], axis=1).to_numpy(dtype=float)
    return np.column_stack([np.ones(len(matrix)), matrix]), {
        "numeric_features": list(numeric.columns),
        "categorical_features": expected_columns,
    }


def fit_ridge(train_x: np.ndarray, train_y: np.ndarray) -> np.ndarray:
    penalty = np.eye(train_x.shape[1])
    penalty[0, 0] = 0.0
    return np.linalg.solve(train_x.T @ train_x + RIDGE_ALPHA * penalty, train_x.T @ train_y)


def metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    error = predicted - actual
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error**2)))
    denominator = float(np.sum((actual - np.mean(actual)) ** 2))
    r2 = float(1 - np.sum(error**2) / denominator) if denominator else None
    return {"mae_kw": mae, "rmse_kw": rmse, "r2": r2}


def evaluate(frame: pd.DataFrame, model_name: str, predictions: np.ndarray) -> list[dict]:
    scored = frame[["floor", "zone", "ac_power_kw"]].copy()
    scored["prediction_kw"] = predictions
    rows = []
    scopes = [("overall", None), ("floor", ["floor"]), ("zone", ["floor", "zone"])]
    for scope, group_columns in scopes:
        groups = [((), scored)] if group_columns is None else scored.groupby(group_columns, sort=True)
        for keys, group in groups:
            if not isinstance(keys, tuple):
                keys = (keys,)
            values = metrics(group["ac_power_kw"].to_numpy(), group["prediction_kw"].to_numpy())
            rows.append(
                {
                    "model": model_name,
                    "scope": scope,
                    "floor": keys[0] if group_columns else "ALL",
                    "zone": keys[1] if group_columns and len(group_columns) == 2 else "ALL",
                    "rows": int(len(group)),
                    **values,
                }
            )
    return rows


def main() -> None:
    frame, metadata = build_experiment_frame()
    train = frame[frame["split"].eq("train")]
    test = frame[frame["split"].eq("test")].copy()
    categories = {
        "floor": sorted(train["floor"].unique().tolist()),
        "zone": sorted(train["zone"].unique().tolist()),
    }
    results = []
    for model_name, include_weather in (("Model A", False), ("Model B", True)):
        train_x, feature_info = feature_matrix(train, include_weather, categories)
        test_x, _ = feature_matrix(test, include_weather, categories)
        coefficients = fit_ridge(train_x, train["ac_power_kw"].to_numpy())
        predictions = test_x @ coefficients
        results.extend(evaluate(test, model_name, predictions))
        metadata[f"{model_name}_features"] = feature_info

    metrics_frame = pd.DataFrame(results)
    pivot = metrics_frame.pivot_table(
        index=["scope", "floor", "zone", "rows"],
        columns="model",
        values=["mae_kw", "rmse_kw", "r2"],
    ).reset_index()
    pivot.columns = [
        "_".join(column).strip("_").lower().replace(" ", "_")
        if isinstance(column, tuple)
        else column
        for column in pivot.columns
    ]
    pivot["mae_improvement_pct"] = (
        (pivot["mae_kw_model_a"] - pivot["mae_kw_model_b"])
        / pivot["mae_kw_model_a"]
        * 100
    )
    pivot["rmse_improvement_pct"] = (
        (pivot["rmse_kw_model_a"] - pivot["rmse_kw_model_b"])
        / pivot["rmse_kw_model_a"]
        * 100
    )
    pivot.to_csv(OUTPUT_METRICS, index=False)
    overall = pivot[(pivot["scope"] == "overall")].iloc[0]
    metadata["ridge_alpha"] = RIDGE_ALPHA
    metadata["test_fraction_by_timestamp"] = TEST_FRACTION
    metadata["results"] = {
        "overall_mae_improvement_pct": float(overall["mae_improvement_pct"]),
        "overall_rmse_improvement_pct": float(overall["rmse_improvement_pct"]),
        "overall_model_a": {
            "mae_kw": float(overall["mae_kw_model_a"]),
            "rmse_kw": float(overall["rmse_kw_model_a"]),
            "r2": float(overall["r2_model_a"]),
        },
        "overall_model_b": {
            "mae_kw": float(overall["mae_kw_model_b"]),
            "rmse_kw": float(overall["rmse_kw_model_b"]),
            "r2": float(overall["r2_model_b"]),
        },
    }
    OUTPUT_SUMMARY.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(metrics_frame.to_string(index=False))
    print(f"\nWrote {OUTPUT_METRICS}")
    print(f"Wrote {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()
