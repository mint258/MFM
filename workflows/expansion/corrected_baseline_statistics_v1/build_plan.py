"""Standalone metadata-only current1M/Common-clone plan builder. Never submits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys

VERSION='alpha-original502-generic3642-recovery-v1'
MODULE='workflows.expansion.corrected_baseline_statistics_v1.run'
REVIEWS={
 'baseline_review':(1918,'5217385cfa77f2702e181aa8d97be579b6289ce2a51e60334930ff9f7ae04f69'),
 'common_review':(3514,'30201799f051916d5117a4782479778a82fbf072ee59238a8472edf1973dceb9')}


def need(ok,message):
    if not ok:raise ValueError(message)


def pin(path):
    path=Path(path).absolute();s=path.lstat()
    need(stat.S_ISREG(s.st_mode)and s.st_uid==1264 and s.st_size<=2<<20,'Own small metadata/source only; large DB/bodies must wait for Guard')
    raw=path.read_bytes();t=path.lstat()
    need((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==(t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns,t.st_ctime_ns),'Stable metadata/source')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read(ref):
    need(pin(ref['path'])=={k:ref[k]for k in('path','bytes','sha256')},'Exact small source/authority pin required')
    return json.loads(Path(ref['path']).read_bytes())


def review(path,kind,job):
    ref=pin(path);need((ref['bytes'],ref['sha256'])==REVIEWS[kind],'Exact actual Root review required')
    body=read(ref);parent=body['actual_parent'];account=read(body['actual_accounting_reference'])
    need(body['reviewer']=='root'and parent['JobIDRaw']==job and parent['UID']=='1264'and parent['State']=='COMPLETED'
        and parent['ExitCode']=='0:0'and parent['endpoint']=='218.192.171.238:22'and parent in account['actual_parents'],'Actual reviewed Alpha parent C0')
    raw=account['raw_sacct_reference'];need(pin(raw['path'])=={k:raw[k]for k in('path','bytes','sha256')},'Exact actual raw accounting source')
    return ref,body


def save(path,body):
    with Path(path).open('x',encoding='utf-8')as stream:json.dump(body,stream,sort_keys=True,separators=(',',':'));stream.write('\n')
    return pin(path)


def build(a):
    need(os.getuid()==1264 and sys.flags.isolated,'Actual Alpha standalone Python-I metadata builder')
    baseline_ref,baseline=review(a.baseline_review,'baseline_review','1885183')
    common_ref,common=review(a.common_review,'common_review','1885178')
    qref=baseline['producer_receipt_reference'];q=read(qref);producer=read(common['producer_receipt_reference'])
    original=read(common['original_population_tables_receipt_reference'])
    need(q['actual_parent']['job_id']=='1885183'and q['population_version']==VERSION and q['source_pool_receipt']==baseline['source_pool_reference']
        and producer['profile_admission']['job_id']=='1885178','Actual profile job_id and explicit distinct population version')
    resources=read(pin(a.resource_template));old_plan=read(q['resource_plan'])
    refs={}
    extra=[pin(a.entry),pin(a.launcher),pin(a.rpc_program),pin(__file__)]+[pin(p)for p in Path(__file__).parent.glob('*.py')]
    for ref in resources['code_references']+old_plan['code_references']+original['source_references']+extra:
        read(ref)if ref['path'].endswith('.json')else need(pin(ref['path'])=={k:ref[k]for k in('path','bytes','sha256')},'Actual copied source pin')
        need(ref['path']not in refs or refs[ref['path']]==ref,'No conflicting source refs');refs[ref['path']]=ref
    budget_ref=pin(a.storage_budget);budget=read(budget_ref)
    need(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2'and budget['reviewer']=='root'
        and budget['scope_total_caps_bytes']['reports']==5000000000,'Actual reports aggregate budget')
    need(all(re.fullmatch('[A-Za-z0-9_.-]+',s)for s in(a.tag,a.node,a.partition))and a.workers>=16,'Actual fixed Slurm tokens/CPU declaration')
    need(not a.output_directory.exists(),'Fresh control output, preserve old templates')
    a.output_directory.mkdir(parents=True)
    keep=('runtime_profile_reference','quota_snapshot','quota_authority','other_future_closed_scope_credit_reference')
    plan={k:resources[k]for k in keep if k in resources};plan['quota_authority']=dict(plan['quota_authority']);plan['quota_authority'].pop('publisher',None)
    plan.update(schema='PUBCHEM_CORRECTED_BASELINE_STATISTICS_PLAN_V1',scope_key='corrected_baseline_population_statistics_v1',
        population_version=VERSION,analysis_version=VERSION+'-statistics-with-closed-Common-v1',endpoint='218.192.171.238:22',uid=1264,
        corrected_baseline_receipt_reference=qref,corrected_baseline_actual_reference=baseline_ref,common_statistics_actual_reference=common_ref,
        output_scope_root='/gfshome/alpha/pubchem_expansion_20261103/reports',output_directory='/gfshome/alpha/pubchem_expansion_20261103/reports/'+a.tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID',
        workers=a.workers,software_rss_budget_bytes=a.software_rss_budget_bytes,minimum_node_available_bytes=24<<30,sqlite_cache_bytes=1<<30,
        output_cap_bytes=budget['scope_total_caps_bytes']['reports'],other_future_reserved_bytes=budget['other_future_reserved_bytes_for_each_scope']['reports'],
        minimum_free_bytes=budget['minimum_free_after_all_future_bytes'],reviewed_storage_budget_reference=budget_ref,
        code_references=list(refs.values()),population_manifests=[],nearest_manifests=[],batch_rows=1024,
        original_common_recomputed=False,current_baseline_full_recount=True,resource_template_reference=pin(a.resource_template))
    template=a.output_directory/'plan_template.json';plan_ref=save(template,plan)
    argv=[str(a.python),'-I','-B',str(a.launcher),'--template',str(template),'--base-root',str(a.base),'--entry',str(a.entry),
        '--module',MODULE,'--tag',a.tag,'--control-root',str(a.control_root),'--gluster-rpc-program',str(a.rpc_program)]
    script='\n'.join(['#!/bin/bash','#SBATCH --partition='+a.partition,'#SBATCH --nodelist='+a.node,'#SBATCH --nodes=1',
        '#SBATCH --ntasks=1','#SBATCH --cpus-per-task='+str(a.workers),'#SBATCH --time=0','#SBATCH --job-name='+a.tag,
        '#SBATCH --output='+str(a.control_root/(a.tag+'_%j.out')),'set -euo pipefail','unset SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU',
        'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1','cd '+shlex.quote(str(a.base)),'exec '+shlex.join(argv),''])
    batch=a.output_directory/'statistics.sbatch';batch.write_text(script,encoding='utf-8')
    return save(a.output_directory/'build_receipt.json',dict(schema='PUBCHEM_CORRECTED_BASELINE_STATISTICS_TEMPLATE_BUILD_V1',
        status='ACTUAL_AUTHORITIES_BOUND_NOT_SUBMITTED',plan_template=plan_ref,sbatch=pin(batch),launcher_argv=argv,
        actual_baseline_review=baseline_ref,actual_Common_review=common_ref,large_data_or_DB_read=False,Common_recomputed=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in('baseline-review','common-review','resource-template','storage-budget','entry','launcher','rpc-program','python','base','control-root','output-directory'):
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--node',required=True);p.add_argument('--partition',default='cpu');p.add_argument('--tag',default='corrected_baseline_Common_statistics_v1')
    p.add_argument('--workers',type=int,default=16);p.add_argument('--software-rss-budget-bytes',type=int,default=48<<30)
    print(json.dumps(build(p.parse_args()),sort_keys=True),flush=True)


if __name__=='__main__':main()
