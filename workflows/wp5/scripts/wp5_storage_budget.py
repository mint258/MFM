"""G3 metadata budget: real full-scope G6 raw, formal packing, conservative top29.

No QM, no LMDB creation, no source mutation. Run only after G3 and all six G6
reports close. Root submits. Current archive/engine/parser/Parquet remain frozen.
"""
from __future__ import annotations
import argparse,ast,concurrent.futures,json,math,multiprocessing,os,socket,sqlite3,sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
DEPS=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2')
sys.path[:0]=[str(DEPS/'deps'),str(DEPS/'scripts/deps')]
import wp5_archive_v2 as A
STRATA=('0_10','11_20','21_30','31_50','51_75','76_100','above_100')
BARRIER=None
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    q=p.with_name(p.name+'.pending');q.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');q.replace(p)
def bins(n):
    return next(s for cutoff,s in ((10,'0_10'),(20,'11_20'),(30,'21_30'),(50,'31_50'),(75,'51_75'),(100,'76_100'),(float('inf'),'above_100')) if n<=cutoff)
def init(barrier):
    global BARRIER;BARRIER=barrier
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    BARRIER.wait(timeout=240)
def packing_part(item):
    import pyarrow.parquet as pq
    rank,path,workers=item;groups=defaultdict(lambda:{'records':0,'molecules':0,'sum_record_atoms2':0,'sum_mol_atoms2':0,'max_records':0})
    seen=records=0
    for batch in pq.ParquetFile(path).iter_batches(batch_size=4096,columns=['task_id','lane','records','total_atoms','size_stratum'],use_threads=False):
        for r in batch.to_pylist():
            if int(r['task_id'])%workers!=rank:continue
            key=(int(r['task_id']),int(r['lane']),r['size_stratum']);g=groups[key];n=int(r['records']);atoms=int(r['total_atoms'])
            g['records']+=n;g['molecules']+=1;g['sum_record_atoms2']+=n*atoms*atoms;g['sum_mol_atoms2']+=atoms*atoms;g['max_records']=max(g['max_records'],n)
            seen+=1;records+=n
    return {'worker_pid':os.getpid(),'records':records,'molecules':seen,'groups':[{'task_id':k[0],'lane':k[1],'size_stratum':k[2],**v} for k,v in groups.items()]}
def g6_calibration(item):
    import pyarrow.parquet as pq
    report_path,manifest=item;report=read(report_path)
    if report['status']!='G6_FULL_CHAIN_PASSED':raise ValueError('Only actual closed G6 full-chain reports are calibration')
    root=Path(report_path).parent
    selected=read(root/'selected_molecules.json')
    # Selection manifests may be a list or carry rows/selected_molecules.
    chosen=selected if isinstance(selected,list) else selected.get('selected_molecules',selected.get('molecules',selected.get('rows',selected.get('selected',[]))))
    row_count={};atoms_by_mol={}
    for row in chosen:
        if not isinstance(row,dict):continue
        mid=row.get('molecule_id')
        if mid:
            if isinstance(row.get('records'),int):row_count[mid]=row['records']
            for key in ('max_total_atoms','total_atoms','molecule_max_total_atoms'):
                if row.get(key) is not None:atoms_by_mol[mid]=int(row[key]);break
    rows=[];stage=[];overheads=[];dicts=A.load_dictionaries(manifest);codec=A.Zstd()
    phases=[];canonical_bytes=0;completed_records=0
    for phase_path in report['phases']:
        phase=read(phase_path);archive=phase['archive']
        canonical=phase.get('canonical_record_attempts')
        if canonical is None:raise ValueError('Actual permanent canonical index reference missing')
        canonical_bytes+=canonical['bytes'];completed_records+=phase['completed_records_this_run']
        if not archive or A.file_sha(archive['path'])!=archive['sha256']:raise ValueError('G6 archive SHA binding differs')
        reader=A.ArchiveReader(archive['path'],manifest);frames=0
        try:
            for rid,task in reader.db.execute('SELECT record_id,calc_type FROM records'):
                raw=reader.get(rid,task);meta=raw['metadata'];mid=raw['molecule_id'];n=atoms_by_mol.get(mid)
                xyz=next((f for f in raw['input_files'] if f['name']=='input.xyz'),None)
                if xyz is not None:
                    actual=int(xyz['data'].splitlines()[0])
                    if n is None:n=actual
                if n is None or n<=0:raise ValueError('G6 atomic count unavailable for actual raw-size calibration')
                heavy=meta.get('size_stratum')
                packed=reader.db.execute('SELECT length(input_frame),length(raw_frame),length(metadata_frame),raw_bytes FROM records WHERE record_id=? AND calc_type=?',(rid,task)).fetchone()
                frames+=packed[0]+(packed[1] or 0)+packed[2]
                output=raw['output_files']
                if output is None:raise ValueError('G6 must use ALL: actual full scientific raw unavailable under selective outputs')
                extra=[f for f in output if f['name'] not in {'input.out','process.out','input.aux'}]
                aux=[f for f in output if f['name']=='input.aux']
                extra_bytes=len(codec.compress(A.bundle(extra)[0],dicts[task]['data'])) if extra else 0
                aux_raw=sum(f['byte_count'] for f in aux)
                aux_compressed=len(codec.compress(A.bundle(aux)[0],dicts[task]['data'])) if aux else 0
                rows.append({'record_id':rid,'molecule_id':mid,'calc_type':task,'size_stratum':heavy,
                    'atoms':n,'scope_status':raw['scope_status'],'is_minimum':bool(meta.get('is_minimum')),
                    'extra_frame_bytes':extra_bytes,'extra_atoms2_ratio':extra_bytes/(n*n),
                    'full_output_frame_bytes':packed[1] or 0,'input_frame_bytes':packed[0],'metadata_frame_bytes':packed[2],
                    'AUX_raw_bytes':aux_raw,'AUX_compressed_bytes':aux_compressed,
                    'extra_member_names':[f['name'] for f in extra],'all_binary_members_kept':True})
            phases.append({'archive_path':archive['path'],'archive_bytes':archive['bytes'],'frame_bytes':frames,
                'physical_to_frame_ratio':archive['bytes']/frames if frames else None})
        finally:reader.close()
    # Queue receipts retain each actual stage size after the temporary wire is retired.
    queue=root/'queue.sqlite'
    db=sqlite3.connect('file:'+quote(str(queue),safe='/')+'?mode=ro',uri=True)
    try:
        for mid,receipt_json,n in db.execute('SELECT molecule_id,receipt_json,record_count FROM molecules WHERE receipt_json IS NOT NULL'):
            receipt=json.loads(receipt_json)
            if receipt.get('stage_compressed_wire_bytes') is None:raise ValueError('Actual G6 per-molecule stage bytes missing in queue receipt')
            stage.append({'molecule_id':mid,'records':int(n),'compressed_wire_bytes':receipt['stage_compressed_wire_bytes'],
                'uncompressed_wire_bytes':receipt['stage_wire_bytes'],'max_atoms':atoms_by_mol.get(mid)})
    finally:db.close();codec.close()
    # Real member Parquet supplies the group label, which old raw metadata may omit.
    groups={r['molecule_id']:r['size_stratum'] for r in pq.read_table(report['raw_compression_by_record'],columns=['molecule_id','size_stratum'],use_threads=False).to_pylist()}
    for r in rows:r['size_stratum']=groups[r['molecule_id']]
    for r in stage:r['size_stratum']=groups[r['molecule_id']]
    return {'worker_pid':os.getpid(),'path':str(report_path),'sha256':A.file_sha(report_path),'node':report['node'],
        'rows':rows,'stage':stage,'physical_archive_ratios':phases,
        'scratch_peaks':report['resource_peaks'],'canonical_index_measured_bytes':canonical_bytes,
        'canonical_index_measured_records':completed_records,'binary_restart_files_are_counted_not_subtracted':True}
def upper_rates(benchmark,calibration):
    metrics=[r for w in benchmark['workers'] for r in w['metrics']]
    samples=benchmark['sample_strata'];ratios=[r for w in benchmark['workers'] for r in w['aux_ratios']]
    measured=[r for c in calibration for r in c['rows']];rates={};unknown=[];archive_factors={}
    for policy in ('ALL','SELECTIVE'):
        all_rows=[r for r in metrics if r['policy']==policy]
        all_frames=sum(r['input_frame_bytes']+r['raw_frame_bytes']+r['metadata_frame_bytes'] for r in all_rows)
        overhead=(sum(w['archives'][policy]['bytes'] for w in benchmark['workers'])-all_frames)/len(all_rows)
        archive_factors[policy]=overhead
        for key in STRATA:
            ns=samples[key]['records'];nm=samples[key]['molecules']
            eligible=[r for r in all_rows if not r['formal_excluded_calibration_only'] and r['size_stratum']==key]
            by_task={}
            for task in A.CALC_TYPES:
                rows=[r for r in eligible if r['calc_type']==task];actual=[r for r in measured if r['calc_type']==task and r['size_stratum']==key]
                if len(rows)!=ns or not actual:raise ValueError('Formal-eligible sample or actual G6 task/stratum calibration missing: '+key+'/'+task)
                aux_examples=[r for r in ratios if r['calc_type']==task and r['size_stratum']==key]
                ratio=max((r['ratio'] for r in aux_examples),default=None)
                direct_aux=[r for r in actual if r['AUX_raw_bytes']>0]
                if direct_aux:ratio=max([r['AUX_compressed_bytes']/r['AUX_raw_bytes'] for r in direct_aux]+([ratio] if ratio is not None else []))
                if ratio is None:ratio=max((r['ratio'] for r in ratios if r['calc_type']==task),default=None)
                base_rec=sum(r['input_frame_bytes']+r['metadata_frame_bytes']+overhead for r in rows)/ns
                out_rec=out_mol=aux_rec=aux_mol=0
                for r in rows:
                    if not r['output_retained']:continue
                    minimum=policy=='SELECTIVE' and r['retention_reason']=='SUCCESS_MOLECULAR_MINIMUM'
                    denom=nm if minimum else ns
                    if minimum:out_mol+=r['raw_frame_bytes']/denom
                    else:out_rec+=r['raw_frame_bytes']/denom
                    missing=r['missing_aux_raw_bytes']
                    if missing is None:
                        if task.startswith('xtb_'):missing=0 # AUX is MOPAC-specific; full xTB raw extras measured independently
                        elif direct_aux:missing=max(r['AUX_raw_bytes'] for r in direct_aux)
                        else:unknown.append({'size_stratum':key,'calc_type':task,'reason':'No actual AUX size for legacy unknown'});continue
                    if missing:
                        if ratio is None:unknown.append({'size_stratum':key,'calc_type':task,'reason':'No real AUX dictionary compression witness'});continue
                        amount=(missing*ratio+1024)/denom
                        if minimum:aux_mol+=amount
                        else:aux_rec+=amount
                # All extra regular files, including binary restart, are compressed
                # separately. Adding frames is a conservative model of joint compression.
                extra_beta=max(r['extra_atoms2_ratio'] for r in actual)
                old_case={(r['record_id'],r['calc_type']):r for r in rows}
                metadata_delta=max([0]+[r['metadata_frame_bytes']-old_case[(r['record_id'],task)]['metadata_frame_bytes']
                    for r in actual if (r['record_id'],task) in old_case])
                if policy=='ALL':extra_rec_beta=extra_beta;extra_mol_beta=0
                else:
                    nonmin=[r for r in rows if not r['is_minimum']]
                    failure_fraction=sum(r['scope_status']!='SUCCESS' for r in rows)/ns
                    # Use the larger of observed seeded audit and exact1% expectation.
                    audits=sum(r['retention_reason']=='SEEDED_1_PERCENT_SUCCESS_AUDIT' for r in rows)/ns
                    expected_audits=0.01*sum(r['scope_status']=='SUCCESS' for r in nonmin)/ns
                    extra_rec_beta=extra_beta*(failure_fraction+max(audits,expected_audits))
                    minimum_success=sum(r['scope_status']=='SUCCESS' and r['is_minimum'] for r in rows)/nm
                    extra_mol_beta=extra_beta*minimum_success
                by_task[task]={'base_record_bytes':base_rec+metadata_delta,'legacy_output_record_bytes':out_rec+aux_rec,
                    'legacy_output_molecule_bytes':out_mol+aux_mol,'extra_record_atoms2_coefficient':extra_rec_beta,
                    'extra_molecule_atoms2_coefficient':extra_mol_beta,'G6_extra_max_compressed_bytes_per_atom_squared':extra_beta,
                    'G6_witness_records':len({r['record_id'] for r in actual}),'G6_metadata_delta_per_record_upper':metadata_delta,
                    'AUX_upper_compression_ratio':ratio,'AUX_unknown_sizes_use_actual_G6_max_upper_not_zero':True}
            rates[(policy,key)]=by_task
    return rates,unknown,archive_factors

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');p.add_argument('--workers',type=int,default=16)
    p.add_argument('--benchmark');p.add_argument('--g6-reports',nargs='*');p.add_argument('--quota')
    p.add_argument('--assignments',default=str(ROOT/'packing/molecule_assignments.parquet'))
    p.add_argument('--tasks',default=str(ROOT/'packing/tasks.json'));p.add_argument('--population',default=str(ROOT/'population/manifest.json'))
    p.add_argument('--base-temporary-bytes',type=int,default=100_000_000_000)
    p.add_argument('--remaining-tests-not-in-quota-bytes',type=int);p.add_argument('--output')
    a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('AST_PASS_METADATA_ONLY_NO_QM_LMDB');return
    if not a.benchmark or not a.output: p.error('--benchmark and --output required')
    if a.workers<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers:raise ValueError('16 allocated effective metadata workers required')
    if socket.gethostname().split('.')[0] not in {f'compute-0-{n}' for n in range(14,20)}:raise ValueError('WP5 node14..19 only')
    benchmark=read(a.benchmark)
    if benchmark['status']!='G3_ALL_PILOT12_ARCHIVE_AND_FAMILY_BENCHMARK_CLOSED':raise ValueError('Closed full G3 benchmark required')
    if len(a.g6_reports or [])!=6:raise ValueError('Actual six G6 terminal reports required, failed startup is not0byte sample')
    population=read(a.population);tasks=read(a.tasks)['tasks'];job=os.environ['SLURM_JOB_ID']
    out=Path(a.output).absolute()
    if not out.is_relative_to(ROOT):raise ValueError('Only new own WP5 output')
    if out.exists():raise FileExistsError(out)
    manifest=benchmark['dictionary_manifest']['path'];ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=init,initargs=(barrier,)) as pool:
        packing=list(pool.map(packing_part,[(i,a.assignments,a.workers) for i in range(a.workers)],chunksize=1))
        calibration=list(pool.map(g6_calibration,[(r,manifest) for r in a.g6_reports],chunksize=1))
    pids={r['worker_pid'] for r in packing}
    if len(pids)<16:raise ValueError('Effective16 packing readers not observed')
    if (sum(r['records'] for r in packing),sum(r['molecules'] for r in packing),len(tasks))!=(11231854,1220466,72):
        raise ValueError('MANIFEST_FORMAL_PACKING_COUNT_MISMATCH')
    if {c['node'] for c in calibration}!={f'compute-0-{n}' for n in range(14,20)}:raise ValueError('Six original physical G6 nodes required')
    rates,unknown,overhead=upper_rates(benchmark,calibration);groups=[g for r in packing for g in r['groups']]
    if unknown:
        save(out,{'status':'G3_PENDING_REAL_AUX_STORAGE_CALIBRATION','unknown':unknown,'scientific_missing_is_not_zero':True});return
    # G3 measures permanent family bytes without reserializing scientific values.
    family_files=[r for w in benchmark['workers'] for r in w['family_files']]
    family_rates={s:sum(r['strata'].get(s,{}).get('bytes',0) for r in family_files)/benchmark['sample_strata'][s]['records'] for s in STRATA}
    eligible_molecules={r['molecule_id'] for w in benchmark['workers'] for r in w['metrics'] if not r['formal_excluded_calibration_only']}
    stage_by_mol={r['molecule_id']:r for w in benchmark['workers'] for r in w['staged'] if r.get('policy')=='ALL' and r.get('molecule_id') in eligible_molecules}
    stage_rates={s:sum(r['compressed_wire_bytes'] for r in stage_by_mol.values() if r['size_stratum']==s)/benchmark['sample_strata'][s]['records'] for s in STRATA}
    ratio_witness=defaultdict(list)
    for c in calibration:
        for r in c['stage']:
            old=stage_by_mol.get(r['molecule_id']);s=r['size_stratum']
            if old and old['record_count']==r['records']:
                ratio=r['compressed_wire_bytes']/old['compressed_wire_bytes'];kind='SAME_WHOLE_MOLECULE_SOURCE'
            else:
                ratio=r['compressed_wire_bytes']/(stage_rates[s]*r['records']);kind='WITHIN_STRATUM_RECORD_RATE_PROXY'
            ratio_witness[s].append({'molecule_id':r['molecule_id'],'ratio':ratio,'kind':kind,'records':r['records']})
    stage_factors={s:max([1.0]+[v['ratio'] for v in ratio_witness[s]]) for s in STRATA}
    # Never reduce temporary capacity by an unproven format savings: take at least1.
    costs={};lane_costs=defaultdict(lambda:defaultdict(float))
    for task in tasks:
        costs[int(task['task_id'])]={'task_id':int(task['task_id']),'record_count':task['records'],'molecule_count':task['molecules'],
            'pending_family_bytes':0,'staging_bytes':0,'archive_ALL_bytes':0,'archive_SELECTIVE_bytes':0}
    for g in groups:
        tid=g['task_id'];s=g['size_stratum'];n=g['records'];m=g['molecules'];cost=costs[tid]
        stage=n*stage_rates[s]*stage_factors[s];family=n*family_rates[s]
        cost['staging_bytes']+=stage;cost['pending_family_bytes']+=family
        for policy in ('ALL','SELECTIVE'):
            amount=0
            for r in rates[(policy,s)].values():
                amount+=n*(r['base_record_bytes']+r['legacy_output_record_bytes'])+m*r['legacy_output_molecule_bytes']
                amount+=g['sum_record_atoms2']*r['extra_record_atoms2_coefficient']+g['sum_mol_atoms2']*r['extra_molecule_atoms2_coefficient']
            cost['archive_'+policy+'_bytes']+=amount
            lane_costs[(tid,g['lane'])]['archive_'+policy]+=amount;lane_costs[(tid,g['lane'])]['stage']+=stage
    costs=list(costs.values());total_family=sum(v['pending_family_bytes'] for v in costs)
    canonical_rate=max(c['canonical_index_measured_bytes']/c['canonical_index_measured_records'] for c in calibration)
    canonical_bytes=canonical_rate*11231854
    def top29(field):
        rows=sorted(costs,key=lambda v:v[field],reverse=True)[:29]
        return {'bytes':sum(v[field] for v in rows),'tasks':[v['task_id'] for v in rows]}
    staging=top29('staging_bytes');pending=top29('pending_family_bytes')
    for policy in ('ALL','SELECTIVE'):
        for task in costs:
            task['vacuum_'+policy+'_bytes']=max((v['archive_'+policy]+v['stage'] for (tid,lane),v in lane_costs.items() if tid==task['task_id']),default=0)
    quota=read(a.quota) if a.quota else None;free=(quota or {}).get('quota_parsed',{}).get('remaining_bytes')
    if free is None:free=(quota or {}).get('remaining_bytes')
    plans=[];temporary_contexts={}
    shared=Path(manifest).parent;shared_bytes=sum(p.stat().st_size for p in shared.iterdir() if p.is_file())
    remaining=a.remaining_tests_not_in_quota_bytes
    for policy in ('ALL','SELECTIVE'):
        final_archive=sum(v['archive_'+policy+'_bytes'] for v in costs)
        consolidation=top29('archive_'+policy+'_bytes');vacuum=top29('vacuum_'+policy+'_bytes')
        # The basic100GB reserve already covers the one-lane-at-a-time VACUUM
        # extra and ordinary scratch. Raise it only if the measured/modelled
        # top29 largest single-lane copies exceed that reserve; do not count it twice.
        basic_reserve=max(a.base_temporary_bytes,vacuum['bytes'])
        temporary_canonical=sum(sorted([v['record_count']*canonical_rate for v in costs],reverse=True)[:29])
        temp=basic_reserve+staging['bytes']+pending['bytes']+temporary_canonical+consolidation['bytes']+(remaining or 0)
        peak=final_archive+total_family+canonical_bytes+shared_bytes+400_000_000_000+temp
        plans.append({'policy':policy,'final_archive_bytes':final_archive,'permanent_family_float64_bytes':total_family,
            'permanent_canonical_index_bytes':canonical_bytes,
            'future_float32_export_reserve_bytes':400_000_000_000,'dictionary_shared_bytes':shared_bytes,
            'temporary_bytes':temp,'writeback_peak_bytes':peak,'headroom_bytes':free-peak if free is not None else None,
            'headroom_GB_decimal':(free-peak)/1e9 if free is not None else None,
            'no_consolidation_alternative_peak_bytes':peak-consolidation['bytes'],
            'no_consolidation_alternative_headroom_bytes':free-peak+consolidation['bytes'] if free is not None else None})
        temporary_contexts[policy]={'base_temporary_reserve_bytes':basic_reserve,'requested_basic_reserve_bytes':a.base_temporary_bytes,'simultaneous_staging_bytes':staging['bytes'],
            'pending_parquet_duplicate_bytes':pending['bytes']+temporary_canonical,'pending_canonical_index_bytes':temporary_canonical,'simultaneous_consolidation_extra_bytes':consolidation['bytes'],
            'largest_lane_VACUUM_bytes_top29':vacuum['bytes'],'VACUUM_is_inside_basic_reserve_not_added_twice':True,
            'remaining_tests_not_in_quota_bytes':remaining,'top29_staging':staging,'top29_pending':pending,
            'top29_consolidation':consolidation,'top29_vacuum':vacuum}
    selected=None;complete=free is not None and remaining is not None
    if complete:
        for policy in ('ALL','SELECTIVE'):
            plan=next(p for p in plans if p['policy']==policy)
            if plan['headroom_bytes']>=200_000_000_000:selected=policy;break
    union={r['molecule_id'] for c in calibration for r in c['stage']}
    source_rates=[{'policy':policy,'size_stratum':s,'tasks':tasks} for (policy,s),tasks in rates.items()]
    report={'status':('G3_FINAL_STORAGE_PASS' if selected else 'G3_STOP_BOTH_BELOW200GB') if complete else 'G3_PENDING_FRESH_QUOTA_AND_REMAINING_TEST_BYTES',
        'policy_selected':selected,'formal_records':11231854,'formal_molecules':1220466,'main_tasks':72,'concurrent_slots':29,
        'actual_metadata_worker_pids':sorted(pids),'source_benchmark':{'path':a.benchmark,'sha256':A.file_sha(a.benchmark)},
        'G6_sources':[{'path':c['path'],'sha256':c['sha256'],'node':c['node']} for c in calibration],
        'G6_distinct_whole_molecules':len(union),'G6_node_observations':sum(len(c['stage']) for c in calibration),
        'G6_duplicate_molecules_are_not_independent_samples':True,'source_dictionary_manifest':manifest,
        'formal_eligible_pilot_sample':benchmark['formal_context_closure'],'quota':quota,'plans':plans,
        'temporary_contexts':temporary_contexts,'per_task':costs,'measured_SQLite_overhead_per_call':overhead,
        'extra_raw_and_input_metadata_rates':source_rates,'stage_ratio_witness':dict(ratio_witness),'stage_factors_used':stage_factors,
        'method':'Conservative independent top29 sums for staging, pending family, new-old raw consolidation, singlelane/jobVACUUM inside the basic temporary reserve. Sidefiles from actualG6 ALL include binaryrestart; separate frame additions are conservative, not joint-compressed measurements.',
        'sidefile_size_model':'Maximum actual percalc/stratum dict-compressed extra bytes/atoms^2, applied to exact formal assignment record-weighted and molecule-weighted atoms^2; no smaller format savings assumed.',
        'original_input_gap':'Old pilot input files are reconstructed and have no historical original-input SHA. G6 actual inputs include original files and versions/keywords from actual frozen capture.',
        'no_training600GB_double_count':True,'no_scientific_reserialization':True,'QM_started':False,'LMDB_created':False,
        'source_files_written_or_deleted':False,'source_sha256':A.file_sha(__file__)}
    save(out,report);print(json.dumps({'status':report['status'],'policy_selected':selected,'path':str(out)}))
if __name__=='__main__':main()
