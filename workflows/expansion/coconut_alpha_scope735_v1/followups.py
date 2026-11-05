"""Emit future impact/manifest/index plans from real closed inputs; never submit."""
import argparse
import json
import os
from pathlib import Path
import shlex
from workflows.expansion.alpha_runtime_v1 import common as Q
from workflows.expansion.coconut_alpha_cached735_v1 import support as S
from .plan import A,B,D,BASE
from .run import native_parent


def triple(r):return {k:r[k] for k in ('path','bytes','sha256')}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('impact','source-manifest','index'),required=True)
    p.add_argument('--deployment',type=Path,action='append',required=True)
    p.add_argument('--runtime-template',type=Path,default=B/'all11_native_fixture4_v1_plan_template.json')
    p.add_argument('--future-budget-review',type=Path)
    p.add_argument('--node',choices=('sonmi1','compute-0-1'),default='compute-0-1')
    p.add_argument('--tag',required=True);p.add_argument('--output-directory',type=Path,required=True)
    p.add_argument('--ledger-receipt',type=Path);p.add_argument('--ledger-accounting',type=Path)
    p.add_argument('--corrected-pool',type=Path)
    p.add_argument('--root-coconut-acceptance',type=Path);p.add_argument('--source-manifest',type=Path)
    p.add_argument('--inventory',type=Path,default=A/'inputs/decontamination_main_origin_20261103/inventory.json')
    p.add_argument('--transport-review',type=Path,default=B/'all10_replicas_1885168_root_actual_v1.json')
    a=p.parse_args()
    Q.need(os.getuid()==1264 and a.tag and all(c.isalnum() or c in '_-' for c in a.tag),'Actual Alpha metadata-only plan builder')
    old=Q.load(a.runtime_template)
    keys=('endpoint','uid','workers','runtime_profile_reference','quota_snapshot','quota_authority','minimum_free_bytes',
          'minimum_node_available_bytes','output_scope_root','output_cap_bytes','other_future_reserved_bytes',
          'other_future_closed_scope_credit_reference','software_rss_budget_bytes')
    plan={k:old[k] for k in keys if k in old}
    plan['workers']=16;plan['software_rss_budget_bytes']=8<<30;plan['minimum_node_available_bytes']=24<<30
    plan['duckdb_memory_bytes']=6<<30;plan['sqlite_cache_bytes']=1<<30
    if a.future_budget_review:
        budget=Q.load(a.future_budget_review)
        Q.need(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and budget['reviewer']=='root'
            and budget['endpoint']=='218.192.171.238:22' and budget['uid']==1264,'Actual Root all-scope storage')
        scope=Path(plan['output_scope_root']).name
        Q.need(scope in budget['other_future_reserved_bytes_for_each_scope'],'Existing actual scope budget')
        plan['other_future_reserved_bytes']=budget['other_future_reserved_bytes_for_each_scope'][scope]
        plan['future_budget_review_reference']=Q.reference(a.future_budget_review)
        plan.pop('other_future_closed_scope_credit_reference',None)
    refs={r['path']:r for r in old['code_references']};dep=None
    for path in a.deployment:
        dep=Q.load(path)
        for r in dep['code_references']:
            Q.need(r['path'] not in refs or refs[r['path']]==r,'Unambiguous source bodies')
            Q.verify(r);refs[r['path']]=r
    plan['code_references']=list(refs.values())
    if a.mode=='impact':
        Q.need(a.ledger_receipt and a.ledger_accounting and a.corrected_pool,'Actual ledger/accounting/corrected pool required')
        ledger=S.load(Q.reference(a.ledger_receipt))
        native_parent(S.load(Q.reference(a.ledger_accounting)),Q.reference(a.ledger_receipt),ledger['profile_admission']['job_id'])
        from workflows.expansion.pubchem_generic_recovery_overlay_v1 import reader
        reader.validate_header(S.load(Q.reference(a.corrected_pool)))
        plan.update(schema='ALPHA_COCONUT735_CORRECTED_POOL_IMPACT_PLAN_V1',
            scope_key='alpha_coconut735_corrected_pool_impact_v1',
            ledger_receipt_reference=Q.reference(a.ledger_receipt),ledger_actual_accounting_reference=Q.reference(a.ledger_accounting),
            source_pool_receipt_reference=Q.reference(a.corrected_pool))
        module='workflows.expansion.coconut_alpha_scope735_v1.impact'
    else:
        inventory=Q.load(a.inventory);transport=Q.load(a.transport_review)
        Q.need(transport['status']=='ACCEPTED_INPUT_BYTE_TRANSPORT_ONLY'
            and transport['logical_refs']==511 and transport['all_Main_origin_refs_preserved'] is True,
            'Actual original511 all10-source replicas, not Common')
        ready=inventory['original_ready9_manifest_reference'];mol=inventory['molnet_acceptance_reference']
        plan.update(ready9_manifest_reference=ready,root_molnet21_acceptance_reference=mol,
                    parent_transport_manifest=transport['parent_transport_manifest'])
        if a.mode=='source-manifest':
            Q.need(a.root_coconut_acceptance,'Actual Root735 coverage adoption required, not pending ledger')
            coco=Q.load(a.root_coconut_acceptance)
            Q.need(coco['schema']=='ROOT_COCONUT735_ACTUAL_CONSERVATIVE_COVERAGE_ACCEPTANCE_V1'
                and coco['status']=='APPROVED_FOR_CLOSED735_CONSERVATIVE_EXCLUSION_V3'
                and coco['reviewer']=='root','Existing V3 actual Root acceptance')
            plan.update(schema='ALPHA_ALL11_SOURCE_MANIFEST_PLAN_V3',scope_key='alpha_all11_manifest_v3',
                        root_coconut735_acceptance_reference=Q.reference(a.root_coconut_acceptance))
            seeds=[ready,mol,plan['root_coconut735_acceptance_reference']]
            module='workflows.expansion.alpha_all11_index_v3.manifest'
        else:
            Q.need(a.source_manifest,'Actual composed source manifest required')
            manifest=Q.load(a.source_manifest)
            Q.need(manifest['schema']=='expansion_decontamination_sources_with_constraints_v3'
                and manifest['prior_manifest_reference']==ready
                and manifest['root_molnet21_acceptance_reference']==mol
                and len(manifest['sources'])==11,'Exact complete existing all11 source manifest')
            plan.update(schema='ALPHA_ALL11_EXCLUSION_INDEX_PLAN_V3',scope_key='alpha_all11_index_v3',
                        source_manifest_reference=Q.reference(a.source_manifest))
            seeds=[ready,mol,plan['source_manifest_reference']]
            module='workflows.expansion.alpha_all11_index_v3.run'
        from .dependencies import Collector,discover
        if a.mode=='source-manifest':cocoref=plan['root_coconut735_acceptance_reference']
        else:cocoref=manifest['root_coconut735_acceptance_reference']
        collector=Collector(plan['parent_transport_manifest'])
        plan['data_references'],plan['metadata_reference_discovery']=discover(collector,ready,mol,cocoref,
            plan.get('source_manifest_reference'))
    plan['quota_authority']=dict(plan['quota_authority']);plan['quota_authority'].pop('publisher',None)
    plan['output_directory']=str(Path(plan['output_scope_root'])/(a.tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID'))
    Q.need(not a.output_directory.exists(),'Fresh plan metadata only');a.output_directory.mkdir(parents=True)
    template=a.output_directory/(a.mode+'_plan_template.json');Q.write(template,plan)
    argv=[str(A/'software/pubchem_completion_20261103_venv/bin/python'),'-I','-B',str(D/'node_launcher_rpc_v3_resume.py'),
        '--template',str(template),'--base-root',str(BASE),'--entry',str(Q.verify(dep['entry_reference'])),
        '--module',module,'--tag',a.tag,'--control-root',str(B/'node_epochs'),
        '--gluster-rpc-program',str(D/'gluster_readonly_rpc.py')]
    batch=a.output_directory/(a.mode+'.sbatch')
    with batch.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('\n'.join(['#!/bin/bash','#SBATCH --partition=cpu','#SBATCH --nodelist='+a.node,
          '#SBATCH --ntasks=1','#SBATCH --cpus-per-task=16','#SBATCH --time=0',
          '#SBATCH --job-name='+a.tag,'#SBATCH --output='+str(D/(a.tag+'_%j.out')),
          'set -euo pipefail','unset SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU',
          'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1',
          'cd '+shlex.quote(str(BASE)),'exec '+shlex.join(argv),'']))
    print(json.dumps(dict(status='SOURCE_ONLY_NOT_SUBMITTED',module=module,
        template=Q.reference(template),sbatch=Q.reference(batch)),sort_keys=True))


if __name__=='__main__':main()

