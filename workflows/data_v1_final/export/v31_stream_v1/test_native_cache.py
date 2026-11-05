"""One in-memory Native-reader integration fixture; no real LMDB or benchmark."""
import collections,copy,os,pickle,sys,types,unittest
from unittest.mock import patch
import numpy as np
from . import physical as G
from ...conformers.window2_source_cache_v1.keep_source_map import KeepSourceMap


class NativeCacheReaderCheck(unittest.TestCase):
    def test_exact_physical_override_preserves_logical_identity_and_original_read(self):
        logical='/share/home/zixiao/dataset/lmdb_new/native.lmdb'
        cached='/tmp/closed-native-cache/native.lmdb'
        same_basename='/share/home/zixiao/dataset/other/native.lmdb'
        mapper=KeepSourceMap({logical:cached})
        original={'positions_A':np.array([[np.nextafter(1.,2.),-0.,1e-200]],dtype='<f8'),
                  'atomic_numbers':np.array([6],dtype='<i8'),'native_record_id':'unchanged-opaque-ID'}
        payload=pickle.dumps(original,protocol=5);opens=[];keys=[]
        class Transaction:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def get(self,key):keys.append(key);return payload
        class Environment:
            def begin(self,*args,**kwargs):
                self_outer.assertEqual((args,kwargs),((),{}));return Transaction()
            def close(self):pass
        self_outer=self
        def open_lmdb(path,**kwargs):opens.append((path,kwargs));return Environment()
        G.completed_source_map.cache_clear()
        try:
            with patch.dict(sys.modules,{'lmdb':types.SimpleNamespace(open=open_lmdb)}),patch.object(KeepSourceMap,'from_plan',return_value=mapper) as load_plan:
                for use_map,source,expected in ((False,logical,logical),(True,logical,cached),(True,same_basename,same_basename)):
                    row={'source_path':source,'real_index':17,'native_record_id':'unchanged-opaque-ID'};before=copy.deepcopy(row)
                    with patch.dict(os.environ),patch.object(G,'HANDLES',collections.OrderedDict()):
                        if use_map:os.environ['DATA_V1_COMPLETED_SOURCE_CACHE_PLAN']='/memory/closed-plan.json'
                        else:os.environ.pop('DATA_V1_COMPLETED_SOURCE_CACHE_PLAN',None)
                        actual=G.native(row)
                        self.assertEqual(list(G.HANDLES),[source])
                    self.assertEqual(row,before);self.assertEqual(opens[-1][0],expected)
                    self.assertEqual(opens[-1][1],dict(subdir=False,readonly=True,lock=False,create=False,readahead=False,max_readers=1024))
                    self.assertEqual(actual['positions_A'].dtype,np.dtype('<f8'))
                    self.assertEqual(actual['positions_A'].tobytes(),original['positions_A'].tobytes())
                    self.assertEqual(actual['atomic_numbers'].tobytes(),original['atomic_numbers'].tobytes())
                    self.assertEqual(actual['native_record_id'],original['native_record_id'])
                load_plan.assert_called_once_with('/memory/closed-plan.json')
            self.assertEqual(keys,[b'000000017']*3)
        finally:G.completed_source_map.cache_clear()


if __name__=='__main__':unittest.main()