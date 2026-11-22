"""I1 cooperative controls: native handoff contract, no output creation, clean thread exit."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from i1_runtime_control import request_handoff,watch
from phychem_mfm.phase1.p_recipe_handoff import read_request


class I1RuntimeTests(unittest.TestCase):
    def configuration(self,root):
        return dict(run="I1_synthetic",output=str(Path(root)/"not_created"),
                    handoff_request=str(Path(root)/"control/request.json"))

    def test_deadline_request_matches_original_native_contract(self):
        with tempfile.TemporaryDirectory() as root:
            c=self.configuration(root)
            request_handoff(c,"synthetic-job","deadline")
            self.assertEqual(read_request(c)["action"],"SAVE_AND_EXIT")
            self.assertFalse(Path(c["output"]).exists())
            with self.assertRaisesRegex(ValueError,"different"):
                request_handoff(c,"other-job","deadline")

    def test_normal_completion_joins_without_request(self):
        with tempfile.TemporaryDirectory() as root:
            c=self.configuration(root);done=threading.Event()
            thread=threading.Thread(target=watch,args=(c,"synthetic-job"),kwargs=dict(
                done=done,stop_requested=lambda:False,stop_new_at=1e20,
                guard=lambda:None,telemetry=lambda:None,interval=.001))
            thread.start();done.set();thread.join()
            self.assertFalse(thread.is_alive());self.assertFalse(Path(c["handoff_request"]).exists())

    def test_storage_failure_requests_one_own_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            c=self.configuration(root);done=threading.Event();ticks=iter([0.,2.,3.,4.])
            def fail():
                done.set();raise OSError("synthetic capacity")
            watch(c,"synthetic-job",done=done,stop_requested=lambda:False,
                  stop_new_at=1e20,guard=fail,telemetry=lambda:None,
                  interval=.001,guard_interval=1.,now=lambda:next(ticks))
            value=read_request(c)
            self.assertEqual(value["run"],c["run"])
            self.assertTrue(value["reason"].startswith("actual_storage"))


if __name__=="__main__":
    unittest.main()
