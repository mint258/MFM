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
import wp5_archive_v4 as A
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
    rank,path,workers,unknown_molecules=item;groups=defaultdict(lambda:{'records':0,'molecules':0,'sum_record_atoms2':0,'sum_mol_atoms2':0,'max_records':0,
        'unknown_energy_records':0,'unknown_energy_molecules':0,'unknown_record_atoms2':0,'unknown_mol_atoms2':0})
    seen=records=0
    for batch in pq.ParquetFile(path).iter_batches(batch_size=4096,columns=['task_id','lane','records','total_atoms','size_stratum','molecule_id'],use_threads=False):
        for r in batch.to_pylist():
            if int(r['task_id'])%workers!=rank:continue
            key=(int(r['task_id']),int(r['lane']),r['size_stratum']);g=groups[key];n=int(r['records']);atoms=int(r['total_atoms'])
            g['records']+=n;g['molecules']+=1;g['sum_record_atoms2']+=n*atoms*atoms;g['sum_mol_atoms2']+=atoms*atoms;g['max_records']=max(g['max_records'],n)
            if r['molecule_id'] in unknown_molecules:
                g['unknown_energy_records']+=n;g['unknown_energy_molecules']+=1
                g['unknown_record_atoms2']+=n*atoms*atoms;g['unknown_mol_atoms2']+=atoms*atoms
            seen+=1;records+=n
    return {'worker_pid':os.getpid(),'records':records,'molecules':seen,'groups':[{'task_id':k[0],'lane':k[1],'size_stratum':k[2],**v} for k,v in groups.items()]}
def g6_calibration(item):
    import pyarrow.parquet as pq
    report_path,manifest=item;report=read(report_path)
    if report['status'] not in {'G6_FULL_CHAIN_PASSED','G6_FULL_CHAIN_PASSED_WITH_RECORDED_SCIENTIFIC_OUTCOMES'} or report.get('issues'):
        raise ValueError('Only actual closed G6 full-chain reports are calibration')
    root=Path(report_path).parent;cohort=Path(report.get('source_run') or root)
    selection_path=cohort/'selected_molecules.json';selected=read(selection_path)
    chosen=selected if isinstance(selected,list) else selected.get('selected_molecules',selected.get('molecules',selected.get('rows',[])))
    atoms_by_mol={r['molecule_id']:int(r.get('max_total_atoms',r.get('total_atoms'))) for r in chosen}
    chosen_count={r['molecule_id']:int(r['records']) for r in chosen}
    if len(chosen_count)!=20:raise ValueError('MANIFEST_G6_SELECTION_NOT_TWENTY_WHOLE_MOLECULES')
    queue=Path(report.get('queue') or cohort/'queue.sqlite')
    db=sqlite3.connect('file:'+quote(str(queue),safe='/')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:latest=[dict(r) for r in db.execute('SELECT * FROM molecules')]
    finally:db.close()
    if len(latest)!=20 or {r['molecule_id'] for r in latest}!=set(chosen_count) or any(r['state']!='COMPLETE' or not r['receipt_json'] for r in latest):
        raise ValueError('MANIFEST_G6_LATEST_TWENTY_COMPLETED_MOLECULES_NOT_CLOSED')
    latest_by_mol={r['molecule_id']:r for r in latest};stage=[]
    for row in latest:
        receipt=json.loads(row['receipt_json']);mid=row['molecule_id'];n=int(row['record_count'])
        if n!=chosen_count[mid]:raise ValueError('MANIFEST_G6_RECEIPT_SOURCE_RECORD_COUNT_MISMATCH')
        if receipt.get('stage_compressed_wire_bytes') is None or receipt.get('stage_wire_bytes') is None:
            raise ValueError('Actual G6 durable per-molecule stage bytes missing')
        stage.append({'molecule_id':mid,'records':n,'compressed_wire_bytes':receipt['stage_compressed_wire_bytes'],
            'uncompressed_wire_bytes':receipt['stage_wire_bytes'],'max_atoms':atoms_by_mol[mid],
            'producer_context':receipt.get('context'),'attempt_id':row['attempt'],
            'format':'ACTUAL_CONTEXT_RESULT_POPULATION_ROWS_FROM_DURABLE_QUEUE'})
    frame_path=Path(report['raw_compression_by_record'])
    frame_ref={'path':str(frame_path),'bytes':frame_path.stat().st_size,'sha256':A.file_sha(frame_path)}
    measured=pq.read_table(frame_path,columns=['record_id','molecule_id','calc_type','size_stratum','attempt_id','input_frame_bytes','raw_frame_bytes','metadata_frame_bytes'],use_threads=False).to_pylist()
    observed={(r['record_id'],r['calc_type']):r for r in measured}
    if len(observed)!=12*sum(chosen_count.values()) or len(measured)!=len(observed):raise ValueError('MANIFEST_G6_LATEST_RAW_MEASUREMENT_ROWS_NOT_CLOSED')
    strata_by_mol={r['molecule_id']:r['size_stratum'] for r in measured}
    rows=[];phases=[];historical=[];canonical_bytes=canonical_records=0;native_minimum_ids=defaultdict(set)
    dicts=A.load_dictionaries(manifest);codec=A.Zstd();archive_paths=set();seen=set()
    try:
        for entry in report['phases']:
            if isinstance(entry,str):
                completion_path=Path(entry);phase_root=completion_path.parent;completion=read(completion_path);archive=completion['archive']
            else:
                phase_root=Path(entry['root']);completion_path=Path(entry['completion_path']);completion=read(completion_path);archive=entry.get('archive')
            # Repaired phase0 keeps FAILED historical completion untouched. Its
            # successful export_completion supplies actual immutable count/refs.
            export_path=phase_root/'export_completion.json'
            exported=read(export_path) if export_path.is_file() else None
            if archive is None:
                if exported and exported.get('molecules',0):raise ValueError('Completed G6 export has no archive reference')
                phases.append({'root':str(phase_root),'actual_admissions':0,'no_scientific_sample_produced':True});continue
            if archive['path'] in archive_paths:raise ValueError('Duplicate immutable G6 phase archive reference')
            archive_paths.add(archive['path'])
            if Path(archive['path']).stat().st_size!=archive['bytes'] or A.file_sha(archive['path'])!=archive['sha256']:raise ValueError('G6 archive SHA/bytes binding differs')
            canonical=(exported or {}).get('canonical') or completion.get('canonical_record_attempts')
            if canonical is None:raise ValueError('Actual permanent canonical index reference missing')
            if Path(canonical['path']).stat().st_size!=canonical['bytes'] or A.file_sha(canonical['path'])!=canonical['sha256']:raise ValueError('Actual canonical index SHA/bytes differs')
            if canonical['rows']%12:raise ValueError('Canonical physical row count is not record*12')
            canonical_bytes+=canonical['bytes'];canonical_records+=canonical['rows']//12
            reader=A.ArchiveReader(archive['path'],manifest);frames=0;latest_frames=0;phase_historical=[]
            try:
                for stored in reader.db.execute('SELECT record_id,calc_type,molecule_id,length(input_frame) AS input_frame_bytes,length(raw_frame) AS raw_frame_bytes,length(metadata_frame) AS metadata_frame_bytes,length(CAST(output_manifest AS BLOB)) AS manifest_bytes FROM records'):
                    rid,task,mid=stored['record_id'],stored['calc_type'],stored['molecule_id']
                    amount=stored['input_frame_bytes']+(stored['raw_frame_bytes'] or 0)+stored['metadata_frame_bytes']
                    frames+=amount
                    if mid not in latest_by_mol:raise ValueError('G6 archive contains a molecule outside its fixed20 cohort')
                    if str(Path(latest_by_mol[mid]['archive_path']).absolute())!=str(Path(archive['path']).absolute()):
                        # Previous failed/signal attempts are retained separately.
                        # They are not duplicate observations of the latest sample.
                        value={'record_id':rid,'molecule_id':mid,'calc_type':task,'size_stratum':strata_by_mol[mid],
                            'archive_path':archive['path'],'frames_bytes':amount,'manifest_bytes':stored['manifest_bytes'],
                            'attempt_is_historical':True}
                        historical.append(value);phase_historical.append(value);continue
                    key=(rid,task)
                    if key in seen or key not in observed:raise ValueError('Latest G6 raw key absent or repeated')
                    seen.add(key);witness=observed[key];latest_frames+=amount
                    if witness['attempt_id']!=latest_by_mol[mid]['attempt']:raise ValueError('Latest G6 attempt differs from measured raw Parquet')
                    if (stored['input_frame_bytes'],stored['raw_frame_bytes'],stored['metadata_frame_bytes'])!=(witness['input_frame_bytes'],witness['raw_frame_bytes'],witness['metadata_frame_bytes']):
                        raise ValueError('Measured latest G6 frame bytes differ from immutable archive')
                    raw=reader.get(rid,task);meta=raw['metadata'];n=atoms_by_mol[mid]
                    xyz=next((f for f in raw['input_files'] if f['name']=='input.xyz'),None)
                    if xyz is not None and int(xyz['data'].splitlines()[0])!=n:raise ValueError('Actual G6 input atom count differs from selected source')
                    output=raw['output_files']
                    if output is None:raise ValueError('G6 ALL actual full raw unavailable; empty successful directory is not inferred')
                    if meta.get('is_minimum'):native_minimum_ids[mid].add(rid)
                    extra=[f for f in output if f['name'] not in {'input.out','process.out','input.aux'}];aux=[f for f in output if f['name']=='input.aux']
                    extra_bytes=len(codec.compress(A.bundle(extra)[0],dicts[task]['data'])) if extra else 0
                    aux_raw=sum(f['byte_count'] for f in aux);aux_compressed=len(codec.compress(A.bundle(aux)[0],dicts[task]['data'])) if aux else 0
                    rows.append({'record_id':rid,'molecule_id':mid,'calc_type':task,'size_stratum':witness['size_stratum'],
                        'attempt_id':latest_by_mol[mid]['attempt'],'atoms':n,'scope_status':raw['scope_status'],'is_minimum':bool(meta.get('is_minimum')),
                        'extra_frame_bytes':extra_bytes,'extra_atoms2_ratio':extra_bytes/(n*n),'uncompressed_output_manifest_bytes':stored['manifest_bytes'],
                        'full_output_frame_bytes':stored['raw_frame_bytes'] or 0,'input_frame_bytes':stored['input_frame_bytes'],'metadata_frame_bytes':stored['metadata_frame_bytes'],
                        'AUX_raw_bytes':aux_raw,'AUX_compressed_bytes':aux_compressed,'extra_member_names':[f['name'] for f in extra],'all_binary_members_kept':True})
                phases.append({'archive_path':archive['path'],'archive_bytes':archive['bytes'],'frame_bytes':frames,'latest_frame_bytes':latest_frames,
                    'historical_attempt_raw_rows':len(phase_historical),'historical_attempt_frame_bytes':sum(r['frames_bytes'] for r in phase_historical),
                    'physical_to_frame_ratio':archive['bytes']/frames if frames else None,
                    'completion_path':str(completion_path),'canonical_reference':canonical,
                    'repaired_phase_keeps_original_failed_completion':bool(isinstance(entry,dict) and entry.get('repaired_without_QM'))})
            finally:reader.close()
    finally:codec.close()
    if seen!=set(observed) or len(rows)!=12*sum(chosen_count.values()):raise ValueError('MANIFEST_LATEST_TWENTY_RAW_COUNT_MISMATCH')
    for r in stage:
        r['size_stratum']=strata_by_mol[r['molecule_id']]
        if r['max_atoms']<=0 or r['records']<=0 or r['compressed_wire_bytes']<=0:raise ValueError('Actual current-format wholeMol staging size/atoms/count unavailable')
        r['compressed_bytes_per_record_atoms2']=r['compressed_wire_bytes']/(r['records']*r['max_atoms']**2)
    if any(len(ids)>1 for ids in native_minimum_ids.values()):raise ValueError('G6 metadata flags conflict within a molecule')
    missing_flags=sorted(set(chosen_count)-set(native_minimum_ids))
    return {'worker_pid':os.getpid(),'path':str(report_path),'sha256':A.file_sha(report_path),'node':report['node'],
        'rows':rows,'stage':stage,'physical_archive_ratios':phases,'historical_attempts_measured_raw_rows':historical,
        'selection_reference':{'path':str(selection_path),'sha256':A.file_sha(selection_path)},'raw_compression_reference':frame_ref,
        'queue_reference':{'path':str(queue),'sha256':A.file_sha(queue)},
        'scratch_peaks':report['resource_peaks'],'minimum_flags_missing_in_preserved_legacy_ALL_metadata':missing_flags,
        'minimum_flag_context':'ALL G6 byte calibration does not depend on old minimum flags; formal SELECTIVE uses measured audit4513909 and corrected runner4 flags.',
        'canonical_index_measured_bytes':canonical_bytes,'canonical_index_measured_records':canonical_records,
        'binary_restart_files_are_counted_not_subtracted':True}
def original_manifest_sizes(benchmark):
    sizes={}
    for w in benchmark['workers']:
        path=w['archives']['ALL']['path'];db=sqlite3.connect('file:'+quote(str(path),safe='/')+'?mode=ro',uri=True)
        try:
            for rid,task,length in db.execute('SELECT record_id,calc_type,length(CAST(output_manifest AS BLOB)) FROM records'):
                if (rid,task) in sizes:raise ValueError('Duplicate G3 manifest record/task')
                sizes[(rid,task)]=int(length)
        finally:db.close()
    if len(sizes)!=120240:raise ValueError('MANIFEST_G3_OUTPUT_MEMBER_COUNT_NOT_CLOSED')
    return sizes
def upper_rates(benchmark,calibration,manifest_sizes):
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
                # output_manifest is a separate uncompressed SQL TEXT column.
                # Its new full-scope member growth must be counted even for omitted raw.
                old_manifest_mean=sum(manifest_sizes[(r['record_id'],task)] for r in rows)/len(rows)
                manifest_deltas=[]
                for r in actual:
                    baseline=manifest_sizes.get((r['record_id'],task),old_manifest_mean)
                    manifest_deltas.append(r['uncompressed_output_manifest_bytes']-baseline)
                manifest_delta=max([0]+manifest_deltas)
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
                by_task[task]={'base_record_bytes':base_rec+metadata_delta+manifest_delta,'legacy_output_record_bytes':out_rec+aux_rec,
                    'legacy_output_molecule_bytes':out_mol+aux_mol,'extra_record_atoms2_coefficient':extra_rec_beta,
                    'extra_molecule_atoms2_coefficient':extra_mol_beta,'G6_extra_max_compressed_bytes_per_atom_squared':extra_beta,
                    'G6_witness_records':len({r['record_id'] for r in actual}),'G6_metadata_delta_per_record_upper':metadata_delta,
                    'G6_uncompressed_manifest_SQL_delta_per_record_upper':manifest_delta,
                    'AUX_upper_compression_ratio':ratio,'AUX_unknown_sizes_use_actual_G6_max_upper_not_zero':True}
            rates[(policy,key)]=by_task
    return rates,unknown,archive_factors

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');p.add_argument('--workers',type=int,default=16)
    p.add_argument('--benchmark');p.add_argument('--g6-reports',nargs='*');p.add_argument('--quota')
    p.add_argument('--minimum-manifest',default=str(ROOT/'gates/g3/minimum_audit_4513909/manifest.json'))
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
    if population.get('status')!='WP5_FORMAL_POPULATION_CLOSED' or (population['formal_records'],population['formal_molecules'])!=(11231854,1220466):raise ValueError('MANIFEST_FORMAL_POPULATION_NOT_CLOSED')
    out=Path(a.output).absolute()
    if not out.is_relative_to(ROOT):raise ValueError('Only new own WP5 output')
    if out.exists():raise FileExistsError(out)
    minimum=read(a.minimum_manifest)
    if minimum['status']!='FORMAL_MINIMUM_AUDIT_CLOSED' or (minimum['formal_records'],minimum['formal_molecules'])!=(11231854,1220466):raise ValueError('MANIFEST_FORMAL_MINIMUM_AUDIT_NOT_CLOSED')
    min_ref=minimum['minima']
    if Path(min_ref['path']).stat().st_size!=min_ref['bytes'] or A.file_sha(min_ref['path'])!=min_ref['sha256']:raise ValueError('Actual minimum audit SHA/bytes changed')
    unknown_molecules=set()
    if minimum['unknown_energy_molecules']:
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(min_ref['path']).iter_batches(batch_size=4096,columns=['molecule_id','minimum_unknown_reason'],use_threads=False):
            unknown_molecules.update(r['molecule_id'] for r in batch.to_pylist() if r['minimum_unknown_reason'] is not None)
        if len(unknown_molecules)!=minimum['unknown_energy_molecules']:raise ValueError('MANIFEST_MINIMUM_UNKNOWN_MOLECULES_MISMATCH')
    manifest=benchmark['dictionary_manifest']['path'];ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=init,initargs=(barrier,)) as pool:
        packing=list(pool.map(packing_part,[(i,a.assignments,a.workers,unknown_molecules) for i in range(a.workers)],chunksize=1))
        calibration=list(pool.map(g6_calibration,[(r,manifest) for r in a.g6_reports],chunksize=1))
    pids={r['worker_pid'] for r in packing}
    if len(pids)<16:raise ValueError('Effective16 packing readers not observed')
    if (sum(r['records'] for r in packing),sum(r['molecules'] for r in packing),len(tasks))!=(11231854,1220466,72):
        raise ValueError('MANIFEST_FORMAL_PACKING_COUNT_MISMATCH')
    for task in tasks:
        task_groups=[g for r in packing for g in r['groups'] if g['task_id']==int(task['task_id'])]
        if (sum(g['records'] for g in task_groups),sum(g['molecules'] for g in task_groups))!=(task['records'],task['molecules']):raise ValueError('MANIFEST_PER_TASK_PACKING_COUNTS_MISMATCH')
    if {c['node'] for c in calibration}!={f'compute-0-{n}' for n in range(14,20)}:raise ValueError('Six original physical G6 nodes required')
    minimum_strata={r['size_stratum']:r for r in minimum['strata']}
    for key in STRATA:
        local=[g for r in packing for g in r['groups'] if g['size_stratum']==key]
        expected=minimum_strata[key]
        if (sum(g['records'] for g in local),sum(g['molecules'] for g in local),sum(g['unknown_energy_records'] for g in local),sum(g['unknown_energy_molecules'] for g in local))!=(expected['records'],expected['molecules'],expected['records_in_unknown_energy_molecules'],expected['unknown_energy_molecules']):
            raise ValueError('MANIFEST_PACKING_MINIMUM_COUNTS_MISMATCH_'+key)
    rates,unknown,overhead=upper_rates(benchmark,calibration,original_manifest_sizes(benchmark));groups=[g for r in packing for g in r['groups']]
    if unknown:
        save(out,{'status':'G3_PENDING_REAL_AUX_STORAGE_CALIBRATION','unknown':unknown,'scientific_missing_is_not_zero':True});return
    # G3 measures permanent family bytes without reserializing scientific values.
    family_files=[r for w in benchmark['workers'] for r in w['family_files']]
    family_rates={s:sum(r['strata'].get(s,{}).get('bytes',0) for r in family_files)/benchmark['sample_strata'][s]['records'] for s in STRATA}
    # Old G3 wire was retired/VACUUMed; its sizes remain NULL. The G6 current
    # formal layout is the actual witness, not a reconstructed legacy stage.
    stage_witness=defaultdict(list)
    for c in calibration:
        for r in c['stage']:
            stage_witness[r['size_stratum']].append({**r,'node':c['node'],'source_report':c['path']})
    stage_beta={}
    for key in STRATA:
        values=stage_witness[key]
        if not values:raise ValueError('Actual G6 staging stratum witness missing: '+key)
        stage_beta[key]=max(v['compressed_bytes_per_record_atoms2'] for v in values)
    # Exact formal n_records*N_atoms^2, conservative per-layer measured maximum.
    costs={};lane_costs=defaultdict(lambda:defaultdict(float))
    for task in tasks:
        costs[int(task['task_id'])]={'task_id':int(task['task_id']),'record_count':task['records'],'molecule_count':task['molecules'],
            'pending_family_bytes':0,'staging_bytes':0,'archive_ALL_bytes':0,'archive_SELECTIVE_bytes':0}
    for g in groups:
        tid=g['task_id'];s=g['size_stratum'];n=g['records'];m=g['molecules'];cost=costs[tid]
        stage=g['sum_record_atoms2']*stage_beta[s];family=n*family_rates[s]
        cost['staging_bytes']+=stage;cost['pending_family_bytes']+=family
        for policy in ('ALL','SELECTIVE'):
            def raw_cost(policy_key,records,molecules,record_atoms2,mol_atoms2):
                value=0
                for rate in rates[(policy_key,s)].values():
                    value+=records*(rate['base_record_bytes']+rate['legacy_output_record_bytes'])+molecules*rate['legacy_output_molecule_bytes']
                    value+=record_atoms2*rate['extra_record_atoms2_coefficient']+mol_atoms2*rate['extra_molecule_atoms2_coefficient']
                return value
            if policy=='SELECTIVE' and g['unknown_energy_molecules']:
                amount=raw_cost(policy,n-g['unknown_energy_records'],m-g['unknown_energy_molecules'],
                    g['sum_record_atoms2']-g['unknown_record_atoms2'],g['sum_mol_atoms2']-g['unknown_mol_atoms2'])
                amount+=raw_cost('ALL',g['unknown_energy_records'],g['unknown_energy_molecules'],g['unknown_record_atoms2'],g['unknown_mol_atoms2'])
            else:amount=raw_cost(policy,n,m,g['sum_record_atoms2'],g['sum_mol_atoms2'])
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
        'G6_duplicate_molecules_are_not_independent_samples':True,
        'G6_actual_source_context':[{'node':c['node'],'selection':c['selection_reference'],'queue':c['queue_reference'],
            'raw_compression':c['raw_compression_reference'],'phase_archives':c['physical_archive_ratios'],
            'historical_attempt_raw_rows':len(c['historical_attempts_measured_raw_rows']),
            'historical_attempt_frame_bytes':sum(r['frames_bytes'] for r in c['historical_attempts_measured_raw_rows']),
            'old_ALL_minimum_flag_missing_molecules':c['minimum_flags_missing_in_preserved_legacy_ALL_metadata']} for c in calibration],
        'G6_retries_are_latest_attempt_byte_witnesses_not_extra_formal_population':True,'source_dictionary_manifest':{'path':manifest,'sha256':A.file_sha(manifest)},
        'source_population_manifest':{'path':a.population,'sha256':A.file_sha(a.population)},
        'source_packing_tasks':{'path':a.tasks,'sha256':A.file_sha(a.tasks)},
        'source_packing_assignments':{'path':a.assignments,'sha256':A.file_sha(a.assignments)},
        'formal_eligible_pilot_sample':benchmark['formal_context_closure'],'quota':quota,'plans':plans,
        'temporary_contexts':temporary_contexts,'per_task':costs,'measured_SQLite_overhead_per_call':overhead,
        'extra_raw_and_input_metadata_rates':source_rates,'current_format_G6_stage_witness':dict(stage_witness),'current_format_stage_max_bytes_per_record_atoms2':stage_beta,
        'legacy_retired_stage_sizes_are_NULL_not_reconstructed':True,
        'minimum_audit':{'path':a.minimum_manifest,'sha256':A.file_sha(a.minimum_manifest),'manifest':minimum},
        'SELECTIVE_unknown_minimum_policy':'ALL raw for each exact affected molecule; measured formal unknown count used, not assumed zero',
        'method':'Conservative independent top29 sums for staging, pending family, new-old raw consolidation, singlelane/jobVACUUM inside the basic temporary reserve. Sidefiles from actualG6 ALL include binaryrestart; separate frame additions are conservative, not joint-compressed measurements.',
        'sidefile_size_model':'Maximum actual percalc/stratum dict-compressed extra bytes/atoms^2 plus actual uncompressedSQL membermanifest growth, applied to exact formal assignment record-weighted and molecule-weighted atoms^2; no smaller format savings assumed.',
        'original_input_gap':'Old pilot input files are reconstructed and have no historical original-input SHA. G6 actual inputs include original files and versions/keywords from actual frozen capture.',
        'stage_size_model':'G6 actually captured current formal pickle5 context/result/population_rows; maximum compressed bytes/(records*atoms^2) per seven strata times exact formal record-weighted atom^2. Legacy retired measurements are NULL and excluded.',
        'no_training600GB_double_count':True,'no_scientific_reserialization':True,'QM_started':False,'LMDB_created':False,
        'source_files_written_or_deleted':False,'source_sha256':A.file_sha(__file__)}
    save(out,report);print(json.dumps({'status':report['status'],'policy_selected':selected,'path':str(out)}))
if __name__=='__main__':main()
