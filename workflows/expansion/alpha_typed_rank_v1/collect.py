"""Read actual CPP full-pool, source capsule and private budget inputs; no submit."""
import argparse
import os
from pathlib import Path
import sys
from ..alpha_runtime_v1 import common as Q
from . import authority


def collect(a):
    Q.need(os.getuid()==1264 and sys.flags.isolated,'Actual isolated Alpha metadata collector required')
    wref=authority.ref(a.compiled_wrapper);rref=authority.ref(a.compiled_actual_review)
    wrapper,native,query=authority.inputs(wref,rref)
    dref=authority.ref(a.rank_deployment);deployment=authority.read(dref);authority.deployed(deployment)
    b=authority.ref(a.storage_partition_review);chosen=authority.partition(b,a.partition_key)
    template=authority.read(authority.ref(a.resource_template));refs=deployment['code_references']
    for value in refs:
        Q.need(value['bytes']<=2<<20,'Source references must not disguise large data');Q.verify(value)
    Q.need(not a.output_directory.exists(),'Fresh collector metadata output required')
    a.output_directory.mkdir(parents=True)
    keep=('runtime_profile_reference','quota_authority','quota_snapshot','minimum_node_available_bytes',
      'software_rss_budget_bytes','parent_rss_cap_bytes','sql_memory_bytes','spill_cap_bytes','parent_transport_manifest')
    plan={k:template[k]for k in keep if k in template}
    plan.update({k:chosen[k]for k in ('output_scope_root','output_cap_bytes','other_future_reserved_bytes','minimum_free_bytes')})
    Q.need(all(k in plan for k in ('software_rss_budget_bytes','parent_rss_cap_bytes','sql_memory_bytes','spill_cap_bytes'))
      and 0<plan['sql_memory_bytes']<plan['parent_rss_cap_bytes']<=plan['software_rss_budget_bytes'],
      'Actual Root SQL/spill/tree/node resource template required')
    plan.update(schema='PUBCHEM_TYPED_EXACT_RANK_PLAN_V1',scope_key='alpha_typed_rank_closed_N_v1',endpoint=Q.ENDPOINT,
      uid=1264,workers=16,novelty_receipt=wrapper['original_scientific_receipt_reference'],
      compiled_execution_wrapper_reference=wref,compiled_full_pool_actual_review_reference=rref,
      storage_partition_actual_review_reference=b,storage_partition_key=a.partition_key,
      rank_deployment_reference=dref,code_references=refs,source_resource_template_reference=authority.ref(a.resource_template),
      output_directory=str(Path(chosen['output_scope_root'])/(a.tag+'_LAUNCHER_ASSIGN_REAL_JOB_ID')))
    pref=Q.write(a.output_directory/'plan_template.json',plan)
    return Q.write(a.output_directory/'collection_receipt.json',dict(schema='ALPHA_TYPED_RANK_INPUT_COLLECTION_V1',
      status='ACTUAL_METADATA_COLLECTED_NOT_SUBMITTED',plan_template_reference=pref,compiled_execution_wrapper_reference=wref,
      compiled_full_pool_actual_review_reference=rref,eligible_molecules=native['queries'],rank_deployment_reference=dref,
      source_capsule_body_and_relative_path_verified=True,large_DATA_or_active_DB_read=False,no_future_hashes_invented=True,
      module='workflows.expansion.alpha_typed_rank_v1.entry'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('compiled-wrapper','compiled-actual-review','rank-deployment','resource-template','storage-partition-review','output-directory'):
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--partition-key',required=True);p.add_argument('--tag',default='alpha_typed_rank_closed_N_v1')
    print(collect(p.parse_args()))


if __name__=='__main__':main()
