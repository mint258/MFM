"""Build the independent representation-validation plan without submission."""
import argparse
import json
import os
from pathlib import Path
import shlex
from ..alpha_runtime_v1 import common as Q

A=Path('/gfshome/alpha/codex_data_v1_20261026');B=A/'control/pubchem_expansion_runtime_20261103';D=A/'control/pubchem_completion_environment_20261103'
BASE=A/'code/pubchem_completion_20261103_497c584'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--deployment',required=True,type=Path);p.add_argument('--output-directory',required=True,type=Path)
    p.add_argument('--native-review',type=Path,default=B/'common_hold119_native_1885171_root_actual_v1.json')
    p.add_argument('--tag',default='generic_representation_repair_validation_v1');a=p.parse_args()
    Q.need(os.getuid()==1264 and '/' not in a.tag and '..' not in a.tag,'Actual Alpha metadata builder')
    review=Q.load(a.native_review);native=Q.load(Q.verify(review['producer_receipt_reference']));old=Q.load(Q.verify(native['plan']));deployment=Q.load(a.deployment)
    keys=('endpoint','uid','workers','runtime_profile_reference','quota_snapshot','quota_authority','minimum_free_bytes',
      'minimum_node_available_bytes','output_scope_root','output_cap_bytes','other_future_reserved_bytes','other_future_closed_scope_credit_reference','software_rss_budget_bytes')
    plan={k:old[k] for k in keys if k in old}
    plan.update(schema='ALPHA_GENERIC_REPRESENTATION_REPAIR_VALIDATION_PLAN_V1',scope_key='generic_representation_repair_validation_v1',
      native_diagnostic_receipt_reference=review['producer_receipt_reference'],native_diagnostic_actual_accounting_reference=Q.reference(a.native_review),
      repair_source_deployment_reference=Q.reference(a.deployment),Common_reference_release_authorized=False)
    refs={}
    for ref in [*old['code_references'],*deployment['code_references']]:
        Q.need(ref['path'] not in refs or refs[ref['path']]==ref,'Unique actual source pins');Q.verify(ref);refs[ref['path']]=ref
    plan['code_references']=list(refs.values());plan['quota_authority']=dict(plan['quota_authority']);plan['quota_authority'].pop('publisher',None)
    plan['output_directory']=str(Path(plan['output_scope_root'])/(a.tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID'))
    Q.need(not a.output_directory.exists(),'Fresh plan metadata');a.output_directory.mkdir(parents=True)
    template=a.output_directory/'repair_validation_plan_template.json';Q.write(template,plan)
    argv=[str(A/'software/pubchem_completion_20261103_venv/bin/python'),'-I','-B',str(D/'node_launcher_rpc_v3_resume.py'),
      '--template',str(template),'--base-root',str(BASE),'--entry',str(Q.verify(deployment['entry_reference'])),
      '--module','workflows.expansion.generic_representation_repair_v1.validate','--tag',a.tag,
      '--control-root',str(B/'node_epochs'),'--gluster-rpc-program',str(D/'gluster_readonly_rpc.py')]
    batch=a.output_directory/'repair_validation.sbatch'
    with batch.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('\n'.join(['#!/bin/bash','#SBATCH --partition=cpu','#SBATCH --nodelist=sonmi1','#SBATCH --ntasks=1',
          '#SBATCH --cpus-per-task=16','#SBATCH --time=0','#SBATCH --job-name='+a.tag,'#SBATCH --output='+str(D/(a.tag+'_%j.out')),
          'set -euo pipefail','unset SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU','export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1',
          'cd '+shlex.quote(str(BASE)),'exec '+shlex.join(argv),'']))
    print(json.dumps(dict(status='REPAIR_VALIDATION_TEMPLATE_ONLY_NOT_SUBMITTED',template=Q.reference(template),sbatch=Q.reference(batch)),sort_keys=True))


if __name__=='__main__':main()
