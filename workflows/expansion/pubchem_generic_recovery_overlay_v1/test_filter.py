"""Native binding parity against original direct-Parquet V3/H-only scientific code."""
from pathlib import Path
import sqlite3
import tempfile
from types import FunctionType
import unittest
from .filter import run_core,original_core,empty_domain


class Native(unittest.TestCase):
    def test_logical_binding_equals_original_direct_filter(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory(prefix='overlay_filter_synthetic_') as tmp:
            root=Path(tmp);rows=[]
            for cid,letter,composition,elements,heavy in [(10,'A','[[6,1]]',[6],1),(20,'B','[[8,1]]',[8],1),(30,'C','[[6,2]]',[6],2),(40,'H','[]',[],0)]:
                key=letter*14+'-'+'B'*10+'-C'
                rows.append(dict(cid=cid,full_key=key,wp5_key=key[:14]+':C',non_h_composition=composition,elements=elements,heavy_atoms=heavy,mw=float(cid)))
            source=root/'synthetic.parquet';pq.write_table(pa.Table.from_pylist(rows),source)
            index=root/'synthetic.sqlite';db=sqlite3.connect(index)
            db.executescript('CREATE TABLE excluded(kind TEXT,key TEXT,dataset TEXT); CREATE TABLE constraints(rule_id TEXT,dataset TEXT); CREATE TABLE constraint_atoms(rule_id TEXT,z INTEGER,n INTEGER);')
            db.executemany('INSERT INTO excluded VALUES (?,?,?)',[('full',rows[0]['full_key'],'moleculenet'),('composition','[[8,1]]','coconut')])
            db.execute('INSERT INTO constraints VALUES (?,?)',['positiveC2','moleculenet']);db.execute('INSERT INTO constraint_atoms VALUES (?,?,?)',['positiveC2',6,2]);db.commit();db.close()
            connection=original_core.connection;scope=dict(vars(original_core))
            scope['connection']=lambda *a,**k:empty_domain.ExtendedDomainConnection(connection(*a,**k))
            direct=FunctionType(original_core.filter_core.__code__,scope,original_core.filter_core.__name__)
            (root/'direct').mkdir();expected=direct(source,index,root/'direct',2,128<<20,lambda:None)
            def synthetic_binder(db,pool,check):
                db.read_parquet(str(source)).create_view('candidates');return []
            (root/'logical').mkdir();actual=run_core(None,index,root/'logical',2,128<<20,lambda:None,candidate_binder=synthetic_binder)
            self.assertEqual(actual[2],expected[2])
            self.assertEqual(pq.read_table(actual[0]['path']).to_pylist(),pq.read_table(expected[0]['path']).to_pylist())
            self.assertEqual(pq.read_table(actual[0]['path']).to_pylist(),[rows[-1]])
            self.assertEqual(actual[2]['excluded_molecules'],3)
            self.assertIs(original_core.connection,connection)
