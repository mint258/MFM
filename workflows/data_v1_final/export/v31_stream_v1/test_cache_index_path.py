"""One synthetic cache-index storage-hint fixture; no real labels or arrays."""
import json,pathlib,sqlite3,tempfile,unittest
from unittest.mock import patch
import pyarrow as pa
import pyarrow.parquet as pq
from . import source_bridge as S,prepare_runtime as P


class CacheIndexPathCheck(unittest.TestCase):
    def test_default_local_rows_marker_reuse_and_frozen_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);default=root/'default';shared=root/'shared';local=root/'tmpfs-private';default.mkdir();shared.mkdir()
            def save(path,value):path.write_text(json.dumps(value));return S.I.ref(path)
            parts=root/'typed_identity.parquet'
            pq.write_table(pa.Table.from_pylist([
                {'record_id':'r-b','molecule_id':'m-b','sprime_conf_idx':7,'calc_type':'t2','geometry_id':'g-b'},
                {'record_id':'r-a','molecule_id':'m-a','sprime_conf_idx':2,'calc_type':'t1','geometry_id':'g-a'},
                {'record_id':'r-source','molecule_id':'m-a','sprime_conf_idx':2,'calc_type':'t3','geometry_id':None}]),parts)
            part_ref=save(root/'part.json',{'parts':[S.I.ref(parts)]})
            pp=root/'projection.json';save(pp,{'part_manifests':[part_ref]})
            labels=root/'gid_metadata.sqlite'
            with sqlite3.connect(labels) as database:
                database.execute('CREATE TABLE labels(gid TEXT)');database.executemany('INSERT INTO labels VALUES(?)',[('g-b',),('g-a',)])
            d3=root/'d3.json';save(d3,{'files':[S.I.ref(labels)]})
            overrides=root/'overrides.parquet';pq.write_table(pa.Table.from_pylist([{'record_id':'r-a','field_id':4,'reason':'toy_mask'}]),overrides)
            override_ref=save(root/'override_manifest.json',{'files':[S.I.ref(overrides)]})
            norm=root/'normalization.json';save(norm,{'statistics':{'mask_overrides_reference':override_ref}})
            aliases=root/'source_aliases.parquet';pq.write_table(pa.Table.from_pylist([{'source_pprime_record_id':'r-source','geometry_id':'g-source'}]),aliases)
            base={'source_working_root':str(default),'pprime_cache':str(pp),'uff_d3_cache':str(d3),'pm7_normalization':str(norm),'extra_geometry_tables':[S.I.ref(aliases)]}
            events=[]
            class Guard:
                def wait(self,path,**kwargs):events.append((pathlib.Path(path),local.exists()))
            with patch.object(S,'from_plan',return_value=None):normal=S.cache_index(base)
            changed=dict(base,source_working_root=str(shared),cache_index_working_root=str(local))
            with patch.object(S,'from_plan',return_value=Guard()):moved=S.cache_index(changed)
            self.assertEqual(normal['database']['path'],str(default/'cache_index.sqlite'))
            self.assertEqual(moved['database']['path'],str(local/'cache_index.sqlite'))
            self.assertEqual(events[:2],[(local,False),(shared/'cache_index.json',False)])
            self.assertTrue((shared/'cache_index.json').is_file());self.assertFalse((shared/'cache_index.sqlite').exists())
            def contents(reference):
                with sqlite3.connect(reference['database']['path']) as database:
                    schema=list(database.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name"))
                    tables={name:list(database.execute('SELECT * FROM '+name+' ORDER BY rowid'))for name in ('pp','d3','overrides')}
                return schema,tables
            self.assertEqual(contents(normal),contents(moved))
            self.assertEqual([row[0]for row in contents(moved)[1]['pp']],['m-b','m-a','m-a'])
            unused=root/'unused-new-hint';marker_before=(shared/'cache_index.json').read_bytes()
            # Closed marker wins over a changed resource hint and performs no source IO.
            with patch.object(S,'from_plan',side_effect=AssertionError('closed marker re-admitted')),patch.object(S.sqlite3,'connect',side_effect=AssertionError('closed index reopened')):
                self.assertEqual(S.cache_index(dict(changed,cache_index_working_root=str(unused))),moved)
                with self.assertRaisesRegex(ValueError,'FROZEN_CACHE_INDEX_INPUTS_CHANGED'):
                    S.cache_index(dict(changed,pprime_cache='different-immutable-input'))
            self.assertFalse(unused.exists());self.assertEqual((shared/'cache_index.json').read_bytes(),marker_before)
            runtime=root/'runtime';runtime.mkdir();path=root/'bound-plan.json'
            original={'runtime_metadata_root':str(runtime),'cache_index_working_root':str(local),'source_working_root':str(shared)}
            path.write_text(json.dumps(dict(original,cache_index_working_root=str(unused))))
            save(runtime/'bound_plan.json',{'plan_path':str(path),'plan':original})
            resumed=P.prepare(path);self.assertEqual(resumed['cache_index_working_root'],str(unused))
            self.assertEqual(resumed['source_working_root'],str(shared))


if __name__=='__main__':unittest.main()
