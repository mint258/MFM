"""Production entry: compare parent identity using each geometry's physical key.

The registered v1 baseline remains byte-for-byte intact. This narrow adapter
replaces only its known parent-key predicate; every other validator and all
materialization code run unchanged. UFF native_record_id is provenance only.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from . import materialize as baseline
from .io import read_json, write_json
from wire_v1.store import file_ref

_BASE_VALIDATE = baseline.validate
_OLD = "p.native_record_id IS NOT g.native_record_id OR p.sprime_conf_idx IS NOT g.sprime_conf_idx"
_NEW = "(g.geometry_source='pm7' AND p.native_record_id IS NOT g.native_record_id) OR (g.geometry_source='uff_sprime' AND p.sprime_conf_idx IS NOT g.sprime_conf_idx)"


class PhysicalParentKeys:
    def __init__(self, connection):
        self.connection = connection
        self.replacements = 0

    def execute(self, sql, parameters=()):
        if _OLD in sql:
            if not sql.startswith("SELECT 1 FROM geometries g LEFT JOIN geometries p ON p.geometry_id=g.parent_geometry_id") or sql.count(_OLD) != 1:
                raise ValueError("BASELINE_PARENT_PREDICATE_CHANGED_REVIEW_REQUIRED")
            self.replacements += 1
            sql = sql.replace(_OLD, _NEW, 1)
        return self.connection.execute(sql, parameters)

    def __getattr__(self, name):
        return getattr(self.connection, name)


def validate(connection):
    adapter = PhysicalParentKeys(connection)
    _BASE_VALIDATE(adapter)
    if adapter.replacements != 1:
        raise ValueError("BASELINE_PARENT_PREDICATE_NOT_FOUND_REVIEW_REQUIRED")


def run(config, output, *, fixture=False, workers=16):
    original = baseline.validate
    if original is not _BASE_VALIDATE:
        raise ValueError("UNEXPECTED_VALIDATOR_OVERRIDE")
    baseline.validate = validate
    try:
        result = baseline.run(config, output, fixture=fixture, workers=workers)
    finally:
        baseline.validate = original
    write_json(Path(output) / "physical_parent_keys_v2_receipt.json", {
        "status": "FIXTURE_ONLY" if fixture else "PHYSICAL_PARENT_KEYS_V2_APPLIED",
        "d5_manifest": file_ref(Path(output) / "manifest.json"),
        "variant_source": file_ref(Path(__file__)),
        "baseline_source": file_ref(Path(baseline.__file__)),
        "physical_parent_keys": {"pm7": ["molecule_id", "geometry_source", "native_record_id"],
                                 "uff_sprime": ["molecule_id", "geometry_source", "sprime_conf_idx"]},
        "uff_native_record_id_used_as_identity": False,
        "all_other_baseline_validation_unchanged": True})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--fixture", action="store_true")
    a = p.parse_args(); run(read_json(a.config), a.output, fixture=a.fixture)


if __name__ == "__main__":
    main()
