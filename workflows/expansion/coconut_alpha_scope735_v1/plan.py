"""Metadata-only ledger plan builder; emits a reviewable sbatch and never submits."""
import argparse
import json
import os
from pathlib import Path
import shlex
from workflows.expansion.alpha_runtime_v1 import common as Q
A=Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103'
D=A/'control/pubchem_completion_environment_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584'
MODULE='workflows.expansion.coconut_alpha_scope735_v1.run'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--deployment',required=True,type=Path)
    p.add_argument('--inputs',required=True,type=Path)
    p.add_argument('--runtime-template',type=Path,default=B/'all11_native_fixture4_v1_plan_template.json')
    p.add_argument('--future-budget-review',type=Path)
    p.add_argument('--node',choices=('sonmi1','compute-0-1'),default='sonmi1')
    p.add_argument('--output-directory',required=True,type=Path)
    p.add_argument('--tag',default='coconut735_scope_approved_v1')
    a=p.parse_args()
    Q.need(os.getuid()==1264 and a.tag and all(c.isalnum() or c in '_-' for c in a.tag),'Actual Alpha safe metadata tag')
    old=Q.load(a.runtime_template);dep=Q.load(a.deployment);inputs=Q.load(a.inputs)
    required={'primary3_receipt_reference','primary3_actual_accounting_reference','native735_receipt_reference',
              'native735_actual_accounting_reference','structural735_actual_accounting_reference',
              'scope_proposal_reference','actual_user_approval_reference'}
    Q.need(set(inputs)==required,'Exact machine-derived original inputs, no injected runtime or source scope')
    for ref in inputs.values():Q.verify(ref)
    keys=('endpoint','uid','workers','runtime_profile_reference','quota_snapshot','quota_authority','minimum_free_bytes',
          'minimum_node_available_bytes','output_scope_root','output_cap_bytes','other_future_reserved_bytes',
          'other_future_closed_scope_credit_reference','software_rss_budget_bytes')
    plan={k:old[k] for k in keys if k in old}
    if a.future_budget_review:
        budget=Q.load(a.future_budget_review)
        Q.need(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and budget['reviewer']=='root'
               and budget['endpoint']=='218.192.171.238:22' and budget['uid']==1264,'Actual Root future storage budget')
        # The schema is explicit: caller supplies the reviewed reports value.
        plan['other_future_reserved_bytes']=budget['other_future_reserved_bytes_for_each_scope']['reports']
        plan['future_budget_review_reference']=Q.reference(a.future_budget_review)
        plan.pop('other_future_closed_scope_credit_reference',None)
    plan.update(inputs,schema='ALPHA_COCONUT735_APPROVED_SCOPE_LEDGER_PLAN_V1',
        scope_key='alpha_coconut735_approved_scope_ledger_v1',
        ledger_source_deployment_reference=Q.reference(a.deployment))
    refs={}
    for ref in [*old['code_references'],*dep['code_references']]:
        Q.verify(ref);Q.need(ref['path'] not in refs or refs[ref['path']]==ref,'Unique immutable source pins');refs[ref['path']]=ref
    plan['code_references']=list(refs.values());plan['workers']=16
    plan['software_rss_budget_bytes']=8<<30;plan['minimum_node_available_bytes']=24<<30
    plan['quota_authority']=dict(plan['quota_authority']);plan['quota_authority'].pop('publisher',None)
    plan['output_directory']=str(Path(plan['output_scope_root'])/(a.tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID'))
    Q.need(not a.output_directory.exists(),'Fresh output metadata only');a.output_directory.mkdir(parents=True)
    template=a.output_directory/'scope735_plan_template.json';Q.write(template,plan)
    argv=[str(A/'software/pubchem_completion_20261103_venv/bin/python'),'-I','-B',str(D/'node_launcher_rpc_v3_resume.py'),
          '--template',str(template),'--base-root',str(BASE),'--entry',str(Q.verify(dep['entry_reference'])),
          '--module',MODULE,'--tag',a.tag,'--control-root',str(B/'node_epochs'),
          '--gluster-rpc-program',str(D/'gluster_readonly_rpc.py')]
    batch=a.output_directory/'scope735.sbatch'
    with batch.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('\n'.join(['#!/bin/bash','#SBATCH --partition=cpu','#SBATCH --nodelist='+a.node,
          '#SBATCH --ntasks=1','#SBATCH --cpus-per-task=16','#SBATCH --time=0',
          '#SBATCH --job-name='+a.tag,'#SBATCH --output='+str(D/(a.tag+'_%j.out')),
          'set -euo pipefail','unset SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU',
          'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1',
          'cd '+shlex.quote(str(BASE)),'exec '+shlex.join(argv),'']))
    print(json.dumps(dict(status='PLAN_TEMPLATE_ONLY_NOT_SUBMITTED',module=MODULE,
         template=Q.reference(template),sbatch=Q.reference(batch)),sort_keys=True))


if __name__=='__main__':main()

