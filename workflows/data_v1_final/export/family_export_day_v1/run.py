"""One real CPU Parent: preflight, field claims, candidate, shards and source QA."""
from __future__ import annotations
import argparse,concurrent.futures as cf,io,json,multiprocessing as mp,os,pathlib,subprocess,time,traceback,unittest
for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[_name]='1'
from . import contract as C,io as I,project as P,transport as T,writer as W
L=C.legacy();O=L['pipeline_v1.io'];CODEC=L['wire_v1.codec']


def preflight(out):
    from . import test_boundaries,source_inverse
    report={};log=io.StringIO()
    for name,case,expected in [('family',test_boundaries.Boundaries,3),('original_pairs',__import__('pipeline_v1.test_source_pairs_v2',fromlist=['SparsePairTests']).SparsePairTests,4)]:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(case);C.need(suite.countTestCases()==expected,'EXACT_PREFLIGHT_METHOD_COUNT:'+name)
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        report[name]={'count':result.testsRun,'failures':result.failures,'errors':result.errors}
        C.need(result.wasSuccessful() and result.testsRun==expected,'SOURCE_PREFLIGHT_FAILED:'+name)
    # Frozen wire fixtures use only their own explicit test-root argument. The
    # CLI owns its globals, all fixture writers and all spawned handles.
    command=[C.PY,'-B','-m','wire_v1.tests','--output',str(out/'wire_fixtures'),'--workers','16']
    env=dict(os.environ);env['PYTHONPATH']=str(C.EXPORT)+os.pathsep+env.get('PYTHONPATH','')
    with (out/'wire_fixture.log').open('xb') as f:completed=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,env=env,check=False)
    wire=json.loads((out/'wire_fixtures/test_summary.json').read_text())
    C.need(completed.returncode==0 and wire['status']=='PASS' and wire['unit_tests']==8 and wire['all_workers_actually_closed'] is True,'ORIGINAL_WIRE8_AND16_SPAWN_ALL_HANDLES_CLOSED')
    report['original_wire']=wire;report['source_inverse']=source_inverse.proof();report['total_unit_methods']=15
    (out/'pure_tests.log').write_text(log.getvalue());C.Q.write_new(out/'preflight.json',report)
    return report


def task_key(index,spec,rg,offset):
    import hashlib
    return hashlib.sha256(CODEC.canonical_json([index,C.reference(spec['file']),rg,offset,spec])).hexdigest()


def tasks(specs,kind,stage,out,compiled,frames):
    import pyarrow.parquet as pq
    for index,spec in enumerate(specs):
        if spec['kind']!=kind:continue
        with I.same_parent_fd(spec['file'],frames[spec['file']['path']]) as fd:
            with os.fdopen(os.dup(fd),'rb') as raw:
                pf=pq.ParquetFile(raw);offset=0
                try:
                    for rg in range(pf.metadata.num_row_groups):
                        key=task_key(index,spec,rg,offset)
                        yield key,(index,spec,[rg],str(stage),str(out/(key+'.sqlite')),compiled,offset)
                        offset+=pf.metadata.row_group(rg).num_rows
                finally:pf.close()


def merge_piece(db,result):
    db.execute('ATTACH DATABASE ? AS completed_source',(result['reference']['path'],))
    try:
        # PK conflicts are evidence of ambiguous source ownership. Do not
        # overwrite, deduplicate or choose the latest file in this writer.
        db.execute('INSERT INTO pieces SELECT * FROM completed_source.pieces');db.commit()
    finally:db.execute('DETACH DATABASE completed_source')


def stage_sources(db,pool,specs,kind,stage,out,compiled,frames,budget,authority,completed,resume):
    pending={};cursor=iter(tasks(specs,kind,stage,out,compiled,frames));exhausted=False
    while pending or not exhausted:
        while not exhausted and len(pending)<32 and not I.OBS.stop_requested():
            try:budget.check();key,task=next(cursor)
            except StopIteration:exhausted=True;break
            if key in resume:
                result=resume.pop(key)
                with I.held(result['reference'],authority,budget.check):pass
                merge_piece(db,result);completed[key]=result;I.append(out/'closed_tasks.jsonl',dict(result,task_key=key,adopted_prior_parent=True));continue
            path=pathlib.Path(task[4]);C.need(not path.exists(),'NO_IMPLICIT_RETRY_OR_OVERWRITE_SOURCE_TASK')
            I.append(out/'dispatch.jsonl',{'task_key':key,'source_index':task[0],'row_group':task[2][0],'absolute_offset':task[-1],'output':str(path),'parent_job_id':os.environ['SLURM_JOB_ID']})
            pending[pool.submit(P.source_worker,task)]=key
        if I.OBS.stop_requested():exhausted=True
        if not pending:break
        done,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
        for future in done:
            key=pending.pop(future)
            try:
                result=future.result();result['reference']=I.actual_ref(result['path']);authority.add(result['reference']);merge_piece(db,result)
                completed[key]=result;I.append(out/'closed_tasks.jsonl',dict(result,task_key=key,adopted_prior_parent=False))
            except BaseException as exc:
                I.append(out/'errors.DATA.jsonl',{'task_key':key,'type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),'partial_output_not_adopted':True})
                I.OBS.mark_stop('SOURCE_TASK_UNKNOWN_NO_CURSOR_ACCEPTANCE',{'task_key':key,'type':type(exc).__name__})
    C.need(not pending,'ALL_ALREADY_STARTED_WORKERS_DRAINED_NO_CANCEL')
    return exhausted and not I.OBS.stop_requested()


def resume_tasks(plan,authority,budget):
    result={}
    if not plan.get('resume_adoption_reference'):return result
    review=C.meta(plan['resume_adoption_reference'])
    C.need(review['schema']=='ROOT_FAMILY_SOURCE_CURSOR_ADOPTION_V1' and review['status']=='APPROVED_EXACT_C0_CLOSED_SOURCE_TASKS'
        and review['reviewer']=='root' and review['source_release_reference']==plan['source_release_reference']
        and review['field_geometry_policy_reference']==plan['field_geometry_policy_reference'],'NO_RETRY_UNKNOWN_OR_DIFFERENT_SOURCE_POLICY')
    closure=review['actual_closure_references'];r=C.meta(closure['receipt']);proof=C.meta(closure['startup_proof'])
    from workflows.data_v1_final.export.common_day_parent_v1 import parent as B
    B.account(closure['accounting'],str(proof['job_id']),proof['request']['node'],16)
    C.need(r['schema']=='FAMILY_EXPORT_DAY_RECEIPT_V1' and r['startup_proof_reference']==closure['startup_proof']
        and r['source_release_reference']==plan['source_release_reference'],'REAL_PRIOR_PARTIAL_C0_NOT_FAILED_TIMEOUT_ACCEPTANCE')
    for item in I.jsonl(review['closed_source_tasks_reference'],authority,budget.check):
        key=item['task_key'];C.need(key not in result,'UNIQUE_ADOPTED_SOURCE_TASK');result[key]=item
    return result


def partitions(db,compiled,index,map_bytes):
    """Only equal actual geometry/field domains share a store schema."""
    import hashlib
    db.execute('DELETE FROM partition_members');groups={}
    for geometry in db.execute('SELECT geometry_id,geometry_source,view_id FROM selected_geometry WHERE geometry_id IN(SELECT geometry_id FROM shard_members) ORDER BY geometry_id'):
        gid,src,view=geometry;keys=[('geometry',src,view,None,())];families={}
        for row in db.execute("SELECT part FROM pieces WHERE geometry_id=? AND part!='__geometry__' ORDER BY part",(gid,)):
            tid=row[0];t=P.target(compiled,tid);C.need(t['geometry_source']==src,'ACTUAL_TARGET_PHYSICAL_GEOMETRY_SOURCE')
            families.setdefault(t['family'],[]).append(tid)
        keys.extend(('labels',src,view,family,tuple(tids)) for family,tids in sorted(families.items()))
        for key in keys:groups.setdefault(key,[]).append(gid)
    result=[]
    for key,gids in sorted(groups.items(),key=lambda x:repr(x[0])):
        kind,src,view,family,tids=key;name='shard_'+str(index).zfill(6)+'_'+hashlib.sha256(CODEC.canonical_json(key)).hexdigest()[:24]
        for gid in gids:db.execute('INSERT INTO partition_members VALUES(?,?)',(name,gid))
        result.append({'name':name,'kind':kind,'geometry_source':src,'view_id':view,'family':family,'target_ids':list(tids),'map_bytes':map_bytes})
    db.commit();return result

def write_shards(db,compiled,source,plan,out,budget,claims_reference,proof,completed):
    config=dict(source['export_configuration']);config.update(maximum_output_bytes=plan['output_cap_bytes'],
        _source_files=source['_specs'],_field_claims_reference=claims_reference,_actual_parent_job_id=str(proof['job_id']),
        _reason_codebook_sha256=source['reason_codebook_reference']['sha256'],_budget_check=budget.check,
        _schema_authorities=source['_schema_authorities'],_retire=budget.retire)
    C.need(type(config['molecules_per_shard']) is int and 1<=config['molecules_per_shard']<=5000,'BOUNDED_INTERNAL_SHARDS_NOT_SLURM_BATCHES')
    last='';index=0
    while True:
        mids=[r[0] for r in db.execute('SELECT molecule_id FROM selected_molecules WHERE molecule_id>? ORDER BY molecule_id LIMIT ?',(last,config['molecules_per_shard']))]
        if not mids:break
        if I.OBS.stop_requested():break
        old=db.execute('SELECT header FROM complete_shards WHERE shard_index=?',(index,)).fetchone()
        if old is not None:
            h=json.loads(old[0]);C.need(h['first_mid']==mids[0] and h['last_mid']==mids[-1] and h['molecules']==len(mids),'EXACT_SAME_D5_ORDER_SHARD_CURSOR')
            completed.append(h);last=mids[-1];index+=1;continue
        budget.check();db.execute('DELETE FROM shard_members')
        for mid in mids:db.execute('INSERT INTO shard_members SELECT geometry_id FROM selected_geometry WHERE molecule_id=?',(mid,))
        db.commit();directory=out/('shard_'+str(index).zfill(6));directory.mkdir(exist_ok=False)
        local=dict(config,partitions=partitions(db,compiled,index,config['map_bytes_per_store']))
        local['actual_shard_target_ids']={r[0] for r in db.execute("SELECT DISTINCT part FROM pieces WHERE part!='__geometry__' AND geometry_id IN(SELECT geometry_id FROM shard_members)")}
        # Names are globally unique but actual files live directly under out.
        # Each store closes before the durable shard cursor is published.
        stores=W.export_shard(db,out,compiled,local)
        for store in stores:
            ref=I.data_json_new(directory/(store['name']+'.json'),store)
            db.execute('INSERT INTO stores VALUES(?,?,?,?,?,?,?,?)',(store['name'],store['path'],json.dumps(store,separators=(',',':')),store['records'],store['molecules'],store['geometry_source'],store['view_id'],store['kind']))
        header={'shard_index':index,'first_mid':mids[0],'last_mid':mids[-1],'molecules':len(mids),'stores':len(stores),'actual_parent_job_id':str(proof['job_id'])}
        db.execute('INSERT INTO complete_shards VALUES(?,?)',(index,json.dumps(header)));db.commit();I.append(out/'shard_cursors.jsonl',header)
        completed.append(header);last=mids[-1];index+=1
    remaining=db.execute('SELECT count(*) FROM selected_molecules WHERE molecule_id>?',(last,)).fetchone()[0]
    return remaining


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=pathlib.Path,required=True);parser.add_argument('--startup-proof',type=pathlib.Path,required=True);args=parser.parse_args()
    plan=C.Q.load(args.plan);proof,parents=I.guard(args.plan,plan,args.startup_proof);out=I.literal(plan['output_directory']);C.need(not out.exists(),'FRESH_INDEPENDENT_EXPORT_OUTPUT')
    out.mkdir(parents=True,exist_ok=False);tests=preflight(out)
    plan=dict(plan,_startup_proof_path=str(args.startup_proof))
    I.OBS.start_observer(proof,{'resource_evidence_output':str(C.resource_output(plan)),'resource_evidence_local_cap_bytes':512<<20,
        'memavailable_soft_floor_bytes':4<<30,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':plan['output_cap_bytes']})
    try:budget=I.Budget(plan,proof,out)
    except BaseException as exc:
        C.Q.write_new(out/'receipt.json',{'schema':'FAMILY_EXPORT_DAY_RECEIPT_V1','status':'RESOURCE_STARTUP_HOLD_BEFORE_DATA','actual_parent_job_id':str(proof['job_id']),
            'plan_reference':C.Q.pin(args.plan),'startup_proof_reference':C.Q.pin(args.startup_proof),'error_type':type(exc).__name__,'error':str(exc),
            'preflight_reference':C.Q.pin(out/'preflight.json'),'scientific_DATA_read':False,'current_parent_C0_claimed':False})
        I.OBS.MONITOR.finish();raise
    authority=I.Authority(out/'derived_authority.sqlite',plan['data_references']);db=None
    receipt={'schema':'FAMILY_EXPORT_DAY_RECEIPT_V1','status':'PARTIAL_OR_UNKNOWN_NO_EXPORT_RELEASE','plan_reference':C.Q.pin(args.plan),
        'startup_proof_reference':C.Q.pin(args.startup_proof),'actual_parent_job_id':str(proof['job_id']),'source_release_reference':plan['source_release_reference'],
        'actual_cpus':16,'preflight_reference':C.Q.pin(out/'preflight.json'),'preflight_methods':15,'source_inverse':tests['source_inverse'],'errors':[],'remaining_shards':None,
        'source_roundtrip_records':0,'all_handles_closed':False,'pilot_counts_exact':False,'final_consumer_release':False,'science_QM_UFF_calls':0}
    closed={};shards=[]
    try:
        C.need(budget.last_quota['publisher_expires_unix_seconds']-time.time()>=I.R.remaining_wall(budget.clock,time.monotonic())+300,'FINITE_ACTUAL_PROVIDER_COVERS_REMAINING_PARENT_PLUS300')
        frames=I.hash_inputs(plan['data_references'],budget);source=dict(parents[6]);component=parents[5]
        from . import claims,verify
        prior=None
        if plan.get('resume_adoption_reference'):
            adoption=C.meta(plan['resume_adoption_reference']);prior=C.meta(adoption['actual_closure_references']['receipt'])
            geometry_ref=prior['geometry_database_reference'];claim_ref=prior['field_claims_reference'];candidate=prior['inline_final_label_candidate']
            # Exact immutable candidate objects survive continuation. We do not
            # regenerate an equivalent-looking normalizer with different SHA.
            for ref in [geometry_ref,claim_ref,*candidate['data_references']]:C.need(ref in authority,'ALL_PRIOR_IMMUTABLE_OBJECTS_ROOT_DECLARED')
        else:
            geometry_ref=P.geometry_database(plan,component,source,out,budget,authority);authority.add(geometry_ref)
            plan['_geometry_database_path']=geometry_ref['path']
            claim_ref=claims.materialize(plan,proof,out,budget,authority);authority.add(claim_ref)
            claim=C.meta(claim_ref);C.need(claim['status']=='COMPLETE_COMMON_FIELD_GEOMETRY_CLAIMS_NOT_FINAL_RELEASE' and claim['unknown_field_claims']==0,'COMPLETE_REAL_FIELD_CLAIMS_BEFORE_MASK_PUBLISH')
            authority.add(claim['database_reference'])
            from workflows.data_v1_final.labels.final_release_v1.produce import materialize_candidate
            directive=dict(parents[3],runtime_actual_field_claims_reference=claim_ref,root_reviewed_directive_reference=plan['final_release_directive_reference'])
            candidate=materialize_candidate(directive,proof,out/'final_release_candidate',budget=budget,validate_mapping=T.compile_targets)
        claim=C.meta(claim_ref);authority.add(claim['database_reference']);plan['_geometry_database_path']=geometry_ref['path']
        for ref in [*candidate['data_references'],*(candidate[k] for k in ('registry_reference','mapping_reference','normalization_reference','mask_release_reference','candidate_reference'))]:authority.add(ref)
        receipt['inline_final_label_candidate']=candidate;receipt['field_claims_reference']=claim_ref;receipt['geometry_database_reference']=geometry_ref
        registry=C.meta(candidate['registry_reference']);mapping=C.meta(candidate['mapping_reference']);compiled=T.compile_targets(registry,mapping)
        source['_schema_authorities']={'exact_final_label_candidate':{k:candidate[k] for k in ('registry_reference','mapping_reference','normalization_reference','mask_release_reference','candidate_reference')},
            'source_specification_reference':source['source_specification_reference'],'D5_order_manifest_reference':component['order_manifest_reference'],
            'D5_geometry_map_manifest_reference':component['geometry_map_manifest_reference'],'D5_diagnostic_manifest_reference':component['diagnostic_manifest_reference']}
        masks=C.meta(candidate['mask_release_reference']);specs=list(I.jsonl(source['source_specification_reference'],authority,budget.check));source['_specs']=specs
        C.need(len(specs)<=100000 and len({(s['source_family'],s['kind'],s.get('task'),s['file']['path']) for s in specs})==len(specs),'BOUNDED_EXPLICIT_UNIQUE_SOURCE_SPECS')
        for spec in specs:
            C.need(spec['kind'] in ('geometry','labels') and spec['source_identity_verified'] is True,'EXACT_VERIFIED_SOURCE_SELECTOR')
            C.need(spec['file'] in authority,'EXACT_SOURCE_FILE_DATA_DECLARATION')
            for tid in spec.get('targets',[]):P.target(compiled,tid)
        db,d5=P.selection_database(plan,component,source,compiled,masks,out,budget,authority,geometry_ref)
        stage=out/'export_stage.sqlite';C.need(db.execute('PRAGMA database_list').fetchone()[2]==str(stage),'EXACT_CURRENT_STAGE_DATABASE')
        geometry_db=O.connect(geometry_ref['path'],readonly=True)
        try:
            for row in geometry_db.execute('SELECT * FROM actual_child_rows'):
                if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actual_child_rows'").fetchone() is None:db.execute('CREATE TABLE actual_child_rows(source_sha TEXT,physical_row_index INTEGER,geometry_id TEXT,record_id TEXT,molecule_id TEXT,calc_type TEXT,input_sha TEXT,PRIMARY KEY(source_sha,physical_row_index))')
                db.execute('INSERT INTO actual_child_rows VALUES(?,?,?,?,?,?,?)',tuple(row))
        finally:geometry_db.close()
        if db.execute("SELECT name FROM sqlite_master WHERE name='actual_child_rows'").fetchone() is None:db.execute('CREATE TABLE actual_child_rows(source_sha TEXT,physical_row_index INTEGER,geometry_id TEXT,record_id TEXT,molecule_id TEXT,calc_type TEXT,input_sha TEXT,PRIMARY KEY(source_sha,physical_row_index))')
        if prior is not None:
            oldpath=prior['selection_reference'];C.need(oldpath in authority,'EXACT_PRIOR_SELECTION_DATA_ROOT_ADOPTED')
            with I.held(oldpath,authority,budget.check):pass
            db.execute('ATTACH DATABASE ? AS adopted',(pathlib.Path(oldpath['path']).as_uri()+'?mode=ro&immutable=1',))
            for table in ('stores','exported','complete_shards'):db.execute('INSERT INTO '+table+' SELECT * FROM adopted.'+table)
            db.commit();db.execute('DETACH DATABASE adopted')
        db.commit();fmap=I.json_body(plan['field_map_reference'],authority,budget.check)
        context={'job_id':str(proof['job_id']),'node':proof['request']['node'],'control':budget.control,'frames':frames,
            'claim_database_reference':P.combined_claim_database(source,plan,claim,out,budget,authority),'field_ids':{f['field_key']:f['field_id'] for f in fmap}}
        stageout=out/'source_tasks';stageout.mkdir();(stageout/'errors.DATA.jsonl').touch();counter=mp.get_context('spawn').Value('q',0)
        resume=resume_tasks(plan,authority,budget)
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=P.initialize,initargs=(counter,plan['output_cap_bytes']//3,context)) as pool:
            complete=stage_sources(db,pool,specs,'geometry',stage,stageout,compiled,frames,budget,authority,closed,resume)
            if complete:
                O.reject_rows(db,"SELECT 1 FROM selected_geometry g LEFT JOIN pieces p ON p.geometry_id=g.geometry_id AND p.part='__geometry__' WHERE p.geometry_id IS NULL",'MISSING_ACTUAL_GEOMETRY_BEFORE_LABELS')
                complete=stage_sources(db,pool,specs,'labels',stage,stageout,compiled,frames,budget,authority,closed,resume)
        C.need(not resume or I.OBS.stop_requested(),'ADOPTED_SOURCE_TASK_NOT_PRESENT_IN_EXACT_SOURCE_PLAN')
        receipt['closed_source_tasks']=len(closed);receipt['source_tasks_reference']=I.actual_ref(stageout/'closed_tasks.jsonl') if (stageout/'closed_tasks.jsonl').exists() else None
        if complete:
            budget.retire(stageout)
            P.expected_coverage(db,context['claim_database_reference'],compiled,context['field_ids'])
            receipt['remaining_shards']=write_shards(db,compiled,source,plan,out,budget,claim_ref,proof,shards)
            if receipt['remaining_shards']==0:
                verification=verify.run(db,stage,out,specs,compiled,context,budget)
                receipt.update(source_roundtrip_records=verification['source_roundtrip_records'],all_handles_closed=verification['all_handles_closed'],verification_reference=verification['reference'],LMDB_data_bytes=verification['LMDB_data_bytes'],immutable_manifest_bytes=verification['immutable_manifest_bytes'])
                counts={r[0]:r[1] for r in db.execute('SELECT effective_role,count(*) FROM selected_molecules GROUP BY effective_role')}
                receipt['selected_molecules_by_role']=counts;receipt['pilot_counts_exact']=plan['purpose']!='pilot55k' or counts=={'TRAIN':50000,'VAL':5000}
                C.need(receipt['pilot_counts_exact'],'EXACT_PILOT55K');receipt['status']='COMPLETE_TECHNICAL_EXPORT_PENDING_EXTERNAL_SEAL'
        # Full store catalogue is DATA; login never enumerates journal/features.
        catalogue=out/'stores.DATA.jsonl'
        with catalogue.open('xb') as f:
            for row in db.execute('SELECT manifest FROM stores ORDER BY name'):f.write(row[0].encode()+b'\n')
            f.flush();os.fsync(f.fileno())
        receipt['stores_catalogue_reference']=I.actual_ref(catalogue);db.commit();db.close();db=None
        receipt['selection_reference']=I.actual_ref(stage);receipt['shard_cursor_reference']=I.actual_ref(out/'shard_cursors.jsonl') if shards else None
    except BaseException as exc:
        receipt['errors'].append({'type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()});receipt['status']='UNKNOWN_OR_ERROR_HOLD_NO_IMPLICIT_RETRY'
    finally:
        if db is not None:db.close()
        budget.finish();I.OBS.MONITOR.finish();receipt['memory_observation_reference']=C.Q.pin(C.resource_output(plan)/'closure.json')
        receipt['resource_observation']=budget.receipt();authority.close()
        C.need(receipt['resource_observation']['whole_parent_bytes']+(512<<20)<=plan['output_cap_bytes'],'WHOLE_PARENT_AND_RESOURCE_EVIDENCE_WITHIN_REVIEWED_CAP')
        receipt['closed_internal_shards']=len(shards);C.Q.write_new(out/'receipt.json',receipt)
    if receipt['status']=='UNKNOWN_OR_ERROR_HOLD_NO_IMPLICIT_RETRY':raise SystemExit(1)


if __name__=='__main__':main()