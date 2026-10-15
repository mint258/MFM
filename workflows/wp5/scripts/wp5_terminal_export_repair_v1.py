"""Export the two verified unretired terminal roots only; no QM or source LMDB.
The current contract authorizes metadata processing. Old SCI provenance stays
at its original contract3/package/job/session; run.json is never rewritten.
"""
from __future__ import annotations
import argparse,concurrent.futures,json,multiprocessing,os,platform,socket,time,traceback
from collections import Counter
from pathlib import Path
import wp5_queue_reconcile_v2 as Q
ROOT=Q.ROOT
PLAN=ROOT/'reports/terminal_reconciliation_plan_v2_job_4514064/plan.json'
PLAN_SHA='0dae1608329acf62ce25c5272a41fa5fdfc90511fe84866d62555d8d4b2a0906'
CONTRACT=ROOT/'configs/production_contract_v4.json'
CONTRACT_SHA='41852032a9f063ed5c4fe88912ad72ec65b1b0e69fd4c11e9ccbb0db65f2b84d'
APPLY=ROOT/'reports/terminal_reconciliation_apply_v2_20261011/report.json'
ALLOW={('15','4514017'):(2,20),('20','4514022'):(1,10)}
SCI=('wp5_engine_v3.py','wp5_parser_v2.py','wp5_archive_v5.py','wp5_parquet_v2.py','wp5_registry_coverage_v2.py','wp5_scf_metadata_v2.py')

def selection(reports):
    selected=[r for r in reports if r['staged_molecules']>0]
    if {(str(r['task_id']),str(r['job_id'])) for r in selected}!=set(ALLOW) or len(selected)!=2:raise ValueError('EXACT_TWO_UNRETIRED_ROOTS_REQUIRED')
    for r in selected:
        if r['errors'] or r['conflicts'] or r['retired_molecules'] or (r['staged_molecules'],r['records'])!=ALLOW[(str(r['task_id']),str(r['job_id']))]:raise ValueError('UNRETIRED_PLAN_ROOT_COUNTS_DIFFER')
    return sorted(selected,key=lambda r:str(r['task_id']))

def pool_init(barrier):
    barrier.wait(timeout=180)

def hash_ref(ref):
    p=Path(ref['path']);actual=Q.digest(p)
    if actual!=ref['sha256'] or 'bytes' in ref and p.stat().st_size!=ref['bytes']:raise ValueError('SOURCE_OR_PERMANENT_SHA_DIFFERS:'+str(p))
    return {**ref,'actual_sha256':actual,'actual_bytes':p.stat().st_size,'worker_pid':os.getpid()}

def hash_parallel(refs,workers):
    # All workers perform a real hash. Repeat only small source hashes if the
    # permanent set is shorter; do not relabel allocated CPUs as effective work.
    if not refs:return []
    tasks=list(refs)
    while len(tasks)<workers:tasks+=refs[:workers-len(tasks)]
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=ctx,initializer=pool_init,initargs=(barrier,)) as pool:
        results=list(pool.map(hash_ref,tasks,chunksize=1))
    if len({r['worker_pid'] for r in results})<16:raise ValueError('AT_LEAST16_EFFECTIVE_HASH_WORKERS_REQUIRED')
    return results

def rebase_deadlines(options,mono,epoch,hours):
    # These are metadata controls, not saved SCI execution context or recipes.
    out=dict(options);duration=min(float(hours),46.)*3600
    out.update(job_exit_monotonic=mono+48*3600,hard_monotonic=mono+duration,
               hard_epoch=epoch+duration,admit_monotonic=mono+duration,
               sql_deadline_monotonic=mono+duration)
    return out,mono+duration

def verify_inputs(args,out):
    Q.node_guard();Q.stop_guard()
    if Q.digest(args.plan)!=PLAN_SHA or Q.digest(args.contract)!=CONTRACT_SHA:raise ValueError('EXACT_CLOSED_PLAN_CURRENT_CONTRACT4_SHA_REQUIRED')
    plan=Q.load(args.plan);contract=Q.load(args.contract);applied=Q.load(args.apply_report)
    if plan['status']!='REVIEWABLE_PLAN_NO_QUEUE_WRITE' or plan['conflicts']:raise ValueError('CLOSED_CONFLICT_FREE_PLAN_REQUIRED')
    if applied['status']!='METADATA_ONLY_RECONCILIATION_COMPLETE' or applied['plan']['sha256']!=PLAN_SHA or any(r['status'] not in {'APPLIED','ALREADY_APPLIED'} for r in applied['results']):raise ValueError('ACTUAL_RECONCILIATION_APPLY_CLOSURE_REQUIRED')
    if contract['schema']!='WP5_PRODUCTION_CONTRACT_V1' or contract['status']!='PRODUCTION_CONTRACT_FROZEN' or contract['policy']!=Q.POLICY:raise ValueError('CURRENT_CONTRACT4_SCOPE_DIFFERS')
    for field in ('run_reports','actions','queue_snapshot','export_roots','submitted'):
        ref=plan[field]
        if Q.digest(ref['path'])!=ref['sha256']:raise ValueError('PLAN_LEAF_CHANGED:'+field)
    sources={ref['path']:ref for ref in contract['sources']}
    need=[ROOT/'scripts'/name for name in SCI]+[ROOT/'scripts/wp5_runner_v11.py',ROOT/'scripts/wp5_queue_reconcile_v2.py',ROOT/'scripts/wp5_accounting_v2.py']
    for path in need:
        if str(path) not in sources:raise ValueError('CURRENT_CONTRACT_SOURCE_NOT_BOUND:'+str(path))
    roots=selection(Q.load(plan['run_reports']['path']))
    references=[sources[str(p)] for p in need]
    references += [contract[k] for k in ('protocol','registry','audit_manifest','reproduction_package','node_authority','node_scope_plan','authority')]
    runs=[]
    for root_report in roots:
        root=Path(root_report['run_root']);run_path=root/'run.json';run=Q.load(run_path);old=run['options']
        if Q.digest(run_path)!=root_report['run_json_sha256']:raise ValueError('OLD_RUN_SHA_DIFFERS')
        if root.resolve()!=Path(old['run_root']).resolve() or not root.resolve().is_relative_to((ROOT/'runtime').resolve()):raise ValueError('OLD_RUN_SCOPE_DIFFERS')
        if (root/'export_completion.json').exists():raise ValueError('ROOT_ALREADY_CLOSED_DO_NOT_REEXPORT')
        if Path(old['production_contract']).name!='production_contract_v3.json':raise ValueError('OLD_SCI_CONTRACT3_PROVENANCE_REQUIRED')
        if root_report['session']!=old['session'] or root_report['job_id']!=str(old['job_id']):raise ValueError('OLD_SESSION_JOB_DIFFERS')
        for ref in old['source_bindings']:references.append(ref)
        old_refs={x['path']:x['sha256'] for x in old['source_bindings']}
        for path in [ROOT/'scripts'/name for name in SCI]:
            if old_refs.get(str(path))!=sources[str(path)]['sha256']:raise ValueError('SCI_SOURCE_CHANGED_SINCE_ORIGINAL_EXECUTION:'+str(path))
        for old_key,new_key in (('protocol','protocol'),('registry','registry'),('audit_membership','audit_manifest')):
            if old_refs.get(old[old_key])!=contract[new_key]['sha256']:raise ValueError('SCI_PROTOCOL_REGISTRY_AUDIT_CHANGED')
        runs.append({'root_report':root_report,'run':run,'options':old})
    # Deduplicate identical bindings; a conflicting expected SHA is never hidden.
    by_path={}
    for ref in references:
        prior=by_path.get(ref['path'])
        if prior and prior['sha256']!=ref['sha256']:raise ValueError('CURRENT_OLD_BINDING_SHA_CONFLICT:'+ref['path'])
        by_path[ref['path']]=ref
    binding_results=hash_parallel(list(by_path.values()),args.workers)
    proof=Q.terminal_proof(Q.registered_jobs(plan['submitted']['path']),out)
    if not proof['all_terminal']:raise ValueError('ORIGINAL78_NOT_ALL_TERMINAL')
    return plan,contract,runs,binding_results,proof

def before_scope(item,queue_path):
    from wp5_archive_v5 import ArchiveReader
    opt=item['options'];root=Path(opt['run_root']);expected=item['root_report'];q=Q.readonly(queue_path);seen={};lanes=[]
    try:
        for path in sorted((root/'temporary_lanes').glob('lane_*.sqlite')):
            reader=ArchiveReader(path,opt['dictionaries']);lanes.append(str(path))
            try:
                for stage in reader.iter_staged():
                    complete=reader.completion(stage['molecule_id']);e=Q.validate_payload(stage,complete,opt,reader.db)
                    if e['context']['attempt_id']!=0:raise ValueError('THIS_REPAIR_EXACT_ATTEMPT0_ONLY')
                    mid=stage['molecule_id'];row=q.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone()
                    if row is None or row['state']!='COMPLETE' or row['owner']!=opt['session'] or row['attempt']!=0 or row['export_json'] is not None:raise ValueError('APPLIED_QUEUE_CURRENT_SCI_OWNER_SCOPE_DIFFERS')
                    receipt=json.loads(row['receipt_json'])
                    if receipt['context']!=e['context'] or receipt['counts']!=e['receipt']['counts']:raise ValueError('QUEUE_RECEIPT_DIFFERS_FROM_SHA_VERIFIED_SCI')
                    if mid in seen:raise ValueError('DUPLICATE_MOLECULE_ACROSS_LANES')
                    seen[mid]={'molecule_id':mid,'records':stage['record_count'],'wire_sha256':stage['wire_sha256'],
                               'receipt':complete['receipt'],'receipt_sha256':e['receipt_sha256'],'context':e['context'],
                               'record_ids':[r['record_id'] for r in stage['payload']['population_rows']],
                               'source_archive':str(path),'completion_rank':row['completion_rank']}
            finally:reader.close()
        if (len(seen),sum(s['records'] for s in seen.values()))!=(expected['staged_molecules'],expected['records']):raise ValueError('ONLY_EXACT3_WHOLE_MOLECULES_30RECORDS_ALLOWED')
        return {'run_root':str(root),'lane_paths':lanes,'molecules':list(seen.values())}
    finally:q.close()

def after_scope(item,before,outcome,queue_path):
    from wp5_archive_v5 import ArchiveReader
    opt=item['options'];root=Path(opt['run_root']);result=outcome['result'];expected=ALLOW[(str(opt['task_id']),str(opt['job_id']))]
    if (result['molecules'],result['records'])!=expected or result['archive']['scientific_task_outcomes']!=12*expected[1]:raise ValueError('EXPORTED_PERMANENT_12N_COUNTS_DIFFERS')
    refs=result['families']+[result['canonical'],result['archive']]
    reader=ArchiveReader(result['archive']['path'],opt['dictionaries']);q=Q.readonly(queue_path);closed=[]
    try:
        for old in before['molecules']:
            mid=old['molecule_id'];c=reader.completion(mid)
            if c is None or c['wire_sha256']!=old['wire_sha256'] or c['record_count']!=old['records'] or Q.sha(Q.canonical(c['receipt']))!=old['receipt_sha256']:raise ValueError('PERMANENT_SCI_RECEIPT_WIRE_PROVENANCE_CHANGED')
            row=q.execute('SELECT * FROM molecules WHERE molecule_id=?',(mid,)).fetchone();pub=json.loads(row['export_json']) if row['export_json'] else None
            if row['state']!='COMPLETE' or row['owner']!=opt['session'] or row['attempt']!=0 or row['completion_rank']!=old['completion_rank']:raise ValueError('QUEUE_SCI_STATE_RANK_OWNER_CHANGED')
            rec=json.loads(row['receipt_json'])
            if rec['context']!=old['context'] or rec['counts']!=old['receipt']['counts']:raise ValueError('QUEUE_SCI_CONTEXT_COUNTS_CHANGED')
            if pub is None or pub['archive']['path']!=result['archive']['path'] or row['archive_path']!=result['archive']['path'] or pub['archive']['sha256']!=result['archive']['sha256']:raise ValueError('QUEUE_EXPORT_NOT_DURABLY_PUBLISHED')
            for k in ('reproduction_package_sha256','audit_membership_sha256'):
                if rec['context'][k]!=old['context'][k]:raise ValueError('ORIGINAL_SCI_PACKAGE_PROVENANCE_CHANGED')
            closed.append({'molecule_id':mid,'records':old['records'],'wire_sha256':old['wire_sha256'],'context':old['context'],
                           'completion_rank':old['completion_rank'],'queue_export_published':True,'permanent_receipt_readback':True})
        raw=0
        for record_id,calc,execution in reader.db.execute('SELECT record_id,calc_type,execution_id FROM records'):
            got=reader.get(record_id,calc,execution)
            if got['input_files'] or got['input_bodies_saved']:raise ValueError('INPUT_BODY_UNAUTHORIZED')
            raw+=1
        if raw!=result['archive']['raw_records']:raise ValueError('RETAINED_RAW_READBACK_COUNT_DIFFERS')
        if reader.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('PERMANENT_ARCHIVE_INTEGRITY_FAILED')
    finally:reader.close();q.close()
    return {'run_root':str(root),'old_run_sha256':item['root_report']['run_json_sha256'],'result':result,
            'closed_molecules':closed,'complete_raw_member_SHA_readbacks':raw,'permanent_refs':refs,
            'old_run_json_unchanged':Q.digest(root/'run.json')==item['root_report']['run_json_sha256']}

def execute(args):
    if args.workers<24:raise ValueError('24WORKERS_REQUIRED')
    out=Path(args.out)
    if not out.resolve().is_relative_to((ROOT/'reports').resolve()):raise ValueError('NEW_REPORT_OUTPUT_SCOPE_REQUIRED')
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic();epoch=time.time()
    base={'schema':'WP5_TWO_ROOT_TERMINAL_EXPORT_REPAIR_V1','source_sha256':Q.digest(__file__),'processing_job_id':os.environ.get('SLURM_JOB_ID'),
          'processing_host':socket.gethostname(),'python_version':platform.python_version(),'start_epoch':epoch,'QM_started':False,'original_LMDB_opened':False,
          'plan':{'path':str(args.plan),'sha256':PLAN_SHA},'current_metadata_contract':{'path':str(args.contract),'sha256':CONTRACT_SHA},
          'original_SCI_contract_and_package_provenance_preserved':True,'closed_other_roots_reexported':False}
    reports=[]
    try:
        plan,contract,items,bindings,proof=verify_inputs(args,out)
        base.update(source_bindings_readback=bindings,source_binding_actual_workers=sorted({x['worker_pid'] for x in bindings}),accounting=proof,
                    applied_reconciliation={'path':str(args.apply_report),'sha256':Q.digest(args.apply_report)})
        import wp5_runner_v11 as R
        for item in items:
            before=before_scope(item,plan['queue']);Q.write_json(out/('before_task_'+str(item['options']['task_id'])+'.json'),before)
            options,deadline=rebase_deadlines(item['options'],started,epoch,args.metadata_hours)
            Q.stop_guard()
            if time.monotonic()>=deadline:raise TimeoutError('CURRENT_METADATA_DEADLINE_REACHED_NO_QM')
            outcome=R.bounded_finalize(options,deadline)
            Q.write_json(out/('finalizer_task_'+str(options['task_id'])+'.json'),{'old_run_sha256':item['root_report']['run_json_sha256'],
                'original_scientific_options':item['options'],'new_metadata_deadline_host':socket.gethostname(),
                'rebased_controls':{k:options[k] for k in ('job_exit_monotonic','hard_monotonic','hard_epoch','admit_monotonic','sql_deadline_monotonic')},
                'original_session_job_context_preserved':True,'processing_runner_sha256':Q.digest(R.__file__),'outcome':outcome})
            if outcome.get('error'):raise RuntimeError('FROZEN_R11_EXPORT_RECORDED_ERROR:'+outcome['error'])
            reports.append(after_scope(item,before,outcome,plan['queue']))
        permanent=hash_parallel([ref for r in reports for ref in r['permanent_refs']],args.workers)
        base.update(status='EXACT_TWO_ROOT_EXPORT_REPAIR_COMPLETE',roots=reports,molecules=sum(len(r['closed_molecules']) for r in reports),
                    records=sum(r['result']['records'] for r in reports),requested_task_outcomes=sum(r['result']['archive']['scientific_task_outcomes'] for r in reports),
                    permanent_refs_SHA_readback=permanent,permanent_readback_actual_workers=sorted({x['worker_pid'] for x in permanent}),elapsed_seconds=time.monotonic()-started)
        if (base['molecules'],base['records'],base['requested_task_outcomes'])!=(3,30,360):raise ValueError('EXACT3_30_360_CLOSURE_REQUIRED')
        Q.write_json(out/'report.json',base);print(json.dumps({k:base[k] for k in ('status','molecules','records','requested_task_outcomes','elapsed_seconds')}));return 0
    except BaseException:
        base.update(status='METADATA_EXPORT_REPAIR_RECORDED_ERROR',error=traceback.format_exc(limit=12),completed_roots=reports,elapsed_seconds=time.monotonic()-started)
        Q.write_json(out/'report.json',base);print(base['error']);return 1

def check():
    import ast
    ast.parse(Path(__file__).read_text())
    roots=[{'task_id':k[0],'job_id':k[1],'staged_molecules':v[0],'records':v[1],'retired_molecules':0,'errors':[],'conflicts':[]} for k,v in ALLOW.items()]
    assert len(selection(roots))==2
    try:selection(roots+[{'staged_molecules':1,'task_id':'other','job_id':'1'}]);raise AssertionError('extra root accepted')
    except ValueError:pass
    old={'session':'old','job_id':'4514017','context':'untouched','hard_monotonic':-100,'source_bindings':['old-SCI']}
    rebased,deadline=rebase_deadlines(old,1000,2000,100)
    assert rebased['session']==old['session'] and rebased['job_id']==old['job_id'] and rebased['source_bindings']==old['source_bindings']
    assert deadline==1000+46*3600 and rebased['hard_epoch']==2000+46*3600 and old['hard_monotonic']==-100
    assert 'initialize_worker' not in {n.func.attr for n in ast.walk(ast.parse(Path(__file__).read_text())) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
    print('TWO_ROOT_SCOPE_DEADLINE_PROVENANCE_FIXTURE_PASS_NO_QM_NO_LMDB_NO_QUEUE')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--plan',type=Path,default=PLAN)
    p.add_argument('--contract',type=Path,default=CONTRACT);p.add_argument('--apply-report',type=Path,default=APPLY);p.add_argument('--out',type=Path)
    p.add_argument('--workers',type=int,default=24);p.add_argument('--metadata-hours',type=float,default=46)
    args=p.parse_args()
    if args.check:check()
    else:
        if not args.out:p.error('--out required')
        if not 0<args.metadata_hours<=46:p.error('metadata-hours must be positive and <=46')
        raise SystemExit(execute(args))
