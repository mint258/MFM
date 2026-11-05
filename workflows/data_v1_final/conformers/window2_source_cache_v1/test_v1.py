"""One pure mapping/fallback test, without LMDB/native/science reads."""
import unittest
from .keep_source_map import KeepSourceMap


class KeepSourceMapTests(unittest.TestCase):
    def test_exact_completed_source_mapping_and_uncached_fallback_never_mix_sources(self):
        first='/source/one/shared-name.lmdb';second='/source/two/shared-name.lmdb'
        cache='/tmp/completed-cache/one.lmdb'
        sources=KeepSourceMap.from_plan({'closed_source_path_map':{first:cache},
            'sources':[{'path':second,'proposed_cache_path':'/tmp/partial/two.lmdb'}]})
        calls=[]
        def original_reader(row):
            calls.append(row)
            return row['source_path'],row['record_id'],row['real_index'],row['molecule_id']
        wrapped=sources.wrap_native(original_reader)
        row={'source_path':first,'record_id':'RID-unchanged','real_index':17,'molecule_id':'MID-unchanged'}
        before=dict(row)
        self.assertEqual(wrapped(row),(cache,'RID-unchanged',17,'MID-unchanged'))
        self.assertEqual(row,before);self.assertIsNot(calls[-1],row)
        uncached=dict(row,source_path=second)
        self.assertEqual(wrapped(uncached),(second,'RID-unchanged',17,'MID-unchanged'))
        self.assertIs(calls[-1],uncached)
        for path in (first+'.partial','/other/shared-name.lmdb',first.replace('/one/','/one/./')):
            self.assertEqual(sources.physical_path(path),path)
        self.assertEqual(KeepSourceMap.from_plan().physical_path(first),first)
        self.assertEqual(sources.physical_path(second),second)


if __name__=='__main__':unittest.main()