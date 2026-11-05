"""Cold-seeded local binding resume and new shared authority, using toy data."""
import json,shutil,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from .binding import BindingStore
from . import prepare as P

class LocalBindingWork(unittest.TestCase):
    def test_selected_reuse_candidate_reference_resume_and_closed_local_publication(self):
        import pyarrow as pa,pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);old=root/'shared_v2';old.mkdir();local=root/'node_local';local.mkdir()
            out=root/'shared_v3';out.mkdir()
            plan={'first2':'frozen_first2','common':'frozen_common','source_index':'frozen_index',
                'additional_pprime_roots':['closed_labels'],'native_record_index':'frozen_native','source_plan':'frozen_shards',
                'binding_working_root':str(local)}
            inputs={name:plan[name] for name in ('first2','common','source_index','additional_pprime_roots','native_record_index','source_plan')}
            selected={'molecule_id':'M','sprime_conf_idx':7,'geometry_id':'G7','source_path':'original-source','source_row_index':0,'source_format':'parquet'}
            raw={'source_record_id':'native:exact','atomic_numbers':[6,1],'coordinates':[[1.0000000000000002,0.,0.],[2.,0.,0.]],'status':'SUCCESS','converged':True,'sprime_conf_idx':7}
            old_file=old/'physical_bindings.sqlite';first=BindingStore(old_file);first.freeze_inputs(inputs)
            first.add(selected,raw);first.close_selected(1);first.close()
            # Root's real transport occurs only after the original process exits;
            # the fixture seeds its closed DB without touching any original input.
            shutil.copyfile(old_file,local/'physical_bindings.sqlite')
            store,local_file,shared_file=P.open_bindings(plan,out)
            with patch.object(P,'geometry',side_effect=AssertionError('SELECTED_GEOMETRY_REPLAY_FORBIDDEN')):
                self.assertFalse(P.selected_bindings(store,{('M',7):selected}))
            references=[]
            for index in range(2):
                filename=root/('candidate_%d.parquet'%index)
                row=dict(selected,molecule_id='extra'+str(index),sprime_conf_idx=8+index,geometry_id='GX'+str(index),geometry_source='uff_sprime')
                pq.write_table(pa.Table.from_pylist([row]),filename);references.append(P.info(filename,1))
            P.candidate_bindings(store,references[:1])
            store.candidate(dict(selected,molecule_id='uncommitted',geometry_id='not-closed'))
            store.db.close()  # a later failure rolls back only the incomplete work
            store,local_file,shared_file=P.open_bindings(plan,out)
            real_reader=pq.ParquetFile
            with patch.object(pq,'ParquetFile',wraps=real_reader) as opened:
                P.candidate_bindings(store,references)
                self.assertEqual([call.args[0] for call in opened.call_args_list],[references[1]['path']])
            self.assertEqual(store.raw(('M',7)),raw)
            self.assertIsNone(store.db.execute('SELECT 1 FROM candidates WHERE gid=?',('not-closed',)).fetchone())
            with self.assertRaisesRegex(ValueError,'SAME_FROZEN_CANDIDATE_REFERENCE_REQUIRED'):
                store.candidate_ref_complete(0,dict(references[0],bytes=references[0]['bytes']+1))
            store.close()
            def transfer(arguments,check):
                self.assertEqual(arguments[:3],['rsync','--sparse','--']);self.assertTrue(check)
                with self.assertRaises(sqlite3.ProgrammingError):store.db.execute('SELECT 1')
                self.assertFalse((out/'manifest.json').exists())
                shutil.copyfile(arguments[3],arguments[4])
            with patch.object(P.subprocess,'run',side_effect=transfer) as transported:
                reference=P.publish_binding_database(local_file,shared_file)
                self.assertEqual(transported.call_count,1)
            self.assertEqual(reference['path'],str(out/'physical_bindings.sqlite'));self.assertNotEqual(reference['path'],str(old_file))
            checkdb=sqlite3.connect('file:'+reference['path']+'?mode=ro',uri=True)
            try:self.assertEqual(json.loads(checkdb.execute('SELECT raw FROM selected WHERE mid=? AND conf=?',('M',7)).fetchone()[0]),raw)
            finally:checkdb.close()
            P.save(out/'manifest.json',{'physical_binding_database':reference})
            self.assertTrue(old_file.exists());self.assertEqual(P.read(out/'manifest.json')['physical_binding_database'],reference)
            with self.assertRaisesRegex(ValueError,'NO_OVERWRITE'):P.publish_binding_database(local_file,shared_file)
