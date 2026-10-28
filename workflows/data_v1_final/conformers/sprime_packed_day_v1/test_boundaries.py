"""Exactly6 synthetic methods, once per real parent before scientific DATA."""
import ast,gzip,hashlib,inspect,json,pathlib,tempfile,unittest
from . import contract as C,runtime as I,census as Z,worker as W,history as H,operational as O
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as OLD


class Boundaries(unittest.TestCase):
    def test_shared_original_key_and_seed_no_resource_namespace_retry(self):
        mid='mol_synthetic_0001';key=C.F.task_key(mid,'fill_10N')
        expected=hashlib.sha256(('sprime-fill-once-v1:'+C.F.KERNEL_SHA+':'+mid+':fill_10N').encode()).hexdigest()
        self.assertEqual(key,expected);self.assertNotEqual(key,C.F.task_key(mid,'retry_once'))
        self.assertEqual(C.F.seed_for(mid,False),max(int.from_bytes(hashlib.sha256(('sprime-ETKDGv3-v1:'+mid).encode()).digest()[:4],'big')&0x7fffffff,1))
        # Consumed failures/UNKNOWN and successful packets use the same original
        # key domain; no resource revision or second-day mode can make them new.
        self.assertEqual(H.anti_join(['unclaimed'],{'valid_old_packet','failed_old_packet','consumed_UNKNOWN'}),1)
        for consumed in ('valid_old_packet','failed_old_packet','consumed_UNKNOWN'):
            with self.assertRaises(ValueError):H.anti_join(['unclaimed',consumed],{'valid_old_packet','failed_old_packet','consumed_UNKNOWN'})
    def test_original_retained_geometry_and_real_fallback_not_claimed_unique(self):
        selection=C.F.module('selection',C.F.sources()['selection'])
        old={'candidate_key':'existing:0','coordinates':[[0.,0.,0.]],'energy':0.,'seed':3,'origin':'accepted_sprime','original_sprime_conf_idx':0}
        candidate={'candidate_key':'generated:0','coordinates':[[0.,0.,0.]],'energy':1.,'seed':7,'origin':'data_v1_fill_10N','candidate_id':0}
        rows=selection.select_fill([old],[candidate],2,lambda a,b:0.,0.5)
        self.assertEqual(rows[0]['coordinates'],old['coordinates']);self.assertEqual(rows[0]['seed'],3)
        self.assertTrue(rows[1]['below_dedup_threshold']);self.assertEqual(rows[1]['min_rmsd_to_previously_selected_A'],0.)
    def test_canonical_clock_real_shape_including_startup_and900_drain(self):
        from datetime import datetime
        start=datetime.fromisoformat('2026-10-28T08:00:00+08:00').timestamp()
        proof={'observed_at':'2026-10-28T00:00:10+00:00','root_observed_at':'2026-10-28T08:00:10+08:00','job_id':'1',
            'job_metadata':'JobId=1 JobState=RUNNING RunTime=00:00:10 TimeLimit=1-00:00:00 StartTime=2026-10-28T08:00:00 EndTime=2026-10-29T08:00:00'}
        clock=I.wall_clock(proof,86400,now_wall=start+30,now_monotonic=100.)
        self.assertEqual(clock['conservative_elapsed_at_anchor_seconds'],30);self.assertEqual(I.remaining_wall(clock,100.),86370.)
        self.assertEqual(I.remaining_wall(clock,85570.),900.)
        with self.assertRaises(ValueError):I.remaining_wall(clock,99.)
        # Shared helper's explicit synthetic hooks: unchanged original validation,
        # one metadata reread only; real persistent event writer, no science/pool.
        import types
        from workflows.data_v1_final.execution import finite_quota_observation_guard_v1 as guard
        expected={'path':'/synthetic/current_provider_identity.json','bytes':1,'sha256':'d'*64}
        class OriginalObservation:
            def __init__(self,sampled=100.2,expires=1000.,provider='RUNNING',identity=None,second_error=None,error=None):
                self.calls=0;self.identity=expected if identity is None else identity;self.second_error=second_error;self.error=error
                self.last={'identity_reference':self.identity,'provider_status':provider,'observed_unix_seconds':sampled,
                    'publisher_expires_unix_seconds':expires,'snapshot_reference':dict(expected,path='/synthetic/original_snapshot.json')}
            def observe(self):
                self.calls+=1
                if self.calls==1:raise ValueError(guard.TIME_ERROR if self.error is None else self.error)
                if self.second_error is not None:raise ValueError(self.second_error)
                return {'free_bytes':999999999999}
        def exercise(client,recorder,wall=100.):
            times={'wall':wall,'mono':10.};waits=[]
            def wait(seconds):waits.append(seconds);times['wall']+=seconds;times['mono']+=seconds
            result=guard.observe(client,expected_identity_reference=expected,record=recorder,
                wall_clock=lambda:times['wall'],monotonic=lambda:times['mono'],wait=wait)
            return result,waits
        with tempfile.TemporaryDirectory() as d:
            budget=object.__new__(I.Budget);budget.out=pathlib.Path(d);budget.cap=128<<20
            budget.proof={'job_id':'synthetic-resource-parent','node':'compute-0-18'};budget.plan={'quota_provider_identity_reference':expected}
            budget.quota_event_count=0;budget.quota_event_bytes=0;budget.quota_event_references=[]
            I.save(budget.out/'writer_state.json',{'charged_written_bytes':0,'reservations':{}})
            client=OriginalObservation();result,waits=exercise(client,budget.record_quota_event)
            self.assertEqual(client.calls,2);self.assertEqual(result['free_bytes'],999999999999)
            self.assertEqual(len(waits),1);self.assertLessEqual(waits[0],1.1)
            self.assertEqual(budget.quota_event_count,2)
            events=[I.read_json(ref) for ref in budget.quota_event_references]
            self.assertEqual([e['resource_event']['phase'] for e in events],['FIRST_ORIGINAL_VALIDATOR_REJECTION','SECOND_ORIGINAL_CLIENT_ACCEPTED'])
            self.assertTrue(all(e['actual_single_parent_job_id']=='synthetic-resource-parent' and e['node']=='compute-0-18' for e in events))
            for client in (OriginalObservation(sampled=-21.),OriginalObservation(expires=99.),OriginalObservation(provider='EXPIRED'),
                OriginalObservation(identity=dict(expected,sha256='e'*64)),OriginalObservation(error='ANOTHER_ORIGINAL_ERROR')):
                rows=[]
                with self.assertRaises(ValueError):exercise(client,rows.append)
                self.assertEqual(client.calls,1)
                self.assertTrue(not rows or rows[0]['eligible_for_one_original_client_reread']is False)
            rows=[];client=OriginalObservation(second_error=guard.TIME_ERROR)
            with self.assertRaises(ValueError):exercise(client,rows.append)
            self.assertEqual(client.calls,2);self.assertEqual(rows[-1]['phase'],'SECOND_ORIGINAL_CLIENT_FAILED_STOP')
            def failed_recorder(event):raise OSError('SYNTHETIC_EVENT_PERSISTENCE_FAILURE')
            client=OriginalObservation()
            with self.assertRaises(OSError):exercise(client,failed_recorder)
            self.assertEqual(client.calls,1)
    def test_exclusive_claim_and_orphan_evidence_never_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'original-key.json';row={'task_key':'a'*64,'job_id':'123','science_result_observed':False}
            ref=I.save(path,row)
            with self.assertRaises(FileExistsError):I.save(path,dict(row,job_id='fake-new'))
            self.assertEqual(I.read_json(ref),row)
            I.save(pathlib.Path(d)/'orphan_start.json',{'task_key':row['task_key'],'owner':'old'})
            self.assertTrue((pathlib.Path(d)/'orphan_start.json').exists());self.assertFalse(row['science_result_observed'])
            bounds={'max_registered_parents':1,'max_files_per_parent':2,'max_bytes_per_parent':4096,'max_task_file_bytes':4096}
            reader=H.ClosedReader(d,H.limits(bounds),lambda:None);first=reader.reference(path)
            self.assertEqual(reader.read(first),row)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):reader.reference(path)
            with self.assertRaises(ValueError):reader.reference(pathlib.Path(d).parent/'outside_the_registered_root')
            with self.assertRaises(ValueError):H.limits(dict(bounds,max_files_per_parent=True))
            # Existing >2MiB operational JSON is not scientific DATA or absent.
            # Only its explicit fixed-root CPU path bypasses the small reader.
            root=pathlib.Path(d)/'closed-large-parent';root.mkdir();plan_ref={'path':'/synthetic/plan','bytes':1,'sha256':'a'*64}
            proof_ref={'path':'/synthetic/proof','bytes':1,'sha256':'b'*64};index_ref={'path':str(root/'index.parquet'),'bytes':1,'sha256':'c'*64}
            pre=I.save(root/'preflight.json',{'tests_run':9,'failures':0,'errors':0,'skips':0,'expected_failures':0,'unexpected_successes':0})
            value={'schema':'SPRIME_PACKED_DAY_RECEIPT_V1','status':'actual synthetic closed parent','actual_single_parent_job_id':'9','uid':1278,
                'node':'compute-0-13','allocated_cpus':64,'plan_reference':plan_ref,'startup_proof_reference':proof_ref,'preflight_reference':pre,
                'original_plan_reference':plan_ref,'inputs_review_reference':proof_ref,'resolution_index_reference':index_ref,
                'complete_errors_reference':dict(index_ref,path=str(root/'errors.jsonl')),'state_counts':{'UNKNOWN':1},
                'all_started_native_tasks_drained':True,'child_Slurm_jobs_created':0,'new_parent_C0_or_Common_quality_release_claimed':False,
                'new_QM_calls':0,'resource_report':{'padding':'x'*(2<<20)}}
            full=I.save(root/'receipt.json',value);s=(root/'receipt.json').lstat()
            loc={'path':full['path'],'bytes':s.st_size,'uid':s.st_uid,'inode':s.st_ino,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns,
                'nlink':s.st_nlink,'mode':s.st_mode,'regular':True,'symlink':False}
            self.assertEqual(O.locator(loc,root),loc)
            for bad in (dict(loc,bytes=True),dict(loc,bytes=O.LIMIT+1),dict(loc,path=str(root/'different.json')),dict(loc,sha256='0'*64)):
                with self.assertRaises(ValueError):O.locator(bad,root)
            with self.assertRaises(ValueError):C.G.read_small(full['path'])
            origin={'entry':{'producer_receipt_reference':None,'large_operational_metadata_entry_reference':proof_ref,'actual_receipt_locator':loc,
                'producer_plan_reference':plan_ref,'startup_proof_reference':proof_ref},'root':str(root),'job_id':'9',
                'plan':{'original_plan_reference':plan_ref,'inputs_review_reference':proof_ref,'cpus':64},'owner_parent':{'actual':{'state':'COMPLETED','alloc_cpus':64}}}
            large=H.ClosedReader(root,{'max_registered_parents':1,'max_files_per_parent':8,'max_bytes_per_parent':8<<20,'max_task_file_bytes':1<<20},lambda:None)
            actual,actual_ref,header_ref=O.read(origin,large,lambda owner,raw:I.exclusive(root/'small_header.json',raw),{'synthetic':True})
            self.assertEqual(actual,value);self.assertEqual(actual_ref,full);self.assertLess(header_ref['bytes'],2<<20)
            header=I.read_json(header_ref);self.assertEqual(header['receipt_projection']['state_counts'],{'UNKNOWN':1})
            self.assertEqual(header['source_operational_receipt_reference'],full)
            changed=dict(origin,entry=dict(origin['entry'],actual_receipt_locator=dict(loc,inode=loc['inode']+1)))
            with self.assertRaises(ValueError):O.read(changed,large,lambda *args:None,{'synthetic':True})
    def test_float64_identity_bits_and_bounded_full_packet_readback(self):
        import numpy as np
        numbers=[6,1];coords=[[float(np.nextafter(1.,2.)),0.,0.],[0.,0.,1.]];atom=hashlib.sha256(np.asarray(numbers,dtype='<i8').tobytes()).hexdigest()
        geo=OLD.common().geometry_sha(numbers,coords)
        row={'molecule_id':'synthetic','sprime_conf_idx':0,'atomic_numbers':numbers,'coordinates':coords,'atom_order_sha256':atom,
            'geometry_sha256':geo,'source_record_id':'native_1','status':'SUCCESS','converged':True,'uff_energy_kcal_mol':1.,
            'origin':'accepted_sprime','original_sprime_conf_idx':0,'seed':3,'candidate_id':None,'below_dedup_threshold':False}
        packet={'summary':{'molecule_id':'synthetic','source_record_id':'native_1','atom_order_sha256':atom},'conformers':[row]}
        value={'packet_compressed_limit_bytes':1<<20,'packet_uncompressed_limit_bytes':4<<20}
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'toy.json.gz';ref=I.exclusive(p,gzip.compress(C.F.canonical(packet),mtime=0));self.assertEqual(OLD.read_packet(ref,value),packet)
            with self.assertRaises(ValueError):OLD.read_packet(dict(ref,sha256='0'*64),value)
        other=dict(row,coordinates=np.asarray(coords,dtype='<f4').astype('<f8').tolist())
        with self.assertRaises(ValueError):Z.coordinate_identity(other)
        other.pop('geometry_sha256')
        self.assertNotEqual(Z.coordinate_identity(row),Z.coordinate_identity(other))
        # Execute the exact original writer -> wholeSHA/reopen -> history reader.
        # Every value is synthetic; no native source, ledger, SCI or pool is opened.
        import sqlite3,types
        import pyarrow as pa,pyarrow.parquet as pq
        from . import run as producer
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);db=sqlite3.connect(root/'fixture.sqlite')
            db.execute('CREATE TABLE metas(k TEXT PRIMARY KEY,mid TEXT,meta TEXT,bid TEXT,candidate INTEGER,state TEXT,evidence TEXT)')
            db.execute('CREATE TABLE errors(n INTEGER PRIMARY KEY,phase TEXT,k TEXT,error TEXT)')
            package={'path':str(root/'prior_packet.json.gz'),'bytes':1,'sha256':'e'*64};keys=[]
            for n,state in enumerate(('DURABLE_PACKAGE_VALIDATED','CONSUMED_UNKNOWN_NO_RETRY','UNSUPPORTED')):
                mid='synthetic-index-'+str(n);cohort='unsupported' if n==2 else 'fill_10N';key=C.F.task_key(mid,cohort);keys.append(key)
                meta={'molecule_id':mid,'cohort':cohort,'expected_conformers':n+1,'effective_role':'TRAIN'}
                evidence={'science_result_observed':n==0}
                if n==0:evidence['package_reference']=package
                db.execute('INSERT INTO metas VALUES(?,?,?,?,?,?,?)',(key,mid,C.F.canonical(meta).decode(),'batch-00114',1,state,C.F.canonical(evidence).decode()))
            db.execute('INSERT INTO errors VALUES(1,?,?,?)',('HISTORICAL_UNKNOWN',keys[1],'SYNTHETIC_UNKNOWN_PRESERVED'));db.commit()
            census=types.SimpleNamespace(db=db,check=lambda:None)
            budget=types.SimpleNamespace(write=lambda path,raw:I.exclusive(path,raw))
            plan_ref={'path':'/synthetic/actual_old_plan.json','bytes':1,'sha256':'b'*64}
            index,errors,counts=producer.export_index(census,budget,root,{'job_id':'synthetic-true-parent'},plan_ref)
            limits={'max_registered_parents':1,'max_files_per_parent':32,'max_bytes_per_parent':1<<20,'max_task_file_bytes':1<<20}
            def closed_read(reference):
                reader=H.ClosedReader(root,H.limits(limits),lambda:None)
                return H.operational_index(census,{},reader,{'resolution_index_reference':reference,'complete_errors_reference':errors})
            actual=closed_read(index);self.assertEqual(actual['rows'],3);self.assertEqual(actual['old_observed_packages'],{keys[0]:package})
            self.assertEqual(counts,{'DURABLE_PACKAGE_VALIDATED':1,'CONSUMED_UNKNOWN_NO_RETRY':1,'UNSUPPORTED':1})
            rows=pq.read_table(index['path']).to_pylist();self.assertTrue(all('evidence_json' in row and 'evidence' not in row for row in rows))
            def bad_index(name,rows):
                sink=pa.BufferOutputStream();pq.write_table(pa.Table.from_pylist(rows),sink,compression='zstd')
                return I.exclusive(root/(name+'.parquet'),sink.getvalue().to_pybytes())
            bad_cases={'missing_row':rows[:-1],'duplicate_key':rows+[dict(rows[0])],
                'wrong_mid':[dict(row,molecule_id='wrong') if n==0 else dict(row) for n,row in enumerate(rows)],
                'wrong_N':[dict(row,expected_conformers=99) if n==0 else dict(row) for n,row in enumerate(rows)],
                'wrong_column':[dict((('evidence' if k=='evidence_json' else k),v) for k,v in row.items()) for row in rows]}
            for name,bad_rows in bad_cases.items():
                with self.assertRaises(ValueError):closed_read(bad_index(name,bad_rows))
            with self.assertRaises(ValueError):closed_read(dict(index,sha256='0'*64))
            db.close()
    def test_exact_one_original_scientific_call_and_single_real_parent(self):
        tree=ast.parse(inspect.getsource(W.one));calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='SCIENCE' and n.func.attr=='process_task']
        self.assertEqual(len(calls),1)
        text=inspect.getsource(W);self.assertNotIn('subprocess.',text);self.assertNotIn('os.system',text)
        plan={'original_plan_reference':{'path':'/synthetic/plan','bytes':1,'sha256':'a'*64},'inputs_review_reference':{'path':'/synthetic/review','bytes':1,'sha256':'b'*64},
            'cpus':64,'output_cap_bytes':528<<30}
        params=C.parameters(plan);self.assertTrue(params['one_true_parent_no_child_sbatch_srun_or_child_C0']);self.assertEqual(params['cpus'],64)
        self.assertEqual(params['stop_dispatch_before_wall_seconds'],900)
        self.assertEqual(C.origin_resources({'cpus':64}),(64,'compute-0-13',1))
        for node in ('compute-0-14','compute-0-18'):
            for cpus in (16,64,96):
                new=dict(plan,cpus=cpus,node=node,packed_resource_contract_version=2)
                self.assertEqual(C.origin_resources(new),(cpus,node,2))
                req={'schema':'CPU_PACKED_DAY_REQUEST_V2','scope_key':C.KEY,'cpus':cpus,'requested_cpus':cpus,'node':node}
                C.origin_request(new,req)
                header={'actual_allocated_cpus':cpus,'actual_node':node,'packed_resource_contract_version':2}
                C.header_resources(header,new)
                with self.assertRaises(ValueError):C.header_resources(dict(header,actual_node='compute-0-13'),new)
                with self.assertRaises(ValueError):C.header_resources(dict(header,actual_allocated_cpus=cpus+1),new)
                with self.assertRaises(ValueError):C.origin_request(new,dict(req,schema='CPU_PACKED_DAY_REQUEST_V1'))
        for bad in ({'cpus':16},{'cpus':64,'node':'compute-0-18'},{'cpus':97,'node':'compute-0-18','packed_resource_contract_version':2}):
            with self.assertRaises(ValueError):C.origin_resources(bad)
        self.assertEqual(H.positive_ticks('123456'),123456)
        for bad in ('0123','0','-1','1.0',True,None):
            with self.assertRaises(ValueError):H.positive_ticks(bad)
        # The actual old packed binding is called with a synthetic, closed
        # original task/claim/start/header. No global ledger or native is opened.
        import types
        mid='synthetic-packed-continuation';cohort='fill_10N';key=C.F.task_key(mid,cohort);task={'meta':{'task_key':key,'molecule_id':mid,'cohort':cohort}}
        root=pathlib.Path('/synthetic/closed-packed-parent');jid='123';bid='batch-00114'
        plan_ref={'path':'/synthetic/plan','bytes':1,'sha256':'b'*64}
        header_ref={'path':str(root/'internal_prepared'/bid/'prepared.json'),'bytes':1,'sha256':'c'*64}
        lr={'path':str(C.F.ledger_path(key)),'bytes':1,'sha256':'d'*64}
        start={'resource_scope':C.KEY,'task_key':key,'molecule_id':mid,'job_id':jid,'uid':1278,'node':'compute-0-13','pid':222,
            'pid_start_ticks':'456','boot_id':'synthetic-boot','task_sha256':C.F.sha_value(task),'seed':C.F.seed_for(mid,False),
            'internal_batch_id':bid,'dispatch_reference':lr}
        claim={'schema':'SPRIME_DISPATCH_INTENT_V3','resource_scope':C.KEY,'task_key':key,'molecule_id':mid,'job_id':jid,'uid':1278,
            'node':'compute-0-13','parent_pid':111,'parent_start_ticks':'123','boot_id':start['boot_id'],'task_sha256':start['task_sha256'],
            'seed':start['seed'],'internal_batch_id':bid,'packed_plan_reference':plan_ref,'prepared_reference':header_ref,
            'single_real_parent':True,'kernel_sha256':C.F.KERNEL_SHA}
        header={'schema':'SPRIME_PACKED_INTERNAL_PREPARED_V1','actual_allocated_cpus':64,'actual_single_parent_job_id':jid,
            'packed_plan_reference':plan_ref,'native_task_keys_and_seed_domains_changed':False}
        proof={'job_id':jid,'node':'compute-0-13','boot_id':start['boot_id'],
            'parent_identity':{'pid':111,'uid':1278,'start_ticks':123,'boot_id':start['boot_id']}}
        H.dispatch_binding(claim,start,proof,plan_ref,task)
        with self.assertRaises(ValueError):H.dispatch_binding(dict(claim,parent_start_ticks='124'),start,proof,plan_ref,task)
        with tempfile.TemporaryDirectory() as d:
            proof_ref=I.save(pathlib.Path(d)/'proof.json',proof)
            start_ref={'path':str(root/'starts'/(key+'.json')),'bytes':1,'sha256':'e'*64}
            refs={lr['path']:lr,start_ref['path']:start_ref}
            values={lr['path']:claim,start_ref['path']:start,header_ref['path']:header}
            ctx=types.SimpleNamespace(packed_plan={'output_directory':str(root),'cpus':64},packed_receipt={'plan_reference':plan_ref,
                'startup_proof_reference':proof_ref,'actual_single_parent_job_id':jid},reference=lambda p:refs[str(p)],
                read=lambda r:values[r['path']],require=lambda r:pathlib.Path(r['path']),_task_header=header_ref,_task_rows={key:task})
            packet={'molecule_id':mid,'source':{'path':str(root/'packets'/(key+'.json.gz'))},'summary':{'seed':start['seed']},'formal_start':start}
            self.assertEqual(H.binding(ctx,packet,{},{} )['once_ledger_sha256'],lr['sha256'])
            header['actual_allocated_cpus']=16
            with self.assertRaises(ValueError):H.binding(ctx,packet,{},{} )
