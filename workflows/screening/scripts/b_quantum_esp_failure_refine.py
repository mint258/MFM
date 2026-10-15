#!/usr/bin/env python3
"""16-worker refinement of stored B1 failure diagnostics; no QM or LMDB."""
from __future__ import annotations
import argparse
import collections
import concurrent.futures as futures
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
sys.dont_write_bytecode=True
sys.path[:0]=['/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/docs/deps',
 '/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps']
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
BARRIER=None
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def initialize(barrier):
    global BARRIER
    BARRIER=barrier
def original_log_sources(call):
    ref=call.get('archive')
    if not ref:return []
    if sha(ref['path'])!=ref['sha256']:raise ValueError('MANIFEST_OLD_ARCHIVE_SHA_DIFFERS')
    process=subprocess.Popen([shutil.which('zstd') or 'zstd','-d','-c',ref['path']],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    result=[]
    try:
        with tarfile.open(fileobj=process.stdout,mode='r|') as stream:
            for member in stream:
                if member.name not in (ref['member_prefix']+'/input.out',ref['member_prefix']+'/process.out'):continue
                content=stream.extractfile(member).read();text=content.decode(errors='replace')
                result.append({'file':member.name,'sha256':hashlib.sha256(content).hexdigest(),
                  'diagnostic_lines':[line.strip() for line in text.splitlines() if re.search(r'not work|SURFAC|RADIUS|not converg|SCF.*fail|error|keyword|TOO MANY NEIGHBORS|SIGABRT|SIGSEGV|received signal|free\(|malloc|double free|Backtrace',line,re.I)][-40:]})
    finally:
        while process.stdout.read(1<<20):pass
        process.stdout.close();error=process.stderr.read();code=process.wait()
    if code:raise RuntimeError('OLD_ARCHIVE_DECODE_FAILED:'+error.decode(errors='replace'))
    return result
def refine(chunk):
    BARRIER.wait(timeout=120)
    rows=[]
    for case in chunk:
        original=case['original_detail'];original['failure_text_sources']=original_log_sources(original)
        for call in [original,*case['details']]:
            text=' '.join(call.get('diagnostic_lines',[]))+' '+str(call.get('failure_reason',''))
            sources=call.get('failure_text_sources',[])
            text+=' '+' '.join(line for source in sources for line in source.get('diagnostic_lines',[]))
            old=call.get('actual_causal_reason') or call.get('failure_code') or call['status'];reason=old;diagnosis='STORED_CLASSIFICATION'
            if old.startswith('SKIPPED_') or call['status']=='SUCCESS':pass
            elif re.search(r'ESP method does not work with .d. orbitals',text,re.I):reason='D_ORBITAL_UNSUPPORTED';diagnosis='EXPLICIT_RETAINED_MOPAC_TEXT'
            elif re.search(r'VECTOR LENGTH OF ZERO IN SURFAC|RADIUS.*(?:IS ZERO|NOT DEFINED)|SUPPLY A VALUE IN SUBROUTINE SURFAC',text,re.I):reason='SURFACE_OR_UNDEFINED_RADIUS';diagnosis='EXPLICIT_RETAINED_MOPAC_TEXT'
            elif re.search(r'TOO MANY NEIGHBORS',text,re.I):reason='ESP_NEIGHBOR_LIMIT_EXCEEDED';diagnosis='EXPLICIT_RETAINED_MOPAC_TEXT'
            elif re.search(r'SCF DOES NOT CONVERGE|SCF DID NOT CONVERGE|SCF NOT CONVERGED|SCF FAILED|FAILURE TO ACHIEVE SCF|UNABLE TO ACHIEVE SELF.CONSISTENCY',text,re.I):reason='CONFIRMED_SCF_FAILURE';diagnosis='EXPLICIT_RETAINED_MOPAC_TEXT'
            elif isinstance(call.get('returncode'),int) and call['returncode']<0:
                reason='MOPAC_SIGNAL_ABORT';diagnosis='ACTUAL_NEGATIVE_RETURN_CODE_WITHOUT_MORE_SPECIFIC_DIAGNOSIS'
            elif old in ('QM_EXIT_OR_SCF_FAILED','MISSING_PROPERTY_WITHOUT_SPECIFIC_DIAGNOSIS'):
                reason='MISSING_ESP_WITH_UNRESOLVED_CAUSE';diagnosis='NO_CONFIRMED_SCF_DIAGNOSIS'
            rows.append({'record_id':case['record_id'],'molecule_id':case['molecule_id'],'size_stratum':case['size_stratum'],
              'elements':case['elements'],'task':call['task'],'status':call['status'],'returncode':call.get('returncode'),
              'stage':'original_native' if call is original else 'fresh_retest','previous_reason':old,'refined_reason':reason,'diagnosis_basis':diagnosis,
              'diagnostic_lines':[line for source in sources for line in source.get('diagnostic_lines',[])],
              'diagnostic_sources':sources,'worker_pid':os.getpid()})
    return rows
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',required=True);p.add_argument('--out',required=True)
    p.add_argument('--workers',type=int,default=16);p.add_argument('--check',action='store_true');args=p.parse_args()
    if args.check:
        import ast;ast.parse(Path(__file__).read_text());print('B1_FAILURE_REFINE_AST_PASS_NO_DATA');return 0
    if not os.environ.get('SLURM_JOB_ID') or not 16<=args.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK',0)):raise ValueError('SLURM_16_ACTUAL_WORKERS_REQUIRED')
    import pyarrow.parquet as pq
    report=json.loads(Path(args.report).read_text());cases=report['cases']
    if report['scope']!='B1_ESP200_CLOSED_ANALYSIS' or len(cases)!=200:raise ValueError('MANIFEST_B1_COUNTS_DIFFER')
    plan=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/b_quantum/plan')
    manifest=json.loads((plan/'manifest.json').read_text());sample=plan/'esp_200.parquet'
    if sha(sample)!=manifest['samples']['esp_200.parquet']['sha256']:raise ValueError('MANIFEST_OLD_DETAIL_SAMPLE_SHA_DIFFERS')
    original={row['record_id']:json.loads(row['original_esp_detail_json']) for row in pq.read_table(sample,columns=['record_id','original_esp_detail_json']).to_pylist()}
    if set(original)!={case['record_id'] for case in cases}:raise ValueError('MANIFEST_OLD_FRESH_CASE_IDS_DIFFER')
    for case in cases:case['original_detail']=original[case['record_id']]
    context=mp.get_context('spawn');barrier=context.Barrier(args.workers)
    with futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=context,initializer=initialize,initargs=(barrier,)) as pool:
        rows=[row for result in pool.map(refine,[cases[i::args.workers] for i in range(args.workers)]) for row in result]
    if len(rows)!=600 or len({row['worker_pid'] for row in rows})!=args.workers:raise ValueError('MANIFEST_CASE_WORKER_COUNTS_DIFFER')
    tasks={}
    for task in sorted({row['task'] for row in rows}):
        members=[row for row in rows if row['task']==task]
        tasks[task]={'reasons':dict(collections.Counter(row['refined_reason'] for row in members)),
          'returncodes':dict(collections.Counter(str(row['returncode']) for row in members)),
          'reason_element_scopes':{reason:dict(collections.Counter(str(z) for row in members if row['refined_reason']==reason for z in set(row['elements']))) for reason in sorted({row['refined_reason'] for row in members})}}
    output={'scope':'B1_RETAINED_FAILURE_REFINEMENT_ONLY','job_id':os.environ['SLURM_JOB_ID'],'seed':20261011,
      'source_report':str(Path(args.report).absolute()),'source_report_sha256':sha(args.report),'source_script_sha256':sha(__file__),
      'original_200_sample_sha256':sha(sample),'original_plan_sha256':sha(plan/'manifest.json'),
      'actual_worker_pids':sorted({row['worker_pid'] for row in rows}),'task_statistics':tasks,'cases':rows,
      'QM_calls':0,'LMDB_opened':False,'costs_and_outcomes_changed':False,
      'interpretation':'TOO MANY NEIGHBORS is a directly retained ESP error. A negative return code identifies a software signal termination, not confirmed SCF nonconvergence. No unobserved underlying scientific cause is inferred; standalone and fallback recovery remain zero.'}
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as file:json.dump(output,file,indent=2);file.write('\n')
    print(json.dumps({'scope':output['scope'],'workers':len(output['actual_worker_pids']),'task_statistics':tasks}));return 0
if __name__=='__main__':raise SystemExit(main())
