#!/usr/bin/env python3
"""Paired POLAR cost check: one B without POLAR per selected native minimum.

At most five original-energy minima per nonempty size stratum are selected
from the full WP1-retained pilot panel. The paired B with POLAR is read from
completed pilot output. The frozen native-v2 engine owns QM invocation, sparse
parsing, verified termination, archives and scratch cleanup. No other QM call,
Hessian, optimization or LMDB write is performed.
"""
from __future__ import annotations
import argparse
import concurrent.futures as futures
import copy
import hashlib
import importlib.util
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import socket
import stat
import sys
import time

sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent
ROOT=HERE.parent
POLAR='POLAR(E=(0.0),BETA=0,GAMMA=0)'
ENGINE=None
TASK=None


def import_engine(path):
    spec=importlib.util.spec_from_file_location('wp4_polar_pinned_engine',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def initialize(sources,config,output,deadline,stop_event):
    global ENGINE,TASK
    output=Path(output)
    ENGINE=import_engine(output/'source_snapshot/wp4_native_pilot_v2.py')
    ENGINE.initialize(sources,config,str(output),str(output/'source_snapshot/wp4_parsers.py'),deadline,stop_event)
    TASK=copy.deepcopy(config['tasks'][0])


def paired_result(row,pilot_roots,engine):
    """Read exactly this molecule's committed pilot Parquet, never rerun it."""
    import pyarrow.parquet as pq
    molecule_hash=hashlib.sha256(row['molecule_id'].encode()).hexdigest()[:24]
    matches=[]
    for root in pilot_roots:
        path=Path(root)/'molecules'/molecule_hash/'results.parquet'
        receipt_path=path.parent/'receipt.json'
        if not path.is_file() or not receipt_path.is_file(): continue
        receipt=json.loads(receipt_path.read_text())
        ref=receipt.get('parquet',{})
        if ref.get('sha256')!=engine.sha(path): raise ValueError('PAIRED_PILOT_PARQUET_SHA_DIFFERS:'+str(path))
        rows=pq.read_table(path,columns=['record_id','task','details_json']).to_pylist()
        for item in rows:
            if item['record_id']==row['record_id'] and item['task']=='pm7_B':
                result=json.loads(item['details_json'])
                if result.get('source_payload_sha256')!=row['record_payload_sha256']:
                    raise ValueError('PAIRED_PILOT_PAYLOAD_DIFFERS:'+row['record_id'])
                matches.append({'result':result,'parquet':{'path':str(path),'sha256':ref['sha256']},
                                'receipt_sha256':engine.sha(receipt_path)})
    if len(matches)>1: raise ValueError('DUPLICATE_PAIRED_PILOT_RECORD:'+row['record_id'])
    return matches[0] if matches else None


def record_worker(item):
    import pyarrow as pa
    import pyarrow.parquet as pq
    row,paired=item
    record_hash=hashlib.sha256(row['record_id'].encode()).hexdigest()[:24]
    directory=ENGINE.OUTPUT/'records'/record_hash
    directory.mkdir(parents=True,exist_ok=True)
    identity=ENGINE.stable_sha({'record_id':row['record_id'],'payload':row['record_payload_sha256'],
                                'paired':paired,'task':TASK})
    receipt_path=directory/'receipt.json'
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text())
        if receipt['input_identity_sha256']!=identity: raise ValueError('COST_RECEIPT_BINDING_DIFFERS')
        for field in ('parquet','archive'):
            ref=receipt.get(field)
            if ref and ENGINE.sha(ref['path'])!=ref['sha256']: raise ValueError('COST_RECEIPT_OUTPUT_DIFFERS')
        return {**receipt,'resumed_without_QM':True,'resumed_worker_pid':os.getpid()}
    state_path=directory/'state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else {'identity':identity,'attempts':[]}
    if state['identity']!=identity: raise ValueError('COST_CHECKPOINT_BINDING_DIFFERS')
    old=next((r for r in reversed(state['attempts']) if r['status'] not in ENGINE.UNFINISHED),None)
    if old is None:
        if time.time()>ENGINE.DEADLINE-30 or ENGINE.STOP_EVENT.is_set():
            return {'status':'PARTIAL_RESUMABLE','record_id':row['record_id'],'worker_pid':os.getpid()}
        if paired is None:
            result=ENGINE.skipped(row,None,TASK,'PAIRED_B_NOT_AVAILABLE')
        else:
            primary=paired['result']
            primary_HOF=primary.get('values',{}).get('heat_of_formation_kcal_mol')
            eligible=primary.get('B_base_success') is True and primary_HOF is not None and math.isfinite(float(primary_HOF))
            if not eligible:
                result=ENGINE.skipped(row,None,TASK,'PAIRED_B_CORE_FAILED')
            else:
                try:
                    native=ENGINE.read_native(row)
                    if native['native_coordinates_sha256']!=primary.get('native_coordinates_sha256') or native['native_atom_order_sha256']!=primary.get('native_atom_order_sha256'):
                        raise ValueError('PAIRED_NATIVE_COORDINATES_OR_ATOM_ORDER_DIFFERS')
                    expected=(TASK['keywords']+' THREADS=1').split()
                    keywords=primary.get('keywords','')
                    if keywords.count(POLAR)!=1 or keywords.replace(POLAR,'').split()!=expected:
                        raise ValueError('PAIRED_B_KEYWORDS_DIFFER_BY_MORE_THAN_POLAR')
                    result=ENGINE.invoke(TASK,native,row,directory)
                except Exception as exc:
                    result=ENGINE.skipped(row,None,TASK,'SOURCE_OR_PAIR_BINDING_FAILED')
                    result['failure_reason']=type(exc).__name__+': '+str(exc)
        result['cost_probe_variant']='B_WITHOUT_POLAR_ONLY'
        result['paired_B_with_POLAR']=paired
        comparable=result.get('B_base_success') is True and paired is not None
        if comparable:
            primary=paired['result']
            get=lambda obj,key:obj.get(key)
            result['paired_cost']={
                'B_with_POLAR_elapsed_seconds':primary['elapsed_seconds'],
                'B_without_POLAR_elapsed_seconds':result['elapsed_seconds'],
                'POLAR_increment_elapsed_seconds':primary['elapsed_seconds']-result['elapsed_seconds'],
                'B_with_POLAR_QM_CPU_seconds':get(primary,'qm_child_cpu_seconds'),
                'B_without_POLAR_QM_CPU_seconds':get(result,'qm_child_cpu_seconds'),
                'POLAR_increment_QM_CPU_seconds':primary['qm_child_cpu_seconds']-result['qm_child_cpu_seconds'] if get(primary,'qm_child_cpu_seconds') is not None and get(result,'qm_child_cpu_seconds') is not None else None,
                'HOF_with_minus_without_POLAR_kcal_mol':primary['values']['heat_of_formation_kcal_mol']-result['values']['heat_of_formation_kcal_mol'],
                'B_with_POLAR_raw_bytes':get(primary,'raw_total_bytes'),'B_without_POLAR_raw_bytes':get(result,'raw_total_bytes'),
                'B_with_POLAR_getter_seconds':primary['values'].get('mulliken_overlap_qc',{}).get('elapsed_seconds'),
                'B_without_POLAR_getter_seconds':result['values'].get('mulliken_overlap_qc',{}).get('elapsed_seconds'),
                'timing_scope':'Frozen engine elapsed is QM subprocess wall time; getter timing separate. Signed paired delta, no clipping.',
            }
        state['attempts'].append(result); ENGINE.save_json(state_path,state)
        old=result
    if old['status'] in ENGINE.UNFINISHED:
        return {'status':'PARTIAL_RESUMABLE','record_id':row['record_id'],'worker_pid':os.getpid()}
    archive=ENGINE.compact_archives(state['attempts'],directory/'raw_outputs.tar.zst')
    final=state['attempts'][-1]
    final['invocation_task_name']=final['task']
    final['task']='pm7_B_noPOLAR'
    parquet=directory/'results.parquet'; pending=parquet.with_name(parquet.name+'.pending')
    table=pa.Table.from_pylist([ENGINE.row_for_parquet(final)],schema=ENGINE.parquet_schema(pa))
    pq.write_table(table,pending,compression='zstd'); pending.replace(parquet)
    receipt={'status':'COMPLETE_WITH_RECORDED_OUTCOME','record_id':row['record_id'],'molecule_id':row['molecule_id'],
             'size_stratum':row['size_stratum'],'input_identity_sha256':identity,'worker_pid':os.getpid(),
             'job_id':os.environ['SLURM_JOB_ID'],'outcome':final['status'],'failure_code':final.get('failure_code'),
             'paired_cost':final.get('paired_cost'),'actual_QM_attempts':sum(r.get('argv') is not None for r in state['attempts']),
             'parquet':{'path':str(parquet),'bytes':parquet.stat().st_size,'sha256':ENGINE.sha(parquet)},'archive':archive}
    ENGINE.save_json(receipt_path,receipt)
    # The committed Parquet/archive retain every interrupted attempt's logs.
    partials=directory/'partial_archives'
    if partials.exists():
        for path in partials.iterdir():
            info=path.lstat()
            if info.st_uid!=os.getuid() or not stat.S_ISREG(info.st_mode):
                raise RuntimeError('NONOWNED_COST_PARTIAL_ARCHIVE_CLEANUP')
            path.unlink()
        partials.rmdir()
    state_path.unlink()
    return receipt


def aggregates(receipts):
    import statistics
    groups={}
    for receipt in receipts:
        if receipt.get('paired_cost'):
            groups.setdefault(receipt['size_stratum'],[]).append(receipt['paired_cost'])
            groups.setdefault('ALL_SELECTED',[]).append(receipt['paired_cost'])
    result={}
    for group,values in groups.items():
        fields={}
        for key in ('POLAR_increment_elapsed_seconds','POLAR_increment_QM_CPU_seconds','HOF_with_minus_without_POLAR_kcal_mol'):
            observed=[r[key] for r in values if r.get(key) is not None]
            fields[key]={'n':len(observed),'min':min(observed),'median':statistics.median(observed),'mean':statistics.mean(observed),'max':max(observed)} if observed else None
        result[group]={'paired_records':len(values),'metrics':fields}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panel'); parser.add_argument('--panel-manifest'); parser.add_argument('--record-index')
    parser.add_argument('--paired-pilot-root',nargs='+'); parser.add_argument('--output')
    parser.add_argument('--engine',default=str(HERE/'wp4_native_pilot_v2.py'))
    parser.add_argument('--config',default=str(HERE/'wp4_native_v2_config.json'))
    parser.add_argument('--source-plan'); parser.add_argument('--per-stratum',type=int,default=5)
    parser.add_argument('--workers',type=int,default=16); parser.add_argument('--wall-seconds',type=float,default=3600)
    parser.add_argument('--resume',action='store_true'); parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    engine=import_engine(args.engine)
    config=json.loads(Path(args.config).read_text())
    task=copy.deepcopy(next(task for task in config['tasks'] if task['name']=='pm7_B'))
    if task['keywords'].count(POLAR)!=1: raise ValueError('ONE_EXACT_STATIC_POLAR_KEYWORD_REQUIRED')
    task['keywords']=' '.join(task['keywords'].replace(POLAR,'').split())
    task['required_values']=[x for x in task['required_values'] if x!='static_polar_block']
    config['tasks']=[task]
    config['cost_probe_scope']='ONLY_PM7_B_WITHOUT_POLAR_NO_XTB_NO_HESS'
    if args.check:
        import ast
        ast.parse(Path(__file__).read_text()); ast.parse(Path(args.engine).read_text())
        assert POLAR not in task['keywords'] and '1SCF' in task['keywords'] and 'static_polar_block' not in task['required_values']
        assert len(config['tasks'])==1 and config['tasks'][0]['name']=='pm7_B'
        print(json.dumps({'status':'AST_SINGLE_B_NO_POLAR_PASS','QM_started':False,'LMDB_opened':False})); return 0
    if not all((args.panel,args.record_index,args.output,args.paired_pilot_root)): parser.error('Panel/index/output/paired pilot root required')
    if not 1<=args.per_stratum<=5 or args.wall_seconds<=150: parser.error('per-stratum must be 1..5 and wall-seconds >150')
    allocated=int(os.environ.get('SLURM_CPUS_PER_TASK',0))
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=allocated: raise ValueError('SLURM_16_EFFECTIVE_CPUS_REQUIRED')
    os.environ.update(engine.THREAD_ENV); os.environ['CUDA_VISIBLE_DEVICES']=''
    config['zstd_executable']=shutil.which(config['zstd_executable']) or config['zstd_executable']
    for field in ('mopac_executable','zstd_executable'):
        if not Path(config[field]).is_file() or not os.access(config[field],os.X_OK): raise ValueError('EXECUTABLE_UNAVAILABLE:'+field)
    scratch=Path(config['scratch_base']).absolute()
    if not scratch.is_dir() or str(scratch).startswith(('/share/','/home/')): raise ValueError('NODE_LOCAL_SCRATCH_REQUIRED')
    output=Path(args.output).absolute()
    if not output.is_relative_to(engine.PROJECT/'runs/phase1_dataset_rebuild_20261010'): raise ValueError('USE_THIS_PHASE_OUTPUT_ROOT')
    output.mkdir(parents=True,exist_ok=True)
    groups=engine.load_panel(args.panel,args.record_index,args.workers)
    strata={}; missing_minimum=[]
    for molecule,rows in groups:
        minimum=next((row for row in rows if row.get('molecule_lowest_energy_conformer') is True),None)
        if minimum is None: missing_minimum.append(molecule); continue
        strata.setdefault(minimum['size_stratum'],[]).append(minimum)
    selected=[row for stratum in sorted(strata) for row in sorted(strata[stratum],
              key=lambda r:hashlib.sha256((str(config['seed'])+'|POLAR_COST|'+r['record_id']).encode()).hexdigest())[:args.per_stratum]]
    if not selected: raise ValueError('NO_LOWEST_ORIGINAL_ENERGY_RECORDS')
    pilot_roots=[Path(path).absolute() for path in args.paired_pilot_root]
    pilot_metadata=[]
    for root in pilot_roots:
        path=root/'metadata.json'; metadata=json.loads(path.read_text())
        pilot_config=metadata['config']
        if pilot_config['seed']!=config['seed']: raise ValueError('PAIRED_PILOT_SEED_DIFFERS')
        if metadata['software']['executables']['mopac_executable']['sha256']!=engine.sha(config['mopac_executable']): raise ValueError('PAIRED_MOPAC_EXECUTABLE_DIFFERS')
        pilot_metadata.append({'root':str(root),'metadata_sha256':engine.sha(path),'actual_source_binding':metadata['input_and_implementation_binding']})
    items=[(row,paired_result(row,pilot_roots,engine)) for row in selected]
    binding={'panel_sha256':engine.sha(args.panel),'record_index_path':str(Path(args.record_index).absolute()),
             'record_index_bytes':Path(args.record_index).stat().st_size,'script_sha256':engine.sha(__file__),
             'engine_sha256':engine.sha(args.engine),'config_sha256':engine.sha(args.config),
             'getter_sha256':engine.sha(HERE/'wp4_mulliken_pairs_v2.py'),'parser_sha256':engine.sha(HERE/'wp4_parsers.py'),
             'selection_sha256':engine.stable_sha(items),'per_stratum':args.per_stratum,'paired_pilot_metadata':pilot_metadata}
    plan_path=Path(args.source_plan) if args.source_plan else engine.DEFAULT_PLAN
    sources=json.loads(plan_path.read_text())['sources']
    if len(sources)!=11: raise ValueError('ORIGINAL_ELEVEN_LMDB_SOURCES_REQUIRED')
    binding['source_plan_sha256']=engine.sha(plan_path)
    if args.panel_manifest: binding['panel_manifest_sha256']=engine.sha(args.panel_manifest)
    metadata_path=output/'metadata.json'
    if metadata_path.exists():
        metadata=json.loads(metadata_path.read_text())
        if not args.resume or metadata['binding']!=binding: raise ValueError('RESUME_BINDING_DIFFERS_OR_NOT_REQUESTED')
    else:
        snapshot=output/'source_snapshot'; snapshot.mkdir()
        for src,name in ((Path(__file__),'wp4_polar_cost_probe.py'),(Path(args.engine),'wp4_native_pilot_v2.py'),
                         (HERE/'wp4_parsers.py','wp4_parsers.py'),(HERE/'wp4_mulliken_pairs_v2.py','wp4_mulliken_pairs_v2.py')):
            shutil.copyfile(src,snapshot/name)
        engine.save_json(snapshot/'config.json',config)
        engine.save_json(metadata_path,{'scope':'PAIRED_POLAR_COST_PROBE_NOT_FULL_NATIVE_PILOT','binding':binding,
            'seed':config['seed'],'modified_only_keyword':POLAR,'config':config,'selected_records':selected,
            'nonempty_lowest_energy_strata':{k:len(v) for k,v in strata.items()},'molecules_without_known_minimum':missing_minimum,
            'python_logical_entry':sys.executable,'packages':{name:engine.package_version(name) for name in ('numpy','pyarrow','torch','rdkit','lmdb','duckdb')},
            'units':config['units'],'primary_call_recomputed':False,'hessian_or_other_calls':False,'LMDB_write':False,
            'selection_scope':'Deterministic at most five panel minima per stratum; no replacement when paired B failed/missing.',
            'timing_interpretation':'Small paired wall/CPU differences can be signed and noisy; report all observations, strata and HOF changes.'})
    deadline=time.time()+args.wall_seconds-120
    if os.environ.get('SLURM_JOB_END_TIME'): deadline=min(deadline,float(os.environ['SLURM_JOB_END_TIME'])-120)
    context=mp.get_context('spawn'); stop_event=context.Event()
    def stopping(signum,frame): stop_event.set()
    signal.signal(signal.SIGTERM,stopping); signal.signal(signal.SIGINT,stopping)
    receipts,errors=[],[]; started=time.monotonic()
    with futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,
            initializer=initialize,initargs=(sources,config,str(output),deadline,stop_event)) as pool:
        pending={pool.submit(record_worker,item):item[0]['record_id'] for item in items}
        for future in futures.as_completed(pending):
            try: receipts.append(future.result())
            except Exception as exc: errors.append({'record_id':pending[future],'error':type(exc).__name__+': '+str(exc)})
            engine.save_json(output/'progress.json',{'job_id':os.environ['SLURM_JOB_ID'],'planned_records':len(items),'closed_or_partial_records':len(receipts),'errors':errors})
    complete=sum(r['status']=='COMPLETE_WITH_RECORDED_OUTCOME' for r in receipts)
    summary={'status':'COST_PROBE_ATTEMPT_COMPLETE' if complete==len(items) and not errors else 'PARTIAL_RESUMABLE',
             'job_id':os.environ['SLURM_JOB_ID'],'hostname':socket.gethostname(),'seed':config['seed'],
             'planned_records':len(items),'completed_records':complete,'receipts':receipts,'errors':errors,
             'actual_worker_pids':sorted({r.get('resumed_worker_pid',r['worker_pid']) for r in receipts}),
             'elapsed_seconds':time.monotonic()-started,'stratified_paired_statistics':aggregates(receipts),
             'with_POLAR_QM_calls':0,'without_POLAR_QM_attempts':sum(r.get('actual_QM_attempts',0) for r in receipts),
             'Hessian_calls':0,'LMDB_written':False,'native_full_pilot_complete':False}
    engine.save_json(output/('job_'+os.environ['SLURM_JOB_ID']+'_summary.json'),summary)
    print(json.dumps({k:summary[k] for k in ('status','job_id','planned_records','completed_records','without_POLAR_QM_attempts')}))
    return 2 if errors else 0


if __name__=='__main__': raise SystemExit(main())
