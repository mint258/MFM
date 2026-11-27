import unittest
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace
from unittest.mock import patch
from fullft_runtime_ram_20261127 import POLICY, anonymous_pss, remaining_ram_check, admit_runtime, validate_policy, self_sample


class RuntimeRAM(unittest.TestCase):
    def test_only_anonymous_proportional_pages_are_credited(self):
        self.assertEqual(anonymous_pss('Pss_File: 900 kB\nPss_Shmem: 800 kB\nPss_Anon: 3 kB\nLazyFree: 0 kB'), 3072)
        self.assertEqual(anonymous_pss('Pss_Anon: 3 kB\nLazyFree: 1 kB'),2048)
        self.assertEqual(anonymous_pss('Pss_Anon: 3 kB\nLazyFree: 5 kB'),0)
        for text in ('Pss: 100 kB', 'Pss_Anon: -1 kB', 'Pss_Anon: 3 MB', 'Pss_Anon: unknown kB','Pss_Anon: 3 kB'):
            self.assertIsNone(anonymous_pss(text))

    def test_already_committed_memory_does_not_reduce_headroom_twice(self):
        # 64 pretraining +6 fit +16 system; a3-byte own allocation reduces
        # MemAvailable and remaining fit demand equally. Peer reserve is kept.
        calls=[]
        def check(need):
            calls.append(need)
            if 16+need+4 > 87:
                raise ValueError('physical shortfall')
            return dict(own=need, reserve=16, peers=4, available=87)
        report, accounting=remaining_ram_check(70,6,lambda:dict(credit_bytes=3),check)
        self.assertEqual(calls,[67])
        self.assertEqual(report['reserve'],16)
        self.assertEqual(report['peers'],4)
        self.assertEqual(accounting['this_fit_peak_bytes'],6)
        self.assertEqual(accounting['registered_S_peak_bytes'],70)

    def test_real_external_pressure_still_refuses(self):
        def check(need):
            if 16+need > 82:raise ValueError('physical shortfall')
        with self.assertRaisesRegex(ValueError,'physical shortfall'):
            remaining_ram_check(70,6,lambda:dict(credit_bytes=3),check)

    def test_missing_or_out_of_contract_credit_never_weakens_guard(self):
        calls=[]
        remaining_ram_check(70,6,lambda:dict(credit_bytes=0),lambda need:calls.append(need))
        self.assertEqual(calls,[70])
        with self.assertRaises(ValueError):
            remaining_ram_check(70,6,lambda:dict(credit_bytes=7),lambda need:None)

    def test_freed_residency_is_rechecked_conservatively(self):
        samples=iter((3,2,1,0));calls=[]
        report,accounting=remaining_ram_check(70,6,
            lambda:dict(credit_bytes=next(samples)),lambda need:calls.append(need))
        self.assertEqual(calls,[67,68,69,70])
        self.assertEqual(accounting['committed_own_anon_bytes'],0)

    def test_default_off_and_existing_refusals_are_preserved(self):
        with patch('storage_line_20261122.admit',side_effect=RuntimeError('disk refusal')) as old:
            with self.assertRaisesRegex(RuntimeError,'disk refusal'):
                admit_runtime({}, {})
            old.assert_called_once_with({})
        validate_policy({'runtime_ram_accounting':POLICY})
        with self.assertRaises(ValueError):validate_policy({'runtime_ram_accounting':'unknown'})

    def test_enabled_mode_checks_physical_disk_before_any_ram_credit(self):
        import storage_line_20261122 as line
        with TemporaryDirectory() as tmp:
            root=Path(tmp); registry=root/'registry';registry.mkdir()
            (registry/'s-recipe.json').write_text(json.dumps({'entries':[
                dict(kind='node_disk',node='compute-0-20',path='/',bytes=32*1024**2),
                dict(id='pretraining',kind='node_ram',node='compute-0-20',bytes=64),
                dict(id='this_fit',kind='node_ram',node='compute-0-20',bytes=6)]}))
            quota=root/'runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json'
            quota.parent.mkdir(parents=True)
            quota.write_text(json.dumps(dict(uid=os.getuid(),filesystem='/share',
                observed_time=time.time(),available_bytes=100000)))
            calls=[]
            def check(owner,kind,need,**kwargs):
                calls.append((kind,kwargs))
                raise RuntimeError('actual root disk refused')
            guard=SimpleNamespace(REGISTRY=registry,_same_device=lambda *a:{'/'},
                AdmissionRefused=RuntimeError,check_with_timeout=check)
            storage=SimpleNamespace(ROOT=root,shared_guard=guard,claim_current=lambda:17)
            with patch.object(line,'storage',storage),patch('socket.gethostname',return_value='compute-0-20'),patch('fullft_runtime_ram_20261127.self_sample') as sample:
                with self.assertRaisesRegex(RuntimeError,'actual root disk refused'):
                    admit_runtime(dict(runtime_ram_accounting=POLICY,node='compute-0-20',peak_ram_bytes=6,runtime_ram_reservation_id='this_fit'),{})
                sample.assert_not_called()
            self.assertEqual(calls,[('node_disk',dict(path='/',new_inodes=1000))])

    def test_other_phase_peak_is_not_a_current_fit_reservation(self):
        import storage_line_20261122 as line
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'s-recipe.json').write_text(json.dumps({'entries':[
                dict(kind='node_disk',node='compute-0-20',path='/',bytes=32*1024**2),
                dict(id='pretraining',kind='node_ram',node='compute-0-20',bytes=64)]}))
            guard=SimpleNamespace(REGISTRY=root,_same_device=lambda *a:{'/'},AdmissionRefused=RuntimeError)
            storage=SimpleNamespace(ROOT=root,shared_guard=guard,claim_current=lambda:17)
            with patch.object(line,'storage',storage),patch('socket.gethostname',return_value='compute-0-20'):
                with self.assertRaisesRegex(RuntimeError,'No exact current-fit'):
                    admit_runtime(dict(runtime_ram_accounting=POLICY,node='compute-0-20',peak_ram_bytes=6,runtime_ram_reservation_id='this_fit'),{})

    def test_foreign_process_identity_cannot_earn_credit(self):
        with self.assertRaises(ValueError):
            self_sample(dict(pid=os.getpid(),uid=1,start_ticks=0,ppid=0,state='R'),6*1024**3)
