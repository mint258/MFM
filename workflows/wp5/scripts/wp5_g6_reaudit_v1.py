#!/usr/bin/env python3
"""One metadata-only job reaudits the six completed R9 G6 cohorts. No QM/claims.
The original18 phase receipts, queues and permanent artifacts are read only.
"""
from __future__ import annotations
import argparse,ast,collections,concurrent.futures,hashlib,json,multiprocessing,os,socket,time,traceback
from pathlib import Path
from types import SimpleNamespace
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
JOBS={'12':'4513963','13':'4513964','14':'4513965','17':'4513966','18':'4513967','19':'4513968'}
ORIGINAL_HARNESS_SHA='d9d30d9693a6284a24b0df3471b530193dfed3fb7bcb946145f62d5ea919e4af'
AUDIT4_SHA='233e5b9e36dee8a6abdef38a73c5c45bd21c68560af40518e0bd5bc8b85d5b9b'
_C={}
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def save(path,data):
    with Path(path).open('x') as f:json.dump(data,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def ref(path):
    p=Path(path);return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def init(deadline,barrier):
    global _C
    _C={'deadline':deadline}
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);barrier.wait(timeout=180)
def check_reference(item):
    if time.time()>=_C['deadline']:raise TimeoutError('G6_REAUDIT_INTERNAL46H_BOUND')
    path=Path(item['path'])
    if item.get('bytes') is not None and path.stat().st_size!=item['bytes']:raise ValueError('REAUDIT_IMMUTABLE_BYTES_CHANGED:'+str(path))
    actual=sha(path)
    if actual!=item['sha256']:raise ValueError('REAUDIT_IMMUTABLE_SHA_CHANGED:'+str(path))
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':actual,'worker_pid':os.getpid()}
def cohort(item):
    import wp5_g6_current_policy_v4 as audit4
    if time.time()>=_C['deadline']:raise TimeoutError('G6_REAUDIT_INTERNAL46H_BOUND')
    a=SimpleNamespace(**item['options']);summary=audit4.audit(a,item['phases'],item['ids'],item['stats'],item['queue'])
    rows=audit4.queue_rows(item['queue'])
    if not all(r['state']=='COMPLETE' for r in rows):raise ValueError('REAUDIT_LATEST20_QUEUE_NOT_COMPLETE')
    result={'schema':'WP5_G6_READONLY_REAUDIT_V1','status':'G6_CURRENT_POLICY_FULL_CHAIN_PASSED','QM_started':False,
      'node':item['node'],'original_designed_node':{'compute-0-12':'compute-0-15','compute-0-13':'compute-0-16'}.get(item['node'],item['node']),
      'original_execution_job':item['job'],'molecules':20,**summary,'five_file_groups':sorted({r[4] for r in item['stats']}),
      'seven_size_strata':sorted({audit4.size(r[2]) for r in item['stats']}),'largest_pilot_eligible_total_atoms':item['largest'],
      'phase_completions':item['completion_refs'],'original_execution_run_refs':item['run_refs'],
      'original_execution_source_bindings':item['source_bindings'],'original_queue_before':item['queue_ref'],
      'original_selection':item['selection_ref'],'artificial_cutoff_completed':16,'resume_new_completed':4,'one_cleanup_max':True,
      'phase0_permanent_SHA_checked':True,'all18_original_phase_exports_checked':True,'original_scientific_task_outcomes_including_once_retry':item['scientific_calls'],
      'source_correction':'Queue receipt.context.execution_id; complete owner archive path, with original strict scientific/schema/raw/readback/concurrent16 checks unchanged',
      'old_harness':{'path':str(ROOT/'scripts/wp5_g6_current_policy_v3.py'),'sha256':ORIGINAL_HARNESS_SHA},
      'audit_source':{'path':str(ROOT/'scripts/wp5_g6_current_policy_v4.py'),'sha256':AUDIT4_SHA},
      'metadata_script':{'path':str(Path(__file__)), 'sha256':sha(__file__)},'new_QM':False,'worker_pid':os.getpid(),
      'resource_peaks':[info['resource_peaks'] for path,info in item['phases']],
      'staged_compressed_wire_bytes':[info.get('staged_compressed_wire_bytes') for path,info in item['phases']],
      'staged_uncompressed_wire_bytes':[info.get('staged_uncompressed_wire_bytes') for path,info in item['phases']],
      'final200_waived':False,'permanent_artifacts_overwritten':False,'queue_mutated':False}
    if ref(item['queue'])!=item['queue_ref']:raise ValueError('READ_ONLY_REAUDIT_QUEUE_CHANGED')
    save(a.out/'report.json',result)
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workers',type=int,default=24);p.add_argument('--out',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
    for name,expected in [('wp5_g6_current_policy_v3.py',ORIGINAL_HARNESS_SHA),('wp5_g6_current_policy_v4.py',AUDIT4_SHA)]:
        if sha(Path(__file__).with_name(name))!=expected:raise ValueError('BOUND_REAUDIT_SOURCE_DIFFERS:'+name)
    if a.check:ast.parse(Path(__file__).read_text());assert len(JOBS)==6;print('G6_READONLY_REAUDIT_SCOPE_AST_PASS_NO_QM_NO_QUEUE_MUTATION');return
    if not os.environ.get('SLURM_JOB_ID') or not 24<=a.workers<=int(os.environ.get('SLURM_CPUS_PER_TASK','0')):raise ValueError('ACTUAL24CPU_METADATA_REAUDIT_REQUIRED')
    out=a.out or ROOT/'gates/g6_reaudit'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
    original_refs={};items=[]
    def bind(reference):
        path=reference['path']
        if path in original_refs and original_refs[path]['sha256']!=reference['sha256']:raise ValueError('CONFLICTING_ORIGINAL_REFERENCE:'+path)
        original_refs[path]=reference
    try:
        for number,job in JOBS.items():
            node='compute-0-'+number;original=ROOT/'gates/g6_current'/node/('job_'+job)
            selection=original/'selected_molecules.json';s=json.loads(selection.read_text());m=s['molecules']
            ids=[r['molecule_id'] for r in m];stats=[(r['molecule_id'],r['records'],r['max_heavy_atoms'],r['max_total_atoms'],r['file_group']) for r in m]
            if len(ids)!=20 or len(set(ids))!=20:raise ValueError('ORIGINAL20_MOLECULE_COHORT_DIFFERS')
            phases=[];completion_refs=[];run_refs=[];source_bindings=[];scientific_calls=0
            first_options=None
            for phase in ('phase_0','phase_1','cleanup_once'):
                root=original/phase;path=root/'completion.json';info=json.loads(path.read_text());completion_refs.append(ref(path))
                if info['status']!='WP5_JOB_CLOSED' or info['error'] or not info['scratch_clean'] or any(w['error_count'] for w in info['workers']):raise ValueError('ORIGINAL_G6_PHASE_NOT_CLOSED:'+str(root))
                if any(not w['cleanup']['work_root_removed'] or not w['cleanup']['LMDB_handles_closed'] for w in info['workers']):raise ValueError('ORIGINAL_G6_WORKER_SCRATCH_OR_HANDLES_FAILED')
                expected_mols=16 if phase=='phase_0' else (4 if phase=='phase_1' else 1)
                if info['completed_molecules_this_run']!=expected_mols:raise ValueError('ORIGINAL16_PLUS4_PLUS_ONCE_RETRY_CHANGED')
                if phase=='phase_0' and len({w['pid'] for w in info['workers'] if w['completed']})<16:raise ValueError('ORIGINAL_DISTINCT16_COMPUTE_PID_PROOF_MISSING')
                invocation=json.loads((original/(phase+'_invocation.json')).read_text())
                if invocation['returncode']!=0:raise ValueError('ORIGINAL_G6_RUNNER_NONZERO')
                runpath=root/'run.json';run=json.loads(runpath.read_text());run_refs.append(ref(runpath))
                options=run['options'];source_bindings.append({'phase':phase,'bindings':options['source_bindings']})
                for r in options['source_bindings']:bind(r)
                if first_options is None:first_options=options
                for r in info['families']+[info['archive']]:bind(r)
                if info.get('canonical_record_attempts'):bind(info['canonical_record_attempts'])
                scientific_calls+=info['archive']['scientific_task_outcomes'];phases.append((root,info))
            nodeout=out/node;nodeout.mkdir()
            opts={'out':nodeout,'protocol':Path(first_options['protocol']),'dictionaries':Path(first_options['dictionaries']),
              'audit_membership':Path(first_options['audit_membership'])}
            queue=original/'queue.sqlite';items.append({'node':node,'job':job,'options':opts,'phases':phases,'ids':ids,'stats':stats,'queue':queue,
              'queue_ref':ref(queue),'selection_ref':ref(selection),'largest':s['largest_total_atoms'],'completion_refs':completion_refs,
              'run_refs':run_refs,'source_bindings':source_bindings,'scientific_calls':scientific_calls})
        ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(a.workers);deadline=time.time()+46*3600;pids=set()
        with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=init,initargs=(deadline,barrier)) as pool:
            checks=list(pool.map(check_reference,original_refs.values(),chunksize=1));pids.update(c['worker_pid'] for c in checks)
            if len(pids)<16:raise ValueError('EFFECTIVE_METADATA_WORKERS_BELOW16')
            reports=list(pool.map(cohort,items,chunksize=1))
        summary={'schema':'WP5_SIX_NODE_G6_READONLY_REAUDIT_V1','status':'G6_CURRENT_POLICY_FULL_CHAIN_PASSED','QM_started':False,
          'actual_metadata_job':os.environ['SLURM_JOB_ID'],'metadata_node':socket.gethostname(),'effective_worker_pids':sorted(pids),
          'original_jobs':JOBS,'original_phase_runs':18,'cohort_molecules_including_cross_node_repeats':120,
          'latest_records_including_cross_node_repeats':sum(r['records'] for r in reports),
          'latest_quantum_rows':sum(r['latest_quantum_rows'] for r in reports),
          'original_scientific_task_outcomes_including_once_retry':sum(r['original_scientific_task_outcomes_including_once_retry'] for r in reports),
          'historical_raw_rows':sum(r['historical_raw_rows'] for r in reports),'latest_required_raw_rows':sum(r['latest_required_raw_rows'] for r in reports),
          'latest_raw_rows':sum(r['latest_raw_rows'] for r in reports),'immutable_original_refs_checked':checks,
          'node_reports':[ref(out/r['node']/'report.json') for r in reports],'audit_source_sha256':AUDIT4_SHA,'metadata_script_sha256':sha(__file__),
          'queue_mutated':False,'original_permanent_files_overwritten':False,'new_science_executed':False,'final200_waived':False}
        save(out/'report.json',summary);print(json.dumps({'status':summary['status'],'report':str(out/'report.json')}))
    except BaseException:
        save(out/'failure.json',{'status':'NOT_PASS','QM_started':False,'error':traceback.format_exc(),'script_sha256':sha(__file__)})
        raise
if __name__=='__main__':main()
