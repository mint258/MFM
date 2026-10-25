"""Export entry with dynamic per-field sparse-pair adapter in every spawn worker."""
from __future__ import annotations
import argparse
from pathlib import Path
from . import export as baseline
from .source_v2 import target_arrays
from .io import read_json, write_json
from wire_v1.store import file_ref

_BASE_INITIALIZER = baseline.stage_initializer


def stage_initializer_v2(counter, cap):
    _BASE_INITIALIZER(counter, cap)
    baseline.target_arrays = target_arrays


def run(config, output, *, fixture=False, candidate=False):
    original = baseline.stage_initializer
    if original is not _BASE_INITIALIZER:
        raise ValueError("UNEXPECTED_SOURCE_WORKER_INITIALIZER_OVERRIDE")
    baseline.stage_initializer = stage_initializer_v2
    try:
        result = baseline.run(config, output, fixture=fixture, candidate=candidate)
    finally:
        baseline.stage_initializer = original
    write_json(Path(output) / "source_pair_v2_receipt.json", {
        "status": "FIXTURE_ONLY" if fixture else "CANDIDATE_DYNAMIC_PAIR_SOURCE_V2_APPLIED",
        "export_manifest": file_ref(Path(output) / "manifest.json"),
        "variant_source": file_ref(Path(__file__)),
        "adapter_source": file_ref(Path(__file__).with_name("source_v2.py")),
        "baseline_source": file_ref(Path(baseline.__file__)),
        "field_specific_sparse_pair_indices": True,
        "source_pair_order_direction_and_zero_basis_preserved": True,
        "all_other_production_freeze_guards_unchanged": True,
        "contract_finalized": False, "d3_accepted": False})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--candidate-only", action="store_true")
    p.add_argument("--fixture", action="store_true")
    a = p.parse_args(); run(read_json(a.config), a.output, fixture=a.fixture, candidate=a.candidate_only)


if __name__ == "__main__":
    main()
