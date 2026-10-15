#!/usr/bin/env python3
"""Export an offline W&B run into reproducible JSON/CSV curve data."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from wandb.proto import wandb_internal_pb2
from wandb.sdk.internal.datastore import DataStore


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-file", required=True, help="Path to an offline run-*.wandb file")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--min-step", type=int, default=None)
    parser.add_argument("--max-step", type=int, default=None)
    parser.add_argument("--keys", default=None, help="Optional comma-separated metric allowlist")
    return parser.parse_args()


def decode_history(path: Path) -> list[dict[str, object]]:
    store = DataStore()
    store.open_for_scan(str(path))
    rows: list[dict[str, object]] = []
    while True:
        data = store.scan_data()
        if data is None:
            break
        record = wandb_internal_pb2.Record()
        record.ParseFromString(data)
        if not record.HasField("history"):
            continue
        row: dict[str, object] = {}
        for item in record.history.item:
            key = item.key or "/".join(item.nested_key)
            if key:
                row[key] = json.loads(item.value_json)
        if row:
            rows.append(row)
    return rows


def main() -> None:
    args = parse_args()
    rows = decode_history(Path(args.run_file))
    selected_keys = None if args.keys is None else {item.strip() for item in args.keys.split(",") if item.strip()}
    filtered = []
    for row in rows:
        step = int(row.get("_step", -1))
        if args.min_step is not None and step < args.min_step:
            continue
        if args.max_step is not None and step > args.max_step:
            continue
        if selected_keys is not None:
            row = {key: value for key, value in row.items() if key in selected_keys or key == "_step"}
        filtered.append(row)

    output_json = Path(args.output_json)
    output_csv = Path(args.output_csv)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(filtered, indent=2, sort_keys=True), encoding="utf-8")
    fieldnames = sorted({key for row in filtered for key in row})
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered)
    print(json.dumps({"run_file": args.run_file, "rows": len(filtered), "fields": fieldnames}, sort_keys=True))


if __name__ == "__main__":
    main()
