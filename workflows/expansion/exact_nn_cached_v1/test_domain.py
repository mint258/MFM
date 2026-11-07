"""Original nonempty-domain parity and explicit retained H-only stratum oracle."""
import json
from pathlib import Path
import tempfile
import unittest
from .. import ranking as original
from ..external_sort import create_queues
from .domain import HydrogenDomainDB,projected_row,reference_queues


def rows():
    return [{'cid':i+1,'full_key':('A'*12+chr(65+i//26)+chr(65+i%26))+'-'+'B'*10+'-N',
        'heavy_atoms':5+i%20,'element_combination':'6,8' if i%2 else '6,7',
        'generic_murcko':'s'+str(i%4),'generic_ring_systems':['r'+str(i%3)],
        'nearest_v1_tanimoto':(.1,.5,1.)[i%3],'v1_scaffold_count':i%3,'v1_ring_system_count':i%5,
        'v1_reference_sha256':'a'*64} for i in range(80)]


class HydrogenDomainTests(unittest.TestCase):
    def sql(self,values):
        import duckdb
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pool.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in values))
            db=duckdb.connect()
            try:
                db.read_json(str(path),format='newline_delimited').create('pool');adapter=HydrogenDomainDB(db)
                create_queues(adapter,seed=20261025,queue_size=10);self.assertEqual(adapter.extended_predicates,1)
                result={'R':[],'N':[]}
                for stream,cid,key,rank in db.execute('SELECT * FROM queues ORDER BY stream,stream_rank').fetchall():
                    result[stream].append({'stream':stream,'stream_rank':rank,'cid':cid,'full_key':key})
                return result
            finally:db.close()

    def test_nonempty_domain_is_exactly_original_queue_result(self):
        values=rows();expected=original.queues(values,queue_size=10)
        self.assertEqual(reference_queues(values,queue_size=10),expected)
        self.assertEqual(self.sql(values),expected)

    def test_H_only_rows_keep_actual_empty_stratum_without_relabel_or_drop(self):
        values=rows()
        for row in values[::5]:row['heavy_atoms']=0;row['element_combination']=''
        self.assertIs(projected_row(values[0]),values[0])
        expected=reference_queues(values,queue_size=10);self.assertEqual(self.sql(values),expected)
        self.assertEqual(sum(r['heavy_atoms']==0 and r['element_combination']=='' for r in values),16)


if __name__=='__main__':unittest.main()
