#!/usr/bin/env python3
"""B1 ESP and B3 matched Hessian tests using pinned native-v4 lifecycle."""
from __future__ import annotations
import argparse
import ast
import concurrent.futures as futures
import copy
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import signal
import sys
import time

sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent
OLD=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
NEW=HERE.parent
ENGINE=None
MODES=None
MODE=None
CURRENT_NATIVE=None
BASE_PM7=None
BASE_XTB=None
BASE_ARCHIVE=None

def import_path(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def config_template():
    config=json.loads((OLD/'scripts/wp4_native_v4_config.json').read_text())
    config.update(seed=20261011,timeout_seconds=900,per_file_limit_bytes=268435456,aux_sample_basis_points=10000)
    config['b1_tasks']=[{'name':'b1_ESP_alone','family':'mopac','keywords':'PM7 1SCF XYZ ESP AUX(PRECISION=6) CHARGE=0','required_values':['esp_charges_e']},
      {'name':'b1_ESP_WILLIAMS','family':'mopac','keywords':'PM7 1SCF XYZ ESP WILLIAMS AUX(PRECISION=6) CHARGE=0','required_values':['esp_charges_e']}]
    config['b3_tasks']=[{'name':'b3_xtb_hess','family':'xtb','args':['--gfn','2','--hess','--chrg','0','--uhf','0'],
        'timeout_seconds':3600,'required_values':['frequencies_cm_inverse','ZPE_Eh']},
      {'name':'b3_xtb_ohess','family':'xtb','args':['--gfn','2','--ohess','--chrg','0','--uhf','0'],
        'timeout_seconds':7200,'required_values':['frequencies_cm_inverse','ZPE_Eh','optimized_positions_A']},
      {'name':'b3_pm7_force','family':'mopac','keywords':'PM7 FORCE LET NOREOR XYZ AUX(PRECISION=6) THERMO(298,298) CHARGE=0',
        'timeout_seconds':7200,'required_values':['frequencies_cm_inverse']}]
    return config

def parse_pm7(directory,symbols,**kwargs):
    import numpy as np
    values=BASE_PM7(directory,symbols,**kwargs);directory=Path(directory)
    # AUX is also the authoritative numeric ESP fallback, while refusal/error
    # text and full atom-count checks remain active in the engine.
    if MODE=='esp' and values.get('esp_charges_e') is None and (directory/'input.aux').exists():
        original_read=ENGINE.PARSER.read_aux
        try:
            spec=import_path('small_aux',OLD/'scripts/wp4_parsers.py')
            aux,_=spec.read_aux(directory/'input.aux')
            candidate=aux.get('ELECTROSTATIC_POTENTIAL_CHARGES')
            if isinstance(candidate,list) and len(candidate)==len(symbols):values['esp_charges_e']=candidate;values['ESP_charge_source']='AUX actual numeric array'
        finally:ENGINE.PARSER.read_aux=original_read
    if MODE=='hessian' and (directory/'input.aux').exists():
        aux=MODES.force_aux(directory/'input.aux');freq=aux.get('VIB._FREQ:CM(-1)',[]);flat=aux.get('NORMAL_MODES',[])
        values['frequencies_cm_inverse']=freq or None
        values['PM7_ZPE_kcal_mol']=aux.get('ZERO_POINT_ENERGY:KCAL/MOL',[None])[0]
        if values.get('heat_of_formation_kcal_mol') is None:
            values['heat_of_formation_kcal_mol']=aux.get('HEAT_OF_FORMATION:KCAL/MOL',[None])[0]
        if values.get('heat_of_formation_kcal_mol') is None:
            text=(directory/'input.out').read_text(errors='replace')
            values['heat_of_formation_kcal_mol']=ENGINE.PARSER.scalar(text,r'HEAT OF FORMATION\s*[:=]\s*('+MODES.FLOAT+r')')
        values['FORCE_start_gradient_norm_kcal_mol_A']=aux.get('GRADIENT_NORM:KCAL/MOL/ANGSTROM',[values.get('gradient_norm_kcal_mol_A')])[0]
        stored=aux.get('ATOM_X:ANGSTROMS')
        if stored and len(stored)==3*len(symbols):
            actual=np.asarray(stored).reshape(len(symbols),3)
            values['FORCE_analysis_positions_A']=actual.tolist()
            values['FORCE_original_geometry_max_error_A']=float(np.max(np.abs(actual-CURRENT_NATIVE['coords'])))
        if freq and len(flat)==len(freq)*len(symbols)*3:
            modes=np.asarray(flat).reshape(len(freq),len(symbols),3)
            try:values['mode_analysis']=MODES.torsion_metrics(CURRENT_NATIVE['coords'],CURRENT_NATIVE['z'],modes,freq)
            except Exception as exc:values['mode_analysis']={'status':'MODE_CLASSIFICATION_FAILED','reason':str(exc)}
            np.savez_compressed(directory/'normal_modes.npz',frequencies_cm_inverse=np.asarray(freq),displacements=modes)
        else:values['mode_analysis']={'status':'FORCE_MODE_VECTOR_UNAVAILABLE','frequency_count':len(freq),'coefficient_count':len(flat)}
    return values

def parse_xtb(directory,symbols):
    import numpy as np
    values=BASE_XTB(directory,symbols);directory=Path(directory)
    coords=CURRENT_NATIVE['coords']
    if (directory/'xtbopt.xyz').exists():
        coords=MODES.xyz(directory/'xtbopt.xyz',symbols)
        values['optimized_positions_A']=coords.tolist()
        values['aligned_RMSD_all_atoms_A']=MODES.aligned_rmsd(CURRENT_NATIVE['coords'],coords)
        heavy=np.flatnonzero(CURRENT_NATIVE['z']>1)
        values['aligned_RMSD_heavy_atoms_A']=MODES.aligned_rmsd(CURRENT_NATIVE['coords'],coords,heavy) if len(heavy) else None
        values['raw_coordinate_RMSD_A']=float(np.sqrt(np.mean(np.sum((coords-CURRENT_NATIVE['coords'])**2,axis=1))))
    if (directory/'g98.out').exists():
        try:
            freq,modes=MODES.gaussian_modes(directory/'g98.out',symbols)
            values['parsed_mode_vector_count']=len(modes)
            np.savez_compressed(directory/'normal_modes.npz',frequencies_cm_inverse=freq,displacements=modes)
            values['mode_analysis']=MODES.torsion_metrics(coords,CURRENT_NATIVE['z'],modes,freq)
        except Exception as exc:values['mode_analysis']={'status':'MODE_CLASSIFICATION_FAILED','reason':str(exc)}
    else:values['mode_analysis']={'status':'NO_G98_MODE_FILE'}
    values['analysis_positions_A']=coords.tolist()
    return values

def archive_with_modes(paths,target,prefix):
    if not isinstance(paths,list):paths=list(paths)
    scratch=paths[0].parent
    if MODE=='hessian':
        for name in ('g98.out','vibspectrum','xtbopt.xyz','xtbhess.coord','normal_modes.npz','input.arc','input.aux','input.mop','input.xyz'):
            path=scratch/name
            if path.is_file() and path not in paths:paths.append(path)
    return BASE_ARCHIVE(paths,target,prefix)

def initialize(sources,config,output,mode,deadline,stop_event):
    global ENGINE,MODES,MODE,BASE_PM7,BASE_XTB,BASE_ARCHIVE
    output=Path(output);MODE=mode
    ENGINE=import_path('pinned_native_engine',output/'source_snapshot/wp4_native_pilot_v4.py')
    ENGINE.initialize(sources,config,str(output),str(output/'source_snapshot/wp4_parsers.py'),deadline,stop_event)
    MODES=import_path('b_modes',output/'source_snapshot/b_quantum_modes.py')
    BASE_PM7=ENGINE.PARSER.parse_mopac;BASE_XTB=ENGINE.PARSER.parse_xtb;BASE_ARCHIVE=ENGINE.output_archive
    ENGINE.PARSER.parse_mopac=parse_pm7;ENGINE.PARSER.parse_xtb=parse_xtb;ENGINE.output_archive=archive_with_modes

def worker(row):
    global CURRENT_NATIVE
    import pyarrow as pa
    import pyarrow.parquet as pq
    directory=ENGINE.OUTPUT/'records'/hashlib.sha256(row['record_id'].encode()).hexdigest()[:24]
    directory.mkdir(parents=True,exist_ok=True);receipt_path=directory/'receipt.json'
    identity=ENGINE.stable_sha(row)
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text())
        if receipt['input_identity_sha256']!=identity:raise ValueError('MANIFEST_COMPLETED_RECORD_DIFFERS')
        for key in ('parquet','archive'):
            ref=receipt.get(key)
            if ref and ENGINE.sha(ref['path'])!=ref['sha256']:raise ValueError('MANIFEST_COMPLETED_OUTPUT_DIFFERS')
        return {**receipt,'resumed_without_QM':True,'resumed_worker_pid':os.getpid()}
    tasks=ENGINE.CONFIG['b1_tasks'] if MODE=='esp' else ENGINE.CONFIG['b3_tasks']
    state_path=directory/'state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else {'input_identity_sha256':identity,'attempts':[]}
    if state['input_identity_sha256']!=identity:raise ValueError('MANIFEST_CHECKPOINT_DIFFERS')
    final={r['task']:r for r in state['attempts'] if r['status'] not in ENGINE.UNFINISHED}
    try:CURRENT_NATIVE=ENGINE.read_native(row);read_error=None
    except Exception as exc:CURRENT_NATIVE=None;read_error=str(exc)
    for task in tasks:
        if task['name'] in final:continue
        if ENGINE.STOP_EVENT.is_set() or time.time()>ENGINE.DEADLINE-30:return {'status':'PARTIAL_RESUMABLE','record_id':row['record_id'],'worker_pid':os.getpid()}
        if MODE=='esp' and task['name']=='b1_ESP_WILLIAMS' and final.get('b1_ESP_alone',{}).get('status')=='SUCCESS':
            result=ENGINE.skipped(row,CURRENT_NATIVE,task,'SKIPPED_BASELINE_ESP_SUCCESS')
        elif MODE=='esp' and task['name']=='b1_ESP_WILLIAMS' and 'ESP_D_ORBITAL_UNSUPPORTED' in final.get('b1_ESP_alone',{}).get('qc_codes',[]):
            result=ENGINE.skipped(row,CURRENT_NATIVE,task,'SKIPPED_D_BASIS_UNSUPPORTED_BY_BOTH_SURFACE_METHODS')
        elif read_error:
            result=ENGINE.skipped(row,None,task,'SOURCE_READ_FAILED');result['failure_reason']=read_error
        else:result=ENGINE.invoke(task,CURRENT_NATIVE,row,directory)
        values=result.get('values',{});freq=values.get('frequencies_cm_inverse')
        if isinstance(freq,list):
            values['imaginary_count_below_minus20']=sum(x<-20 for x in freq)
            values['imaginary_count_minus100_to_minus20']=sum(-100<=x<-20 for x in freq)
            values['imaginary_count_below_minus100']=sum(x<-100 for x in freq)
        result['analysis_scope']='B1_ESP_RETEST' if MODE=='esp' else 'B3_HESSIAN_MATCHED_COMPARISON'
        result['optimization_authorized_for_this_task_only']=task['name']=='b3_xtb_ohess'
        state['attempts'].append(result);ENGINE.save_json(state_path,state)
        if result['status'] in ENGINE.UNFINISHED:return {'status':'PARTIAL_RESUMABLE','record_id':row['record_id'],'worker_pid':os.getpid()}
        final[task['name']]=result
    if MODE=='hessian':
        baseline=final.get('b3_xtb_hess',{}).get('values',{}).get('energy_Eh')
        optimized=final.get('b3_xtb_ohess',{}).get('values',{}).get('energy_Eh')
        if baseline is not None and optimized is not None:final['b3_xtb_ohess']['values']['optimized_minus_original_energy_Eh']=optimized-baseline
    archive=ENGINE.compact_archives(state['attempts'],directory/'raw_outputs.tar.zst')
    parquet=directory/'results.parquet';pending=parquet.with_name(parquet.name+'.pending')
    pq.write_table(pa.Table.from_pylist([ENGINE.row_for_parquet(value) for value in final.values()],schema=ENGINE.parquet_schema(pa)),pending,compression='zstd');pending.replace(parquet)
    receipt={'status':'COMPLETE_WITH_RECORDED_OUTCOMES','record_id':row['record_id'],'molecule_id':row['molecule_id'],
      'input_identity_sha256':identity,'worker_pid':os.getpid(),'job_id':os.environ['SLURM_JOB_ID'],
      'statuses':{name:value['status'] for name,value in final.items()},'archive':archive,
      'parquet':{'path':str(parquet),'bytes':parquet.stat().st_size,'sha256':ENGINE.sha(parquet)},
      'sample_metadata':{key:row.get(key) for key in ('size_stratum','esp_failure_reason','original_imaginary_group','original_frequency_band','original_PM7_gradient_norm_kcal_mol_A')},
      'source_read_error':read_error,'actual_QM_attempts':sum(r.get('argv') is not None for r in state['attempts'])}
    ENGINE.save_json(receipt_path,receipt)
    for path in (directory/'partial_archives').glob('*'):
        if path.is_symlink() or not path.is_file() or path.stat().st_uid!=os.getuid():raise ValueError('NONOWNED_REDUNDANT_ARCHIVE')
        path.unlink()
    if (directory/'partial_archives').exists():(directory/'partial_archives').rmdir()
    state_path.unlink();return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=('esp','hessian'),required=True)
    p.add_argument('--sample');p.add_argument('--manifest');p.add_argument('--output');p.add_argument('--workers',type=int,default=16)
    p.add_argument('--wall-seconds',type=float,default=28800);p.add_argument('--resume',action='store_true');p.add_argument('--check',action='store_true');args=p.parse_args()
    config=config_template()
    if args.check:
        ast.parse(Path(__file__).read_text());ast.parse((HERE/'b_quantum_modes.py').read_text())
        assert '1SCF' not in config['b3_tasks'][2]['keywords'] and 'FORCE LET NOREOR' in config['b3_tasks'][2]['keywords']
        assert sum('--ohess' in task.get('args',[]) for task in config['b3_tasks'])==1
        print(json.dumps({'status':'B_QUANTUM_AST_CONFIG_PASS','mode':args.mode,'QM_calls':0,'LMDB_opened':False}));return 0
    if not all((args.sample,args.manifest,args.output)):p.error('sample/manifest/output required')
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):raise ValueError('SLURM_16_PARALLEL_WORKERS_REQUIRED')
    engine=import_path('setup_engine',OLD/'scripts/wp4_native_pilot_v4.py')
    os.environ.update(engine.THREAD_ENV);os.environ['CUDA_VISIBLE_DEVICES']=''
    import pyarrow.parquet as pq
    rows=pq.read_table(args.sample).to_pylist();manifest=json.loads(Path(args.manifest).read_text())
    expected=200 if args.mode=='esp' else 100
    if len(rows)!=expected or len({r['record_id'] for r in rows})!=expected:raise ValueError('MANIFEST_SAMPLE_COUNT_MISMATCH')
    name='esp_200.parquet' if args.mode=='esp' else 'hessian_100.parquet'
    if engine.sha(args.sample)!=manifest['samples'][name]['sha256']:raise ValueError('MANIFEST_SAMPLE_SHA_MISMATCH')
    output=Path(args.output).absolute()
    if output==NEW or not output.is_relative_to(NEW):raise ValueError('USE_NEW_SCREENING_OUTPUT_DIRECTORY')
    output.mkdir(parents=True,exist_ok=True)
    config['zstd_executable']=shutil.which(config['zstd_executable']) or config['zstd_executable']
    binding={'sample_sha256':engine.sha(args.sample),'manifest_sha256':engine.sha(args.manifest),'runner_sha256':engine.sha(__file__),
             'mode_module_sha256':engine.sha(HERE/'b_quantum_modes.py'),'engine_sha256':engine.sha(OLD/'scripts/wp4_native_pilot_v4.py'),
             'mode':args.mode,'config':config}
    metadata_path=output/'metadata.json'
    if metadata_path.exists():
        if not args.resume or json.loads(metadata_path.read_text())['binding']!=binding:raise ValueError('MANIFEST_RESUME_BINDING_DIFFERS')
    else:
        snapshot=output/'source_snapshot';snapshot.mkdir()
        for name in ('wp4_native_pilot_v4.py','wp4_parsers.py','wp4_mulliken_pairs_v3.py'):shutil.copyfile(OLD/'scripts'/name,snapshot/name)
        for name in ('b_quantum_runner.py','b_quantum_modes.py'):shutil.copyfile(HERE/name,snapshot/name)
        engine.save_json(metadata_path,{'scope':'B_QUANTUM_SCREENING_ANALYSIS_ONLY','binding':binding,'seed':config['seed'],
          'job_id':os.environ['SLURM_JOB_ID'],'sample_manifest':manifest,'LMDB_write':False,
          'original_geometry_policy':'Source coords unchanged; only --ohess produces an independent optimized copy.',
          'FORCE_policy':'No1SCF: official v23.0.3 dispatch would skip FORCE. LET permits given nonstationary geometry, NOREOR preserves frame.',
          'software':{name:{'path':config[name],'sha256':engine.sha(config[name])} for name in ('mopac_executable','xtb_executable','zstd_executable')},
          'official_sources':['https://openmopac.net/Manual/force.html','https://openmopac.net/Manual/let.html','https://openmopac.net/Manual/williams.html','https://xtb-docs.readthedocs.io/en/latest/hessian.html']})
    plan=json.loads(engine.DEFAULT_PLAN.read_text());sources=plan['sources']
    deadline=time.time()+args.wall_seconds-120
    if os.environ.get('SLURM_JOB_END_TIME'):deadline=min(deadline,float(os.environ['SLURM_JOB_END_TIME'])-120)
    context=mp.get_context('spawn');stop_event=context.Event();signal.signal(signal.SIGTERM,lambda signum,frame:stop_event.set())
    receipts=[];errors=[];started=time.monotonic()
    with futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,initializer=initialize,
            initargs=(sources,config,str(output),args.mode,deadline,stop_event)) as pool:
        pending={pool.submit(worker,row):row['record_id'] for row in rows}
        for future in futures.as_completed(pending):
            try:receipts.append(future.result())
            except Exception as exc:errors.append({'record_id':pending[future],'error':str(exc)})
            engine.save_json(output/'progress.json',{'planned_records':len(rows),'closed_or_partial_records':len(receipts),'errors':errors,'elapsed_seconds':time.monotonic()-started})
    complete=sum(r['status']=='COMPLETE_WITH_RECORDED_OUTCOMES' for r in receipts)
    summary={'status':'COMPLETE_WITH_RECORDED_OUTCOMES' if complete==len(rows) and not errors else 'PARTIAL_RESUMABLE',
      'mode':args.mode,'job_id':os.environ['SLURM_JOB_ID'],'planned_records':len(rows),'completed_records':complete,'receipts':receipts,
      'errors':errors,'elapsed_seconds':time.monotonic()-started,'actual_worker_pids':sorted({r.get('resumed_worker_pid',r['worker_pid']) for r in receipts}),
      'LMDB_written':False,'original_positions_modified':False}
    engine.save_json(output/('job_'+os.environ['SLURM_JOB_ID']+'_summary.json'),summary);print(json.dumps({k:summary[k] for k in ('status','mode','planned_records','completed_records','errors')}))
    return 1 if errors else 0
if __name__=='__main__':raise SystemExit(main())
