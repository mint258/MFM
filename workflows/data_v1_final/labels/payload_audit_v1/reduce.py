"""Independent canonical coverage and unchanged one-percent quality stop report."""
from __future__ import annotations
import argparse,collections,json
from pathlib import Path
from .run import guard,bounded_worst,json_safe
from .payload import quality_stop_fields
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import load,require,ref,save,need,new_root,unique_bytes,TASKS
from workflows.data_v1_final.labels.source_status_v1.reduce import consume_coverage

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','output','startup-proof'):p.add_argument('--'+key,required=True)
    p.add_argument('--shard-manifest',action='append',required=True);a=p.parse_args();cfg=load(a.config)
    guard(cfg,a.config,a.startup_proof,cfg['reduce_output_cap_bytes']);plan=load(require(cfg['sources']['plan']))
    manifests=[load(path) for path in a.shard_manifest]
    need({m['shard_id'] for m in manifests}==set(range(plan['shards'])) and len(manifests)==plan['shards'],'ALL_SHARDS_EXACTLY_ONCE')
    for m in manifests:need(m['config']==ref(a.config) and m['plan']==cfg['sources']['plan'] and m['status']=='PAYLOAD_SHARD_SCANNED_REDUCTION_REQUIRED','CLOSED_IDENTICAL_PAYLOAD_SCOPE')
    root=new_root(a.output)
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
if __name__=='__main__':main()