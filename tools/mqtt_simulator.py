"""Publish local meter payloads to an MQTT topic.

The simulator does not contain broker credentials. Supply them through
environment variables or command-line options when testing against a broker.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone


def build_payload(source_id: str, floor: str, zone: str, load_type: str, actual_kw: float) -> dict:
    return {
        "source_id": source_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "floor": floor,
        "zone": zone,
        "load_type": load_type,
        "actual_kw": actual_kw,
        "interval_minutes": 1,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    parser.add_argument("--topic", default=os.environ.get("MQTT_TOPIC", "smart-energy/meters"))
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--floor", default="Floor1")
    parser.add_argument("--zone", default="z2")
    parser.add_argument("--load-type", default="AC", choices=("AC", "Light", "Plug"))
    parser.add_argument("--actual-kw", type=float, required=True)
    args = parser.parse_args()

    try:
        import paho.mqtt.client as mqtt
    except ImportError as error:
        raise SystemExit("Install tools/requirements-simulator.txt first") from error

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    username = os.environ.get("MQTT_USERNAME")
    password = os.environ.get("MQTT_PASSWORD")
    if username:
        client.username_pw_set(username, password)
    client.connect(args.host, args.port)
    payload = build_payload(args.source_id, args.floor, args.zone, args.load_type, args.actual_kw)
    result = client.publish(args.topic, json.dumps(payload), qos=1)
    result.wait_for_publish()
    client.disconnect()
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
