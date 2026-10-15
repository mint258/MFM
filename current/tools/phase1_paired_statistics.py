#!/usr/bin/env python3
"""Consume frozen paired-seed statistics; never fit models or select comparisons.

Input metrics and checkpoint/state identities come from the evaluation producer.
This tool verifies actual protocol/plan/metric file bytes and their declared
pairing contract. It does not independently recompute scores or model states.
Formal production use follows the site's CPU Slurm policy; bounded synthetic
correctness checks may run on an authorized compute node.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phychem_mfm.phase1.paired_statistics import analyze_paired_statistics


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key in a statistics input")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON constant in a statistics input")


def _read_object(path, limit):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Statistics input must be a bounded regular file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Statistics input exceeded its byte bound during read")
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_keys,
                       parse_constant=_reject_constant)
    if not isinstance(value, dict):
        raise ValueError("Statistics inputs must contain JSON objects")
    return value, {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, help="Existing frozen protocol; this command never creates or freezes one")
    parser.add_argument("--analysis-plan", required=True, help="Exact analysis artifact already bound by the protocol")
    parser.add_argument("--metrics", required=True, help="Complete pretraining-seed/cell metric records from the evaluation producer")
    parser.add_argument("--output", required=True, help="New JSON receipt path; existing results are preserved")
    args = parser.parse_args(argv)
    began = time.monotonic()
    try:
        protocol, protocol_binding = _read_object(args.protocol, 1024**2)
        plan, plan_binding = _read_object(args.analysis_plan, 1024**2)
        metrics, metrics_binding = _read_object(args.metrics, 32*1024**2)
        output = Path(args.output)
        resolved_output = output.resolve()
        if output.exists() or output.is_symlink() or any(
                resolved_output == Path(binding["path"]) for binding in
                (protocol_binding, plan_binding, metrics_binding)):
            raise ValueError("Statistics output must be new and distinct from its inputs")
        analysis = analyze_paired_statistics(plan, metrics, protocol,
            plan_sha256=plan_binding["sha256"], records_sha256=metrics_binding["sha256"])
        # Check the exact files once more after computation. File hashes bind
        # bytes; metric and checkpoint truth is still producer responsibility.
        for original, limit in ((protocol_binding, 1024**2), (plan_binding, 1024**2), (metrics_binding, 32*1024**2)):
            _, current = _read_object(original["path"], limit)
            if current != original:
                raise ValueError("Statistics input bytes changed during consumption")
        receipt = {"schema_version": "phase1_paired_statistics_file_receipt_v1",
            "status": "STATISTICAL_CONSUMPTION_COMPLETE", "analysis": analysis,
            "input_files": [protocol_binding, plan_binding, metrics_binding],
            "input_files_unchanged": True,
            "acceptance_requires_process_exit_zero": True,
            "verification_scope": "Actual input bytes, declared complete pairing, and statistical computation; no independent model-state or metric recomputation",
            "formal_training_authorized": False, "elapsed_seconds": time.monotonic()-began}
        encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                             allow_nan=False).encode("utf-8")
        receipt["receipt_sha256"] = hashlib.sha256(encoded).hexdigest()
        payload = (json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                              allow_nan=False) + "\n").encode("utf-8")
        if len(payload) > 1024**2:
            raise ValueError("Statistics receipt exceeds its 1 MiB output bound")
        # Publish only a fully written/fsynced receipt. A hard link provides
        # exclusive creation without replacing a concurrently created result.
        pending = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent,
                    prefix=".paired-statistics-", suffix=".pending", delete=False) as stream:
                pending = Path(stream.name)
                if stream.write(payload) != len(payload):
                    raise OSError("Incomplete statistics receipt write")
                stream.flush()
                os.fsync(stream.fileno())
            os.link(pending, output)
        finally:
            if pending is not None:
                pending.unlink(missing_ok=True)
        print(json.dumps({"status": receipt["status"], "output": str(resolved_output),
            "output_bytes": len(payload), "output_sha256": hashlib.sha256(payload).hexdigest()}, sort_keys=True))
        return 0
    except (OSError, TypeError, ValueError, KeyError, OverflowError) as error:
        # Closed partial writes are never valid without a successful process.
        print(json.dumps({"status": "STATISTICAL_CONSUMPTION_FAILED", "error_type": type(error).__name__,
            "reason": str(error)[:1024], "formal_training_authorized": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
