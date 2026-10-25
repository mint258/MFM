"""Conserve every original ordinal x 14 task slots and merge metadata censuses."""
from __future__ import annotations
import argparse, collections, json, time
from pathlib import Path
from .support import (BOUNDARY, ROLES, TASKS, TASK_FAMILIES, guard, identity, load,
    need, new_root, ref, require, save, sqlite_ro, unique_bytes)

def consume_coverage(batch, seen, expected, n):
    import numpy as np
    need(all(batch.column(k).null_count==0 for k in ('record_ordinal','task_code','role_code','review_flags')),'NULL_COVERAGE_KEY')
    ordinal=batch.column('record_ordinal').to_numpy(zero_copy_only=False)
    task=batch.column('task_code').to_numpy(zero_copy_only=False)
    role=batch.column('role_code').to_numpy(zero_copy_only=False)
    need(np.all(ordinal<n) and np.all(task<len(TASKS)) and np.all(role<len(ROLES)),'COVERAGE_KEY_OUT_OF_RANGE')
    encoded=task.astype(np.uint64)*n+ordinal
    need(len(np.unique(encoded))==len(encoded) and not np.any(seen[task,ordinal]),'DUPLICATE_CANONICAL_ORDINAL_TASK')
    need(np.array_equal(expected[ordinal],role),'COVERAGE_EFFECTIVE_ROLE_DIFFERS')
    seen[task,ordinal]=1
    return batch.num_rows

def run(config_path,plan_path,manifest_paths,output,startup_proof):
    cfg=load(config_path);guard(startup_proof,config_path,cfg['reduce_output_cap_bytes'])
    plan=load(plan_path);need(plan['config']==ref(config_path),'PLAN_CONFIG_DIFFERS')
    manifests=[load(p) for p in manifest_paths]
    need(len(manifests)==len(plan['shards']),'ALL_SHARDS_REQUIRED')
    need({m['shard_id'] for m in manifests}=={s['shard_id'] for s in plan['shards']},'SHARD_SET_DUPLICATE_OR_MISSING')
    for m in manifests:need(m['prepared_plan']==ref(plan_path) and m['status']=='SHARD_COMPLETE_REDUCTION_REQUIRED','SHARD_NOT_CLOSED_OR_DIFFERENT_PLAN')
    root=new_root(output);start=time.monotonic()
    import numpy as np
    import pyarrow.parquet as pq
    n=plan['record_count'];seen=np.memmap(root/'seen_ordinal_task.uint8',mode='w+',dtype=np.uint8,shape=(len(TASKS),n))
    expected=np.memmap(root/'expected_role.uint8',mode='w+',dtype=np.uint8,shape=(n,));expected[:]=255
    index=require(plan['canonical_index']);before=identity(index);db=sqlite_ro(index)
    try:
        cursor=db.execute('SELECT record_ordinal,new_role FROM records ORDER BY record_ordinal')
        read=0
        while True:
            batch=cursor.fetchmany(4096)
            if not batch:break
            for ordinal,role in batch:need(expected[ordinal]==255,'DUPLICATE_ROLE_ORDINAL');expected[ordinal]=ROLES[role]
            read+=len(batch)
        need(read==n and np.count_nonzero(expected==255)==0,'EXPECTED_ROLE_INDEX_INCOMPLETE')
    finally:db.close()
    counters={key:collections.Counter() for key in ('status_cross_counts','field_cell_counts','precision_metadata_counts','unknown_registry_counts','duplicate_cell_counts','review_flags_counts','noncanonical_physical_rows','noncanonical_status_counts','role_counts','task_counts')}
    file_refs=[];file_sources=set();physical=canonical=opens=closes=0;max_rss=0
    try:
        expected_sources={r['path']:r for s in plan['shards'] for r in s['files']}
        for m in manifests:
            for item in m['files']:
                report=load(require(item['report']),limit=4<<20)
                need(report['source']==expected_sources.get(report['source']['path']),'SOURCE_NOT_IN_EXACT_FULL_PLAN')
                need(report['source']['path'] not in file_sources,'DUPLICATE_PHYSICAL_SOURCE_FILE');file_sources.add(report['source']['path'])
                need(report['status']=='FILE_AUDITED','FILE_NOT_CLOSED')
                physical+=report['physical_rows'];canonical+=report['canonical_rows']
                for key,value in counters.items():value.update(report[key])
                opens+=report['io_handles_opened'];closes+=report['io_handles_closed'];max_rss=max(max_rss,report['max_rss_bytes'])
                need(report['max_simultaneous_source_handles']==1 and report['io_handles_opened']==1 and report['io_handles_closed']==1,'SOURCE_HANDLE_LIFECYCLE_NOT_CLOSED')
                cp=report['coverage'];need(cp==item['coverage'],'COVERAGE_RECEIPT_DIFFERS')
                if cp is not None:
                    path=require(cp);handle=pq.ParquetFile(path);mass=0
                    try:
                        for batch in handle.iter_batches(batch_size=65536,use_threads=False):
                            mass+=consume_coverage(batch,seen,expected,n)
                    finally:handle.close()
                    need(mass==report['canonical_rows'],'FILE_COVERAGE_MASS_DIFFERS')
                file_refs.append(item['report'])
        need(file_sources==set(expected_sources),'ALL_PHYSICAL_SOURCE_FILES_REQUIRED')
        need((physical,canonical)==(plan['physical_task_rows'],plan['canonical_task_rows']),'PHYSICAL_AND_CANONICAL_MASS_DIFFERS')
        need(physical-canonical==sum(counters['noncanonical_physical_rows'].values())==plan['noncanonical_physical_rows_expected'],'NONCANONICAL_ROWS_NOT_CONSERVED')
        task_coverage={}
        for task,code in TASKS.items():
            mass=int(np.count_nonzero(seen[code]));need(mass==n,'MISSING_CANONICAL_TASK_SLOT:'+task);task_coverage[task]=mass
        need(counters['task_counts']==collections.Counter(task_coverage),'TASK_REPORT_LEDGER_DIFFERS')
        need(counters['role_counts']==collections.Counter({r:v['records']*len(TASKS) for r,v in plan['role_counts'].items()}),'ROLE_SLOT_MASS_DIFFERS')
        need(identity(index)==before,'CANONICAL_INDEX_CHANGED');seen.flush();expected.flush()
        require(cfg['metadata']['registry_v3']);v3=load(cfg['metadata']['registry_v3']['path'])
        status_counts=collections.Counter(x['status'] for x in v3['fields'])
        # These are mapped pre-existing declarations, never newly inferred NA/constant masks.
        field_map=[{k:f.get(k) for k in ('field_key','registry_id','task','family_source','source_path','component','status','status_reason','shape','unit','source_unit','reference_frame')} for f in v3['fields']]
        # Expand observations to every existing component without recomputing NA/constants.
        raw_by_key=collections.defaultdict(list)
        for encoded,count in counters['field_cell_counts'].items():
            role,task,key,status,*state=json.loads(encoded)
            raw_by_key[(task,key)].append({'role':role,'status':status,'observed_state':state,'records':count})
        component_observations=[]
        for field in field_map:
            key=('r'+str(field['registry_id'])) if field['task'] not in ('D20','D3') else field['source_path'].rsplit('.',1)[-1]
            states=raw_by_key.get((field['task'],key),[])
            presence=collections.Counter()
            for state in states:presence[(state['role'],state['status'])]+=state['records']
            denominators=collections.Counter()
            for encoded,count in counters['status_cross_counts'].items():
                role,task,status,*_=json.loads(encoded)
                if task==field['task']:denominators[(role,status)]+=count
            missing={json.dumps(k,separators=(',',':')):v-presence[k] for k,v in denominators.items()}
            need(all(v>=0 for v in missing.values()),'COMPONENT_PRESENCE_EXCEEDS_TASK_MASS')
            component_observations.append({'field_key':field['field_key'],'existing_declaration':field['status'],
                'raw_observation_key':key,'states_shared_by_same_source_components':states,
                'not_present_in_serialized_cells_by_role_status':missing,
                'constant_zero_value_reverified':False,'NA_reclassified':False,
                'JSON_or_array_actual_payload_shape':'UNOBSERVED_WHERE_NOT_PROJECTED'})
        require(cfg['metadata']['registry_v2']);raw_registry=load(cfg['metadata']['registry_v2']['path'])
        from .scan import serialized
        inventory=[]
        for entry in raw_registry['entries']:
            task=entry['task'];key='r'+str(entry['registry_id']);states=raw_by_key.get((task,key),[])
            inventory.append({'registry_id':entry['registry_id'],'task':task,'source_path':entry['source_path'],
                'classification':entry.get('classification'),'excluded_in_original_registry':entry.get('excluded'),
                'source_unit_declaration':entry.get('unit'),'declared_serialization':
                  'SERIALIZED_BY_FROZEN_CODEC' if serialized(entry) else 'TASK_NOT_IN_14_SLOT_SCOPE' if task not in TASKS else 'NOT_SERIALIZED_BY_FROZEN_CODEC',
                'cell_metadata_observations':states,'numeric_payload_observed':False})
        save(root/'raw_registry_inventory.json',{'entries':inventory,'original_registry':cfg['metadata']['registry_v2'],
             'frozen_codec':cfg['metadata']['frozen_parquet_encoder'],'all_raw_registry_entries_retained':True})
        save(root/'component_observations.json',{'components':component_observations,'counts':dict(status_counts),
            'declarations_recomputed':False,'new_masks_created':False})
        save(root/'field_declaration_map.json',{'fields':field_map,'counts':dict(status_counts),'declarations_recomputed':False,'component_statistics_not_target_head_count':True})
        audit={'schema':'SOURCE_STATUS_FULL_CENSUS_V1','status':'SOURCE_METADATA_CENSUS_COMPLETE_PAYLOAD_AUDIT_PENDING',**BOUNDARY,
          'config':ref(config_path),'prepared_plan':ref(plan_path),'shard_manifests':[ref(p) for p in manifest_paths],
          'physical_files':len(file_refs),'physical_task_rows':physical,'canonical_task_rows':canonical,
          'record_count':n,'molecule_count':plan['molecule_count'],'task_coverage':task_coverage,'role_authority':plan['role_counts'],
          'source_file_reports':file_refs,'aggregate_counts':{k:dict(v) for k,v in counters.items()},
          'raw_registry_inventory':ref(root/'raw_registry_inventory.json'),'component_observations':ref(root/'component_observations.json'),'field_declaration_map':ref(root/'field_declaration_map.json'),'declared_component_counts':dict(status_counts),
          'io_handles_opened':opens,'io_handles_closed':closes,'max_worker_rss_bytes':max_rss,
          'coverage_ledger':ref(root/'seen_ordinal_task.uint8'),'role_ledger':ref(root/'expected_role.uint8'),
          'remaining':['actual numeric-array length versus declared shape','JSON compound and sparse-pair payload layout','raw-retained program print precision verification','physical-range/cross-field/robust-z/within-molecule review in a separately budgeted payload pass','unit/origin/frame evidence and final-common D4'],
          'elapsed_seconds':time.monotonic()-start,'startup_proof':ref(startup_proof)}
        need(unique_bytes(root)+(16<<20)<=cfg['reduce_output_cap_bytes'],'REDUCE_OUTPUT_CAP')
        save(root/'audit.json',audit);return audit
    except BaseException as exc:
        seen.flush();expected.flush()
        save(root/'failure.json',{'status':'FULL_CENSUS_NOT_ACCEPTED_PARTIALS_PRESERVED','error':str(exc),'type':type(exc).__name__,'physical_files_seen':len(file_sources),'physical_rows_seen':physical,'canonical_rows_seen':canonical})
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','plan','output','startup-proof'):p.add_argument('--'+key,required=True)
    p.add_argument('--shard-manifest',action='append',required=True);a=p.parse_args()
    report=run(a.config,a.plan,a.shard_manifest,a.output,a.startup_proof)
    print(json.dumps({'status':report['status'],'canonical_task_rows':report['canonical_task_rows']}))
if __name__=='__main__':main()