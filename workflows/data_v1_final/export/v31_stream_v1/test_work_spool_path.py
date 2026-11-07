"""Real work() spool-path regression with tiny synthetic metadata/geometry."""
import concurrent.futures as cf
import io,json,pathlib,pickle,sqlite3,tempfile,unittest
from contextlib import ExitStack,redirect_stdout
from unittest.mock import patch
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from . import source_bridge as S
from .test_stream import schema
from ...labels.window2_normalization_v1 import reader as N


class WorkSpoolPathCheck(unittest.TestCase):
    def test_typed_pprime_and_pm7_sources_never_replace_private_spool_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary);shared=root/'shared';private=root/'private'
            z=[6,1];xyz=[[0.,0.,0.],[1.,0.,0.]];bonds=[[0,1]];codes=[1]
            def raw_row(rid,task):
                return {'record_id':rid,'molecule_id':'m','calc_type':task,'total_atoms':2,'values':'[]',
                        'numeric_issues':'[]','reproduction_package_sha256':'toy','input_bundle_sha256':'toy','input_file_sha256':'toy'}
            pm7=root/'pm7_raw.parquet';pp_raw=root/'pprime_raw.parquet';typed=root/'pprime_typed.parquet'
            pq.write_table(pa.Table.from_pylist([raw_row('native','toy_pm7')]),pm7)
            pq.write_table(pa.Table.from_pylist([raw_row('pp-native','toy_pp')]),pp_raw)
            pq.write_table(pa.Table.from_pylist([{'record_id':'pp-native','molecule_id':'m','sprime_conf_idx':7,
                'calc_type':'toy_pp','geometry_id':'u','fit_eligible':False,'atomic_numbers':z,
                'source_path':str(pp_raw),'physical_row':0,'source_bytes':pp_raw.stat().st_size,'family':'toy_pp'}]),typed)
            original_bytes={path:path.read_bytes() for path in (pm7,pp_raw,typed)}
            identities=root/'identities.sqlite'
            with sqlite3.connect(identities) as db:
                db.executescript('CREATE TABLE members(mid TEXT,role TEXT,common INTEGER); CREATE TABLE orders(mid TEXT,row TEXT); CREATE TABLE held(mid TEXT,src TEXT,physical TEXT); CREATE TABLE geometries(mid TEXT,src TEXT,physical TEXT,gid TEXT,ordinary INTEGER,pointer TEXT);')
                db.execute('INSERT INTO members VALUES(?,?,?)',('m','TRAIN',1))
                orders={'pm7_orders_json':json.dumps({'fixed_random':['native']}),'sprime_orders_json':json.dumps({'fixed_random':[7]})}
                db.execute('INSERT INTO orders VALUES(?,?)',('m',json.dumps(orders)))
                for src,physical,gid in (('pm7','native','p'),('uff_sprime','7','u')):
                    db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?)',('m',src,physical,gid,1,json.dumps({'sprime_conf_idx':7})))
            d3=root/'d3.sqlite'
            with sqlite3.connect(d3) as db:
                db.executescript('CREATE TABLE labels(gid TEXT,entries BLOB,anchor TEXT); CREATE TABLE graphs(anchor TEXT,z BLOB,bonds BLOB,codes BLOB);')
                db.execute('INSERT INTO labels VALUES(?,?,?)',('u',pickle.dumps({},protocol=5),'native'))
                db.execute('INSERT INTO graphs VALUES(?,?,?,?)',('native',*[pickle.dumps(v,protocol=5) for v in (z,bonds,codes)]))
            cache=root/'cache.sqlite'
            with sqlite3.connect(cache) as db:
                db.executescript('CREATE TABLE d3(gid TEXT,path TEXT); CREATE TABLE pp(mid TEXT,conf INTEGER,task TEXT,path TEXT,row INTEGER,gid TEXT);')
                db.execute('INSERT INTO d3 VALUES(?,?)',('u',str(d3)))
                db.execute('INSERT INTO pp VALUES(?,?,?,?,?,?)',('m',7,'toy_pp',str(typed),0,'u'))
            events=[];outer=self
            class Guard:
                def wait(self,path,*args,**kwargs):
                    path=pathlib.Path(path);events.append(path)
                    outer.assertNotIn(path,original_bytes,'source Parquet was treated as an output')
            loc={'family':'base_geometry','molecule_id':'m','record_id':'native','canonical_or_QC_identity':{'job_id':'job0'}}
            geometry={'atomic_numbers':z,'positions_A':xyz,'bond_pairs':bonds,'bond_order_codes':codes}
            state={'plan':{'source_working_root':str(shared),'source_spool_root':str(private),'source_index':'mock-index'},
                   'index':{'database':{'path':str(identities)}},'cache':{'database':{'path':str(cache)}},
                   'schema':schema(),'fields':{},'source_sample_keys':set(),'disk_guard':Guard(),
                   'normalization':{'inputs':{'field_map_reference':{}},'statistics':{'r73_derived_reference':{},'mask_overrides_reference':{}}},
                   'source_groups':{'job0':{}},'recipe':{'tasks':{'toy_pm7':{'input_kind':'ORIGINAL_REGISTRY_CELL_PARQUET'}}}}
            projected=[]
            def projection(db,base,entries,typed_row,raw,source,atomic_numbers,positions,bond_pairs,bond_codes,ranks,role,held):
                projected.append(raw['calc_type'])
                # Keep the actual spool writer and assembler; no native/scientific label call.
                S.add_piece(db,base['molecule_id'],base['geometry_id'],'labels',S.metadata(base,role,ranks),{},held)
            observed=({'molecule_id':'m','record_id':'native'},z,[],{'task_code':3,'physical_row':0},{'path':str(pm7),'family':'toy_pm7'})
            with ExitStack() as stack:
                stack.enter_context(patch.dict(S.STATE,state,clear=True))
                stack.enter_context(patch.object(S,'locators_for_mids',return_value=iter([loc])))
                stack.enter_context(patch.object(S,'iter_source_rows',return_value=iter([(loc,geometry)])))
                stack.enter_context(patch.object(S.G,'physical',return_value=(np.asarray(z),np.asarray(xyz))))
                stack.enter_context(patch.object(S.G,'native',side_effect=AssertionError('native source must not be called')))
                stack.enter_context(patch.object(S.K,'unpack_entries',return_value=[]))
                stack.enter_context(patch.object(S.B,'TASKS',{'toy_pm7':3}))
                stack.enter_context(patch.object(N,'observations',return_value=iter([observed])))
                stack.enter_context(patch.object(S,'project_row',side_effect=projection))
                result=S.work((0,['m'],'TRAIN'))
            expected=private/'TRAIN'/'block_0000000.sqlite';marker=shared/'TRAIN'/'block_0000000.json'
            self.assertEqual(result,{'path':str(expected),'mids':['m']});self.assertEqual(S.I.load(marker),result)
            self.assertTrue(expected.is_file());self.assertEqual(projected,['D3','toy_pm7','toy_pp'])
            with sqlite3.connect(expected) as db:
                rows=list(db.execute('SELECT mid,row FROM molecules'));self.assertEqual(len(rows),1)
                mid,item=rows[0][0],pickle.loads(rows[0][1]);self.assertEqual(mid,'m');self.assertEqual(item['mid'],'m')
                self.assertEqual(len(item['p_records']),1);self.assertEqual(len(item['u_records']),1)
                self.assertEqual(db.execute('SELECT count(*) FROM pieces').fetchone()[0],0)
            self.assertEqual(events[-1],expected)
            for path,before in original_bytes.items():self.assertEqual(path.read_bytes(),before)
            # Early completion logging cannot consume/reorder the original exception.
            class Pool:
                def submit(self,function,task):
                    outer.assertIs(function,S.work);return cf.Future()
            pool=Pool();log=io.StringIO()
            with redirect_stdout(log):
                success=S.submit_source_block(pool,(10,['m'],'TRAIN'));success.set_result({'toy':'closed'})
                failed=S.submit_source_block(pool,(11,['m'],'TRAIN'));error=RuntimeError('synthetic later block failure');failed.set_exception(error)
                cancelled=S.submit_source_block(pool,(12,['m'],'TRAIN'));self.assertTrue(cancelled.cancel())
            messages=[json.loads(line) for line in log.getvalue().splitlines()]
            self.assertEqual([message['phase']for message in messages],['SOURCE_BLOCK_FAILED','SOURCE_BLOCK_FAILED'])
            self.assertEqual([message['block']for message in messages],[11,12])
            self.assertIn('synthetic later block failure',messages[0]['error']);self.assertIn('CancelledError',messages[1]['error'])
            self.assertEqual(success.result(),{'toy':'closed'})
            with self.assertRaises(RuntimeError) as caught:failed.result()
            self.assertIs(caught.exception,error)
            with self.assertRaises(cf.CancelledError):cancelled.result()


if __name__=='__main__':unittest.main()
