"""Our concurrent reservations and binding only; no models or old-result checks."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import storage_line_20261122 as storage
import train_line_storage_20261122 as entry


class LineStorageTests(unittest.TestCase):
    def row(self,kind,amount,node='compute-0-20',path=None):
        return dict(kind=kind,bytes=amount,node=node,path=path)

    def test_two_S_readers_on_same_node_are_added(self):
        entries=[self.row('node_ram',16),self.row('node_ram',16),self.row('node_ram',64,node='compute-0-22')]
        self.assertEqual(storage.requirements(entries,'compute-0-20',{'/'}),(0,32))

    def test_root_and_tmp_share_one_actual_device_budget(self):
        entries=[self.row('node_disk',16,path='/'),self.row('node_disk',64,path='/tmp'),
                 self.row('node_disk',100,node='compute-0-12',path='/')]
        self.assertEqual(storage.requirements(entries,'compute-0-20',{'/','/tmp'}),(80,0))
        self.assertEqual(storage.requirements(entries,'compute-0-20',{'/'}),(16,0))

    def test_startup_admits_the_whole_line_not_only_the_incoming_reader(self):
        gib=1024**3
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch)
            registry=root/'registry'
            registry.mkdir()
            entries=[self.row('node_ram',16*gib),self.row('node_ram',16*gib),
                     self.row('node_disk',64*1024**2,path='/')]
            (registry/'s-recipe.json').write_text(json.dumps(dict(entries=entries)))
            quota=root/'runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json'
            quota.parent.mkdir(parents=True)
            quota.write_text(json.dumps(dict(uid=os.getuid(),filesystem='/share',
                observed_time=time.time(),available_bytes=10**12)))
            with (patch.object(storage.storage,'ROOT',root),
                  patch.object(storage.storage,'claim_current',return_value=123),
                  patch.object(storage.storage.shared_guard,'REGISTRY',registry),
                  patch.object(storage.socket,'gethostname',return_value='compute-0-20'),
                  patch.object(storage.storage.shared_guard,'_same_device',return_value={'/'}),
                  patch.object(storage.storage.shared_guard,'check_with_timeout',return_value={'checked':True}) as checks):
                storage.admit(dict(peak_ram_bytes=16*gib))
            checks.assert_any_call('s-recipe','node_ram',32*gib)
            checks.assert_any_call('s-recipe','node_disk',64*1024**2,path='/',new_inodes=1000)
            checks.assert_any_call('s-recipe','shared_fs',123,path='/share',new_inodes=20000,quota_available=10**12)

    def exercise(self,fails):
        original=entry.entry.capacity
        c=dict(peak_ram_bytes=16)
        def numerical(actual,*,scheduler_record):
            self.assertIs(actual,c)
            self.assertEqual(scheduler_record,{'actual':'allocation'})
            for _ in range(3):
                entry.entry.capacity()
            if fails:
                raise RuntimeError('fixture exception')
            return 'unchanged training'
        with patch.object(entry,'admit',return_value={'all':'declared futures'}) as admission:
            with patch.object(entry.entry,'run',side_effect=numerical):
                if fails:
                    with self.assertRaisesRegex(RuntimeError,'fixture exception'):
                        entry.run(c,scheduler_record={'actual':'allocation'})
                else:
                    self.assertEqual(entry.run(c,scheduler_record={'actual':'allocation'}),'unchanged training')
        admission.assert_called_once_with(c)
        self.assertIs(entry.entry.capacity,original)

    def test_admission_is_once_instead_of_each_telemetry_sample(self):
        self.exercise(False)

    def test_binding_is_restored_after_a_real_training_exception(self):
        self.exercise(True)


if __name__=='__main__':
    unittest.main()
