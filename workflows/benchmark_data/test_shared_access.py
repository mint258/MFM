import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from workflows.benchmark_data.shared_access import check_access,publish,seal_geometry


class SharedAccessTests(unittest.TestCase):
    def test_other_nodes_wait_for_a_real_closure_without_copying_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);db=folder/'queue.sqlite'
            publish(folder/'access.json',{'producer_job':1,'producer_node':'fixture-writer',
                'cross_node_read_allowed':False,'immutable':False})
            with self.assertRaises(RuntimeError):check_access(db)
            with patch('workflows.benchmark_data.shared_access.socket.gethostname',return_value='fixture-writer'):
                self.assertFalse(check_access(db)['immutable'])
            publish(folder/'access.json',{'producer_job':1,'producer_node':'fixture-writer',
                'cross_node_read_allowed':True,'immutable':True})
            self.assertTrue(check_access(db)['immutable'])
            self.assertFalse(db.exists())

    def test_manifest_alone_does_not_seal_an_active_or_different_producer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'geometry/shared_v1';folder.mkdir(parents=True)
            manifest=folder/'producer_1.json'
            manifest.write_text(json.dumps({'job':'1','status':'ALL_QUEUED_MOLECULES_TERMINAL','states':{'READY':3}}))
            with patch('workflows.benchmark_data.shared_access.completed_evidence',side_effect=RuntimeError('SYNTHETIC running source')):
                with self.assertRaises(RuntimeError):seal_geometry(root,1)
            self.assertFalse((folder/'access.json').exists())
            with patch('workflows.benchmark_data.shared_access.completed_evidence',return_value={'source_node':'fixture-writer','raw':'SYNTHETIC closed metadata'}):
                seal_geometry(root,1)
            self.assertTrue(check_access(folder/'queue.sqlite')['immutable'])

if __name__=='__main__':unittest.main()
