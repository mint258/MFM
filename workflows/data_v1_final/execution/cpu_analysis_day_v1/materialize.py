"""One actual Root input -> exact packed request review -> immutable request."""
import argparse,copy
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.registry import own_directory
from . import contract as C
Q=C.Q

def draft(path):
    v=Q.load(path);C.need(v['schema']=='ROOT_REQUESTED_ANALYSIS_DAY_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','ACTUAL_ROOT_PACKED_REQUEST')
    name=v['job_name'];C.need(type(name)is str and C.re.fullmatch('dv1_aday_[a-zA-Z0-9_]+',name),'SAFE_PACKED_NAME')
    root=C.BASE/name;C.need(not root.exists() and not any(p.is_symlink() for p in (root,*root.parents)),'ONE_FRESH_PACKED_REQUEST_DIRECTORY')
    r={k:copy.deepcopy(v[k]) for k in ('cpus','node','scope_key','scope_parameters','producer_plan_reference','estimated_peak_output_bytes','resource_authority_reference',
        'quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference','data_references')}
    r.update(schema=C.REQUEST,kind='analysis',pilot=False,partition='cpu',job_name=name,requested_cpus=r['cpus'],
        wall_seconds=C.WALL,memory_policy=C.MEMORY,exclusive_requested=False,workdir=str(Q.PROJECT),startup_wait_seconds=120,
        startup_proof_path=str(root/'proof.json'),execution_argv=[Q.PY,'-B','-m',C.SCOPES[r['scope_key']],'--plan',r['producer_plan_reference']['path'],'--startup-proof',str(root/'proof.json')])
    C.shape(r);C.resources(r);own_directory(root)
    script=root/'parent.sbatch';text=f'''#!/bin/bash
#SBATCH --job-name={name}
#SBATCH --partition=cpu
#SBATCH --nodelist={r['node']}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={r['cpus']}
#SBATCH --time=24:00:00
#SBATCH --output={root}/parent_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH={C.REPO}:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
cd {Q.PROJECT}
exec {Q.PY} -B -m workflows.data_v1_final.execution.cpu_analysis_day_v1.launch --request {root}/request.json
'''
    with script.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    r['script_reference']=Q.pin(script)
    refs=[*v['source_references'],*(Q.pin(p) for p in C.sources()),Q.pin(path),r['producer_plan_reference'],r['resource_authority_reference'],
        r['root_carveout_review_reference'],r['quota_provider_review_reference'],r['quota_provider_identity_reference'],
        *C.Provider.references(r['quota_provider_review_reference'])]
    a=C.authority(r['resource_authority_reference']);refs.append(a['persistent_previous_user_cpu_memory_authority_reference'])
    r['source_references']=C.unique(refs);bodies=[C.O.pin(x,small=False) for x in r['data_references']]
    C.need(not {x['path'] for x in bodies}&{x['path'] for x in refs},'DATA_SOURCE_DISJOINT_NO_LOGIN_DATA_HASH')
    for ref in r['source_references']:C.need(Q.pin(ref['path'])==ref,'ACTUAL_CURRENT_SMALL_SOURCE_PARENT_REF')
    template={'schema':'ROOT_EXACT_ANALYSIS_DAY_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,'request_fields':r,
        'one86400_parent_all_source_preflight_in_parent':True,'old_science_seeds_once_and_quality_unchanged':True,
        'no_fake_child_Slurm_C0':True,'all_current_future_reserves_counted_once':True}
    tr=Q.write_new(root/'review.template.json',template)
    return Q.write_new(root/'draft.json',{'schema':'ANALYSIS_DAY_DRAFT_V1','template_reference':tr,'request_fields':r,
        'submitted':False,'scientific_DATA_opened_or_hashed':False})

def finalize(path,review_path):
    d=Q.load(path);C.need(d['schema']=='ANALYSIS_DAY_DRAFT_V1','EXACT_PACKED_DRAFT');template=C.meta(d['template_reference'])
    rr=Q.pin(review_path);review=C.meta(rr);C.need(rr!=d['template_reference'] and review['status']=='APPROVED' and review['reviewer']=='root','INDEPENDENT_CONCRETE_ROOT_REVIEW')
    for k,v in template.items():
        if k not in ('status','reviewer'):C.need(C.O.same(review[k],v),'EXACT_PACKED_REVIEW_FIELD:'+k)
    r=copy.deepcopy(d['request_fields']);r['root_review_reference']=rr;r['source_references']=C.unique([*r['source_references'],rr]);C.validate(r)
    return Q.write_new(Path(r['startup_proof_path']).parent/'request.json',r)

def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=p.parse_args();print(draft(a.request) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
