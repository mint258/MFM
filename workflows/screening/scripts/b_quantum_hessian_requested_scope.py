#!/usr/bin/env python3
"""Validate retained B3 requests independently of an unrelated D4 parse error."""
from __future__ import annotations
import argparse
import collections
import concurrent.futures as futures
import copy
import hashlib
import importlib.util
import io
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time
sys.dont_write_bytecode=True
HERE=Path(__file__).absolute().parent
sys.path[:0]=['/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/docs/deps',
 '/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps']
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
REPORTER_SHA='738cf64c6464ace80c06ba1f5276a58f95988b27859aa9b5c6e9f6b5632c4575'
ELEMENTS={'H':1,'B':5,'C':6,'N':7,'O':8,'F':9,'Si':14,'P':15,'S':16,'Cl':17,'Se':34,'Br':35,'I':53}
BARRIER=None
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def initialize(barrier):
    global BARRIER
    BARRIER=barrier
def parse_xyz(data):
    import numpy as np
    lines=data.decode(errors='strict').splitlines();n=int(lines[0]);rows=[line.split() for line in lines[2:2+n]]
    if len(rows)!=n:raise ValueError('XYZ_ROW_COUNT_DIFFERS')
    symbols=[row[0] for row in rows];coords=np.asarray([[float(x) for x in row[1:4]] for row in rows])
    if coords.shape!=(n,3) or not np.isfinite(coords).all():raise ValueError('XYZ_COORDINATES_INVALID')
    return symbols,coords
def retained_files(case):
    calls=case['details'];by_archive=collections.defaultdict(list);found={}
    for call in calls:
        if call.get('archive'):by_archive[call['archive']['path']].append(call)
    wanted={'input.xyz','xtbopt.xyz','normal_modes.npz','process.out','input.out','vibspectrum'}
    for path,members in by_archive.items():
        expected=members[0]['archive']['sha256']
        if any(call['archive']['sha256']!=expected for call in members) or sha(path)!=expected:raise ValueError('MANIFEST_B3_ARCHIVE_SHA_DIFFERS')
        prefixes={call['archive']['member_prefix']:call for call in members}
        process=subprocess.Popen([shutil.which('zstd') or 'zstd','-d','-c',path],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
                for member in archive:
                    if not member.isfile() or '/' not in member.name:continue
                    prefix,name=member.name.rsplit('/',1);call=prefixes.get(prefix)
                    if call is None or name not in wanted:continue
                    data=archive.extractfile(member).read();digest=hashlib.sha256(data).hexdigest()
                    original=next((file for file in call.get('archived_files',[]) if file['name']==name),None)
                    if original and (original['sha256']!=digest or original['bytes']!=len(data)):raise ValueError('MANIFEST_B3_MEMBER_SHA_DIFFERS')
                    found[(call['task'],name)]=data
        finally:
            while process.stdout.read(1<<20):pass
            process.stdout.close();error=process.stderr.read();code=process.wait()
        if code:raise RuntimeError('ARCHIVE_DECODE_FAILED:'+error.decode(errors='replace'))
    return found
def validate_case(case):
    import numpy as np
    files=retained_files(case);result=copy.deepcopy(case)
    source_call=next(call for call in case['details'] if call['task']=='b3_xtb_hess')
    original_positions=np.asarray(source_call.get('values',{}).get('analysis_positions_A'))
    for call in result['details']:
        task=call['task'];values=call.get('values',{});n=call['natoms'];issues=[];evidence={}
        original_outcome={key:copy.deepcopy(call.get(key)) for key in ('status','failure_code','failure_reason','length_issues','missing_properties','qc_codes','returncode')}
        if call.get('returncode')!=0:issues.append('NONZERO_RETURN_CODE')
        if values.get('normal_end') is not True:issues.append('NORMAL_END_NOT_CONFIRMED')
        def scalar(name):
            value=values.get(name)
            if not isinstance(value,(int,float)) or not math.isfinite(value):issues.append('MISSING_OR_NONFINITE_'+name)
        def numeric_array(name,shape):
            try:array=np.asarray(values.get(name),dtype=float)
            except (TypeError,ValueError):issues.append('INVALID_'+name);return
            if array.shape!=shape or not np.isfinite(array).all():issues.append('INVALID_'+name)
        numeric_array('frequencies_cm_inverse',(3*n,))
        scalar('heat_of_formation_kcal_mol' if task=='b3_pm7_force' else 'energy_Eh')
        if task!='b3_pm7_force':
            numeric_array('IR_km_mol',(3*n,));scalar('ZPE_Eh');scalar('enthalpy_Eh')
            numeric_array('thermo_tot_H_cal_mol_Cp_cal_mol_K_S_cal_mol_K_S_J_mol_K',(4,))
        else:scalar('PM7_ZPE_kcal_mol');scalar('FORCE_start_gradient_norm_kcal_mol_A')
        text=files.get((task,'process.out' if task!='b3_pm7_force' else 'input.out'),b'').decode(errors='replace')
        if re.search(r'SCF DOES NOT CONVERGE|SCF NOT CONVERGED|SCF FAILED|UNABLE TO ACHIEVE SELF.CONSISTENCY|SCC IS NOT CONVERGED|SELF CONSISTENT CHARGE ITERATOR DID NOT CONVERGE',text,re.I):issues.append('RETAINED_SCF_FAILURE')
        try:
            symbols,coords=parse_xyz(files[(task,'input.xyz')])
            if len(symbols)!=n:issues.append('INPUT_ATOM_COUNT_DIFFERS')
            order_sha=hashlib.sha256(np.asarray([ELEMENTS[s] for s in symbols],dtype='<i8').tobytes()).hexdigest()
            if order_sha!=call['native_atom_order_sha256']:issues.append('INPUT_ATOM_ORDER_HASH_DIFFERS')
            if original_positions.shape!=(n,3):issues.append('SOURCE_POSITION_COUNT_DIFFERS')
            else:
                error=float(np.max(np.abs(coords-original_positions)));evidence['archived_input_original_coordinate_max_error_A']=error
                if error>1e-10:issues.append('SOURCE_INPUT_COORDINATES_DIFFER')
                if hashlib.sha256(original_positions.astype('<f8').tobytes()).hexdigest()!=call['native_coordinates_sha256']:issues.append('SOURCE_COORDINATE_HASH_DIFFERS')
            analysis_coords=coords
            if task=='b3_xtb_ohess':
                optimized_symbols,optimized=parse_xyz(files[(task,'xtbopt.xyz')])
                if optimized_symbols!=symbols:issues.append('OPTIMIZED_ATOM_ORDER_DIFFERS')
                numeric_array('optimized_positions_A',(n,3))
                if np.asarray(values.get('optimized_positions_A')).shape==(n,3):
                    error=float(np.max(np.abs(optimized-np.asarray(values['optimized_positions_A']))))
                    evidence['archived_optimized_values_max_error_A']=error
                    if error>1e-10:issues.append('OPTIMIZED_COORDINATE_VALUES_DIFFER')
                evidence['optimization_converged_message']=bool(re.search(r'GEOMETRY OPTIMIZATION CONVERGED',text,re.I))
                if not evidence['optimization_converged_message']:issues.append('OPTIMIZATION_CONVERGENCE_UNCONFIRMED')
                evidence['optimized_coordinate_sha256']=hashlib.sha256(optimized.astype('<f8').tobytes()).hexdigest()
                analysis_coords=optimized
            evidence['native_atom_order_sha256']=order_sha
        except Exception as exc:issues.append('GEOMETRY_EVIDENCE_UNAVAILABLE:'+str(exc))
        try:
            mode_bytes=files[(task,'normal_modes.npz')]
            with np.load(io.BytesIO(mode_bytes),allow_pickle=False) as modes:
                frequency=np.asarray(modes['frequencies_cm_inverse']);displacement=np.asarray(modes['displacements'])
                if frequency.ndim!=1 or len(frequency) not in (3*n,3*n-5,3*n-6) or displacement.shape!=(len(frequency),n,3) or not np.isfinite(displacement).all() or not np.isfinite(frequency).all():issues.append('NORMAL_MODE_ARRAY_INVALID')
                source_frequency=np.asarray(values.get('frequencies_cm_inverse'))
                if frequency.shape==source_frequency.shape:
                    difference=float(np.max(np.abs(frequency-source_frequency)));evidence['mode_vs_report_frequency_max_error_cm_inverse']=difference
                    if difference>0.05:issues.append('NORMAL_MODE_FREQUENCIES_DIFFER')
                elif source_frequency.shape==(3*n,) and len(frequency) in (3*n-5,3*n-6):
                    remaining=list(range(3*n));difference=0.
                    for value in frequency:
                        selected=min(remaining,key=lambda index:abs(source_frequency[index]-value))
                        difference=max(difference,float(abs(source_frequency[selected]-value)));remaining.remove(selected)
                    evidence['mode_vs_report_frequency_max_error_cm_inverse']=difference
                    evidence['mode_file_omitted_external_frequency_count']=len(remaining)
                    evidence['mode_file_omitted_frequency_max_abs_cm_inverse']=float(np.max(np.abs(source_frequency[remaining])))
                    if difference>0.05 or np.max(np.abs(source_frequency[remaining]))>20:issues.append('NORMAL_MODE_FREQUENCIES_DIFFER')
                else:issues.append('NORMAL_MODE_FREQUENCY_COUNT_DIFFERS')
                evidence['normal_mode_count']=len(frequency);evidence['mode_displacement_shape']=list(displacement.shape)
            evidence['normal_modes_npz_sha256']=hashlib.sha256(mode_bytes).hexdigest()
        except Exception as exc:issues.append('NORMAL_MODE_EVIDENCE_UNAVAILABLE:'+str(exc))
        collisions=[]
        if task=='b3_xtb_ohess':
            for line in text.splitlines():
                tokens=line.split()
                if len(tokens)!=8 or not tokens[0].isdigit() or not tokens[1].isdigit() or tokens[2] not in ELEMENTS:continue
                try:float(tokens[6])
                except ValueError:continue
                try:float(tokens[7])
                except ValueError:collisions.append(line.strip())
        evidence['legacy_D4_false_positive_distance_table_lines']=collisions
        lengths=set(call.get('length_issues',[]));allowed_nonrequested={'D4_atomic_C6_au','D4_atomic_alpha_bohr3'}
        scope_exclusion=(task=='b3_xtb_ohess' and original_outcome['status']=='PROPERTY_FAILED'
          and original_outcome['failure_code']=='ATOMIC_ARRAY_LENGTH_MISMATCH' and bool(lengths)
          and lengths<=allowed_nonrequested and not call.get('missing_properties') and bool(collisions))
        if original_outcome['status']!='SUCCESS' and not scope_exclusion:issues.append('ORIGINAL_OUTCOME_NOT_ELIGIBLE_FOR_NARROW_SCOPE_REVIEW')
        call['engine_outcome_preserved']=original_outcome
        call['requested_scope_review']={'status':'VALIDATED_REQUESTED_PROPERTIES' if not issues else 'REQUESTED_PROPERTIES_NOT_VALIDATED',
          'issues':list(dict.fromkeys(issues)),'evidence':evidence,'excluded_nonrequested_array_QC':sorted(lengths) if scope_exclusion else [],
          'explanation':'Legacy 8-column D4 candidate parsing falsely appends the max/min atom distance, then alpha conversion fails; this leaves a 2-value C6 array and blocks the valid 7-column fallback. B3 does not request D4 labels. Scope outcome requires independent retained geometry/order, mode, IR and thermo validation; original outcome is preserved.' if scope_exclusion else None}
        if not issues:
            call['status']='SUCCESS';call['actual_causal_reason']='SUCCESS'
            if scope_exclusion:
                values['D4_atomic_C6_au']=None;values['D4_atomic_alpha_bohr3']=None
                call['failure_code']=None;call['missing_properties']=[]
        else:call['status']='REQUESTED_SCOPE_FAILED';call['actual_causal_reason']='REQUESTED_SCOPE_VALIDATION_FAILED'
    result['requested_scope_worker_pid']=os.getpid();return result
def batch(cases):
    BARRIER.wait(timeout=120)
    return [validate_case(case) for case in cases]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-report',required=True);p.add_argument('--out',required=True)
    p.add_argument('--workers',type=int,default=16);p.add_argument('--check',action='store_true');args=p.parse_args()
    if args.check:
        import ast;ast.parse(Path(__file__).read_text());print('B3_REQUESTED_SCOPE_AST_PASS_NO_DATA');return 0
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):raise ValueError('SLURM_16_WORKERS_REQUIRED')
    if sha(HERE/'b_quantum_report.py')!=REPORTER_SHA:raise ValueError('MANIFEST_FROZEN_REPORTER_DIFFERS')
    frozen=load_module('frozen_B3_reporter',HERE/'b_quantum_report.py')
    source=json.loads(Path(args.input_report).read_text());cases=source['cases']
    if source['scope']!='B3_HESSIAN100_CLOSED_ANALYSIS' or len(cases)!=100 or len({case['record_id'] for case in cases})!=100:raise ValueError('MANIFEST_B3_CASE_COUNTS_DIFFER')
    root=HERE.parent/'b_quantum/hessian/job_4513528';metadata=json.loads((root/'metadata.json').read_text());manifest=metadata['sample_manifest']
    if sha(root/'metadata.json')!=source['run_metadata_sha256']:raise ValueError('MANIFEST_B3_RUN_METADATA_DIFFERS')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False);started=time.monotonic();context=mp.get_context('spawn')
    with futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,initializer=initialize,initargs=(context.Barrier(args.workers),)) as pool:
        checked=[case for result in pool.map(batch,[cases[i::args.workers] for i in range(args.workers)]) for case in result]
    checked_by_id={case['record_id']:case for case in checked}
    checked=[checked_by_id[case['record_id']] for case in cases]
    workers=sorted({case['requested_scope_worker_pid'] for case in checked})
    if len(workers)!=args.workers or len(checked)!=100:raise ValueError('MANIFEST_WORKER_OR_CASE_COUNTS_DIFFER')
    calls=[call for case in checked for call in case['details']]
    stats=frozen.task_statistics(calls);analysis=frozen.hessian_report(checked,manifest)
    for task,original in source['task_statistics'].items():
        if original['QM_wall_seconds_all_attempts']!=stats[task]['QM_wall_seconds_all_attempts']:raise ValueError('MANIFEST_SPENT_SERVICE_TIME_CHANGED')
    report={'scope':'B3_VALIDATED_REQUESTED_SCOPE_OFFLINE_REVIEW','job_id':os.environ['SLURM_JOB_ID'],'seed':20261011,
      'source_report':str(Path(args.input_report).absolute()),'source_report_sha256':sha(args.input_report),
      'script_sha256':sha(__file__),'frozen_reporter_sha256':REPORTER_SHA,'actual_worker_pids':workers,'elapsed_seconds':time.monotonic()-started,
      'original_task_statistics':source['task_statistics'],'task_statistics':stats,'analysis':analysis,'cases':checked,
      'scope_exclusions':dict(collections.Counter(call['task'] for call in calls if call['requested_scope_review']['excluded_nonrequested_array_QC'])),
      'requested_scope_issues':dict(collections.Counter(issue for call in calls for issue in call['requested_scope_review']['issues'])),
      'normal_mode_frequency_printing_tolerance_cm_inverse':0.05,'QM_calls':0,'LMDB_opened':False,'original_outputs_modified':False,
      'geometry_context':'Hess and FORCE retain original PM7 geometry. OHess has independent GFN2-optimized geometry; optimized properties cannot be substituted onto source coordinates.',
      'status_context':'SUCCESS in this report means independently validated B3 requested scope. Frozen engine statuses and QC are preserved in every case; unrelated D4 values are absent from the projection.'}
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps({'scope':report['scope'],'workers':len(workers),'scope_exclusions':report['scope_exclusions'],
      'requested_scope_issues':report['requested_scope_issues'],'task_statistics':stats}));return 0
if __name__=='__main__':raise SystemExit(main())
