"""Three isolated physical-key boundary tests, no repeat of full D5 fixtures."""
from __future__ import annotations
import argparse
from pathlib import Path
import unittest
from . import materialize
from .materialize_v2 import validate
from .io import check_allocation, connect, fresh_dir, write_json
from wire_v1.store import file_ref

ROOT = None


def database(name, *, uff_idx=0, pm7_native="pm7-native"):
    db = connect(ROOT / (name + ".sqlite"))
    for kind, definition in materialize.SCHEMA.items():
        db.execute("CREATE TABLE " + kind + "(" + definition + ")")
    db.execute("INSERT INTO roles VALUES('m','TRAIN','TRAIN')")
    db.execute("INSERT INTO common VALUES('m',1)")
    db.execute("INSERT INTO features VALUES('m','[1,6]',1,'')")
    rows = [
        ("p", "m", "pm7", "pm7-native", None, None, None),
        ("pv", "m", "pm7", pm7_native, None, "p", "perturbed"),
        ("u", "m", "uff_sprime", "base-trace", 0, None, None),
        ("uv", "m", "uff_sprime", "different-view-trace", uff_idx, "u", "perturbed"),
    ]
    db.executemany("INSERT INTO geometries VALUES(?,?,?,?,?,?,?)", rows)
    db.executemany("INSERT INTO orders VALUES(?,?,?,?,?)", [("m", src, kind, 0, gid)
        for src, gid in (("pm7", "p"), ("uff_sprime", "u")) for kind in ("fixed_random", "energy", "diversity")])
    db.commit()
    return db


class ParentKeyTests(unittest.TestCase):
    def test_uff_same_molecule_idx_different_native_trace_pass(self):
        db = database("uff_trace_pass")
        try:
            with self.assertRaisesRegex(ValueError, "VIEW_PARENT_KEY"):
                materialize.validate(db)  # Explicitly reproduce v1 overconstraint.
            validate(db)
        finally:
            db.close()

    def test_uff_different_idx_fail(self):
        db = database("uff_idx_fail", uff_idx=1)
        try:
            with self.assertRaisesRegex(ValueError, "VIEW_PARENT_KEY"):
                validate(db)
        finally:
            db.close()

    def test_pm7_different_native_fail(self):
        db = database("pm7_native_fail", pm7_native="different-PM7-physical-record")
        try:
            with self.assertRaisesRegex(ValueError, "VIEW_PARENT_KEY"):
                validate(db)
        finally:
            db.close()


def main():
    global ROOT
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args(); check_allocation(True); ROOT = fresh_dir(a.output)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ParentKeyTests))
    write_json(ROOT / "test_summary.json", {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "source_data_read": False,
        "sources": [file_ref(Path(__file__)), file_ref(Path(__file__).with_name("materialize_v2.py")), file_ref(Path(materialize.__file__))]})
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
