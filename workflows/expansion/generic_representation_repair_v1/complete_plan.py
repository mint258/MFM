"""Build new fullCommon completion only after actual repair validation review."""
import argparse
import json
import os
from pathlib import Path
import shlex
from ..alpha_runtime_v1 import common as Q
from ..exact_nn_cached_v1 import alpha_common_repaired as Authority

A=Path('/gfshome/alpha/codex_data_v1_20261026');B=A/'control/pubchem_expansion_runtime_20261103';D=A/'control/pubchem_completion_environment_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repair-validation-review',required=True,type=Path)
    p.add_argument('--deployment',required=True,type=Path);p.add_argument('--output-directory',required=True,type=Path)
    p.add_argument('--tag',default='fullCommon_representation_repaired_completion_v1');a=p.parse_args()
    Q.need(os.getuid()==1264 and '/' not in a.tag and '..' not in a.tag,'Actual Alpha metadata builder')
    review_ref=Q.reference(a.repair_validation_review);review=Q.load(a.repair_validation_review)
    validation,review=Authority.validated(review['producer_receipt'],review_ref)
    native=Q.load(Q.verify(validation['native_diagnostic_receipt_reference']));audit=Q.load(Q.verify(native['origin']['audit_receipt']))
    source_ref=audit['original_Common_receipt'];source=Q.load(Q.verify(source_ref));old=Q.load(Q.verify(source['plan']));deployment=Q.load(a.deployment)
    keys=('endpoint','uid','workers','runtime_profile_reference','quota_snapshot','quota_authority','minimum_free_bytes',
      'minimum_node_available_bytes','output_scope_root','output_cap_bytes','other_future_reserved_bytes','other_future_closed_scope_credit_reference')
    plan={k:old[k] for k in keys if k in old}
    plan.update(schema='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PLAN_V1',scope_key='full_common_generic_representation_repair_completion_v1',
      workers=16,software_rss_budget_bytes=16<<30,original_full_source_receipt_reference=source_ref,
      original_full_source_actual_accounting_reference=audit['original_actual_accounting_reference'],
      repair_validation_receipt_reference=review['producer_receipt'],repair_validation_review_reference=review_ref,
      completion_source_deployment_reference=Q.reference(a.deployment),Common_reference_acceptance_pending_new_C0=True)
    refs={}
    validation_plan=Q.load(Q.verify(validation['plan']))
    for ref in [*old['code_references'],*old['scientific_source_references'],*validation_plan['code_references'],*deployment['code_references']]:
        Q.need(ref['path'] not in refs or refs[ref['path']]==ref,'Unique exact sourcepins');Q.verify(ref);refs[ref['path']]=ref
    plan['code_references']=list(refs.values());plan['quota_authority']=dict(plan['quota_authority']);plan['quota_authority'].pop('publisher',None)
    plan['output_directory']=str(Path(plan['output_scope_root'])/(a.tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID'))
    Q.need(not a.output_directory.exists(),'Fresh completion metadata plan root');a.output_directory.mkdir(parents=True)
    template=a.output_directory/'fullCommon_completion_plan_template.json';Q.write(template,plan)
    argv=[str(A/'software/pubchem_completion_20261103_venv/bin/python'),'-I','-B',str(D/'node_launcher_rpc_v3_resume.py'),
      '--template',str(template),'--base-root',str(BASE),'--entry',str(Q.verify(deployment['entry_reference'])),
      '--module','workflows.expansion.generic_representation_repair_v1.complete','--tag',a.tag,
      '--control-root',str(B/'node_epochs'),'--gluster-rpc-program',str(D/'gluster_readonly_rpc.py')]
    batch=a.output_directory/'fullCommon_completion.sbatch'
    with batch.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('\n'.join(['#!/bin/bash','#SBATCH --partition=cpu','#SBATCH --nodelist=sonmi1','#SBATCH --ntasks=1',
          '#SBATCH --cpus-per-task=16','#SBATCH --time=0','#SBATCH --job-name='+a.tag,'#SBATCH --output='+str(D/(a.tag+'_%j.out')),
          'set -euo pipefail','unset SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU',
          'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1',
          'cd '+shlex.quote(str(BASE)),'exec '+shlex.join(argv),'']))
    print(json.dumps(dict(status='NEW_COMPLETION_TEMPLATE_ONLY_NOT_SUBMITTED',template=Q.reference(template),sbatch=Q.reference(batch)),sort_keys=True))


if __name__=='__main__':main()
