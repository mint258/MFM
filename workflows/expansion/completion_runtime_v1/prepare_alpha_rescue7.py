"""Queue original exact-NN runtime on prefix7 after the high5 CPU slot closes."""
import pathlib,json,runpy,copy,subprocess,shlex,os
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026');B=A/'control/pubchem_expansion_runtime_20261103';D=A/'control/pubchem_completion_environment_20261103'
TAG='alpha_rescue7_20261105_v1'
def main():
    if os.getuid()!=1264:raise ValueError('Actual Alpha coordinator')
    runpy.run_path(str(A/'code/shard_guard_cadence_20261105_v2/entry.py'),run_name='_rescue_metadata')
    from workflows.expansion.alpha_runtime_v1 import common as Q
    from workflows.expansion.alpha_sharded_novelty_v1 import prepare_pipeline as P,partition,run
    native=subprocess.check_output(['sinfo','-N','-h','-o','%N %P %t %C'],text=True)
    pure=[line.split()for line in native.splitlines()if line.split()[1].rstrip('*')=='cpu']
    if any(int(row[3].split('/')[1])>=32 for row in pure):raise ValueError('Fresh pure-CPU32 slot exists; select it before this idle-host fallback')
    origin_path=B/'node_epochs/main_rescue_resume_20261105_v1_high5_job_1885264/plan.json'
    origin=Q.load(origin_path);source_ref=origin['source_deployment_reference'];source=Q.load(Q.verify(source_ref));entry=Q.verify(source['entry']);seed=copy.deepcopy(origin)
    removed=[]
    for key in ('execution_argv','runtime_existing_output_stage_reused','resume_output_directory','resume_previous_allocations','external_score_import_references','external_score_import_completed','launcher_startup_proof_reference','upstream_completed'):
        if key in seed:removed.append(key);seed.pop(key)
    seed.update(partition_id='rescue7',assigned_hash_buckets=['7'],scope_key='rescue7_exact209_ref196_20261105_v1',output_directory='/gfshome/alpha/pubchem_expansion_20261103/exact/producer_LAUNCHER_ASSIGN_REAL_JOB_ID',workers=32,worker_rss_cap_bytes=768<<20,parent_rss_cap_bytes=32<<30,software_rss_budget_bytes=64<<30,sql_memory_bytes=24<<30,spill_cap_bytes=48000000000)
    if partition.assignment(seed)!=['7']or set(partition.assignment(seed))&set(partition.assignment(origin)):raise ValueError('7 disjoint from original high5')
    low=Q.load(B/'node_epochs/main_rescue_resume_20261105_v1_low11_job_1885263/plan.json')
    if not set(partition.assignment(seed))<=set(partition.assignment(low)):raise ValueError('Rescue is within unchanged low11 logical scope')
    if seed['reference_manifest']['sha256']!='1ef86c58d193264af960b361a4d04691828b9402f95c77b6ddde7302840fa45e'or seed['filtered_pool_reference']!=low['filtered_pool_reference']:raise ValueError('Same actual full196 and closed209')
    if seed['workers']*seed['worker_rss_cap_bytes']+seed['parent_rss_cap_bytes']>seed['software_rss_budget_bytes']:raise ValueError('Private references/parent fit tree allowance')
    seed_path=B/(TAG+'_seed.json');script=B/(TAG+'.sbatch');py=A/'software/pubchem_completion_20261103_venv/bin/python';base=A/'code/pubchem_completion_20261103_497c584';filtered=Q.verify(seed['filtered_pool_reference'])
    args=[str(py),'-I','-B',str(entry),'workflows.expansion.alpha_sharded_novelty_v1.prepare_pipeline','--mode','nn','--seed',str(seed_path),'--upstream',str(filtered),'--entry',str(entry),'--tag',TAG]
    skip='if test -f '+shlex.quote(str(pathlib.Path(low['output_directory'])/'manifest.json'))+'; then echo RESCUE_NOT_RUN_ORIGINAL_LOW_MANIFEST_ALREADY_EXISTS; exit 0; fi'
    text='\n'.join(['#!/bin/bash','#SBATCH --partition=all','#SBATCH --nodelist=compute-0-2','#SBATCH --nodes=1','#SBATCH --ntasks=1','#SBATCH --cpus-per-task=32','#SBATCH --time=0','#SBATCH --job-name=pubchem_rescue7','#SBATCH --output='+str(B/'node_epochs'/(TAG+'_%j.out')),'set -euo pipefail','unset SBATCH_MEM SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU','export CUDA_VISIBLE_DEVICES=','export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1','cd '+shlex.quote(str(base)),skip,'exec '+shlex.join(args),''])
    subprocess.run(['bash','-n'],input=text,text=True,check=True)
    subprocess.run(['bash','-c','set -euo pipefail; '+next(x for x in text.splitlines()if x.startswith('unset '))],check=True)
    with script.open('x')as f:f.write(text)
    refs=list(source['code_references'])+[Q.reference(script),Q.reference(__file__)]
    if not all(Q.reference(m.__file__)in refs for m in(P,partition,run)):raise ValueError('All actual unchanged preparation/partition/science sources pinned')
    for ref in refs:Q.verify(ref)
    seed.update(code_references=refs,source_deployment_reference=source_ref,origin_resource_plan_reference=Q.reference(origin_path),resource_predecessor_job='1885264',rescue_is_additive_query_work_not_rank_input=True)
    probe=copy.deepcopy(seed)
    if P.prepare(probe,'nn',B,filtered,[])!=seed:raise ValueError('Actual original NN preparation preserves every declared seed field')
    seed_ref=Q.write(seed_path,seed)
    record=dict(schema='PUBCHEM_ALPHA_RESCUE7_PREPARED_V1',origin_resource_plan_reference=Q.reference(origin_path),seed_reference=seed_ref,script_reference=Q.reference(script),entry_reference=Q.reference(entry),source_deployment_reference=source_ref,actual_original_prepare_and_runtime_reused=True,original_low_and_high_bindings_and_running_jobs_modified=False,rank215_dependencies_modified=False,disjoint_from_high5=True,subset_of_original_low11=True,removed_consumed_resume_fields=removed,maximum_concurrent_goal_NN_CPU_after_predecessor=96,query_MD5_prefixes=['7'],complete_reference_records=1196122,original_partitions_still_authoritative=True,rescue_requires_closed_native_import_before_reuse=True,pure_CPU_native_observation=native,coordinator_source=Q.reference(__file__))
    prepared_ref=Q.write(D/(TAG+'_prepared.json'),record)
    job=subprocess.check_output(['sbatch','--parsable','--dependency=afterok:1885264',str(script)],text=True).strip().split(';')[0]
    if not job.isdigit():raise ValueError('Actual scheduler ID')
    intent=Q.write(D/(TAG+'_submitted_id.json'),dict(job_id=job,prepared_reference=prepared_ref))
    state=subprocess.check_output(['scontrol','show','job','-o',job],text=True)
    if not all(x in state for x in('UserId=alpha(1264)','JobState=PENDING','afterok:1885264','NumCPUs=32','ReqNodeList=compute-0-2')):raise ValueError('Actual deferred32CPU node/dependency readback')
    submission=Q.write(D/(TAG+'_submission.json'),dict(job_id=job,prepared_reference=prepared_ref,submitted_id_reference=intent,actual_scheduler_state=state,original_jobs_and_pending_rank_untouched=True))
    print(json.dumps(dict(job_id=job,submission_reference=submission,seed_reference=seed_ref,script_reference=Q.reference(script))),flush=True)
if __name__=='__main__':main()