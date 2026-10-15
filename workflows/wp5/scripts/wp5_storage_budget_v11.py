#!/usr/bin/env python3
"""New user policy G3 estimate: failures + stratified1% RECORD outputs; no inputs.

Only retained calls incur output-container row overhead. All parsed float64
labels and six trace fields remain permanent Parquet. No minima retention.
Old completed G6 provides full-output/stage byte witnesses, not new-G6 PASS.
V11 corrects only demonstrated duplicate peak charges: a family/canonical
.pending file becomes its unique final file by same-directory os.replace, and
the shared queue is updated in place. Staging, raw merge, lane SCI receipt
copies, VACUUM reserve, all permanent values and remaining tests are retained.
Root sole submission; no QM, no original writes, no LMDB.
"""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,json,multiprocessing,os,socket,sys
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
import wp5_storage_budget_v9 as OLD
import wp5_archive_v4 as A
POLICY='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT'
FAIL={'CALCULATION_FAILED','PROPERTY_FAILED','TIMEOUT'}
STRATA=OLD.STRATA
def read(p):return json.loads(Path(p).read_text())
def ref(p):return {'path':str(p),'bytes':Path(p).stat().st_size,'sha256':A.file_sha(p)}
def status(v):
    if v in {'SUCCESS',*FAIL}:return v
    if v in {'RESOURCE_LIMIT_FAILED','SOURCE_READ_FAILED','QM_EXIT_OR_SCF_FAILED'}:return 'CALCULATION_FAILED'
    raise ValueError('Unknown native status is not a fake failure or success:'+str(v))
def audit_rates(manifest,groups,tasks):
    if manifest['status']!='AUDIT_MEMBERSHIP_CLOSED':raise ValueError('Actual stratified record audit must close')
    by={(int(r['file_group']),r['size_stratum']):r for r in manifest['strata']}
    if len(by)!=len(manifest['strata']):raise ValueError('Duplicate audit stratum')
    expected=collections.Counter()
    for g in groups:expected[(int(tasks[g['task_id']]['file_group']),g['size_stratum'])]+=g['records']
    if sum(expected.values())!=11231854:raise ValueError('MANIFEST_AUDIT_FORMAL_RECORD_CLOSURE')
    rates={}
    for key,n in expected.items():
        r=by[key]
        if r['population_records']!=n or not 0<r['selected_records']<=n:raise ValueError('MANIFEST_AUDIT_STRATUM_COUNT_MISMATCH')
        rates[key]=r['selected_records']/n
        if abs(rates[key]-r['actual_fraction'])>1e-14:raise ValueError('Actual audit fraction differs from integer counts')
    if set(by)!=set(expected):raise ValueError('Audit/formal file-group size-stratum keys differ')
    return rates
def raw_rates(benchmark,prototype):
    metrics=[r for w in benchmark['workers'] for r in w['metrics'] if r['policy']=='ALL']
    measured=[r for w in prototype['workers'] for r in w['cases']]
    ratios=[r for w in benchmark['workers'] for r in w['aux_ratios']]
    output={}
    for key in STRATA:
        ns=benchmark['sample_strata'][key]['records']
        for calc in A.CALC_TYPES:
            legacy=[r for r in metrics if r['size_stratum']==key and r['calc_type']==calc and not r['formal_excluded_calibration_only']]
            actual=[r for r in measured if r['size_stratum']==key and r['calc_type']==calc]
            if len(legacy)!=ns or not actual:raise ValueError('Required source task*stratum byte witness missing')
            aux_samples=[r for r in actual if r['AUX_raw_bytes']]
            ratio=max([r['AUX_compressed_bytes']/r['AUX_raw_bytes'] for r in aux_samples]+[r['ratio'] for r in ratios if r['calc_type']==calc and r['size_stratum']==key],default=None)
            if ratio is None:ratio=max((r['ratio'] for r in ratios if r['calc_type']==calc),default=None)
            fail_bytes=success_bytes=0;failed=0
            for r in legacy:
                failure=status(r['scope_status']) in FAIL
                if failure:failed+=1
                amount=r['raw_frame_bytes'] or 0
                missing=r['missing_aux_raw_bytes']
                if missing is None:
                    if calc.startswith('xtb_'):missing=0
                    elif aux_samples:missing=max(r['AUX_raw_bytes'] for r in aux_samples)
                    else:raise ValueError('Unknown historical AUX size without actual complete raw witness')
                if missing:
                    if ratio is None:raise ValueError('AUX dictionary size calibration unavailable')
                    amount+=missing*ratio+1024
                if failure:fail_bytes+=amount
                else:success_bytes+=amount
            # Independently compressed sidefile frames conservatively add to
            # old main-output/AUX reconstruction; no cache bytes subtracted.
            output[(key,calc)]={'pilot_records':ns,'actual_required_scope_failed_records':failed,
                'failure_fraction':failed/ns,'failed_legacy_plus_AUX_bytes_per_record':fail_bytes/ns,
                'success_legacy_plus_AUX_bytes_per_record':success_bytes/ns,
                'full_sidefiles_bytes_per_record_atoms2_upper':max(r['extra_atoms2_ratio'] for r in actual),
                'retained_metadata_frame_bytes_per_case_upper':max(r['metadata_frame_bytes'] for r in actual),
                'complete_raw_witness_records':len({r['record_id'] for r in actual}),
                'AUX_compression_ratio_upper':ratio,'historical_missing_AUX_calibrated_not_false_zero':True}
    return output,metrics
def source_stage_witness(prototype):
    from urllib.parse import quote
    import sqlite3
    witness=[];seen=set()
    for source in prototype['source_reports']:
        report=read(source['path'])
        if A.file_sha(source['path'])!=source['sha256']:raise ValueError('Prototype bound source report changed')
        root=Path(report.get('source_run') or Path(source['path']).parent)
        selected=read(root/'selected_molecules.json')
        rows=selected if isinstance(selected,list) else selected.get('selected_molecules',selected.get('molecules',selected.get('rows',[])))
        atoms={r['molecule_id']:int(r.get('max_total_atoms',r.get('total_atoms'))) for r in rows}
        extras={r['molecule_id']:r for w in prototype['workers'] for r in w['stage_extra'] if r['node']==report['node']}
        db=sqlite3.connect('file:'+quote(str(Path(report.get('queue') or root/'queue.sqlite')),safe='/')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        try:
            current=[dict(r) for r in db.execute('SELECT * FROM molecules')]
            if len(current)!=20 or any(r['state']!='COMPLETE' for r in current):raise ValueError('Actual20 source staging receipts not closed')
            for r in current:
                receipt=json.loads(r['receipt_json']);extra=extras[r['molecule_id']];n=r['record_count'];a=atoms[r['molecule_id']]
                compressed=receipt['stage_compressed_wire_bytes']
                if compressed is None or n<=0 or a<=0:raise ValueError('Actual original current-format durable wire size missing')
                key=(report['node'],r['molecule_id'])
                if key in seen:raise ValueError('Duplicate node molecule staging witness')
                seen.add(key);witness.append({'node':report['node'],'molecule_id':r['molecule_id'],'size_stratum':extra['size_stratum'],
                  'records':n,'atoms':a,'baseline_actual_stage_bytes':compressed,
                  'trace_additional_pickle_compressed_bytes':extra['trace_pickle_compressed_bytes'],
                  'conservative_new_stage_bytes_per_record_atoms2':(compressed+extra['trace_pickle_compressed_bytes'])/(n*a*a)})
        finally:db.close()
    return witness
def lifecycle_evidence():
    runner=ROOT/'scripts/wp5_runner_v8.py'
    archive=ROOT/'scripts/wp5_archive_v5.py'
    expected={
        runner:'9aec4b6fc30d5b7dd4f6c555b343ae838cf84afc560afb76bb3cd453621828e3',
        archive:'3ef37935402fffc9a5111f0dd6b942b279f42581cdea9aeea1a358169d766477'}
    for path,sha in expected.items():
        if A.file_sha(path)!=sha:raise ValueError('Lifecycle source changed; re-review required: '+str(path))
    code=runner.read_text()
    anchors=[
        'already=target.exists()',
        'writer=None if already else pq.ParquetWriter(pending,schema,compression="zstd",compression_level=3)',
        'os.replace(pending,target)',
        'existing=target.exists();pending=target.with_name(target.name+".pending")',
        'count=0;buffer=[];writer=None if existing else pq.ParquetWriter(pending,schema,compression="zstd")',
        'writer.retire_staged_after_verified_parquet(references+[canonical],vacuum=True,preverified=True)',
        'archive=consolidate_archives(paths,final_path,options["dictionaries"],options["protocol"],',
        'queue.publish_export(options["session"],references+[canonical],archive)',
        'UPDATE molecules SET export_json=?,archive_path=? WHERE owner=? AND receipt_json IS NOT NULL']
    if any(anchor not in code for anchor in anchors):raise ValueError('Reviewed lifecycle source anchor absent')
    return {
        'runner':ref(runner),'archive':ref(archive),
        'family_pending_final_union':{
            'lines':'541-579','pending_path':'run_root/parquet/group_G/FAMILY.parquet.pending',
            'final_path':'run_root/parquet/group_G/FAMILY.parquet',
            'proof':'Writer created only when final absent; exact readback then same-directory os.replace. Existing final is read-only validation, no new pending writer.',
            'additional_peak_charge_bytes':0},
        'canonical_pending_final_union':{
            'lines':'605-628','proof':'Same final-exists guard, readback and same-directory os.replace; one physical file represented by pending OR final.',
            'additional_peak_charge_bytes':0},
        'staging_and_raw_merge_retained':{
            'lines':'738-769','proof':'All family and canonical exports verified before stage retirement/VACUUM. Lane raw and SCI receipts remain while final archive is built; lanes removed only after verified consolidation and queue update.'},
        'queue_in_place':{
            'lines':'156-158,765','proof':'UPDATE shared queue rows in place; whole queue is not copied into consolidated raw archive. Permanent queue budget and basic SQLite reserve retained.',
            'additional_whole_queue_copy_bytes':0},
        'peak_model':'Conservative independent top29 stage and raw/SCI receipt copy envelope. Permanent family/canonical file union already includes unfinished pending files; not a measured simultaneous peak.'}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--prototype');p.add_argument('--benchmark');p.add_argument('--quota');p.add_argument('--audit-manifest')
    p.add_argument('--population',default=str(ROOT/'population/manifest.json'))
    p.add_argument('--assignments',default=str(ROOT/'packing/molecule_assignments.parquet'))
    p.add_argument('--tasks',default=str(ROOT/'packing/node_assignment_v3/tasks.json'))
    p.add_argument('--baseline',default=str(ROOT/'configs/pilot_success_baseline.json'))
    p.add_argument('--node-authority',default=str(ROOT/'gates/wp5_node_replacement_user_approved.json'))
    p.add_argument('--base-temporary-bytes',type=int,default=100_000_000_000)
    p.add_argument('--remaining-tests-not-in-quota-bytes',type=int)
    p.add_argument('--reproduction-package');p.add_argument('--workers',type=int,default=16);p.add_argument('--output');a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('NEW_POLICY_BUDGET_AST_PASS_NO_QM');return
    if not all((a.prototype,a.benchmark,a.quota,a.audit_manifest,a.output)):p.error('prototype benchmark quota audit-manifest output required')
    if a.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers or socket.gethostname().split('.')[0] not in OLD.EXECUTION_NODES:raise ValueError('Authorized node/16 effective workers required')
    if a.remaining_tests_not_in_quota_bytes is None:raise ValueError('Root must explicitly include remaining50-double/final200 and new-six test bytes not yet charged')
    lifecycle=lifecycle_evidence()
    benchmark=read(a.benchmark);prototype=read(a.prototype);population=read(a.population);audit=read(a.audit_manifest)
    if benchmark['status']!='G3_ALL_PILOT12_ARCHIVE_AND_FAMILY_BENCHMARK_CLOSED' or prototype['status']!='NEW_POLICY_PHYSICAL_BENCHMARK_CLOSED' or prototype['policy']!=POLICY:raise ValueError('Actual closed complete benchmarks required')
    if prototype['actual_worker_count']<16 or prototype['ordinary_success_container_rows'] or prototype['inputs_saved']:raise ValueError('Measured no-input/no-success-stub prototype not proven')
    authority=read(a.node_authority);tasks_list=read(a.tasks)['tasks'];tasks={int(t['task_id']):t for t in tasks_list}
    if authority['status']!='USER_APPROVED' or authority['old_to_new']!=OLD.AUTHORIZED_MAPPING or sum(authority['authorized_node_slots'].values())!=29:raise ValueError('Scoped actual node authority differs')
    if {t['node'] for t in tasks_list}!=OLD.EXECUTION_NODES:raise ValueError('Current task plan actual nodes differ')
    if population['status']!='WP5_FORMAL_POPULATION_CLOSED' or (population['formal_records'],population['formal_molecules'])!=(11231854,1220466):raise ValueError('MANIFEST_FORMAL_POPULATION_CLOSURE')
    baseline=read(a.baseline)
    if baseline['status']!='PILOT_BASELINE_CLOSED_12_REQUESTED_TASKS':raise ValueError('Original physical native baseline required')
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=OLD.init,initargs=(barrier,)) as pool:
        packing=list(pool.map(OLD.packing_part,[(i,a.assignments,a.workers,set()) for i in range(a.workers)],chunksize=1))
    pids={r['worker_pid'] for r in packing};groups=[g for w in packing for g in w['groups']]
    if len(pids)<16 or (sum(g['records'] for g in groups),sum(g['molecules'] for g in groups),len(tasks))!=(11231854,1220466,72):raise ValueError('MANIFEST_EFFECTIVE_PACKING_CLOSURE')
    q=audit_rates(audit,groups,tasks);rates,metrics=raw_rates(benchmark,prototype)
    # Genuine native failure counts are independent of G5 historical raw gaps.
    native_counts={}
    for calc in A.CALC_TYPES:
        rows=[r for r in metrics if r['calc_type']==calc]
        count=sum(status(r['scope_status'])=='SUCCESS' for r in rows)
        if len(rows)!=10020 or count!=baseline['tasks'][calc]['required_scope_success']:raise ValueError('Native requested-scope success proof differs from original baseline:'+calc)
        native_counts[calc]={'records':len(rows),'required_scope_success':count,'failed':len(rows)-count}
    files=[r for w in benchmark['workers'] for r in w['family_files']]
    family_rate={s:sum(r['strata'].get(s,{}).get('bytes',0) for r in files)/benchmark['sample_strata'][s]['records'] for s in STRATA}
    traces=[r for w in prototype['workers'] for r in w['trace_files']]
    trace_rate={s:sum(r['bytes'] for r in traces if r['size_stratum']==s)/sum(r['rows'] for r in traces if r['size_stratum']==s)*12 for s in STRATA}
    witnesses=source_stage_witness(prototype)
    stage_beta={s:max(w['conservative_new_stage_bytes_per_record_atoms2'] for w in witnesses if w['size_stratum']==s) for s in STRATA}
    archives=[r for w in prototype['workers'] for r in w['archives'] if r['measurement_kind']=='measurement']
    overhead=max(r['physical_nonframe_bytes_per_retained_call'] for r in archives)
    costs={tid:{'task_id':tid,'records':t['records'],'molecules':t['molecules'],'archive_bytes':0.0,'family_bytes':0.0,'trace_bytes':0.0,'staging_bytes':0.0,'estimated_retained_calls':0.0} for tid,t in tasks.items()}
    lanes=collections.defaultdict(lambda:collections.defaultdict(float))
    components=collections.defaultdict(lambda:collections.defaultdict(float))
    for g in groups:
        tid=g['task_id'];s=g['size_stratum'];n=g['records'];aud=q[(int(tasks[tid]['file_group']),s)];c=costs[tid]
        c['family_bytes']+=n*family_rate[s];c['trace_bytes']+=n*trace_rate[s]
        stage=g['sum_record_atoms2']*stage_beta[s];c['staging_bytes']+=stage;lanes[(tid,g['lane'])]['stage']+=stage
        for calc in A.CALC_TYPES:
            rate=rates[(s,calc)];f=rate['failure_fraction'];kept=f+aud*(1-f)
            main=n*(rate['failed_legacy_plus_AUX_bytes_per_record']+aud*rate['success_legacy_plus_AUX_bytes_per_record'])
            extra=g['sum_record_atoms2']*rate['full_sidefiles_bytes_per_record_atoms2_upper']*kept
            meta=n*kept*rate['retained_metadata_frame_bytes_per_case_upper'];sql=n*kept*overhead
            amount=main+extra+meta+sql;c['archive_bytes']+=amount;c['estimated_retained_calls']+=n*kept;lanes[(tid,g['lane'])]['archive']+=amount
            cmp=components[(s,calc)];cmp['legacy_main_and_AUX']+=main;cmp['all_regular_sidefiles']+=extra;cmp['retained_metadata_frame']+=meta;cmp['retained_SQLite_overhead']+=sql;cmp['estimated_retained_calls']+=n*kept
    costs=list(costs.values())
    for c in costs:c['pending_bytes']=c['family_bytes']+c['trace_bytes'];c['vacuum_bytes']=max((v['archive']+v['stage'] for (tid,lane),v in lanes.items() if tid==c['task_id']),default=0)
    def top(field):
        rows=sorted(costs,key=lambda r:r[field],reverse=True)[:29]
        return {'bytes':sum(r[field] for r in rows),'task_ids':[r['task_id'] for r in rows]}
    stage=top('staging_bytes');pending=top('pending_bytes');consolidation=top('archive_bytes');vacuum=top('vacuum_bytes')
    basic=max(a.base_temporary_bytes,vacuum['bytes']);family=sum(c['family_bytes'] for c in costs);trace=sum(c['trace_bytes'] for c in costs);archive=sum(c['archive_bytes'] for c in costs)
    # Preserve measured canonical-index reserve from old report physical refs.
    canonical=[]
    for src in prototype['source_reports']:
        for phase in read(src['path'])['phases']:
            if not phase.get('archive'):continue
            ex=read(Path(phase['root'])/'export_completion.json');r=ex['canonical'];canonical.append(r['bytes']/(r['rows']//12))
    canonical_rate=max(canonical)
    canonical=canonical_rate*11231854;pending_canonical=sum(sorted((t['records']*canonical_rate for t in tasks_list),reverse=True)[:29])
    manifest=benchmark['dictionary_manifest']['path'];shared=sum(p.stat().st_size for p in Path(manifest).parent.iterdir() if p.is_file())
    package=read(a.reproduction_package) if a.reproduction_package else None
    # Already existing package is charged in fresh quota; no double charge.
    package_bytes=0 if package and package.get('status')=='REPRODUCTION_PACKAGE_CLOSED' else None
    molecule_metadata=prototype['source_all_molecule_metadata_page_witnesses']
    meta_rate=sum(max(r['bytes_per_molecule_upper_witness'] for r in molecule_metadata if r['kind']==kind)
        for kind in ('permanent_queue_metadata','permanent_archive_SCI_completion_metadata'))
    all_molecule_metadata_bytes=meta_rate*1220466
    # Lane SCI receipts are duplicated during consolidation; the raw-row
    # retained-only model never removes all-molecule checkpoint receipts.
    receipt_rate=max(r['bytes_per_molecule_upper_witness'] for r in molecule_metadata
        if r['kind']=='permanent_archive_SCI_completion_metadata')
    top29_molecules=sum(sorted((t['molecules'] for t in tasks_list),reverse=True)[:29])
    simultaneous_molecule_metadata_extra=top29_molecules*receipt_rate
    # Permanent family/canonical totals reserve each unique output file once,
    # whether it currently has .pending or final name. Rename does not copy it.
    # Lane receipt pages coexist with final archive receipts; queue stays in place.
    duplicate_charges={
        'pending_family_and_trace_already_in_permanent_file_union':pending['bytes'],
        'pending_canonical_already_in_permanent_file_union':pending_canonical,
        'whole_queue_copy_not_created':top29_molecules*(meta_rate-receipt_rate)}
    temporary=simultaneous_molecule_metadata_extra+basic+stage['bytes']+consolidation['bytes']+a.remaining_tests_not_in_quota_bytes
    quota=read(a.quota);free=quota.get('quota_parsed',{}).get('remaining_bytes',quota.get('remaining_bytes'))
    if free is None:raise ValueError('Fresh actual user quota unavailable')
    peak=all_molecule_metadata_bytes+archive+family+trace+canonical+shared+400_000_000_000+temporary;head=free-peak
    output={'schema':'WP5_NEW_POLICY_STORAGE_BUDGET_V11','status':'NEW_POLICY_STORAGE_ESTIMATE_CLOSED' if package_bytes is not None else 'NEW_POLICY_STORAGE_ESTIMATE_PENDING_PACKAGE',
        'policy':POLICY,'storage_capacity_pass':head>=200_000_000_000,'policy_selected':POLICY if head>=200_000_000_000 and package_bytes is not None else None,
        'G3_or_G6_production_PASS_not_inferred':True,'old_output_witnesses_not_relabelled_new_G6_PASS':True,
        'formal_records':11231854,'formal_molecules':1220466,'tasks':72,'slots':29,
        'permanent_output_archive_bytes':archive,'permanent_all_molecule_checkpoint_and_SCI_metadata_bytes':all_molecule_metadata_bytes,'permanent_family_float64_bytes':family,'permanent_trace_increment_bytes':trace,
        'permanent_canonical_index_bytes':canonical,'dictionary_shared_bytes':shared,'float32_future_reserve_bytes':400_000_000_000,
        'temporary_bytes':temporary,'writeback_peak_bytes':peak,'fresh_quota_remaining_bytes':free,'headroom_bytes':head,
        'required_headroom_bytes':200_000_000_000,'runtime_stop_remaining_bytes':300_000_000_000,
        'temporary_context':{'basic_reserve_bytes':basic,'requested_basic_reserve_bytes':a.base_temporary_bytes,
          'top29_stage':stage,'top29_pending_family_and_trace':{**pending,'additional_peak_charge_bytes':0,'counting':'INCLUDED_IN_PERMANENT_FILE_UNION'},'top29_consolidation':consolidation,
          'top29_single_lane_VACUUM_inside_basic':vacuum,'top29_SCI_completion_metadata_copy_extra_bytes':simultaneous_molecule_metadata_extra,
          'pending_canonical':{'bytes':pending_canonical,'additional_peak_charge_bytes':0,'counting':'INCLUDED_IN_PERMANENT_FILE_UNION'},
          'remaining_50_double_final200_and_newtests_unaccounted_bytes':a.remaining_tests_not_in_quota_bytes},
        'removed_duplicate_peak_charges':duplicate_charges,'removed_duplicate_peak_charges_total_bytes':sum(duplicate_charges.values()),
        'lifecycle_counting_evidence':lifecycle,'original_counting_source':ref(ROOT/'scripts/wp5_storage_budget_v10.py'),
        'ordinary_success_container_rows':0,'input_body_archive_bytes':0,'minimum_retention_calls':0,
        'sample_failure_scope':native_counts,'historical_G5_raw_gaps_not_scientific_failures':True,
        'source_benchmark':ref(a.benchmark),'source_new_physical_prototype':ref(a.prototype),
        'source_audit_membership':ref(a.audit_manifest),'source_population':ref(a.population),
        'source_tasks_current_actual_nodes':ref(a.tasks),'source_assignments':ref(a.assignments),
        'source_authority':ref(a.node_authority),'fresh_quota':quota,
        'reproduction_package_reference':ref(a.reproduction_package) if package else None,'package_already_charged_in_fresh_quota':package_bytes,
        'actual_metadata_worker_pids':sorted(pids),'physical_nonframe_bytes_per_retained_call_upper':overhead,
        'stage_actual_witnesses':witnesses,'all_molecule_metadata_page_witnesses':molecule_metadata,'per_task':costs,
        'percalc_stratum_components':[{'size_stratum':s,'calc_type':t,**v} for (s,t),v in components.items()],
        'source_rate_models':[{'size_stratum':s,'calc_type':t,**v} for (s,t),v in rates.items()],
        'scope':'One explicitly authorized current policy; failure all + exact file-group/stratum record audit rate on success (no overlap double count). All12 tasks of selectedrecord outputs retained. No cache filtering.',
        'method':'Original full10020 required-scope status weights; eligible pilot byte means+historical AUX calibration+actual full-sidefile upper; new output-only SQLite overhead charged only retained calls. Independent top29 stage/raw/SCI receipt copies retained. Family/canonical pending-final union counted once in permanent totals; queue whole-file copy excluded by actual lifecycle.',
        'scientific_precision_changed':False,'no_training600GB_double_count':True,'QM_started':False,'LMDB_created':False,
        'source_sha256':A.file_sha(__file__)}
    pth=Path(a.output).absolute()
    if not pth.is_relative_to(ROOT) or pth.exists():raise ValueError('New immutable own output required')
    OLD.save(pth,output);print(json.dumps({'status':output['status'],'capacity_pass':output['storage_capacity_pass'],'peak_TB_decimal':peak/1e12,'headroom_GB_decimal':head/1e9,'path':str(pth)}))
if __name__=='__main__':main()
