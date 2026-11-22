"""Only startup telemetry wiring; no scientific batch or GPU benchmark."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import train_guarded_startup_20261122 as entry
import test_storage_entry_20261122 as storage_tests

class StartupTests(unittest.TestCase):
    def test_header_only_csv_during_reader_startup_is_not_a_stop_request(self):
        with tempfile.TemporaryDirectory() as scratch:
            (Path(scratch)/'losses.csv').write_text('samples,updates,total,element,noise,bond,preclip_norm,lr,seconds\n')
            requests=[]
            stop=SimpleNamespace(wait=unittest.mock.Mock(side_effect=[False,True]))
            guard=SimpleNamespace(request=requests.append)
            with patch.object(entry,'capacity'),patch.object(entry,'query_gpu',return_value=['uuid','gpu',0,1,2,3]):
                entry.observe(dict(output=scratch,gpu_uuid='uuid'),guard,stop)
            self.assertEqual(requests,[])
            self.assertFalse((Path(scratch)/'gpu_telemetry.csv').exists())

    def test_actual_resource_failure_still_requests_safe_stop(self):
        requests=[]
        stop=SimpleNamespace(wait=lambda seconds:False)
        with patch.object(entry,'capacity',side_effect=RuntimeError('actual admission failure')):
            entry.observe(dict(output='unused',gpu_uuid='uuid'),SimpleNamespace(request=requests.append),stop)
        self.assertEqual(requests,['storage_or_observer_failure: actual admission failure'])

def load_tests(loader,tests,pattern):
    tests.addTests(loader.loadTestsFromModule(storage_tests))
    return tests

if __name__=='__main__':
    unittest.main()
