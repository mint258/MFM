"""Metadata-only phase16 forecast; frozen rates and verified local mirror/CAS overlay."""
from __future__ import annotations
import argparse,collections,concurrent.futures,hashlib,json,math,multiprocessing,os,socket,sqlite3,time
from pathlib import Path
from urllib.parse import quote
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
MOLECULES,RECORDS=1220466,11231854
POLICY='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT'
CALCS=('pm7_B','pm7_cation','pm7_anion','pm7_water','pm7_octanol','xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient')
BARRIER=None
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
def ref(path):return {'path':str(path),'bytes':Path(path).stat().st_size,'sha256':sha(path)}
def load(path,expected=None):
    raw=Path(path).read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if expected is not None and digest!=expected:raise ValueError('BOUND_JSON_SHA_DIFFERS:'+str(path))
    return json.loads(raw),{'path':str(path),'bytes':len(raw),'sha256':digest}
def bound(r):return load(r['path'],r['sha256'])
def fingerprint(path):
    try:s=Path(path).lstat()
    except FileNotFoundError:return None
    import stat
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=1278:raise ValueError('OWN_REGULAR_LOCAL_MIRROR_REQUIRED')
    return {'path':str(path),'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns}
def overlay_rows(plan,applied):
    if applied['status']!='APPLIED_AND_VERIFIED' or not applied['full463_terminal_scope_verified'] or not applied['all_applied_rows_verified'] or applied['plan_skipped_count']:
        raise ValueError('ACTUAL_FULL463_VERIFIED_APPLY_REQUIRED')
    actions,_=bound(plan['actions'])
    if len(actions)!=plan['actions']['count'] or len(applied['results'])!=len(actions):raise ValueError('ACTUAL_CAS_COUNT_REQUIRED')
    changes={};before={}
    for action,result in zip(actions,applied['results']):
        if result['kind']!=action['kind'] or result['status'] not in ('APPLIED','ALREADY_APPLIED') or result.get('verified') is not True:raise ValueError('CAS_ACTION_NOT_VERIFIED')
        if action['kind'] not in ('RESTORE_DURABLE_COMPLETION','RELEASE_TERMINAL_INCOMPLETE','RELEASE_TERMINAL_INFRASTRUCTURE_FAILURE'):continue
        old=action['evidence']['before'] if action['kind']=='RESTORE_DURABLE_COMPLETION' else action['before']
        new=result['after'];mid=old['molecule_id']
        if mid in changes or new['molecule_id']!=mid or new['record_count']!=old['record_count'] or new['attempt']!=old['attempt']:raise ValueError('CAS_OVERLAY_IDENTITY_ATTEMPT_RECORD_COUNT_DIFFERS')
        before[mid]=old;changes[mid]=new
    if len(changes)!=sum(a['kind'] in ('RESTORE_DURABLE_COMPLETION','RELEASE_TERMINAL_INCOMPLETE','RELEASE_TERMINAL_INFRASTRUCTURE_FAILURE') for a in actions):raise ValueError('EVERY_MOLECULE_CAS_OVERLAY_REQUIRED')
    return changes,before
def remaining_from_mirror(mirror,changes,before,deadline):
    local=Path(mirror['local_queue'])
    if mirror['status']!='VERIFIED_LOCAL_MIRROR' or mirror['uid']!=1278 or mirror['hostname']!=socket.gethostname().split('.')[0]:raise ValueError('OWN_SAME_NODE_MIRROR_REQUIRED')
    if local.parent.parent!=Path('/tmp') or not local.parent.name.startswith('wp5_queue_mirror_'):raise ValueError('NODE_LOCAL_SCOPE_REQUIRED')
    for suffix in ('','-journal','-wal','-shm'):
        p=Path(str(local)+suffix)
        if fingerprint(p)!=mirror['local_fingerprints_after'][p.name]:raise ValueError('LOCAL_MIRROR_FINGERPRINT_CHANGED')
    db=sqlite3.connect('file:'+quote(str(local))+'?mode=ro&immutable=1',uri=True,isolation_level=None)
    db.row_factory=sqlite3.Row
    states=collections.defaultdict(lambda:{'molecules':0,'records':0});remaining={};seen=set()
    try:
        cursor=db.execute('SELECT molecule_id,state,task_id,file_group,record_count,attempt FROM molecules')
        try:
            for index,row in enumerate(cursor):
                if index%8192==0 and time.monotonic()>=deadline:raise TimeoutError('METADATA_INTERNAL_DEADLINE')
                row=dict(row);mid=row['molecule_id']
                if mid in changes:
                    old=before[mid]
                    if any(row[k]!=old[k] for k in ('state','task_id','file_group','record_count','attempt')):raise ValueError('MIRROR_CAS_BEFOREIMAGE_DIFFERS')
                    row=changes[mid];seen.add(mid)
                states[row['state']]['molecules']+=1;states[row['state']]['records']+=row['record_count']
                if row['state'] in ('PENDING','RETRY_PENDING'):remaining[mid]=(int(row['task_id']),int(row['file_group']),row['record_count'])
        finally:cursor.close()
    finally:db.close()
    if seen!=set(changes):raise ValueError('CAS_OVERLAY_ROW_MISSING')
    if (sum(v['molecules'] for v in states.values()),sum(v['records'] for v in states.values()))!=(MOLECULES,RECORDS):raise ValueError('FULL_POPULATION_CLOSURE')
    if any(s not in ('COMPLETE','PENDING','RETRY_PENDING') and v['molecules'] for s,v in states.items()):raise ValueError('UNRESOLVED_STATE_NOT_ALLOWED_IN_FORMAL_FORECAST')
    return remaining,dict(states)
def packing_groups(path,remaining):
    import pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(24);pa.set_io_thread_count(8)
    groups={};seen=set();full_m=full_r=0
    columns=['molecule_id','task_id','lane','file_group','size_stratum','records','total_atoms']
    for batch in pq.ParquetFile(path).iter_batches(batch_size=8192,columns=columns,use_threads=True):
        for row in batch.to_pylist():
            full_m+=1;full_r+=row['records'];mid=row['molecule_id']
            if mid not in remaining:continue
            n=int(row['records']);tid=int(row['task_id']);fg=int(row['file_group'])
            if (tid,fg,n)!=remaining[mid] or mid in seen:raise ValueError('REMAINING_PACKING_IDENTITY_OR_DUPLICATE')
            atoms=int(row['total_atoms'])
            if atoms<=0:raise ValueError('PACKING_ATOMS_REQUIRED')
            seen.add(mid);key=(tid,int(row['lane']),fg,row['size_stratum'])
            g=groups.setdefault(key,{'task_id':tid,'lane':int(row['lane']),'file_group':fg,'size_stratum':row['size_stratum'],'molecules':0,'records':0,'sum_record_atoms2':0})
            g['molecules']+=1;g['records']+=n;g['sum_record_atoms2']+=n*atoms*atoms
    if seen!=set(remaining) or (full_m,full_r)!=(MOLECULES,RECORDS):raise ValueError('PACKING_POPULATION_CLOSURE')
    return list(groups.values())
def model_inputs(old,groups):
    benchmark,bref=bound(old['source_benchmark'])
    if benchmark['status']!='G3_ALL_PILOT12_ARCHIVE_AND_FAMILY_BENCHMARK_CLOSED':raise ValueError('BENCHMARK_CLOSED_REQUIRED')
    ss={g['size_stratum'] for g in groups}
    family={s:sum(r['strata'].get(s,{}).get('bytes',0) for w in benchmark['workers'] for r in w['family_files'])/benchmark['sample_strata'][s]['records'] for s in ss}
    del benchmark
    prototype,pref=bound(old['source_new_physical_prototype'])
    if prototype['status']!='NEW_POLICY_PHYSICAL_BENCHMARK_CLOSED':raise ValueError('PROTOTYPE_CLOSED_REQUIRED')
    traces=[r for w in prototype['workers'] for r in w['trace_files']]
    trace={s:sum(r['bytes'] for r in traces if r['size_stratum']==s)/sum(r['rows'] for r in traces if r['size_stratum']==s)*12 for s in ss}
    del prototype
    audit,aref=bound(old['source_audit_membership'])
    totals=collections.Counter()
    for g in groups:totals[(g['file_group'],g['size_stratum'])]+=g['records']
    selected={(int(r['file_group']),r['size_stratum']):r['selected_records'] for r in audit['strata']}
    audit_upper={key:min(1,selected[key]/n) for key,n in totals.items()}
    rates={(r['size_stratum'],r['calc_type']):r for r in old['source_rate_models']}
    beta={s:max(r['conservative_new_stage_bytes_per_record_atoms2'] for r in old['stage_actual_witnesses'] if r['size_stratum']==s) for s in ss}
    receipt=max(r['bytes_per_molecule_upper_witness'] for r in old['all_molecule_metadata_page_witnesses'] if r['kind']=='permanent_archive_SCI_completion_metadata')
    return {'family':family,'trace':trace,'rates':rates,'beta':beta,'audit':audit_upper,'overhead':old['physical_nonframe_bytes_per_retained_call_upper'],'receipt_rate':receipt},[bref,pref,aref]
def init_worker(barrier):
    global BARRIER
    BARRIER=barrier;barrier.wait(timeout=300)
def task_cost(arg):
    if BARRIER is not None:BARRIER.wait(timeout=300)
    tid,groups,model=arg
    c={'task_id':tid,'molecules':0,'records':0,'archive_bytes':0.,'family_bytes':0.,'trace_bytes':0.,'staging_bytes':0.,'estimated_retained_calls':0.}
    lanes=collections.defaultdict(lambda:{'archive':0.,'stage':0.})
    for g in groups:
        n=g['records'];s=g['size_stratum'];aud=model['audit'][(g['file_group'],s)];n2=g['sum_record_atoms2']
        c['molecules']+=g['molecules'];c['records']+=n;c['family_bytes']+=n*model['family'][s];c['trace_bytes']+=n*model['trace'][s]
        stage=n2*model['beta'][s];c['staging_bytes']+=stage;lanes[g['lane']]['stage']+=stage
        for calc in CALCS:
            rate=model['rates'][(s,calc)];f=rate['failure_fraction'];kept=f+aud*(1-f)
            amount=n*(rate['failed_legacy_plus_AUX_bytes_per_record']+aud*rate['success_legacy_plus_AUX_bytes_per_record'])
            amount+=n2*rate['full_sidefiles_bytes_per_record_atoms2_upper']*kept
            amount+=n*kept*(rate['retained_metadata_frame_bytes_per_case_upper']+model['overhead'])
            c['archive_bytes']+=amount;c['estimated_retained_calls']+=n*kept;lanes[g['lane']]['archive']+=amount
    c['vacuum_bytes']=max((v['archive']+v['stage'] for v in lanes.values()),default=0)
    c['pending_family_trace_bytes']=c['family_bytes']+c['trace_bytes'];c['worker_pid']=os.getpid()
    return c
def top29(costs,field):
    rows=sorted(costs,key=lambda r:(-r[field],r['task_id']))[:29]
    return {'bytes':sum(r[field] for r in rows),'task_ids':[r['task_id'] for r in rows]}
def check():
    rate={'failure_fraction':.25,'failed_legacy_plus_AUX_bytes_per_record':2,'success_legacy_plus_AUX_bytes_per_record':4,'full_sidefiles_bytes_per_record_atoms2_upper':.2,'retained_metadata_frame_bytes_per_case_upper':3}
    m={'audit':{(1,'fixture'):.1},'family':{'fixture':5},'trace':{'fixture':7},'beta':{'fixture':2},'rates':{('fixture',c):rate for c in CALCS},'overhead':1}
    g={'records':2,'molecules':1,'size_stratum':'fixture','file_group':1,'lane':0,'sum_record_atoms2':18}
    out=task_cost((0,[g],m));expected=12*(2*(2+.1*4)+18*.2*(.25+.1*.75)+2*(.25+.1*.75)*4)
    assert math.isclose(out['archive_bytes'],expected,rel_tol=0,abs_tol=1e-10) and out['staging_bytes']==36 and out['family_bytes']==10 and out['trace_bytes']==14
    assert out['vacuum_bytes']==out['archive_bytes']+36
    print('PRIVATE_ORIGINAL_MODEL_FORMULA_PASS_NO_QM_NO_PRODUCTION_DB')
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    for name in ('mirror-manifest','expected-mirror-sha256','plan','expected-plan-sha256','applied','expected-apply-sha256','quota','out'):p.add_argument('--'+name)
    p.add_argument('--budget11',default=str(ROOT/'gates/g3/new_policy_budget_v11_job_4513959.json'))
    p.add_argument('--g3-v12',default=str(ROOT/'gates/g3_current_scope_closed_v12.json'))
    p.add_argument('--assignments',default=str(ROOT/'packing/molecule_assignments.parquet'))
    p.add_argument('--production-contract',default=str(ROOT/'configs/production_contract_v7.json'))
    p.add_argument('--collector');p.add_argument('--workers',type=int,default=24);a=p.parse_args()
    if a.check:check();return
    if any(getattr(a,n.replace('-','_')) is None for n in ('mirror-manifest','expected-mirror-sha256','plan','expected-plan-sha256','applied','expected-apply-sha256','quota','out')):p.error('Actual immutable mirror/plan/apply/quota/output required')
    if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-17' or a.workers!=24 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<24:raise ValueError('ACTUAL_COMPUTE17_24_WORKERS_REQUIRED')
    started=time.time();deadline=time.monotonic()+46*3600
    mirror,mref=load(a.mirror_manifest,a.expected_mirror_sha256);plan,planref=load(a.plan,a.expected_plan_sha256);applied,apref=load(a.applied,a.expected_apply_sha256)
    if applied['plan']['sha256']!=planref['sha256'] or applied['plan']['path']!=planref['path']:raise ValueError('ACTUAL_APPLY_PLAN_BINDING_DIFFERS')
    if plan['registered_jobs_count']!=463 or not plan['all_registered_jobs_terminal'] or plan['conflicts'] or plan['skipped']['count']:raise ValueError('FULL463_CONFLICT_FREE_PLAN_REQUIRED')
    if plan['queue_read_mirror']['manifest']!={'path':mref['path'],'sha256':mref['sha256']}:raise ValueError('MIRROR_PLAN_IDENTITY_DIFFERS')
    old,oldref=load(a.budget11);hb,href=load(a.g3_v12)
    if hb['source_budget']['sha256']!=oldref['sha256'] or old['policy']!=POLICY or hb['policy']!=POLICY:raise ValueError('FROZEN_STORAGE_MODEL_POLICY_DIFFERS')
    exports,_=bound(plan['export_roots']);closures=[]
    for item in exports:
        doc,r=load(Path(item['run_root'])/'export_completion.json')
        if (doc['molecules'],doc['records'])!=(item['molecules'],item['records']):raise ValueError('OLD_EXPORT_NOT_CLOSED')
        closures.append(r)
    if len(closures)!=len(exports):raise ValueError('EVERY_ACTUAL_OLD_EXPORT_CLOSURE_REQUIRED')
    changes,before=overlay_rows(plan,applied);remaining,states=remaining_from_mirror(mirror,changes,before,deadline)
    nm,nr=len(remaining),sum(v[2] for v in remaining.values())
    if nm<=0 or nr<=0:raise ValueError('NO_REMAINING_COMPUTE_TO_FORECAST')
    groups=packing_groups(a.assignments,remaining);model,modelrefs=model_inputs(old,groups)
    bytask=collections.defaultdict(list)
    for g in groups:bytask[g['task_id']].append(g)
    tids=[int(c['task_id']) for c in old['per_task']]
    if len(tids)!=72 or not set(bytask)<=set(tids):raise ValueError('ORIGINAL72_TASK_SCOPE')
    context=multiprocessing.get_context('spawn');barrier=context.Barrier(24)
    with concurrent.futures.ProcessPoolExecutor(max_workers=24,mp_context=context,initializer=init_worker,initargs=(barrier,)) as pool:
        costs=list(pool.map(task_cost,[(tid,bytask[tid],model) for tid in tids],chunksize=1))
    pids=sorted({r['worker_pid'] for r in costs})
    if len(pids)!=24 or (sum(r['molecules'] for r in costs),sum(r['records'] for r in costs))!=(nm,nr):raise ValueError('EFFECTIVE24_AND_MODEL_CLOSURE')
    for c in costs:
        if any(not math.isfinite(v) or v<0 for k,v in c.items() if k.endswith('_bytes')):raise ValueError('NONFINITE_COST')
    stage=top29(costs,'staging_bytes');archive_copy=top29(costs,'archive_bytes');vacuum=top29(costs,'vacuum_bytes')
    # Remaining counts come from the exact mirror and reviewed CAS overlay.
    permanent=sum(c['archive_bytes']+c['family_bytes']+c['trace_bytes'] for c in costs)+nr*old['permanent_canonical_index_bytes']/RECORDS+nm*old['permanent_all_molecule_checkpoint_and_SCI_metadata_bytes']/MOLECULES+hb['permanent_HB_addition_bytes']
    receipt_copy=sum(sorted((c['molecules'] for c in costs),reverse=True)[:29])*model['receipt_rate']
    basic=max(old['temporary_context']['requested_basic_reserve_bytes'],vacuum['bytes'])
    tests=old['temporary_context']['remaining_50_double_final200_and_newtests_unaccounted_bytes']
    temporary=basic+stage['bytes']+archive_copy['bytes']+receipt_copy+tests+hb['temporary_stage_HB_addition_bytes']
    reserve=400_000_000_000;peak=permanent+temporary+reserve
    quota,qref=load(a.quota);free=quota.get('quota_parsed',{}).get('remaining_bytes',quota.get('remaining_bytes',quota.get('quota',{}).get('remaining_bytes')))
    if not isinstance(free,(int,float)) or not math.isfinite(free) or free<0:raise ValueError('ACTUAL_FRESH_QUOTA_REQUIRED')
    _,contractref=load(a.production_contract)
    out={'schema':'WP5_PHASE16_REMAINING_STORAGE_FORECAST_V1','status':'REMAINING_STORAGE_ESTIMATE_CLOSED','storage_capacity_pass':free-peak>=200_000_000_000,
        'policy':POLICY,'created_epoch':time.time(),'started_epoch':started,'production_contract':contractref,
        'quota':{'remaining_bytes':free,'source':qref,'actual_document':quota},'headroom_bytes':free-peak,'required_headroom_bytes':200_000_000_000,
        'future_training_reserve_bytes':reserve,'remaining_writeback_peak_bytes':peak,'future_permanent_write_bytes':permanent,'future_temporary_bytes':temporary,
        'remaining_molecules':nm,'remaining_records':nr,'counts':{'population_molecules':MOLECULES,'population_records':RECORDS,'states':states,'remaining_molecules':nm,'remaining_records':nr},
        'queue_reconciliation_report':apref,'source_plan':planref,'mirror_snapshot':{'manifest':mref,'DB_sha256':mirror['local_files_after'][Path(mirror['local_queue']).name]['sha256'],'local_queue':mirror['local_queue'],'fingerprint_verified':True,'original_source_not_reopened':True,'overlay_rows':len(changes),'snapshot_was_before_actual_APPLY':True},
        'old_export_closures':closures,'materialized_permanent_collector':ref(a.collector) if a.collector else None,'source_model':oldref,'source_HB_upper':href,'model_metadata_refs':modelrefs,
        'source_assignments':ref(a.assignments),'actual_worker_pids':pids,'effective_worker_count':24,'groups':groups,'per_task':costs,
        'temporary_context':{'basic_reserve_bytes':basic,'top29_stage':stage,'top29_archive_consolidation_copy':archive_copy,'top29_single_lane_VACUUM_inside_basic':vacuum,'SCI_receipt_copy_extra_bytes':receipt_copy,'original_tests_reserve_bytes':tests,'full_original_HB_stage_upper_bytes':hb['temporary_stage_HB_addition_bytes']},
        'audit_rates_upper':[{'file_group':fg,'size_stratum':s,'upper':v} for (fg,s),v in sorted(model['audit'].items())],
        'permanent_HB_upper_bytes':hb['permanent_HB_addition_bytes'],'existing_dictionary_package_queue_and_exports_not_added_again':True,
        'pending_family_and_canonical_extra_charge_bytes':0,'scientific_configuration_changed':False,'QM_started':False,'source_queue_SQL':False,'source_queue_written':False,
        'method':'Original benchmark family/trace and84 failure/raw upper rates; remaining packing records*N_atoms^2 per task/lane/stratum. Audit upper=min(1,original selected stratum records/remaining stratum records). Original400GB,tests,basic/VACUUM and fullHB upper retained. Already charged files are not recharged.'}
    target=Path(a.out)
    if target.exists() or not target.resolve().is_relative_to(ROOT):raise ValueError('NEW_IMMUTABLE_PROJECT_OUTPUT_REQUIRED')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8',newline='\n') as f:json.dump(out,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    print(json.dumps({'status':out['status'],'capacity_pass':out['storage_capacity_pass'],'peak_TB':peak/1e12,'headroom_GB':(free-peak)/1e9,'path':str(target)}))
if __name__=='__main__':main()
