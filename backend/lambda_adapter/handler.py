"""Forward an AWS IoT Core event to the FastAPI ingest endpoint."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def lambda_handler(event: dict, context: object) -> dict:
    endpoint = os.environ.get("INGEST_API_URL")
    if not endpoint:
        raise RuntimeError("INGEST_API_URL is required")
    payload = event.get("payload", event)
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("IoT event payload must be a JSON object")

    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("INGEST_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=float(os.environ.get("INGEST_API_TIMEOUT", "10"))) as response:
            response_body = response.read().decode("utf-8")
            return {"statusCode": response.status, "body": response_body}
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"FastAPI ingest returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"FastAPI ingest request failed: {error.reason}") from error
