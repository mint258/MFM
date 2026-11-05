"""Original-source readback entry using the same dynamic sparse-pair adapter."""
from __future__ import annotations
import argparse
from pathlib import Path
from . import verify as baseline
from .source_v2 import target_arrays
from .io import write_json
from wire_v1.store import file_ref

_BASE_GROUP_CHECK = baseline.check_source_group


def check_source_group_v2(task):
    original = baseline.target_arrays
    baseline.target_arrays = target_arrays
    try:
        return _BASE_GROUP_CHECK(task)
    finally:
        baseline.target_arrays = original


def run(export_manifest, output, *, fixture=False, sample_records=10000, seed=20261025):
    original = baseline.check_source_group
    if original is not _BASE_GROUP_CHECK:
        raise ValueError("UNEXPECTED_SOURCE_READBACK_WORKER_OVERRIDE")
    baseline.check_source_group = check_source_group_v2
    try:
        result = baseline.run(export_manifest, output, fixture=fixture, sample_records=sample_records, seed=seed)
    finally:
        baseline.check_source_group = original
    write_json(Path(str(output) + ".source_pair_v2.json"), {
        "status": "FIXTURE_ONLY" if fixture else "DYNAMIC_PAIR_SOURCE_V2_READBACK_ADAPTER_USED",
        "readback_receipt": file_ref(Path(output)), "variant_source": file_ref(Path(__file__)),
        "adapter_source": file_ref(Path(__file__).with_name("source_v2.py")),
        "baseline_source": file_ref(Path(baseline.__file__)), "contract_finalized": False, "d3_accepted": False})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--export-manifest", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--sample-records", type=int, default=10000)
    p.add_argument("--fixture", action="store_true")
    a = p.parse_args(); run(a.export_manifest, a.output, fixture=a.fixture, sample_records=a.sample_records)


if __name__ == "__main__":
    main()
