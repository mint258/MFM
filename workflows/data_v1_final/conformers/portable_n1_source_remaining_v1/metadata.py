"""Small Root plan/review/script preparation; no scientific bodies or submission."""
from __future__ import annotations
import argparse,copy,json,pathlib,shlex
from . import contract as C


def startup_proof(plan_path,ready_path,observed_path,out):
    """Root-only small adapter over actual observations, never runs commands.

    Root's existing endpoint controller obtains scheduler/storage observations;
    this function does not reuse a16/32CPU scope for a64CPU native parent.
    """
    import time
    from . import runtime as R
    plan=C.load_path(plan_path);C.review(plan);ready=C.load_path(ready_path);observed=C.load_path(observed_path)
    spec=C.endpoint(plan['endpoint']);now=time.time();job=str(ready['job_id'])
    C.need(ready['schema']=='ACTUAL_PORTABLE_REMAINING_GATE_READY_V4' and ready['endpoint']==spec
        and ready['node']==plan['node'] and ready['cpus']==plan['cpus'] and ready['plan_reference']==C.ref(plan_path),
        'EXACT_ACTUAL_NATIVE_READY_NOT_OLD_CONTROL16_SCOPE')
    C.need(observed['schema']=='ROOT_ACTUAL_PORTABLE_NODE_OBSERVATIONS_V4' and observed['reviewer']=='root'
        and observed['endpoint']==spec['address'] and observed['uid']==spec['uid'] and observed['node']==plan['node']
        and str(observed['job_id'])==job and 0<=now-observed['observed_unix_seconds']<=90
        and 0<=now-ready['observed_unix_seconds']<=110,'ROOT_FRESH_ACTUAL_ENDPOINT_OBSERVATIONS')
    C.need(observed['free_cpus_before_submission']>=plan['cpus'] and observed['partition']=='cpu'
        and observed['memory_limits_requested']is False and observed['memory_admission_evaluated']is False
        and observed['account_free_bytes']-plan['total_future_reserved_bytes']>=C.RESERVE,'ACTUAL_CPU_FREE_AND_ALL_FUTURE200GB')
    for ref in observed['raw_resource_references']:C.verify(ref,2<<20)
    C.need(len(observed['raw_resource_references'])>=3,'RAW_NODE_ALL_USERS_STORAGE_EVIDENCE_REQUIRED')
    j=R.fields(observed['job_metadata']);C.need(j['JobId']==job and j['JobState']=='RUNNING','ACTUAL_RUNNING_PARENT')
    refs={r['path']:r for r in [*plan['source_references'],C.ref(plan_path),plan['root_review_reference']]}
    if plan['role']=='run':
        cost_ref=observed['aggregate_cost_group_reference'];C.need(cost_ref['path']==plan['aggregate_cost_group_path'],'ACTUAL_POST_SUBMISSION_COST_GROUP_PATH')
        pair=C.load(cost_ref);C.need(pair['schema']=='ROOT_ACTUAL_N1_ALPHA_FINITE_COST_GROUP_V1'
            and pair['pair_registered_before_any_startup_proof']is True and pair['no_science_or_C0_claimed_by_pair_registration']is True
            and len(pair['native_parents'])==2 and {r['cpus'] for r in pair['native_parents']}=={16,64},'BOTH_ACTUAL_PARENTS_REGISTERED_BEFORE_EITHER_PROOF')
        for parent in pair['native_parents']:
            peer=C.load(parent['run_plan_reference']);C.review(peer);peer_ready=C.load(parent['ready_reference']);jpeer=R.fields(parent['actual_job_metadata'])
            C.need(str(peer_ready['job_id'])==str(parent['job_id'])==jpeer['JobId'] and peer_ready['plan_reference']==parent['run_plan_reference']
                and peer_ready['execution_not_admitted']is True and peer_ready['endpoint']['uid']==1264
                and peer_ready['cpus']==parent['cpus']==peer['cpus'] and peer_ready['node']==peer['node']==jpeer['NodeList']
                and jpeer['JobState']=='RUNNING' and jpeer['UserId']=='alpha(1264)' and int(jpeer['NumCPUs'])==parent['cpus']
                and R.duration(jpeer['TimeLimit'])==peer['wall_seconds']
                and 0<=now-parent['observed_unix_seconds']<=90 and 0<=now-peer_ready['observed_unix_seconds']<=110,
                'FRESH_TWO_READY_REAL_JOBID_CPU_WALL_BARRIER_NO_EARLY_SINGLE_SHARD_PROOF')
        refs[cost_ref['path']]=cost_ref
    for ref in refs.values():C.verify(ref,2<<20)
    value={'schema':'ROOT_PORTABLE_REMAINING_STARTUP_V4','endpoint_id':spec['id'],'uid':spec['uid'],
        'job_id':job,'node':plan['node'],'boot_id':ready['parent_identity']['boot_id'],
        'plan_reference':C.ref(plan_path),'root_review_reference':plan['root_review_reference'],
        'parent_identity':ready['parent_identity'],'observed_unix_seconds':observed['observed_unix_seconds'],
        'job_metadata':observed['job_metadata'],'allocation_elapsed_seconds':R.duration(j['RunTime']),
        'account_free_bytes':observed['account_free_bytes'],'memory_limits_requested':False,'memory_admission_evaluated':False,
        'actual_resource_observations_reference':C.ref(observed_path),
        'request':{'node':plan['node'],'cpus':plan['cpus'],'wall_seconds':plan['wall_seconds'],
            'kind':'conformer' if plan['role']=='run' else 'analysis','scope_key':C.SCOPE,
            'startup_proof_path':plan['startup_proof_path'],
            'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','execution_argv':plan['execution_argv'],
            'script_reference':C.ref(plan['script_path']),'source_references':list(refs.values()),
            'data_references':plan.get('data_references',[]),
            **{k:plan[k] for k in ('quota_provider_review_reference','quota_provider_identity_reference') if k in plan}}}
    if plan['role']=='run':value['request']['aggregate_cost_group_reference']=observed['aggregate_cost_group_reference']
    return C.save(out,value)


def review_template(plan_path,out):
    plan=C.load_path(plan_path);body={k:v for k,v in plan.items() if k!='root_review_reference'}
    return C.save(out,{'schema':'ROOT_DISJOINT_REMAINING_REVIEW_V4','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'plan_body_sha256':C.value_sha(body),'no_retry_or_claim_reset':True,'no_scientific_recipe_change':True,
        'concrete_plan_reference_before_root_review':C.ref(plan_path)})


def script(plan_path,out):
    plan=C.load_path(plan_path);C.review(plan)
    hours,remainder=divmod(plan['wall_seconds'],3600);minutes,seconds=divmod(remainder,60)
    C.need(plan['cpus'] in (16,32,64,96) and plan['job_name'].startswith('dv1_'),'EXACT_CPU_MENU_AND_OWN_JOB_NAME')
    text='\n'.join(['#!/bin/bash','#SBATCH --job-name='+plan['job_name'],'#SBATCH --partition=cpu',
        '#SBATCH --nodelist='+plan['node'],'#SBATCH --nodes=1','#SBATCH --ntasks=1',
        '#SBATCH --cpus-per-task='+str(plan['cpus']),f'#SBATCH --time={hours:02d}:{minutes:02d}:{seconds:02d}',
        '#SBATCH --no-requeue','#SBATCH --output='+str(pathlib.Path(plan['control_directory'])/'parent_%j.out'),
        'set -euo pipefail','export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1',
        'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1',
        'export PYTHONPATH='+shlex.quote(plan['pythonpath']), 'cd '+shlex.quote(plan['workdir']),
        'exec '+shlex.join([plan['python_executable'],'-B','-m','portable_n1_source_remaining_v1.gate','--plan',str(plan_path)]),''])
    return C.exclusive(out,text.encode())


def manifest_summary(path):
    value=C.load_path(path);C.need(value['schema']=='N1_SOURCE_FINITE_REMAINING_ASSIGNMENTS_V1','ACTUAL_CPU_FROZEN_N1_ASSIGNMENTS')
    return {'remaining':value['remaining_frozen'],'shards':[{'shard_id':x['shard_id'],'endpoint':x['endpoint']['id'],
        'molecules':x['molecules'],'submit_science':x['molecules']>0} for x in value['shards']],
        'empty_shards_must_not_be_submitted':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    q=s.add_parser('review-template');q.add_argument('--plan',type=pathlib.Path,required=True);q.add_argument('--output',type=pathlib.Path,required=True)
    q=s.add_parser('script');q.add_argument('--plan',type=pathlib.Path,required=True);q.add_argument('--output',type=pathlib.Path,required=True)
    q=s.add_parser('summary');q.add_argument('--assignments',type=pathlib.Path,required=True)
    q=s.add_parser('startup-proof')
    for name in ('plan','ready','observations','output'):q.add_argument('--'+name,type=pathlib.Path,required=True)
    a=p.parse_args()
    result=(manifest_summary(a.assignments) if a.action=='summary' else review_template(a.plan,a.output) if a.action=='review-template'
        else startup_proof(a.plan,a.ready,a.observations,a.output) if a.action=='startup-proof' else script(a.plan,a.output))
    print(json.dumps(result))


if __name__=='__main__':main()
