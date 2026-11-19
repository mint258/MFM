"""Exercise new reference-source reuse, without recomputing scientific labels."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib
import pyarrow as pa
import pyarrow.parquet as pq
from workflows.benchmark_data import reference_d20 as r
from workflows.benchmark_data.geometry_queue import schema
from workflows.benchmark_data.downstream_science import identities


class ReferenceReuseTests(unittest.TestCase):
    def test_shared_ready_and_pending_are_reused_and_new_graph_is_computed_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'geometry/shared_v1';folder.mkdir(parents=True)
            queue=folder/'queue.sqlite';db=sqlite3.connect(queue);schema(db)
            descriptor={'names':['fixture'],'values':[1.25],'valid_mask':[True],'issues':[]}
            db.execute('INSERT INTO tasks(mid,model_smiles,state,result) VALUES(?,?,?,?)',
                (identities('CCO')[0],'CCO','SPRIME_AND_D_READY',zlib.compress(json.dumps({'D20':descriptor}).encode())))
            db.execute('INSERT INTO tasks(mid,model_smiles) VALUES(?,?)',(identities('CCN')[0],'CCN'))
            db.commit();db.close()
            (folder/'queue.manifest.json').write_text(json.dumps({'queue':str(queue),'storage_forecast_bytes':1048576}))
            source=root/'input.parquet'
            pq.write_table(pa.table({'record_id':['a','b','c','d'],'model_smiles':['CCO','CCN','CCC','CCC'],
                'domain_eligible':[True]*4}),source)
            argv=['reference_d20','--root',str(root),'--input','fixture='+str(source),
                '--attempt','synthetic','--quota-snapshot',str(root/'synthetic-quota')]
            with patch.object(sys,'argv',argv),patch.object(r,'capacity'),patch.object(r,'original_d20',return_value=descriptor) as compute:
                r.main()
            compute.assert_called_once_with('CCC')
            rows=pq.read_table(root/'labels/reference_D20/synthetic/fixture.parquet').to_pylist()
            self.assertEqual([x['state'] for x in rows],['D20_READY','D20_SOURCE_UNAVAILABLE','D20_READY','D20_READY'])
            self.assertEqual(rows[0]['D20_origin'],'SHARED_GEOMETRY_PRODUCER')

class ClosedDescriptorTests(unittest.TestCase):
    def test_closed_reference_values_reused_before_any_scientific_compute(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'closed.parquet'
            pq.write_table(pa.Table.from_pylist([
                {'model_smiles':'CCC','D20_names':['fixture'],'D20_values':[1.5],
                 'D20_valid_mask':[True],'issues':[],'state':'D20_READY'},
                {'model_smiles':'CCN','D20_names':None,'D20_values':None,
                 'D20_valid_mask':None,'issues':['PENDING'],'state':'D20_SOURCE_UNAVAILABLE'},
            ]),path)
            cache=r.reuse_descriptors([path])
            self.assertEqual(set(cache),{'CCC'})
            self.assertEqual(cache['CCC'][0]['values'],[1.5])
            self.assertTrue(cache['CCC'][1].startswith('CLOSED_REFERENCE_D20:'))

if __name__=='__main__':unittest.main()
