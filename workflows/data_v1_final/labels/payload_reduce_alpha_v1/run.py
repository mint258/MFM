"""Independent Alpha reduction of the exact closed labels512 scan outputs."""
from __future__ import annotations
import argparse,collections,json,os,socket,time
from pathlib import Path
from payload_audit_alpha_v1.run import bounded_worst,json_safe,pre_scan_fixture_gate
from payload_audit_alpha_v1.payload import quality_stop_fields
from payload_audit_alpha_v1.support import load,require,ref,save,need,new_root,unique_bytes,TASKS
from workflows.data_v1_final.labels.source_status_v1.reduce import consume_coverage
from .guard import require_startup
from .inputs import verify_inputs
from payload_audit_alpha_v1.resource_runtime import stop_requested

def reduce_payload(cfg,a):
    plan=load(require(cfg['sources']['plan']))
    manifests=[load(path) for path in a.shard_manifest]
    need({m['shard_id'] for m in manifests}==set(range(plan['shards'])) and len(manifests)==plan['shards'],'ALL_SHARDS_EXACTLY_ONCE')
    for m in manifests:need(m['config']==ref(a.config) and m['plan']==cfg['sources']['plan'] and m['status']=='PAYLOAD_SHARD_SCANNED_REDUCTION_REQUIRED','CLOSED_IDENTICAL_PAYLOAD_SCOPE')
    root=Path(a.output)
    import numpy as np
    import pyarrow.parquet as pq
    expected=np.memmap(require(plan['expected_roles']),mode='r',dtype=np.uint8,shape=(plan['global_records'],))
    seen=np.memmap(root/'coverage.uint8',mode='w+',dtype=np.uint8,shape=(14,plan['global_records']))
    selected=[]
    if plan['mode']=='pilot':
        for group in plan['groups']:
            h=pq.ParquetFile(require(group['owner_index']))
            try:
                for batch in h.iter_batches(columns=['record_ordinal'],use_threads=False):selected.extend(batch.column('record_ordinal').to_pylist())
            finally:h.close()
        need(len(selected)==len(set(selected))==plan['records'],'PILOT_ORDINAL_SET')
    stats=collections.defaultdict(collections.Counter);observations=collections.defaultdict(collections.Counter)
    structural=collections.Counter();raw_counts=collections.Counter();worst={};group_ids=set();molecules=0;opens=closes=0;jump_counts=collections.Counter();reports=[]
    for manifest in manifests:
        for item in manifest['groups']:
            report=load(require(item['report']));gid=report['group_index'];need(gid not in group_ids,'DUPLICATE_OWNER_GROUP');group_ids.add(gid)
            group=next(g for g in plan['groups'] if g['group_index']==gid)
            need(group['source_job_id']==report['source_job_id'] and group['expected_records']==report['records'],'GROUP_SCOPE_DIFFERS')
            molecules+=report['molecules'];opens+=report['source_opens'];closes+=report['source_closes'];need(report['source_opens']==report['source_closes'],'SOURCE_HANDLE_NOT_CLOSED')
            for key,value in report['field_stats'].items():stats[key].update(value)
            for key,value in report['all_component_observations'].items():observations[key].update(value)
            structural.update(report['structural_review_counts']);raw_counts.update(report['raw_payload_counts'])
            require(report['candidate_masks'])
            h=pq.ParquetFile(require(report['coverage']))
            try:
                mass=0
                for batch in h.iter_batches(batch_size=65536,use_threads=False):mass+=consume_coverage(batch,seen,expected,plan['global_records'])
            finally:h.close()
            need(mass==14*group['expected_records'],'GROUP_LEDGER_MASS')
            details=load(require(report['details']),limit=cfg['group_output_cap_bytes'])
            jump_counts.update(details['within_molecule_jump_counts'])
            for key,rows in details['worst20_by_field_reason'].items():
                for row in rows:
                    if isinstance(row.get('score'),str):row=dict(row,score=float(row['score']))
                    bounded_worst(worst,key,row)
            reports.append(item['report'])
    need(group_ids=={g['group_index'] for g in plan['groups']},'ALL_OWNER_GROUPS_REQUIRED')
    need(molecules==plan['molecules'],'MOLECULE_MASS')
    for task,code in TASKS.items():
        need(np.count_nonzero(seen[code])==plan['records'],'EXACT_CANONICAL_TASK_MASS:'+task)
        if selected:need(np.all(seen[code,selected]==1),'EXACT_PILOT_MEMBERSHIP')
    need(len(stats)==146 and len(observations)==264,'UNCHANGED_COMPONENT_DECLARATIONS')
    need(all(s['records']==plan['records'] for s in stats.values()),'ENABLED_COMPONENT_RECORD_DENOMINATORS')
    need(all(s['records']==plan['records'] for s in observations.values()),'ALL_COMPONENT_RECORD_DENOMINATORS')
    stop=quality_stop_fields(stats,plan['records'],cfg['new_mask_fraction_stop']);seen.flush()
    report={'schema':'LABEL_PAYLOAD_AUDIT_REDUCTION_V1','status':'PAYLOAD_QUALITY_STOP_REVIEW_REQUIRED' if stop else 'PAYLOAD_SCAN_CLOSED_CANDIDATES_NOT_FROZEN',
      'mode':plan['mode'],'config':ref(a.config),'plan':cfg['sources']['plan'],'shard_manifests':[ref(p) for p in a.shard_manifest],
      'records':plan['records'],'molecules':molecules,'canonical_task_slots':plan['records']*14,'source_opens':opens,'source_closes':closes,
      'field_stats':{k:dict(v) for k,v in stats.items()},'all_component_observations':{k:dict(v) for k,v in observations.items()},
      'raw_payload_counts':dict(raw_counts),'structural_review_counts':dict(structural),'within_molecule_jump_counts':dict(jump_counts),
      'quality_stop_fields':stop,'quality_stop_fraction':cfg['new_mask_fraction_stop'],'source_group_reports':reports,
      'coverage_ledger':ref(root/'coverage.uint8'),'full_status_rescanned':False,'native_print_precision_verified':False,
      'raw_retained_precision_probe':'NEXT_BOUNDED_STAGE_USING_details.raw_precision_candidates',
      'actual_frame_origin_verified':False,'robust_z_state':'MATCHED_PILOT_TRAIN_REFERENCE' if cfg['calibration'] else 'PENDING_MATCHED_FULL_TRAIN_CALIBRATION',
      'candidate_masks_frozen':False,'normalization_completed':False,'final_common_D4':False,'guide_1_5_completed':False,
      'cost_overrun_policy':'REPORT_AND_CONTINUE; scientific quality thresholds unchanged'}
    save(root/'worst20_by_field_reason.json',json_safe(worst));save(root/'audit.json',report)
    need(unique_bytes(root)<=cfg['reduce_output_cap_bytes'],'REDUCE_OUTPUT_CAP')
    print(json.dumps({'status':report['status'],'stop_fields':stop,'records':plan['records']}))
    if stop:raise SystemExit(2)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan,proof=require_startup(a.plan,a.startup_proof);cfg=load(require(plan['config_reference']))
    a.config=plan['config_reference']['path'];a.output=plan['output_directory'];a.shard_manifest=[plan['scan_manifest_reference']['path']]
    root=new_root(a.output);started=time.monotonic();fixture_gate=None;verification=None
    try:
        fixture_gate=pre_scan_fixture_gate(root,a.startup_proof)
        verification=verify_inputs(plan,proof,root,fixture_gate)
        need(not stop_requested(),'SOFT_STOP_NO_REDUCTION_STARTED')
        reduce_payload(cfg,a)
        audit=load(root/'audit.json')
        need(unique_bytes(root)+(2<<20)<=plan['output_cap_bytes'],'ALPHA_REDUCER_WHOLE_TWO_GIB_CAP')
        result={'schema':'ALPHA_LABEL_PAYLOAD512_REDUCTION_STAGE_CLOSURE_V1','status':'REDUCTION_CLOSED_CANDIDATES_NOT_FROZEN',
          'endpoint':'218.192.171.238:22','uid':os.getuid(),'node':socket.gethostname().split('.')[0],'job_id':str(proof['job_id']),
          'parent_alpha_job_id':'1884788','startup_proof_reference':ref(a.startup_proof),'plan_reference':ref(a.plan),
          'pre_scan_fixture_gate':fixture_gate,'actual_input_verification':verification,'audit_reference':ref(root/'audit.json'),
          'records':audit['records'],'molecules':audit['molecules'],'canonical_task_slots':audit['canonical_task_slots'],
          'quality_stop_fields':audit['quality_stop_fields'],'elapsed_seconds':time.monotonic()-started,
          'actual_environment':plan['actual_environment'],'source_values_read_only':True,'median_MAD_refit':False,
          'candidate_masks_frozen':False,'native_print_precision_verified':False,'actual_frame_origin_verified':False,
          'normalization_completed':False,'final_common_D4':False,'guide_1_5_completed':False,
          'resource_evidence_output':plan['resource_evidence_output'],'resource_observer_reserved_bytes':64<<20}
        save(root/'stage_closure.json',result)
        need(unique_bytes(root)<=plan['output_cap_bytes'],'ALPHA_REDUCER_FINAL_TWO_GIB_CAP')
        print(json.dumps({'status':result['status'],'records':audit['records'],'parent_alpha_job_id':'1884788'}))
    except BaseException as exc:
        save(root/'stage_failure.json',{'schema':'ALPHA_LABEL_PAYLOAD512_REDUCTION_STAGE_CLOSURE_V1',
          'status':'REDUCTION_NOT_ACCEPTED_PARTIALS_PRESERVED_NO_AUTORETRY','error':str(exc),'exception_type':type(exc).__name__,
          'job_id':str(proof['job_id']),'parent_alpha_job_id':'1884788','pre_scan_fixture_gate':fixture_gate,
          'actual_input_verification':verification,'scientific_quality_thresholds_unchanged':True,
          'candidate_masks_frozen':False,'normalization_completed':False,'final_common_D4':False});raise
if __name__=='__main__':main()
