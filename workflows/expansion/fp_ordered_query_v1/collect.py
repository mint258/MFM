"""Collect actual closed fullfilter inputs and fresh source metadata; never submit."""
import argparse
import os
from pathlib import Path
import sys
from ..alpha_runtime_v1 import common as Q
from ..pubchem_generic_recovery_overlay_v1.runtime import VERSION
from . import authority


def metadata_ref(path):
    Q.need(Q.frame(path)[2]<=2<<20,'Collector accepts only small metadata/source files')
    return Q.reference(path)


def collect(a):
    Q.need(os.getuid()==1264 and sys.flags.isolated,'Actual isolated Alpha metadata collection required')
    inputs=dict(schema='PUBCHEM_FP_ORDERED_QUERY_INPUTS_V1',status='ACTUAL_INPUTS_COLLECTED_NOT_DATA_VERIFIED',
      filtered_pool_receipt_reference=metadata_ref(a.filtered_receipt),filtered_pool_actual_review_reference=metadata_ref(a.filtered_actual_review))
    f,pool,review=authority.validate(inputs)
    resource=authority.read(metadata_ref(a.resource_template));budget=authority.read(metadata_ref(a.budget_review))
    deployment=authority.read(metadata_ref(a.source_deployment))
    Q.need(budget['schema']=='ROOT_ALPHA_ALL_FUTURE_STORAGE_BUDGET_V2' and budget['reviewer']=='root'
      and budget['endpoint']=='218.192.171.238:22' and budget['uid']==1264
      and deployment['base_code_root'].startswith('/gfshome/alpha/codex_data_v1_20261026/code/'),
      'Reviewed actual shared Alpha budget and fresh deployed source metadata required')
    sources=deployment['code_references']
    for ref in sources:
        Q.need(ref['bytes']<=2<<20,'Source metadata may not disguise data bodies');Q.verify(ref)
    Q.need(all(any(r['path'].endswith('/fp_ordered_query_v1/'+name) for r in sources)
      for name in ('__init__.py','core.py','authority.py','collect.py','run.py','test_core.py')),'Complete new source package deployment required')
    cache=a.future_full_nn_cache_directory
    Q.need(cache.is_absolute() and cache.is_relative_to('/gfshome/alpha/pubchem_expansion_20261103/exact') and not cache.exists(),
      'Fresh independent full-NN cache directory required; baseline201 cannot be reused here')
    Q.need(not a.output_directory.exists(),'Fresh metadata output namespace required')
    a.output_directory.mkdir(parents=True);iref=Q.write(a.output_directory/'actual_inputs.json',inputs)
    keep=('runtime_profile_reference','quota_snapshot','quota_authority','minimum_node_available_bytes','output_scope_root',
      'other_future_closed_scope_credit_reference','software_rss_budget_bytes','parent_rss_cap_bytes','sql_memory_bytes','spill_cap_bytes')
    plan={k:resource[k] for k in keep if k in resource}
    scope=a.storage_budget_scope
    Q.need(Path(plan['output_scope_root'])==Path('/gfshome/alpha/pubchem_expansion_20261103')/scope
      and budget['quota_root']==plan['quota_authority']['quota_root'],'Aggregate output/quota scope must match reviewed budget scope')
    plan.update(schema='PUBCHEM_FULL_FP_ORDERED_QUERY_PLAN_V1',scope_key='fp_ordered_full_query_v1',population_version=VERSION,
      endpoint='218.192.171.238:22',uid=1264,workers=16,input_authority_reference=iref,
      storage_budget_scope=scope,reviewed_storage_budget_reference=metadata_ref(a.budget_review),
      output_cap_bytes=budget['scope_total_caps_bytes'][scope],other_future_reserved_bytes=budget['other_future_reserved_bytes_for_each_scope'][scope],
      minimum_free_bytes=budget['minimum_free_after_all_future_bytes'],code_references=sources,
      source_deployment_reference=metadata_ref(a.source_deployment),source_resource_template_reference=metadata_ref(a.resource_template),
      future_full_nn_cache_directory=str(cache),output_directory=str(Path(plan['output_scope_root'])/(a.tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID')))
    Q.need(all(k in plan for k in ('parent_rss_cap_bytes','sql_memory_bytes','spill_cap_bytes','software_rss_budget_bytes')),
      'Root must supply actual whole-sort SQL/spill/software allowances, not borrowed missing values')
    if 'parent_transport_manifest' in resource:plan['parent_transport_manifest']=resource['parent_transport_manifest']
    pref=Q.write(a.output_directory/'plan_template.json',plan)
    return Q.write(a.output_directory/'collection_receipt.json',dict(schema='PUBCHEM_FP_ORDERED_QUERY_INPUT_COLLECTION_V1',
      status='ACTUAL_METADATA_COLLECTED_NOT_SUBMITTED',input_authority_reference=iref,plan_template_reference=pref,
      no_future_data_hashes_invented=True,large_candidate_bodies_read=False,eligible_molecules=f['counts']['eligible_molecules'],
      module='workflows.expansion.fp_ordered_query_v1.run',source_deployment_reference=metadata_ref(a.source_deployment)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('filtered-receipt','filtered-actual-review','resource-template','budget-review','source-deployment','output-directory','future-full-nn-cache-directory'):
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--storage-budget-scope',choices=('bulk','exact'),required=True)
    p.add_argument('--tag',default='fp_ordered_full_query_v1')
    a=p.parse_args();print(collect(a))


if __name__=='__main__':main()
