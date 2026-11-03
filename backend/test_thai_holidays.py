"""Feasibility test for Nager.Date Thailand public holidays for 2018."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "external" / "thai_public_holidays_nager_2018.json"
API_URL = "https://date.nager.at/api/v3/PublicHolidays/2018/TH"
START_DATE = date(2018, 1, 1)
END_DATE = date(2018, 12, 31)
REQUIRED_FIELDS = {"date", "localName", "name", "countryCode", "fixed", "global", "types"}


def fetch() -> tuple[int, object, str]:
    request = urllib.request.Request(
        API_URL,
        headers={"Accept": "application/json", "User-Agent": "smart-energy-dashboard-feasibility-test"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = int(response.status)
            raw_body = response.read().decode("utf-8")
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError:
                body = None
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Nager.Date returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Nager.Date request failed: {error.reason}") from error
    return status, body, raw_body


def validate(status: int, body: object, raw_body: str) -> dict:
    errors: list[str] = []
    dates: list[date] = []
    schema_valid = isinstance(body, list)
    if not schema_valid:
        errors.append("Response body is not a JSON array")
    else:
        for index, item in enumerate(body):
            if not isinstance(item, dict):
                errors.append(f"Item {index} is not a JSON object")
                continue
            missing = REQUIRED_FIELDS.difference(item)
            if missing:
                errors.append(f"Item {index} missing fields: {sorted(missing)}")
            try:
                dates.append(date.fromisoformat(item["date"]))
            except (KeyError, TypeError, ValueError):
                errors.append(f"Item {index} has an invalid date")
    duplicates = sorted({value.isoformat() for value in dates if dates.count(value) > 1})
    out_of_range = sorted(
        value.isoformat()
        for value in dates
        if value < START_DATE or value > END_DATE
    )
    if duplicates:
        errors.append(f"Duplicate dates: {duplicates}")
    if out_of_range:
        errors.append(f"Dates outside 2018: {out_of_range}")
    if status != 200:
        errors.append(f"Unexpected HTTP status: {status}")
    return {
        "api_url": API_URL,
        "http_status": status,
        "response_schema": "array<object>" if schema_valid else "invalid",
        "item_count": len(body) if isinstance(body, list) else None,
        "duplicate_dates": duplicates,
        "out_of_range_dates": out_of_range,
        "missing_required_fields": bool(errors),
        "errors": errors,
        "usable_for_model": status == 200 and schema_valid and bool(body) and not errors,
        "raw_response": raw_body,
        "response": body,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    status, body, raw_body = fetch()
    result = validate(status, body, raw_body)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "response"}, indent=2))
    if not result["usable_for_model"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
