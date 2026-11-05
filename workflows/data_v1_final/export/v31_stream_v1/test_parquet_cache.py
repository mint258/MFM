"""One memory-only fixture for bounded exact-path Parquet geometry caching."""
import copy,json,unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pyarrow as pa
from . import physical as G


class ParquetCacheCheck(unittest.TestCase):
    def test_exact_rows_reuse_bounds_and_original_status_checks(self):
        def row(ordinal,converged=True):
            return {'molecule_id':'m','status':'SUCCESS','converged':converged,'sprime_conf_idx':ordinal,
                    'atomic_numbers':[6,1],'coordinates':[[ordinal+0.125,-0.,1.],[2.,0.,-3.5]],
                    'source_record_id':'original-anchor','unused_original_field':{'ordered':[3,1,2]}}
        ordinary=[row(0),row(1),row(2,False),row(3,None)]
        declarations={'molecule_id':'m','geometry_id':'n1','sprime_conf_idx':9,'geometry_source':'uff_sprime',
                      'status':'SUCCESS','converged':True,'source_record_id':'n1-anchor',
                      'ordinary_sprime_member':False,'usage_domain':'pprime_extra'}
        def n1(state):
            return {'molecule_id':'m','geometry_id':'n1','sprime_conf_idx':9,'atomic_numbers':[6,1],
                    'coordinates':[[9.125,-0.,1.],[2.,0.,-3.5]],
                    'metadata_json':json.dumps(dict(declarations,converged=state))}
        sources={'memory:A':[ordinary,[row(4)]],
                 'memory:B':[[row(5)],[n1(True),n1(False),n1(None)]]}
        originals=copy.deepcopy(sources);opened=[];closed=[];decoded=[];footer=[]
        outer=self
        class Parquet:
            def __init__(self,filename,**kwargs):
                outer.assertEqual(kwargs,{'pre_buffer':False});self.filename=filename
                self.num_row_groups=len(sources[filename]);opened.append(filename)
                def group(index):
                    footer.append((filename,index))
                    return SimpleNamespace(num_rows=len(sources[filename][index]))
                self.metadata=SimpleNamespace(row_group=group)
            def read_row_group(self,index,**kwargs):
                outer.assertEqual(kwargs,{'use_threads':False});decoded.append((self.filename,index))
                return pa.Table.from_pylist(sources[self.filename][index])
            def close(self):closed.append(self.filename)
        def pointer(filename,index,**extra):
            return dict(source_format='parquet',source_path=filename,source_row_index=index,molecule_id='m',**extra)
        def exact(filename,index,original,**extra):
            actual,xyz=G.physical(pointer(filename,index,**extra));self.assertEqual(actual,original)
            self.assertEqual(xyz.dtype,np.dtype('<f8'))
            self.assertEqual(xyz.tobytes(),np.asarray(original['coordinates'],dtype='<f8').tobytes())
        G.close_parquet_cache()
        try:
            with patch('pyarrow.parquet.ParquetFile',Parquet):
                exact('memory:A',0,ordinary[0]);exact('memory:A',1,ordinary[1]);exact('memory:A',0,ordinary[0])
                self.assertEqual(opened,['memory:A']);self.assertEqual(decoded,[('memory:A',0)])
                self.assertEqual(footer,[('memory:A',0),('memory:A',1)])
                for index in (2,3):
                    with self.assertRaisesRegex(ValueError,'PHYSICAL_GEOMETRY_NOT_CONVERGED'):G.physical(pointer('memory:A',index))
                for index in (-1,5):
                    with self.assertRaisesRegex(ValueError,'PHYSICAL_GEOMETRY_ROW_MISSING'):G.physical(pointer('memory:A',index))
                self.assertEqual(decoded,[('memory:A',0)])
                with self.assertRaisesRegex(ValueError,'PHYSICAL_GEOMETRY_MID_DIFFERS'):G.physical(dict(pointer('memory:A',0),molecule_id='wrong'))
                with self.assertRaisesRegex(ValueError,'ORIGINAL_ATOM_ORDER_WITNESS_DIFFERS'):G.physical(pointer('memory:A',0,atom_order_sha256='wrong'))
                exact('memory:A',4,sources['memory:A'][1][0]);self.assertEqual(G.PARQUET_GROUP[:2],('memory:A',1))
                exact('memory:A',1,ordinary[1]);self.assertEqual(decoded,[('memory:A',0),('memory:A',1),('memory:A',0)])
                exact('memory:B',0,sources['memory:B'][0][0]);self.assertEqual(closed,['memory:A'])
                extra={'geometry_id':'n1','accepted_component_kind':'CURRENT_CANONICAL_N1_PHYSICAL_ACCEPTED'}
                raw,xyz=G.physical(pointer('memory:B',1,**extra))
                self.assertEqual(raw,dict(declarations,**sources['memory:B'][1][0]))
                self.assertIs(raw['ordinary_sprime_member'],False);self.assertEqual(raw['source_record_id'],'n1-anchor')
                self.assertEqual(xyz.tobytes(),np.asarray(sources['memory:B'][1][0]['coordinates'],dtype='<f8').tobytes())
                for index in (2,3):
                    with self.assertRaisesRegex(ValueError,'GEOMETRY_NOT_ACTUALLY_USABLE'):G.physical(pointer('memory:B',index,**extra))
                self.assertEqual(decoded[-2:],[('memory:B',0),('memory:B',1)])
                exact('memory:A',0,ordinary[0]);self.assertEqual(opened,['memory:A','memory:B','memory:A'])
                self.assertEqual(closed,['memory:A','memory:B']);self.assertEqual(G.PARQUET_GROUP[:2],('memory:A',0))
                self.assertEqual(sources,originals)
        finally:G.close_parquet_cache()
        self.assertEqual(closed,['memory:A','memory:B','memory:A'])


if __name__=='__main__':unittest.main()
