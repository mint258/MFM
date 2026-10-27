"""Separately reviewed final source-slot closure; never a final mask/norm fit."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from .control import CLOSE_SCOPE as SCOPE,need,review_contract
from .coverage import close_full_coverage
from .run import fixtures
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import load,require,small_ref,new_root,save,unique_bytes
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import start_observer


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','startup-proof','output'):p.add_argument('--'+key,required=True)
    a=p.parse_args();cfg=load(a.config);provisional=load(a.startup_proof);request=provisional['request']
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    need(cfg['schema']=='FULL_LABEL_PROJECTION_COVERAGE_CONFIG_V1' and cfg['whole_output_cap_bytes']==2<<30
      and cfg['normalization_allowed'] is False,'SOURCE_COVERAGE_ONLY_TWO_GIB_CAP')
    master=load(require(cfg['master_reference']));review=load(require(cfg['full_review_reference']));review_contract(master,review,cfg['master_reference'])
    bp=request['producer_resource_binding_reference'];binding=load(require(bp))
    need(binding['schema']=='FULL_LABEL_PROJECTION_COVERAGE_RESOURCE_BINDING_V1' and binding['scope_key']==SCOPE
      and binding['scientific_config_reference']==small_ref(a.config) and binding['scope_parameters']==cfg['scope_parameters']
      and binding['resource_authority_reference']==request['queue_authority_reference']==review['resource_authority_reference']
      and binding['memavailable_soft_floor_bytes']==4<<30,'EXACT_COVERAGE_RESOURCE_BINDING')
    need(request['pilot'] is False and request['cpus']==16 and request['wall_seconds']<=172800
      and request['estimated_peak_output_bytes']>=cfg['whole_output_cap_bytes'],'HONEST_SOURCE_CLOSURE_ALLOCATION')
    proof=require_startup(a.startup_proof,expected_kind='analysis',expected_scope_key=SCOPE,
      expected_scope_parameters=cfg['scope_parameters'],required_references=[small_ref(a.config),bp,*cfg['small_references']])
    for r in cfg['source_references']:need(r in request['source_references'],'ACTUAL_COVERAGE_SOURCE_PIN');require(r)
    need(proof['account_free_bytes']>=200000000000+cfg['whole_output_cap_bytes']+cfg['remaining_cache_reservation_bytes']
      +review['other_storage_scope_unwritten_cap_upper_bound_bytes'],'FRESH_COVERAGE_STORAGE_AND_ALL_RESERVED_OUTPUT')
    start_observer(proof,binding);root=new_root(a.output)
    try:
        gate=fixtures(root);snapshot=load(require(cfg['dispatch_snapshot_reference']))
        need(snapshot['metadata']['master']==cfg['master_reference'] and snapshot['metadata']['review']==cfg['full_review_reference'],'ACTUAL_CLOSED_DISPATCH_SNAPSHOT')
        result=close_full_coverage(root,master,snapshot,cfg['canonical_index'])
        result.update(schema='FULL_LABEL_PROJECTION_COVERAGE_V1',config=small_ref(a.config),job_id=str(proof['job_id']),fixture_gate=gate,
          master_reference=cfg['master_reference'],dispatch_snapshot_reference=cfg['dispatch_snapshot_reference'])
        need(unique_bytes(root)+(64<<20)+(2<<20)<=cfg['whole_output_cap_bytes'],'COVERAGE_OUTPUT_WITH_OBSERVER_AND_MANIFEST_CAP')
        save(root/'manifest.json',result);print(json.dumps({'status':result['status'],'sidecar_rows':result['sidecar_rows']}),flush=True)
        need(not result['quality_hold_fields'],'FULL_SOURCE_NEW_MASK_GT1PCT_HOLD_NOT_THRESHOLD_CHANGE')
    except BaseException as exc:
        save(root/'failure.json',{'error':type(exc).__name__+':'+str(exc),'partials_preserved':True,'automatic_retry':False});raise

if __name__=='__main__':main()
