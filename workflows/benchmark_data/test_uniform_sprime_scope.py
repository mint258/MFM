import sqlite3
import unittest
from workflows.benchmark_data.uniform_sprime_scope import source_route,source_closed

class SourceRouting(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.executescript('CREATE TABLE tasks(mid TEXT,model_smiles TEXT,state TEXT);CREATE TABLE membership(dataset TEXT,record_id TEXT,mid TEXT);')
        self.db.execute('INSERT INTO tasks VALUES (?,?,?)',('closed','CCC','UNKNOWN_INTERRUPTED_NO_RETRY'))
        self.db.execute('INSERT INTO membership VALUES (?,?,?)',('original','row7','closed'))

    def tearDown(self):self.db.close()

    def test_closed_failure_routes_to_original_without_science_retry(self):
        self.assertEqual(source_route(self.db,'closed','CCC'),(('original','row7'),'UNKNOWN_INTERRUPTED_NO_RETRY'))
        self.assertIsNone(source_route(self.db,'absent','CCN'))

    def test_inconsistent_graph_and_active_source_rejected(self):
        with self.assertRaises(ValueError):source_route(self.db,'closed','CCN')
        self.db.execute("UPDATE tasks SET state='INTENT'")
        with self.assertRaises(ValueError):source_route(self.db,'closed','CCC')

class GeometryReservation(unittest.TestCase):
    def test_only_native_sealed_terminal_source_retires_future(self):
        access=dict(immutable=True,cross_node_read_allowed=True,publishing_uid=7,producer_job=10,
            actual_closure_evidence=dict(raw='JobId=10 JobState=COMPLETED ExitCode=0:0'))
        producer=dict(job='10',status='ALL_QUEUED_MOLECULES_TERMINAL',states={'READY':12})
        self.assertTrue(source_closed(access,producer,7))
        self.assertFalse(source_closed(access,producer,8))
        producer['states']['INTENT']=1
        self.assertFalse(source_closed(access,producer,7))
        producer['states']['INTENT']=0
        access['actual_closure_evidence']['raw']='JobId=10 JobState=FAILED ExitCode=1:0'
        self.assertFalse(source_closed(access,producer,7))

if __name__=='__main__':unittest.main()
