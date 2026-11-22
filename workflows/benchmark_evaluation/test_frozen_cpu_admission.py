"""Quota transport recovery and private CPU admission; no benchmark data."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from .frozen_cpu_admission import fresh_quota,frozen_cpu_protect

def snapshot(epoch=1000,uid=1278):
    return dict(uid=uid,generation="benchmarkB020261119",returncode=0,
                observed_epoch=epoch,raw="original fixture quota")

class FrozenCPUAdmissionTests(unittest.TestCase):
    def test_only_stale_snapshot_is_retried_and_fresh_second_snapshot_is_used(self):
        old=snapshot(100);new=snapshot(1000);read=Mock(side_effect=[old,new])
        self.assertEqual(fresh_quota("unused",reader=read,clock=lambda:1001,uid=1278),new)
        self.assertEqual(read.call_count,2)
        edge=snapshot(911)
        self.assertEqual(fresh_quota("unused",reader=lambda:edge,clock=lambda:1001,uid=1278),edge)

    def test_identity_or_future_snapshot_never_gets_a_retry(self):
        for first in [snapshot(uid=999),snapshot(1002),
                      dict(snapshot(),returncode=1),dict(snapshot(),generation="foreign")]:
            read=Mock(side_effect=[first,snapshot()])
            with self.assertRaises(RuntimeError):
                fresh_quota("unused",reader=read,clock=lambda:1001,uid=1278)
            self.assertEqual(read.call_count,1)

    def test_two_stale_reads_still_refuse_instead_of_relaxing90seconds(self):
        read=Mock(side_effect=[snapshot(1),snapshot(2)])
        with self.assertRaises(RuntimeError):
            fresh_quota("unused",reader=read,clock=lambda:1001,uid=1278)
        self.assertEqual(read.call_count,2)

    def test_private_cpu2_gate_does_not_modify_original_running_admission(self):
        from workflows.benchmark_data import admission
        original=Path(admission.__file__).read_text()
        old_function=admission.protect
        protected=frozen_cpu_protect(original,"compute-0-2")
        scope=protected.__globals__;calls=[]
        scope["_fresh_quota"]=lambda value:snapshot(1000)
        scope["guard"]=lambda *args:calls.append(args)
        scope["quota_headroom"]=lambda raw,uid:123
        scope["current_pool"]=lambda root,value:value
        with patch("socket.gethostname",return_value="compute-0-2"),patch("os.getuid",return_value=1278),patch("time.time",return_value=1001):
            protected(Path("/fixture-owned"),1,"fixture-snapshot")
            with self.assertRaises(RuntimeError):old_function(Path("/fixture-owned"),1,"fixture-snapshot")
        self.assertEqual(len(calls),1)
        self.assertIs(admission.protect,old_function)
        self.assertIn("range(8,20)",original)
        with self.assertRaises(ValueError):frozen_cpu_protect(original,"compute-0-21")

if __name__=="__main__":
    unittest.main()
