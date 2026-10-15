#!/usr/bin/env python3
"""G5: every retained registry field of all 10,020 archived pilot records.

No quantum calculation is launched. Numerical values come from retained raw
artifacts only; absent AUX/JSON/WBO/gradient/FOD files are explicit verification
gaps. Source outcomes and provenance are preserved separately from reparse QC.
"""
from __future__ import annotations
import argparse, ast, collections, concurrent.futures, hashlib, json, math
import multiprocessing, os
from pathlib import Path
import shutil, stat, struct, subprocess, sys, tarfile, tempfile, time
sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent
AUDIT=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2')
sys.path[:0]=[str(AUDIT/'deps'),str(AUDIT/'scripts/deps')]
import wp5_engine as ENGINE
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
MISSING=object()
ENTRIES=ROWS=TASKS=None
START_BARRIER=None

def sha(path):return ENGINE.sha(path)
def wanted(entry):
    return entry['task'] in ENGINE.TASK_NAMES and not any(name in entry.get('source_path','') for name in ('polar_blocks','static_polar_block','STATIC_finite_field_tensors'))

def lookup(detail,path):
    parts=str(path).strip('/').replace('/','.').split('.')
    if parts and parts[0] in ('detail','details'):parts=parts[1:]
    value=detail
    if parts and parts[0] not in detail and isinstance(detail.get('values'),dict):value=detail['values']
    for part in parts:
        if not isinstance(value,dict) or part not in value:return MISSING
        value=value[part]
    return value

def value_sha(value):
    if value is MISSING:return None
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def exact(a,b):
    if a is MISSING or b is MISSING:return a is b
    if type(a)!=type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[key],b[key]) for key in a)
    if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    if type(a) is float:return struct.pack('>d',a)==struct.pack('>d',b)
    return a==b

def numeric_round_match(a,b,tolerance):
    if isinstance(a,list) and isinstance(b,list):return len(a)==len(b) and all(numeric_round_match(x,y,tolerance) for x,y in zip(a,b))
    if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(numeric_round_match(a[key],b[key],tolerance) for key in a)
    if type(a) is float and type(b) is float:return math.isfinite(a) and math.isfinite(b) and abs(a-b)<=tolerance
    return exact(a,b)

def summarize(value):
    if value is MISSING:return 'ABSENT'
    if value is None:return 'NULL'
    if isinstance(value,list):return f'list[{len(value)}]'
    if isinstance(value,dict):return 'dict:'+','.join(sorted(value))[:200]
    return str(value)[:200]

def iter_pilot_molecules(pilot_root):
    for bucket in sorted(Path(pilot_root).glob('bucket_*')):
        for receipt in sorted((bucket/'molecules').glob('*/receipt.json')):yield receipt

def load_original_details(receipt_path):
    import pyarrow.parquet as pq
    receipt=json.loads(Path(receipt_path).read_text());reference=receipt['parquet'];path=Path(reference['path'])
    if path.stat().st_size!=reference['bytes'] or sha(path)!=reference['sha256']:raise ValueError('PILOT_PARQUET_CHANGED:'+str(path))
    rows=pq.read_table(path,columns=['details_json']).to_pylist()
    details=[json.loads(row['details_json']) for row in rows]
    return receipt,details

def initialize(plan,config,registry,panel_rows,barrier):
    global ENTRIES,ROWS,TASKS,START_BARRIER
    ENGINE.initialize_worker(plan,config,'/tmp',deadline=time.time()+8*3600)
    ENTRIES=[entry for entry in json.loads(Path(registry).read_text())['entries'] if wanted(entry)]
    ROWS={row['record_id']:row for row in panel_rows};TASKS={task['name']:task for task in ENGINE.CONFIG['tasks']}
    START_BARRIER=barrier
    # Exactly the requested worker processes participate before any data work.
    START_BARRIER.wait(timeout=180)

def extract_retained(receipt,details,temp):
    reference=receipt.get('archive');found={};members_by_name={}
    for detail in details:
        archive=detail.get('archive')
        if not archive or not archive.get('member_prefix'):continue
        if archive['path']!=reference['path'] or archive['sha256']!=reference['sha256']:raise ValueError('CALL_ARCHIVE_REFERENCE_DIFFERS')
        slot=(detail['record_id'],detail['task']);prefix=archive['member_prefix']
        directory=temp/hashlib.sha256((slot[0]+'|'+slot[1]).encode()).hexdigest()[:24];directory.mkdir()
        found[slot]=directory
        for item in detail.get('archived_files',[]):
            if Path(item['name']).name!=item['name']:raise ValueError('INVALID_ARCHIVED_FILENAME')
            key=prefix+'/'+item['name']
            if key in members_by_name:raise ValueError('DUPLICATE_ARCHIVED_MEMBER_REFERENCE')
            members_by_name[key]=(directory/item['name'],item)
    if not reference:
        if members_by_name:raise ValueError('MISSING_MOLECULE_ARCHIVE')
        return found
    path=Path(reference['path'])
    if path.stat().st_size!=reference['bytes'] or sha(path)!=reference['sha256']:raise ValueError('PILOT_RAW_ARCHIVE_CHANGED')
    process=subprocess.Popen([ENGINE.CONFIG['zstd_executable'],'-d','-c',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    observed=set()
    try:
        with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
            for member in archive:
                if not member.isfile() or member.name.startswith('/') or '..' in Path(member.name).parts:raise ValueError('INVALID_RAW_ARCHIVE_MEMBER')
                if member.name not in members_by_name:continue
                if member.name in observed:raise ValueError('DUPLICATE_RAW_ARCHIVE_MEMBER')
                target,binding=members_by_name[member.name];stream=archive.extractfile(member)
                data=stream.read()
                if len(data)!=binding['bytes'] or hashlib.sha256(data).hexdigest()!=binding['sha256']:raise ValueError('CALL_RAW_BYTES_SHA_DIFFERS:'+member.name)
                target.write_bytes(data);observed.add(member.name)
    finally:
        while process.stdout.read(1<<20):pass
        process.stdout.close();error=process.stderr.read();code=process.wait()
    if code:raise ValueError('ARCHIVE_DECODE_FAILED:'+error.decode(errors='replace')[-300:])
    missing=set(members_by_name)-observed
    if missing:raise ValueError('ARCHIVE_REFERENCED_FILES_MISSING:'+str(sorted(missing)[:3]))
    return found

def parse_saved(task,native,directory):
    parser=ENGINE.PARSER;legacy=ENGINE.NATIVE
    if task['family']=='mopac':
        parser.read_aux=legacy.native_aux_labels;parser.sigma_pi_entries=lambda text:legacy.sparse_sigma_pi(text,native['pairs'])
        values=parser.parse_mopac(directory,native['symbols'],pair_indices=native['pairs'],reconstruct_mulliken=False)
        if task['name']=='pm7_B':
            overlap=legacy.MULLIKEN.sparse_mulliken_from_aux(directory/'input.aux',native['symbols'],native['pairs'],reference_charges=values.get('mulliken_charges_e'),charge_tolerance_e=ENGINE.CONFIG['mulliken_overlap_charge_tolerance_e'],min_absolute_eigenvalue=ENGINE.CONFIG['mulliken_minimum_absolute_eigenvalue'])
            values['mulliken_overlap_population_pairs']=overlap['pairs'];values['mulliken_overlap_qc']=overlap['qc'];values['mulliken_reconstruction_charge_max_error_e']=overlap['qc'].get('reconstructed_charge_max_error_e')
        population,atoms,kinds=values.get('ao_population_e'),values.get('ao_atom_index_1based'),values.get('ao_types')
        if population and atoms and kinds and len(population)==len(atoms)==len(kinds):
            shell=[{'s':0.,'p':0.,'d':0.,'f':0.,'unknown':0.} for _ in native['symbols']]
            for atom,kind,value in zip(atoms,kinds,population):
                kind=str(kind).upper();key='s' if kind=='S' else 'p' if kind.startswith('P') else 'd' if kind.startswith('D') or kind in ('X2','XZ','Z2','YZ','XY') else 'f' if kind.startswith('F') else 'unknown'
                shell[int(atom)-1][key]+=float(value)
            values['atomic_shell_population_e']=shell
        for key in ('ao_population_e','ao_atom_index_1based','ao_types'):values.pop(key,None)
    else:
        values=parser.parse_xtb(directory,native['symbols'])
        if values.get('wiberg_pairs'):
            selected=set(native['pairs']);values['wiberg_pairs']=[pair for pair in values['wiberg_pairs'] if (max(pair['i'],pair['j']),min(pair['i'],pair['j'])) in selected]
        if task.get('perturbed'):
            import numpy as np
            seed=ENGINE.perturb_seed(native['_row']['record_id'],ENGINE.CONFIG)
            coords=native['coords']+np.random.default_rng(seed).normal(0,ENGINE.CONFIG['perturb_sigma_A'],native['coords'].shape)
            values.update(positions_A=coords.tolist(),elements=native['symbols'],perturb_seed=seed,perturb_sigma_A=ENGINE.CONFIG['perturb_sigma_A'])
    return parser.project_values(task['name'],values),parser.context()

def scope_status(original,values,task,qc):
    text=values.get('normal_end')
    # Specialty xTB projection intentionally omits the common end marker.
    status=original['status']
    missing=[key for key in task['required_values'] if values.get(key) is None or values.get(key)==[] or values.get(key)=={}]
    if status=='PROPERTY_FAILED':
        original_missing=[key for key in original.get('missing_properties',[]) if key not in ENGINE.PARSER.DELETED_FIELDS]
        if not original_missing and not missing and not qc and not values.get('property_failure_lines'):status='SUCCESS'
    if missing or qc:
        if status=='SUCCESS':status='PROPERTY_FAILED'
    return status,missing

def missing_source_reason(task,path,artifacts,expected,actual):
    if path.startswith('detail.') or expected is MISSING:return None
    key=path.removeprefix('values.').split('.')[0]
    if expected is None or expected==[] or expected=={}:return None
    if task['family']=='mopac' and 'input.aux' not in artifacts:
        if key in ('gradient_kcal_mol_A','dipole_Debye','bond_orders','atomic_shell_population_e','mulliken_overlap_population_pairs','mulliken_overlap_qc','mulliken_reconstruction_charge_max_error_e','parse_errors'):return 'AUX_NOT_RETAINED'
    if task['family']=='xtb':
        if key in ('gradient_Eh_bohr','forces_eV_A') and 'gradient' not in artifacts:return 'GRADIENT_NOT_RETAINED'
        if key=='FOD_atom_e' and not any('fod' in item.lower() for item in artifacts):return 'FOD_POPULATION_FILE_NOT_RETAINED'
        if key=='wiberg_pairs' and 'wbo' not in artifacts:return 'WBO_NOT_RETAINED'
        if key=='molecular_quadrupole_traceless_au' and not any(item.endswith('.json') for item in artifacts):return 'JSON_NOT_RETAINED'
    if actual is MISSING or actual is None or actual==[] or actual=={}:return 'REQUESTED_FIELD_NOT_RECONSTRUCTIBLE_FROM_RETAINED_RAW'
    return None

def review_one(receipt_path):
    started=time.monotonic();temp=Path(tempfile.mkdtemp(prefix=f'wp5g5_{os.getuid()}_{os.environ["SLURM_JOB_ID"]}_{os.getpid()}_',dir='/tmp'))
    try:
        receipt,all_details=load_original_details(receipt_path)
        details=[detail for detail in all_details if detail['task'] in TASKS]
        originals={(detail['record_id'],detail['task']):detail for detail in details}
        if len(originals)!=receipt['records']*12:raise ValueError('PILOT_TWELVE_SLOT_CLOSURE_FAIL')
        paths=extract_retained(receipt,details,temp);candidates={};contexts={};native_by_record={};qc_rows=[];issues=[]
        for record_id in sorted({key[0] for key in originals}):
            row=ROWS.get(record_id)
            if row is None:raise ValueError('PILOT_RECORD_NOT_IN_FROZEN_PANEL:'+record_id)
            native=ENGINE.NATIVE.read_native(row);native['_row']=row;native_by_record[record_id]=native
            for task in TASKS.values():
                key=(record_id,task['name']);original=originals[key];actual={name:value for name,value in original.items() if name!='values'}
                context={'artifacts_present':[],'rounding_decimal_places':{}}
                if key in paths:
                    try:values,context=parse_saved(task,native,paths[key])
                    except Exception as exc:values={};issues.append({'record_id':record_id,'task':task['name'],'error':f'{type(exc).__name__}: {exc}'})
                else:values={}
                actual['values']=values
                if 'mulliken_overlap_qc' in values and isinstance(original.get('values',{}).get('mulliken_overlap_qc'),dict):
                    # Historical parsing duration is provenance, not a numerical
                    # output that is expected to recur in an offline reparse.
                    oldqc=original['values']['mulliken_overlap_qc']
                    for timing in ('elapsed_seconds','wall_seconds'):
                        if timing in oldqc and timing in values['mulliken_overlap_qc']:values['mulliken_overlap_qc'][timing]=oldqc[timing]
                atomic=ENGINE.validate_atomic_arrays(actual,native['z'])
                scope,missing=scope_status(original,values,task,atomic)
                actual['source_status']=original['status'];actual['scope_status']=scope
                candidates[key]=actual;contexts[key]=context
                qc_rows.append({'record_id':record_id,'molecule_id':receipt['molecule_id'],'calc_type':task['name'],'source_status':original['status'],'scope_status':scope,'atomic_issues_json':json.dumps(atomic),'requested_missing_json':json.dumps(missing),'artifacts_json':json.dumps(context.get('artifacts_present',[]))})
            ENGINE.derived_quantities([candidates[(record_id,name)] for name in TASKS])
        comparisons=[];counts=collections.Counter();field_counts=collections.Counter()
        for key,original in originals.items():
            actual=candidates[key];task=TASKS[key[1]];context=contexts[key];artifacts=context.get('artifacts_present',[])
            for entry in ENTRIES:
                if entry['task']!=key[1]:continue
                path=entry['source_path'];left=lookup(original,path);right=lookup(actual,path);tolerance=None;reason=None
                if left is MISSING and right is MISSING:status='BOTH_ABSENT'
                elif exact(left,right):status='PROVENANCE_VALIDATED' if path.startswith('detail.') else 'MATCH_BITS'
                elif path in ('values.D4_atomic_C6_au','values.D4_atomic_alpha_bohr3') and context.get('D4_complete_tables',0)>0:
                    status='AUTHORIZED_D4_CORRECTION';reason='HEADER_SCOPED_TRANSACTIONAL_D4'
                elif path=='values.property_failure_lines' and context.get('source_deleted_scope_diagnostics'):
                    status='DELETED_POLAR_DIAGNOSTIC_REMOVED';reason='POLAR_SCOPE_REMOVED_ONLY'
                else:
                    reason=missing_source_reason(task,path,artifacts,left,right)
                    precision=context.get('rounding_decimal_places',{}).get(path.removeprefix('values.'))
                    if precision is not None:
                        tolerance=.5*10.**(-precision)
                        if path=='values.dipole_Debye':tolerance*=ENGINE.PARSER.AU_DIPOLE_TO_DEBYE
                    if reason:status='SOURCE_NOT_ARCHIVED'
                    elif tolerance is not None and numeric_round_match(left,right,tolerance*(1+1e-9)):status='ROUNDING_MATCH';reason='EXPLICIT_STDOUT_DECIMAL_PRECISION'
                    elif left is MISSING:status='NEW_FIELD_PRESENT'
                    else:status='DIFF'
                counts[status]+=1;field_counts[(entry['registry_id'],status)]+=1
                comparisons.append({'record_id':key[0],'molecule_id':receipt['molecule_id'],'calc_type':key[1],'registry_id':int(entry['registry_id']),'source_path':path,'comparison':status,'reason':reason,'expected_sha256':value_sha(left),'reparsed_sha256':value_sha(right),'expected_summary':summarize(left),'reparsed_summary':summarize(right),'rounding_tolerance':tolerance})
        return {'molecule_id':receipt['molecule_id'],'worker_pid':os.getpid(),'record_ids':sorted(native_by_record),'slots':len(originals),'counts':dict(counts),'field_counts':[[rid,status,count] for (rid,status),count in sorted(field_counts.items())],'comparisons':comparisons,'status_rows':qc_rows,'parse_issues':issues,'elapsed_seconds':time.monotonic()-started,'receipt_sha256':sha(receipt_path)}
    finally:
        if temp.parent!=Path('/tmp') or not temp.name.startswith(f'wp5g5_{os.getuid()}_'):raise ValueError('LOCAL_REVIEW_CLEANUP_TARGET')
        for path in [temp,*temp.rglob('*')]:
            info=path.lstat()
            if info.st_uid!=os.getuid() or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):raise ValueError('LOCAL_REVIEW_CLEANUP_OWNER_TYPE')
        shutil.rmtree(temp)

def close_lane():
    START_BARRIER.wait(timeout=180)
    result=ENGINE.close_worker()
    START_BARRIER.wait(timeout=180)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--workers',type=int,default=16)
    p.add_argument('--pilot-root',default=str(OLD/'wp4_native_full_v4'));p.add_argument('--panel',default=str(OLD/'wp4_native_panel/pilot_panel.parquet'))
    p.add_argument('--source-plan',default=str(AUDIT/'plan.json'));p.add_argument('--config',default=str(HERE.parent/'configs/protocol.json'));p.add_argument('--output')
    args=p.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text());assert exact([1.,None],[1.,None]);assert not exact([1.],[1.00001]);assert numeric_round_match([1.],[1.0001],.0005)
        print('WP5_G5_AST_COMPARATOR_PASS_NO_QM_NO_SOURCE_READ');return 0
    allocated=int(os.environ.get('SLURM_CPUS_PER_TASK','0'))
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=allocated:raise ValueError('G5_REQUIRES_AT_LEAST_16_EFFECTIVE_SLURM_WORKERS')
    os.environ.update({key:'1' for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    import pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    panel=pq.read_table(args.panel).to_pylist()
    if len(panel)!=10020 or len({row['record_id'] for row in panel})!=10020:raise ValueError('EXACT_FROZEN_10020_PANEL_REQUIRED')
    receipts=list(iter_pilot_molecules(args.pilot_root))
    if len(receipts)!=1441:raise ValueError('EXACT_FROZEN_1441_PILOT_MOLECULES_REQUIRED')
    config=ENGINE.load_protocol(args.config);registry=config['registry']['path']
    if sha(registry)!=config['registry']['sha256']:raise ValueError('REGISTRY_SHA_DIFFERS')
    output=Path(args.output or HERE.parent/'gates/G5_parser_regression'/('job_'+os.environ['SLURM_JOB_ID']));output.mkdir(parents=True,exist_ok=False)
    comparison_schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('calc_type',pa.string()),('registry_id',pa.int16()),('source_path',pa.string()),('comparison',pa.string()),('reason',pa.string()),('expected_sha256',pa.string()),('reparsed_sha256',pa.string()),('expected_summary',pa.string()),('reparsed_summary',pa.string()),('rounding_tolerance',pa.float64())])
    status_schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('calc_type',pa.string()),('source_status',pa.string()),('scope_status',pa.string()),('atomic_issues_json',pa.string()),('requested_missing_json',pa.string()),('artifacts_json',pa.string())])
    started=time.monotonic();counts=collections.Counter();fields=collections.Counter();records=set();pids=set();slots=0;issues=[];cleanup=[]
    ctx=multiprocessing.get_context('fork');barrier=ctx.Barrier(args.workers)
    try:
        with pq.ParquetWriter(output/'field_regression.parquet.pending',comparison_schema,compression='zstd') as writer, pq.ParquetWriter(output/'reparse_status.parquet.pending',status_schema,compression='zstd') as status_writer:
            with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=ctx,initializer=initialize,initargs=(args.source_plan,args.config,registry,panel,barrier)) as pool:
                futures={pool.submit(review_one,str(path)):str(path) for path in receipts}
                done=0
                for future in concurrent.futures.as_completed(futures):
                    result=future.result();done+=1;counts.update(result['counts']);records.update(result['record_ids']);pids.add(result['worker_pid']);slots+=result['slots'];issues.extend(result['parse_issues'])
                    for rid,status,count in result['field_counts']:fields[(rid,status)]+=count
                    writer.write_table(pa.Table.from_pylist(result['comparisons'],schema=comparison_schema));status_writer.write_table(pa.Table.from_pylist(result['status_rows'],schema=status_schema))
                    if done%50==0:
                        progress={'closed_molecules':done,'molecules':len(receipts),'records':len(records),'worker_pids':sorted(pids),'elapsed_seconds':time.monotonic()-started,'counts':dict(counts)}
                        pending=output/'progress.json.pending';pending.write_text(json.dumps(progress,indent=2)+'\n');pending.replace(output/'progress.json')
                # Each worker gets an explicit cleanup task; barriers ensure
                # os._exit cannot bypass the engine's scratch/LMDB cleanup.
                cleanup=[future.result() for future in [pool.submit(close_lane) for _ in range(args.workers)]]
        (output/'field_regression.parquet.pending').replace(output/'field_regression.parquet');(output/'reparse_status.parquet.pending').replace(output/'reparse_status.parquet')
    except Exception as exc:
        (output/'failure.json').write_text(json.dumps({'error':f'{type(exc).__name__}: {exc}','closed_records':len(records),'slots':slots,'counts':dict(counts)},indent=2)+'\n');raise
    pass_status={'BOTH_ABSENT','MATCH_BITS','PROVENANCE_VALIDATED','ROUNDING_MATCH','AUTHORIZED_D4_CORRECTION','DELETED_POLAR_DIAGNOSTIC_REMOVED'}
    uncovered=sum(count for status,count in counts.items() if status not in pass_status)
    report={'gate':'G5','status':'PASS' if uncovered==0 and not issues and records=={row['record_id'] for row in panel} and slots==120240 and len(pids)>=16 else 'NOT_PASS',
      'records':len(records),'molecules':len(receipts),'requested_slots':slots,'workers_requested':args.workers,'worker_pids':sorted(pids),'actual_worker_count':len(pids),'elapsed_seconds':time.monotonic()-started,
      'comparison_counts':dict(counts),'unverified_or_diff_fields':uncovered,'field_counts':[{'registry_id':rid,'comparison':status,'count':count} for (rid,status),count in sorted(fields.items())],
      'parse_issues':issues,'cleanup':cleanup,'source_scope':'ALL_10020_PILOT_ARCHIVES_READONLY_NO_QM','metadata_replay':'Historical source status and run/archive provenance validated against immutable receipt/raw hashes; physical fields re-parsed, never copied as substitute for absent artifacts.',
      'authorized_changes':['Delete POLAR response and its diagnostic lines','Header-scoped transactional D4 correction'],
      'history_missing_raw_policy':'SOURCE_NOT_ARCHIVED is an unmet regression requirement, never a successful match.',
      'files':{name:{'path':str(output/name),'sha256':sha(output/name),'bytes':(output/name).stat().st_size} for name in ('field_regression.parquet','reparse_status.parquet')},
      'binding':{'script_sha256':sha(__file__),'parser_sha256':sha(HERE/'wp5_parser.py'),'engine_sha256':sha(HERE/'wp5_engine.py'),'protocol_sha256':sha(args.config),'panel_sha256':sha(args.panel),'registry_sha256':sha(registry),'source_plan_sha256':sha(args.source_plan),'seed':config['seed'],'job_id':os.environ['SLURM_JOB_ID'],'python':sys.version,'pyarrow':pa.__version__}}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    md=f"G5: {report['status']}\n\n全量 {len(records)} 个 records / {len(receipts)} 个完整分子 / {slots} 个本轮 task 槽；实际 {len(pids)} 个单核 worker。\n\n逐字段比较：{json.dumps(dict(counts),ensure_ascii=False)}。\n\nSOURCE_NOT_ARCHIVED 为历史 raw 未保留，不能冒充回归通过。所有差异在 field_regression.parquet 中按 record_id/calc_type/registry_id/source_path 逐条列出；reparse_status.parquet 保留 source_status、scope_status、原子数组与 requested 缺失。无 QM 重算，无原始写入。\n"
    (output/'report.md').write_text(md)
    print(json.dumps({'gate':'G5','status':report['status'],'records':len(records),'slots':slots,'actual_workers':len(pids),'counts':dict(counts),'output':str(output)}));return 0
if __name__=='__main__':raise SystemExit(main())
