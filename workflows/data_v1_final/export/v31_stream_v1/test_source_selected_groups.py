"""One tiny fixture for selected physical row-group access; no production scan."""
import math,pathlib,struct,tempfile,unittest
from unittest.mock import patch
import pyarrow as pa
import pyarrow.parquet as pq
from . import source_bridge as S


def original(path,positions,columns=None):
    file=pq.ParquetFile(path,pre_buffer=False);positions=sorted(set(positions));cursor=0;lo=0
    try:
        for batch in file.iter_batches(batch_size=16,columns=columns,use_threads=False):
            hi=lo+batch.num_rows
            while cursor<len(positions)and positions[cursor]<lo:cursor+=1
            while cursor<len(positions)and positions[cursor]<hi:
                position=positions[cursor];cursor+=1;yield position,batch.slice(position-lo,1).to_pylist()[0]
            lo=hi
            if positions and lo>positions[-1]:break
    finally:file.close()


def signature(rows):
    return [(position,tuple((key,struct.pack('<d',value)if isinstance(value,float)else value)for key,value in row.items()))for position,row in rows]


class SelectedPhysicalGroupsCheck(unittest.TestCase):
    def test_selected_positions_keep_rows_columns_order_and_empty_semantics(self):
        with tempfile.TemporaryDirectory()as temporary:
            path=pathlib.Path(temporary)/'source.parquet'
            rows=[dict(row=i,value=float('nan')if i==42 else -0.0 if i==11 else float(i),label='rid%d'%i)for i in range(53)]
            pq.write_table(pa.Table.from_pylist(rows),path,row_group_size=11);before=path.read_bytes()
            for positions in ([42,11,42,-5,999],[52,0,33,22],[],[-2,-1],[999],[11],[True,False,11]):
                for columns in (None,['label','value'],['row']):
                    self.assertEqual(signature(S.read_selected(path,positions,columns)),signature(original(path,positions,columns)))
            calls=[];file=pq.ParquetFile
            class Spy:
                def __init__(self,*args,**kwargs):self.inner=file(*args,**kwargs)
                def __getattr__(self,name):return getattr(self.inner,name)
                def iter_batches(self,*args,**kwargs):
                    calls.append(kwargs.get('row_groups'));return self.inner.iter_batches(*args,**kwargs)
            with patch.object(pq,'ParquetFile',Spy):list(S.read_selected(path,[42,11]))
            self.assertEqual(calls,[[1],[3]])
            calls.clear()
            with patch.object(pq,'ParquetFile',Spy):self.assertEqual(list(S.read_selected(path,[])),[])
            self.assertEqual(calls,[])
            self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()
