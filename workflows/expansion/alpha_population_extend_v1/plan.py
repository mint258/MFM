"""Metadata builder for a fresh fixed1M DB clone plus strict accepted Common."""
import argparse
import json
import os
from pathlib import Path
import socket
from .. import alpha_common_followup_plans_v1 as H
from .run import baseline_binding,strict_addition,frame,reports_budget_value

MODULE='workflows.expansion.alpha_population_extend_v1.run'


def build(args):
    H.need(os.getuid()==1264,'Build actual Alpha source metadata as UID1264')
    acceptance=H.load(args.baseline_acceptance)
    receipt=H.load(H.verify(acceptance['producer_receipt_reference']))
    oldplan=H.load(H.verify(receipt['plan_reference']));old=Path(oldplan['output_directory'])
    adapter=H.load(args.adapter_deployment);stats=H.load(args.statistics_deployment)
    plan={**{k:oldplan[k] for k in ('endpoint','uid','runtime_profile_reference','workers','software_rss_budget_bytes',
      'sqlite_cache_bytes','batch_rows','minimum_node_available_bytes','minimum_free_bytes','output_scope_root',
      'output_cap_bytes','other_future_reserved_bytes','other_future_closed_scope_credit_reference','quota_authority','quota_snapshot')},
      'schema':'ALPHA_POPULATION_ONLY_STRICT_COMMON_EXTENSION_PLAN_V1',
      'scope_key':'alpha_population_only_strict_common_extension_v1',
      'analysis_version':args.analysis_version,'extension_policy':'STRICT_ADD_ONLY_FULL_ACCEPTED_COMMON_V1',
      'population_names':['pubchem_1m','v1_common'],'baseline_acceptance_reference':H.pin(args.baseline_acceptance),
      'baseline_population_reference':receipt['population_manifest_references']['pubchem_1m'],
      'baseline_scope_reference':H.pin(old/'analysis_scope.json'),'baseline_recipe_reference':receipt['functional_group_recipe_reference'],
      'baseline_database_path':str(old/'counted_statistics.sqlite'),
      'baseline_database_physical_frame':frame(old/'counted_statistics.sqlite'),
      'baseline_database_frame_observation':dict(hostname=socket.gethostname(),device_namespace='PLAN_HOST_LOCAL_ONLY'),
      'common_reference_manifest':H.pin(args.common_manifest),
      'adapter_deployment_reference':H.pin(args.adapter_deployment),'statistics_deployment_reference':H.pin(args.statistics_deployment)}
    future_review=getattr(args,'future_budget_review',None)
    if future_review is not None:
        budget=H.load(future_review)
        value=reports_budget_value(budget,plan)
        plan['original_other_future_reserved_bytes']=plan['other_future_reserved_bytes']
        plan['other_future_reserved_bytes']=value
        plan['all_future_storage_budget_review_reference']=H.pin(future_review)
    baseline_binding(plan);strict_addition(plan,H.load(old/'analysis_scope.json'))
    plan['code_references']=H.union(oldplan['code_references'],stats['code_references'],adapter['code_references'],[H.pin(__file__)])
    for ref in plan['code_references']:H.verify(ref)
    H.need(all(ref in plan['code_references'] for ref in receipt['source_references']),'Exact original source closure must be retained')
    plan['quota_authority']=dict(plan['quota_authority']);plan['quota_authority'].pop('publisher',None)
    plan['output_directory']=str(Path(plan['output_scope_root'])/(args.tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID'))
    H.need(not args.output_directory.exists(),'Fresh metadata plan output required')
    args.output_directory.mkdir(parents=True)
    template=args.output_directory/'population_extension_plan_template.json';H.save(template,plan)
    argv=[str(H.A/'software/pubchem_completion_20261103_venv/bin/python'),'-I','-B',str(args.launcher),
      '--template',str(template),'--base-root',str(H.BASE),'--entry',str(H.verify(adapter['entry_reference'])),
      '--module',MODULE,'--tag',args.tag,'--control-root',str(args.control_root),
      '--gluster-rpc-program',str(args.rpc_program)]
    batch=args.output_directory/'population_extension.sbatch'
    lines=[line for line in H.sbatch(argv,H.BASE,args.control_root,args.tag).splitlines() if not line.startswith('#SBATCH --time')]
    index=next(i for i,line in enumerate(lines) if line=='set -euo pipefail')
    lines.insert(index,'#SBATCH --time=0')
    unset='unset SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU'
    if unset not in lines:lines.insert(lines.index('set -euo pipefail')+1,unset)
    with batch.open('x',encoding='utf-8',newline='\n') as stream:stream.write('\n'.join(lines)+'\n')
    return H.save(args.output_directory/'build_receipt.json',dict(schema='ALPHA_POPULATION_STRICT_EXTENSION_PLAN_BUILD_V1',
      status='TEMPLATE_ONLY_NOT_SUBMITTED',template_reference=H.pin(template),sbatch_reference=H.pin(batch),
      baseline_database_SHA_pending_admitted_runtime=True,launcher_argv=argv,module=MODULE,tag=args.tag))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--common-manifest',required=True,type=Path)
    p.add_argument('--adapter-deployment',required=True,type=Path)
    p.add_argument('--output-directory',required=True,type=Path)
    p.add_argument('--baseline-acceptance',type=Path,default=H.B/'baseline_population_statistics_1885167_root_actual_v1.json')
    p.add_argument('--statistics-deployment',type=Path,default=H.D/'statistics_cache_bc4669c_actual_deployment.json')
    p.add_argument('--analysis-version',default='alpha_fixed1M_plus_fullCommon_population_only_20261103_v1')
    p.add_argument('--tag',default='baseline_plus_Common_population_tables_v1')
    p.add_argument('--launcher',type=Path,default=H.D/'node_launcher_rpc_v3_resume.py')
    p.add_argument('--rpc-program',type=Path,default=H.D/'gluster_readonly_rpc.py')
    p.add_argument('--control-root',type=Path,default=H.B/'node_epochs')
    p.add_argument('--future-budget-review',type=Path,help='Optional exact Root all-future reports reservation; original default unchanged')
    a=p.parse_args();print(json.dumps(build(a),sort_keys=True))


if __name__=='__main__':main()
