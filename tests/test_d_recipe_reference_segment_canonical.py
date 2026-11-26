"""Writer adaptation restores process state and never reuses the legacy guard."""
from pathlib import Path
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from tools.d_recipe.reference_segment_canonical import require_closed_predecessor, scoped_collector_writes


class CanonicalCollectorScopeTests(unittest.TestCase):
    def test_saved_receipt_requires_actual_old_processes_to_be_gone(self):
        record = dict(execution_id="ssh:P_D_fixture", status="CURSOR_SAVED_NOT_COMPLETE",
                      returncode=75, remaining_children=[], owned_tree_reaped=True,
                      supervisor=dict(pid=100, start_ticks=10, uids=[os.getuid()] * 4),
                      parent=dict(pid=99, start_ticks=9, uids=[os.getuid()] * 4))
        require_closed_predecessor(record, record["execution_id"], lambda pid: None)
        with self.assertRaisesRegex(ValueError, "still exists"):
            require_closed_predecessor(record, record["execution_id"],
                lambda pid: SimpleNamespace(start_ticks=10 if pid == 100 else 9,
                                            uids=(os.getuid(),) * 4))
        # An unrelated process that reused a PID is not the old producer.
        require_closed_predecessor(record, record["execution_id"],
            lambda pid: SimpleNamespace(start_ticks=11, uids=(os.getuid(),) * 4))
        record["status"] = "RUNNING"
        with self.assertRaisesRegex(ValueError, "saved and fully reaped"):
            require_closed_predecessor(record, record["execution_id"], lambda pid: None)

    def test_committed_phase_uses_only_scope_and_restores_even_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = Mock(side_effect=AssertionError("Historical peer guard must not run"))
            resources = SimpleNamespace(admit_output=previous)
            with self.assertRaisesRegex(ValueError, "escaped"):
                with scoped_collector_writes(resources, root):
                    resources.admit_output({"legacy_peer_copy": 10**30}, root / "collection")
                    resources.admit_output({}, root.parent / "outside")
            self.assertIs(resources.admit_output, previous)
            previous.assert_not_called()


if __name__ == "__main__":
    unittest.main()
