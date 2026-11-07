"""Concrete pilot/QA/same-stage full metadata templates; never submits Slurm."""
import argparse
import copy
import os
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from ..uff3_candidate_v1 import core as C
from . import budget
from .quality_authority import read,accepted
from .ordered_contract import completed_source
from .terminal import parent

BINDINGS=Path('/gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/uff189_quality_bindings_v1/bindings.json')
RESOURCE_KEYS=('endpoint','uid','runtime_profile_reference','quota_snapshot','quota_authority',
               'minimum_node_available_bytes','software_rss_budget_bytes')


def partition_for(config,inline,census,role,routing,output,covered_stage=None):
    caps=config['private_caps_bytes'];Q.need(set(caps)=={'generation','quality','finalizer'}and all(type(v)is int and v>0 for v in caps.values()),'Finite actual generation/QA/finalizer caps')
    global_root=Path(config['global_UFF_scope_root']);routing=Path(routing)
    Q.need(routing.is_relative_to(global_root),'Actual UFF private routing under declared global root')
    # B is native existing UFF bytes outside an already covered generation
    # prefix. Same-stage pilot bytes are inside generation cap, not legacy B.
    covered=Path(covered_stage)if covered_stage else None
    B=0;current=0
    for r in [*census['records'],*census.get('generation_summaries',[])]:
        if r['scope']!='UFF':continue
        path=Path(r['path'])
        if covered and(path==covered or covered in path.parents):current+=r['allocated_bytes']
        else:B+=r['allocated_bytes']
    Q.need(current<=caps['generation'],'Actual closed generation prefix fits its declared private cap')
    peer_caps=sum(v for k,v in caps.items()if k!=role)
    peer_remaining=peer_caps
    if role!='generation':peer_remaining-=min(current,caps['generation'])
    reserve=config['routing_overhead_reserved_bytes']
    Q.need(type(reserve)is int and reserve>=0 and B+sum(caps.values())+reserve<=inline['scope_total_caps_bytes']['UFF'],
           'Actual legacyB+routing+all private caps fit inherited700GB; never assume B=0')
    ancestors=[routing]
    while ancestors[-1]!=global_root:ancestors.append(ancestors[-1].parent)
    other=inline['other_future_reserved_bytes_for_each_scope']['UFF']+peer_remaining+reserve
    return dict(endpoint=Q.ENDPOINT,uid=Q.UID,future_budget=inline,routing_scope_root=str(routing),
        global_UFF_scope_root=str(global_root),routing_ancestor_paths=[str(p)for p in ancestors],
        inner_stage_is_only_child=True,routing_budget_includes_all_ancestors=True,
        closed_legacy_census_reference=inline['closed_census_reference'],closed_legacy_allocated_bytes=B,
        routing_overhead_reserved_bytes=reserve,inner_output_cap_bytes=caps[role],peer_stage_caps_bytes=peer_caps,
        peer_remaining_reserved_bytes=peer_remaining,other_future_reserved_bytes=other)


def resources(config,bindings,inline,part,role,routing,output):
    original=read(config['resources_reference']);deployment=read(config['deployment_reference'])
    plan={k:copy.deepcopy(original[k])for k in RESOURCE_KEYS}
    Q.need(plan['endpoint']==Q.ENDPOINT and plan['uid']==Q.UID,'Actual Alpha resource template, never Main1278')
    workers=config.get('workers',32);Q.need(type(workers)is int and workers>=16,'Actual admitted single-node worker count')
    plan.update(workers=workers,output_scope_root=str(routing),output_directory=str(output),
        output_cap_bytes=part['inner_output_cap_bytes'],other_future_reserved_bytes=part['other_future_reserved_bytes'],
        minimum_free_bytes=inline['minimum_free_after_all_future_bytes'],storage_partition=part,
        metadata_wrapper_reserved_bytes=config['metadata_reserved_bytes'],
        quality_bindings_reference=config['quality_bindings_reference'],
        source_capsule_reference=bindings['source_capsule_reference'],parent_transport_manifest=bindings['parent_transport_manifest'],
        quality_reference_review=bindings['quality_reference_review'])
    profile=read(plan['runtime_profile_reference']);plan['allowed_nodes']=original.get('allowed_nodes',profile['allowed_nodes'])
    if 'software_rss_budget_bytes'in config:plan['software_rss_budget_bytes']=config['software_rss_budget_bytes']
    if 'minimum_node_available_bytes'in config:plan['minimum_node_available_bytes']=config['minimum_node_available_bytes']
    Q.need(workers*config['worker_rss_soft_cap_bytes']+config['parent_rss_cap_bytes']<=plan['software_rss_budget_bytes'],
           'Declared worker and parent software allowances fit reviewed process-tree budget')
    plan['code_references']=deployment['code_references']
    Q.need(all(ref in plan['code_references']for ref in config.get('additional_code_references',[])),
           'Actual deployment must include builder/runtime dependencies; never invent source pins')
    return plan


def prepare(config,source_ref,source_completed,output,bindings_ref=None):
    Q.need(os.getuid()==Q.UID,'Actual Alpha metadata builder UID1264')
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    config=copy.deepcopy(config)
    config['quality_bindings_reference']=bindings_ref or Q.reference(BINDINGS)
    bindings=read(config['quality_bindings_reference']);accepted(bindings['quality_reference_review'])
    source=read(source_ref)
    completed_source({'source_completed':source_completed},source)
    allocations=list(config['closed_allocations'])
    if not any(b['plan_reference']==source['resource_plan']for b in allocations):
        allocations.append({**source_completed,'scope':config['source_budget_scope'],'plan_reference':source['resource_plan']})
    census_ref=budget.census(config['baseline_budget_reference'],allocations,
        config['excluded_active_allocations'],root/'native_closed_blocks.json',config['global_UFF_scope_root'])
    inline=budget.inline(config['baseline_budget_reference'],census_ref);c=budget.read_census(census_ref)
    routing=Path(config['global_UFF_scope_root'])/('generation_'+source_ref['sha256'][:12])
    output=routing/'uff3_pilot_LAUNCHER_ASSIGN_REAL_JOB_ID'
    part=partition_for(config,inline,c,'generation',routing,output)
    plan=resources(config,bindings,inline,part,'generation',routing,output)
    plan.update(schema='PUBCHEM_UFF3_ALLOCATION_PLAN_V1',runtime_action='generation',mode='pilot',
        scope_key='uff3_'+source_ref['sha256'][:16],source_manifest=source_ref,source_completed=source_completed,
        recipe_sha256=C.recipe_sha(),user_policy=config['user_policy_reference'],
        maximum_conformers=3,no_fill=True,no_retry=True,shard_index=0,shard_count=1,
        family_batch_molecules=config.get('family_batch_molecules',64),
        worker_rss_soft_cap_bytes=config['worker_rss_soft_cap_bytes'],
        maximum_molecule_output_bytes=config['maximum_molecule_output_bytes'],
        parent_family_reserved_bytes=config['parent_family_reserved_bytes'],
        ledger_rebuild_reserved_bytes=config['ledger_rebuild_reserved_bytes'],
        selected_molecules=10000,selected_molecules_by_stream={'R':5000,'N':5000},
        selection='Random(20261025),5000 R ranks then5000 N ranks from1..1250000',
        build_metadata={'template_only':True,'Slurm_submitted':False,'source_job_id':source['actual_parent']['job_id'],
                        'no_explicit_SBATCH_memory_request':True,'software_budget_is_not_scheduler_reservation':True})
    return Q.write(root/'pilot_plan_template.json',plan)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True,type=Path)
    p.add_argument('--source-manifest',required=True,type=Path);p.add_argument('--source-accounting',required=True,type=Path)
    p.add_argument('--source-startup',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--bindings',type=Path,default=BINDINGS);a=p.parse_args()
    ref=Q.reference(a.source_manifest);source=read(ref)
    source_completed={'runtime':{**source['actual_parent'],'endpoint':Q.ENDPOINT},
        'accounting_reference':Q.reference(a.source_accounting),'startup_proof_reference':Q.reference(a.source_startup)}
    print(prepare(Q.load(a.config),ref,source_completed,a.output,Q.reference(a.bindings)))


if __name__=='__main__':main()