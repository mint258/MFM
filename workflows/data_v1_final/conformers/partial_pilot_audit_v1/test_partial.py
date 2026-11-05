"""Four new partial-audit boundaries; no producer replay or scientific calculation."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import unittest
from audit_partial import (admit,checkpoint,expected_filenames,require_locator_authorization,terminal_accounting)


class PartialBoundaries(unittest.TestCase):
    def test_timeout_exit_zero_never_becomes_completed_and_steps_not_double_charged(self):
        raw="JobIDRaw|State|ExitCode|ElapsedRaw|AllocCPUS\n4520364|TIMEOUT|0:0|14425|16\n4520364.batch|CANCELLED|0:15|14429|16\n"
        parent,rows,steps=terminal_accounting(raw,"4520364")
        self.assertEqual(parent["state"],"TIMEOUT")
        self.assertEqual(parent["allocated_core_seconds"],230800)
        self.assertAlmostEqual(parent["allocated_core_seconds"]/3600,64.11111111111111)
        self.assertEqual(len(rows),1);self.assertEqual(len(steps),1)
    def test_running_and_completed_parent_cannot_fake_timeout_audit(self):
        for state in ("RUNNING","COMPLETED"):
            with self.assertRaises(ValueError):
                terminal_accounting(f"JobID|State|ExitCode|ElapsedRaw|AllocCPUS\n4520364|{state}|0:0|1|16\n","4520364")
    def test_filename_mapping_uses_exact336_unique_metadata_ids(self):
        mids=[f"fixture{i}" for i in range(336)]
        mapping=expected_filenames(mids)
        self.assertEqual(mapping[hashlib.sha256(b"fixture0").hexdigest()+".json.gz"],"fixture0")
        with self.assertRaisesRegex(ValueError,"UNIQUE"):expected_filenames(mids[:-1]+[mids[0]])
    def test_tasks_body_requires_explicit_readonly_root_locator_authorization(self):
        with self.assertRaisesRegex(ValueError,"LOCATOR_AUTHORIZATION"):
            require_locator_authorization({}, {}, {}, {}, {}, {})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",type=Path,required=True)
    p.add_argument("--cpu-runconfig",type=Path,required=True);p.add_argument("--root-preflight",type=Path,required=True)
    a=p.parse_args();admit(a.root_preflight,Path(__file__),a.cpu_runconfig,a.config,"closure")
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PartialBoundaries))
    checkpoint();return 0 if result.wasSuccessful() else 1


if __name__=="__main__":raise SystemExit(main())
