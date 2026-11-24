"""Only the upstream D proc-disappearance fix as applied to future P runners."""
import unittest
from unittest import mock
import exit_lifecycle as m

class ProcDisappearanceTests(unittest.TestCase):
    def test_process_exits_before_task_directory_observation(self):
        with mock.patch.object(m.Path,"iterdir",side_effect=ProcessLookupError(3,"process exited")):
            self.assertEqual(m.children(123456),set())
    def test_exited_thread_does_not_hide_other_live_children(self):
        tasks=[m.Path("/proc/123456/task/1"),m.Path("/proc/123456/task/2")]
        with mock.patch.object(m.Path,"iterdir",return_value=iter(tasks)):
            with mock.patch.object(m.Path,"read_text",side_effect=[ProcessLookupError(3,"thread exited"),"42 43"]):
                self.assertEqual(m.children(123456),{42,43})
    def test_unrelated_failure_is_not_a_clean_tree(self):
        with mock.patch.object(m.Path,"iterdir",side_effect=PermissionError(13,"not readable")):
            with self.assertRaises(PermissionError):m.children(123456)

if __name__=="__main__":unittest.main()
