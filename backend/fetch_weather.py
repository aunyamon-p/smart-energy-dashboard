"""Fetch hourly historical weather for Bangkok from Open-Meteo.

The output is external data only and is kept separate from CU-BEMS files.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "data" / "external"
OUTPUT_FILE = OUTPUT_DIR / "weather_hourly.csv"
API_URL = "https://archive-api.open-meteo.com/v1/archive"
BANGKOK_LATITUDE = 13.7563
BANGKOK_LONGITUDE = 100.5018
TIMEZONE = "Asia/Bangkok"
REQUEST_TIMEOUT_SECONDS = 30


def expected_timestamps(start_date: str, end_date: str) -> list[datetime]:
    start = datetime.fromisoformat(start_date).replace(tzinfo=ZoneInfo(TIMEZONE))
    end = datetime.fromisoformat(end_date).replace(
        hour=23, minute=0, second=0, microsecond=0, tzinfo=ZoneInfo(TIMEZONE)
    )
    timestamps = []
    current = start
    while current <= end:
        timestamps.append(current)
        current += timedelta(hours=1)
    return timestamps


def fetch_payload(start_date: str, end_date: str) -> tuple[dict, str]:
    params = {
        "latitude": BANGKOK_LATITUDE,
        "longitude": BANGKOK_LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,relative_humidity_2m",
        "timezone": TIMEZONE,
    }
    url = f"{API_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "smart-energy-dashboard/1.0"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status = response.status
            body = response.read()
    except HTTPError as error:
        raise RuntimeError(f"Open-Meteo HTTP error {error.code}: {error.reason}") from error
    except URLError as error:
        raise RuntimeError(f"Open-Meteo connection error: {error.reason}") from error
    except TimeoutError as error:
        raise RuntimeError("Open-Meteo request timed out") from error
    if status != 200:
        raise RuntimeError(f"Open-Meteo returned unexpected HTTP status {status}")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("Open-Meteo returned a non-JSON response") from error
    if payload.get("error"):
        raise RuntimeError(f"Open-Meteo API error: {payload.get('reason', 'unknown error')}")
    return payload, url


def build_rows(payload: dict, start_date: str, end_date: str) -> list[dict[str, str]]:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise RuntimeError("Open-Meteo response has no hourly data")
    times = hourly.get("time")
    temperatures = hourly.get("temperature_2m")
    humidity = hourly.get("relative_humidity_2m")
    if not all(isinstance(values, list) for values in (times, temperatures, humidity)):
        raise RuntimeError("Open-Meteo hourly arrays are missing or malformed")
    if not (len(times) == len(temperatures) == len(humidity)):
        raise RuntimeError("Open-Meteo hourly arrays have different lengths")

    expected = expected_timestamps(start_date, end_date)
    rows = []
    for index, timestamp in enumerate(times):
        local = datetime.fromisoformat(timestamp).replace(tzinfo=ZoneInfo(TIMEZONE))
        rows.append(
            {
                "timestamp": local.isoformat(),
                "timezone": TIMEZONE,
                "temperature_2m_c": "" if temperatures[index] is None else str(temperatures[index]),
                "relative_humidity_2m_pct": "" if humidity[index] is None else str(humidity[index]),
            }
        )
    actual_timestamps = [datetime.fromisoformat(row["timestamp"]) for row in rows]
    if actual_timestamps != expected:
        raise RuntimeError(
            f"Unexpected hourly timestamp coverage: expected {len(expected)} rows "
            f"from {expected[0].isoformat()} to {expected[-1].isoformat()}, "
            f"received {len(actual_timestamps)} rows"
        )
    return rows


def write_rows(rows: list[dict[str, str]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=OUTPUT_DIR, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        writer = csv.DictWriter(temporary, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(OUTPUT_FILE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2018-07-01")
    parser.add_argument("--end-date", default="2018-12-31")
    args = parser.parse_args()
    if args.start_date > args.end_date:
        raise ValueError("start date must not be after end date")
    payload, url = fetch_payload(args.start_date, args.end_date)
    rows = build_rows(payload, args.start_date, args.end_date)
    write_rows(rows)
    missing_temperature = sum(not row["temperature_2m_c"] for row in rows)
    missing_humidity = sum(not row["relative_humidity_2m_pct"] for row in rows)
    print(
        json.dumps(
            {
                "http_status": 200,
                "request_url": url,
                "output": str(OUTPUT_FILE),
                "rows": len(rows),
                "first_timestamp": rows[0]["timestamp"],
                "last_timestamp": rows[-1]["timestamp"],
                "timezone": TIMEZONE,
                "missing_temperature_2m": missing_temperature,
                "missing_relative_humidity_2m": missing_humidity,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f"Weather fetch failed: {error}", file=sys.stderr)
        raise SystemExit(1)
