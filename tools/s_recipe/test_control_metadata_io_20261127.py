import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import control_metadata_io_20261127 as m


class ControlMetadataIO(unittest.TestCase):
    def child(self,path,inherited):
        code=('import json,os;from control_metadata_io_20261127 import acquire_control_lock;'
            'path='+repr(str(path))+';'
            'trusted=lambda stage,pid:'+('pid==os.getppid()' if inherited else 'False')+'\n'
            'try:\n lock,role=acquire_control_lock("test",path,trusted=trusted);print(json.dumps(dict(role=role)))\n'
            'except BlockingIOError: print(json.dumps(dict(role="BLOCKED_BEFORE_MUTATION")))\n')
        return json.loads(subprocess.check_output([sys.executable,'-B','-c',code],text=True,timeout=10))

    def test_independent_controller_cannot_overwrite_parent_forecast(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lock';lock,role=m.acquire_control_lock('test',path,trusted=lambda *a:False)
            try:self.assertEqual(self.child(path,False)['role'],'BLOCKED_BEFORE_MUTATION')
            finally:lock.close()

    def test_verified_actual_parent_lock_does_not_deadlock_statistic_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lock';lock,role=m.acquire_control_lock('test',path,trusted=lambda *a:False)
            try:self.assertEqual(self.child(path,True)['role'],'INHERITED_VERIFIED_PARENT_CONTROL_LOCK')
            finally:lock.close()

    def test_atomic_replace_failure_keeps_previous_control_file_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'current_state.json';path.write_text('{"old":true}\n')
            with patch.object(m,'ATOMIC_TARGETS',{path}),patch.object(m.os,'replace',side_effect=OSError('test')):
                with self.assertRaises(OSError):m.write(path,dict(new=True))
            self.assertEqual(json.loads(path.read_text()),dict(old=True))


if __name__=='__main__':unittest.main()
