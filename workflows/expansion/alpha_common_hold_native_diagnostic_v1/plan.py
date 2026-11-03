"""Metadata-only native diagnostic plan and sbatch; no submit or kernel adoption."""
import argparse
import json
import os
from pathlib import Path
import shlex
from . import science,contracts
from ..alpha_runtime_v1 import common as Q

A=Path('/gfshome/alpha/codex_data_v1_20261026')
B=A/'control/pubchem_expansion_runtime_20261103'
D=A/'control/pubchem_completion_environment_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584'
MODULE='workflows.expansion.alpha_common_hold_native_diagnostic_v1.run'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--deployment',required=True,type=Path);p.add_argument('--output-directory',required=True,type=Path)
    p.add_argument('--audit-accounting',type=Path,default=B/'common_hold119_audit_1885169_root_actual_v1.json')
    p.add_argument('--rss-budget-bytes',type=int,default=16<<30)
    p.add_argument('--tag',default='common_hold119_native_diagnostic_v1')
    a=p.parse_args();Q.need(os.getuid()==1264 and '/' not in a.tag and '..' not in a.tag,'Actual Alpha metadata builder with separate simple tag')
    account=Q.load(a.audit_accounting);contracts.actual_c0(account,'1885169')
    audit_ref=account['producer_receipt_reference'];audit=Q.load(Q.verify(audit_ref));old=Q.load(Q.verify(audit['plan']))
    common=Q.load(Q.verify(audit['original_Common_receipt']));sourceplan=Q.load(Q.verify(common['plan']))
    deployment=Q.load(a.deployment);entry=Q.verify(deployment['entry_reference'])
    murcko=Q.reference(A/'chemprop_compatible_v2/lib/python3.11/site-packages/rdkit/Chem/Scaffolds/MurckoScaffold.py')
    Q.need(murcko['bytes']==4187 and murcko['sha256']==science.MURCKO_SHA,'Exact installed official scaffold source, no code change')
    keys=('endpoint','uid','workers','runtime_profile_reference','quota_snapshot','quota_authority','minimum_free_bytes',
      'minimum_node_available_bytes','output_scope_root','output_cap_bytes','other_future_reserved_bytes','other_future_closed_scope_credit_reference')
    plan={k:old[k] for k in keys if k in old}
    plan.update(schema='ALPHA_COMMON_HOLD119_NATIVE_DIAGNOSTIC_PLAN_V1',scope_key='alpha_common_hold_native_diagnostic_v1',
      workers=16,software_rss_budget_bytes=a.rss_budget_bytes,hold_audit_receipt_reference=audit_ref,
      hold_audit_actual_accounting_reference=Q.reference(a.audit_accounting),official_Murcko_source_reference=murcko,
      diagnostic_candidate_adoption_authorized=False,producer_source_deployment_reference=Q.reference(a.deployment),
      original_scientific_source_plan_reference=common['plan'])
    plan['quota_authority']=dict(plan['quota_authority']);plan['quota_authority'].pop('publisher',None)
    refs={}
    for ref in [*deployment['code_references'],*old['code_references'],*sourceplan['scientific_source_references'],murcko]:
        Q.need(ref['path'] not in refs or refs[ref['path']]==ref,'Conflicting actual source pins');Q.verify(ref);refs[ref['path']]=ref
    plan['code_references']=list(refs.values())
    plan['output_directory']=str(Path(plan['output_scope_root'])/(a.tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID'))
    Q.need(not a.output_directory.exists(),'Fresh metadata plan directory');a.output_directory.mkdir(parents=True)
    template=a.output_directory/'native_diagnostic_plan_template.json';Q.write(template,plan)
    argv=[str(A/'software/pubchem_completion_20261103_venv/bin/python'),'-I','-B',str(D/'node_launcher_rpc_v3_resume.py'),
      '--template',str(template),'--base-root',str(BASE),'--entry',str(entry),'--module',MODULE,'--tag',a.tag,
      '--control-root',str(B/'node_epochs'),'--gluster-rpc-program',str(D/'gluster_readonly_rpc.py')]
    batch=a.output_directory/'native_diagnostic.sbatch'
    text='\n'.join(['#!/bin/bash','#SBATCH --partition=cpu','#SBATCH --nodelist=sonmi1','#SBATCH --ntasks=1',
      '#SBATCH --cpus-per-task=16','#SBATCH --time=0','#SBATCH --job-name='+a.tag,'#SBATCH --output='+str(D/(a.tag+'_%j.out')),
      'set -euo pipefail','unset SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU','export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1',
      'cd '+shlex.quote(str(BASE)),'exec '+shlex.join(argv),''])
    with batch.open('x',encoding='utf-8',newline='\n') as stream:stream.write(text)
    print(json.dumps(dict(status='DIAGNOSTIC_TEMPLATE_ONLY_NOT_SUBMITTED',template=Q.reference(template),sbatch=Q.reference(batch),argv=argv),sort_keys=True))


if __name__=='__main__':main()
