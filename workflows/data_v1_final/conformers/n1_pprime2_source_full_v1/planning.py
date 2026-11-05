"""CPU-only source roster/import/readback; no optimizer or final physical IDs."""
from __future__ import annotations
import gzip,hashlib,json,os,pathlib,re
from . import contract as C,io as I

def packet_readback(task,reference):
    """Apply the same original float64 geometry-SHA checks without rewriting."""
    I.source_check(reference)
    with gzip.open(reference['path'],'rb') as stream:
        body=stream.read(I.PACKET_CAP+1);C.need(len(body)<=I.PACKET_CAP and stream.read(1)==b'','BOUNDED_COMPLETE_PACKET_REQUIRED')
    saved=json.loads(body);catalog=C.load_catalog(I.ref(I.HERE/'frozen_sources.json'))
    original_io=C.module_from_pin('_n1_full_packet_readback_original_io',catalog['references']['io'])
    C.need(saved['task_key']==task['task_key'] and saved['summary']['molecule_id']==task['meta']['molecule_id']
        and saved['common'] is False and saved['pilot_membership'] is False and saved['production_membership'] is False
        and saved['final_common_reference'] is None,'SOURCE_PACKET_IDENTITY_AND_NO_COMMON_RELEASE')
    z=task['source_atomic_numbers'];old=saved['baseline_original_row']
    if saved['baseline_identity'] is not None:
        C.need(C.sha_value(old)==task['baseline_row_sha256'] and original_io.geometry_sha(z,old['coordinates'])==saved['baseline_identity']['geometry_sha256'],'BASELINE_FLOAT64_READBACK_CHANGED')
        C.need(saved['baseline_identity']['geometry_id']==task['baseline_geometry_id'] and saved['baseline_identity']['original_sprime_conf_idx']==0,'ORIGINAL_BASELINE_PHYSICAL_IDENTITY_CHANGED')
    for event in saved['candidate_optimizer_events']:
        if event['finite']:C.need(original_io.geometry_sha(z,event['coordinates'])==event['geometry_sha256'],'CANDIDATE_FLOAT64_READBACK_CHANGED')
    if saved['supplement'] is not None:
        extra=saved['supplement'];C.need(original_io.geometry_sha(z,extra['coordinates'])==extra['geometry_sha256']
            and extra['geometry_sha256']!=saved['baseline_identity']['geometry_sha256'],'SUPPLEMENT_FLOAT64_OR_IDENTITY_READBACK_CHANGED')
        C.need(extra['native_extra_conformer_id']==f"n1p2:{extra['seed']}:{extra['candidate_id']}"
            and extra['source_record_id']==task['records'][0]['record_id'],'NATIVE_SUPPLEMENT_ID_AND_PM7_ANCHOR_PRESERVED')
    return saved


def row_for_task(task,task_ref,base_ref):
    return {'molecule_id':task['meta']['molecule_id'],'task_key':task['task_key'],'task_reference':task_ref,'baseline_reference':base_ref,
        'source_record_id':task['records'][0]['record_id'],'baseline_geometry_id':task['baseline_geometry_id'],
        'original_baseline_sprime_conf_idx':task['existing_conformers'][0]['sprime_conf_idx'],
        'baseline_row_sha256':task['baseline_row_sha256'],'common':False,'pilot_membership':False,'production_membership':False,
        'final_physical_extra_int64_id':None,'physical_int64_integration_status':'PENDING_EXPLICIT_FINAL_GEOMETRY_MAP'}


def freeze_source_roster(prepared,task_refs,base_refs,inventory,pilot_review_ref,proof,out,budget,ready):
    value=dict(prepared);value.pop('tasks',None);value.pop('baseline_packets',None)
    value.update(science_cost_review_reference=pilot_review_ref,common=False,pilot_membership=False,production_membership=False,
        final_common_reference=None,physical_int64_integration_frozen=False,new_UFF_calls=0,new_QM_calls=0,
        tasks_written=len(task_refs),selected_count=len(task_refs),imported_count=0,new_attempt_count=0)
    if not ready:
        value.update(status='PENDING_FULL_SOURCE_TASK_FREEZE',pending_task_references=task_refs,pending_baseline_references=base_refs)
        return value
    review=C.source_review(pilot_review_ref)
    C.need(len(task_refs)==len(base_refs)==C.ELIGIBLE and len(inventory)==C.MOTHER,'ALL_SOURCE_TASKS_AND_MOTHERS_REQUIRED')
    C.need(value['reason_counts']=={'ACCEPTED_BASELINE_COUNT_NOT1':233,'ROLE_FULL_OR_MISSING':65,'SOURCE_BASELINE_READY':4631,'UFF_UNSUPPORTED':176},'UNCHANGED_ALL_MOTHER_ELIGIBILITY_REASONS')
    from collections import Counter
    C.need(dict(Counter(row['effective_role'] for row in inventory))==review['original_mother_effective_roles'],'ALL_MOTHER_EFFECTIVE_ROLES_RETAINED')
    pilot=I.read(review['pilot_receipt_reference']);old_prepared=I.read(review['prepared_reference'])
    account=I.read(review['terminal_all_known_accounting_reference'])
    I.authorized(proof,[pilot_review_ref,review['pilot_receipt_reference'],review['prepared_reference'],review['terminal_all_known_accounting_reference'],account['raw_sacct_reference']])
    terminal=I.terminal_c0(review['terminal_all_known_accounting_reference'],'4521418');I.terminal_c0(review['terminal_all_known_accounting_reference'],'4521417')
    C.need(pilot['schema']=='N1_PPRIME2_PILOT32_RECEIPT_V4' and pilot['job_id']=='4521418'
        and pilot['status']=='ACTUAL32_PACKETS_CLOSED_REQUIRES_SCIENTIFIC_AND_COST_ROOT_REVIEW'
        and pilot['completed_durable_readback_packets']==pilot['claimed']==32 and not(pilot['unknown_started_task_keys'] or pilot['errors']
        or pilot['preexisting_or_unknown_once_keys'] or pilot['unstarted_task_keys']),'REAL_CLOSED_CONSUMED32_REQUIRED')
    C.need(pilot['prepared']==review['prepared_reference'] and old_prepared['job_id']=='4521417' and old_prepared['eligible_count']==4631,'REAL_PILOT_SOURCE_PREPARATION')
    I.authorized(proof,[old_prepared['role_status_usable_audit'],old_prepared['metadata_aggregation_before_validation'],old_prepared['source_population_authority']])
    old_audit=I.read(old_prepared['role_status_usable_audit']);new_audit=I.read(value['role_status_usable_audit'])
    C.need(old_audit['all_mother_ids_sha256']==new_audit['all_mother_ids_sha256'],'FULL_PREP_MOTHER_MEMBERSHIP_CHANGED_FROM_ACTUAL_VALIDATED_PILOT')
    old_tasks={};old_bases={row['path']:row for row in old_prepared['baseline_packets']}
    I.authorized(proof,[*old_prepared['tasks'],*old_prepared['baseline_packets']])
    for reference in old_prepared['tasks']:
        task=I.read(reference);old_tasks[task['task_key']]=(task,reference)
    packets={row['task_key']:row for row in pilot['packets']};claims={row['task_key']:row['start_reference'] for row in pilot['claims']}
    C.need(len(old_tasks)==len(packets)==len(claims)==32 and set(old_tasks)==set(packets)==set(claims),'EXACT_SAME_32_TASK_PACKET_AND_CLAIM_KEYS')
    I.authorized(proof,[*[row['reference'] for row in packets.values()],*claims.values()])
    ledger_keys=set()
    for path in I.LEDGER.iterdir():
        C.need(path.is_file() and not path.is_symlink() and path.suffix=='.json' and re.fullmatch('[0-9a-f]{64}',path.stem),'ONCE_LEDGER_UNKNOWN_ENTRY_REQUIRES_ROOT_REVIEW')
        ledger_keys.add(path.stem)
    if ledger_keys!=set(claims):
        value.update(status='PENDING_LEDGER_DIVERGENCE_NO_GENERATION',unexpected_consumed_keys=sorted(ledger_keys-set(claims)),missing_expected_claims=sorted(set(claims)-ledger_keys))
        return value
    rows=[];imports=[];bases={row['path']:row for row in base_refs}
    for task_ref in task_refs:
        task=I.read(task_ref);key=task['task_key'];C.validate_task(task,value['source_population_authority'])
        base_ref=task['authority_references']['accepted_baseline_evidence'];C.need(bases.get(base_ref['path'])==base_ref,'FULL_SOURCE_BASELINE_PACKET_PIN')
        row=row_for_task(task,task_ref,base_ref)
        if key in claims:
            if budget.observe(reserve=I.ADMIN_RESERVE) is not None:
                value.update(status='PENDING_IMPORT_AFTER_RESOURCE_STOP_NO_GENERATION');return value
            old_task,old_task_ref=old_tasks[key];C.validate_task(old_task,old_prepared['source_population_authority'])
            C.need(task['records']==old_task['records'] and task['existing_conformers']==old_task['existing_conformers']
                and task['source_atomic_numbers']==old_task['source_atomic_numbers'] and task['baseline_geometry_id']==old_task['baseline_geometry_id']
                and task['task_key']==old_task['task_key'],'IMPORTED32_ORIGINAL_SCIENTIFIC_SOURCE_AND_BASELINE_UNCHANGED')
            old_base_ref=old_task['authority_references']['accepted_baseline_evidence'];C.need(old_bases.get(old_base_ref['path'])==old_base_ref,'ORIGINAL32_BASELINE_EVIDENCE_PIN')
            old_base=I.read(old_base_ref);C.need(old_base['original_row']==task['existing_conformers'][0],'IMPORTED32_ORIGINAL_BASELINE_ROW')
            claim=I.read(claims[key]);C.need(claim['task_key']==key and claim['molecule_id']==row['molecule_id']
                and claim['job_id']=='4521418' and claim['seed']==C.proposed_seed(row['molecule_id']) and claim['automatic_retry'] is False,'IMPORTED32_EXISTING_ONCE_CLAIM')
            packet=packet_readback(task,packets[key]['reference']);C.need(packet['runtime']['job_id']=='4521418' and packet['runtime']['uid']==1278
                and packet['summary']['Pprime_actual_records']==2 and packet['supplement'] is not None,'ACTUAL_IMPORTED32_TWO_REAL_GEOMETRIES')
            imported={'molecule_id':row['molecule_id'],'task_key':key,'packet_reference':packets[key]['reference'],'once_claim_reference':claims[key],
                'original_task_reference':old_task_ref,'source_task_reference':task_ref,'original_source_population_authority':old_prepared['source_population_authority'],
                'packet_runtime':packet['runtime'],'status':'IMPORTED_EXISTING_PACKET_FLOAT64_SHA_READBACK_NO_NEW_UFF','new_optimizer_calls':0,
                'native_extra_conformer_id':packet['supplement']['native_extra_conformer_id'],'geometry_id':packet['supplement']['geometry_id'],
                'geometry_sha256':packet['supplement']['geometry_sha256'],'baseline_geometry_id':packet['baseline_identity']['geometry_id']}
            imports.append(imported);row.update(state='IMPORTED_ALREADY_CONSUMED_NO_RETRY',imported_packet_reference=packets[key]['reference'])
        else:row.update(state='UNCONSUMED_NEW_ATTEMPT_NOT_AUTHORIZED_UNTIL_FINITE_ROOT_REVIEW')
        rows.append(row)
    partition=C.expected_source_partition([row['task_key'] for row in rows],[row['task_key'] for row in imports])
    C.need(len(imports)==32 and len(partition['new_keys'])==4599 and len(partition['waves'])==72,'REAL4631_EQUALS_IMPORT32_PLUS_NEW4599')
    roster_ref=I.write(out/'source_tasks.jsonl',b''.join(C.canonical(row)+b'\n' for row in rows),budget.roots)
    imported_ref=I.json_new(out/'imported32.json',{'schema':'N1_SOURCE_FULL_IMPORTED32_V1','status':'ALL32_ORIGINAL_PACKETS_READBACK_NO_NEW_UFF',
        'pilot_receipt_reference':review['pilot_receipt_reference'],'actual_terminal':terminal,'imports':imports,
        'common':False,'pilot_membership':False,'production_membership':False},budget.roots)
    by_key={row['task_key']:row for row in rows};directory=out/'batches';directory.mkdir();batches=[]
    for i,keys in enumerate(partition['waves']):
        batch={'schema':'N1_SOURCE_FULL_FINITE_BATCH_V1','status':'FROZEN_UNCONSUMED_KEYS_REQUIRES_INDEPENDENT_ROOT_REVIEW','batch_index':i,
            'source_preparation_job_id':str(proof['job_id']),'source_population_authority':value['source_population_authority'],
            'source_task_roster':roster_ref,'tasks':[by_key[key] for key in keys],'task_count':len(keys),'maximum_batch_molecules':64,
            'same_once_ledger':str(I.LEDGER),'common':False,'pilot_membership':False,'production_membership':False,
            'physical_int64_integration_frozen':False,'production_population_release':False}
        ref=I.json_new(directory/('%04d.json'%i),batch,budget.roots);batches.append({'batch_index':i,'task_count':len(keys),'reference':ref})
    index_ref=I.json_new(out/'batch_index.json',{'schema':'N1_SOURCE_FULL_BATCH_INDEX_V1','batches':batches,'batch_count':72,
        'task_count':4599,'imported_count':32,'source_task_roster':roster_ref,'source_population_authority':value['source_population_authority'],
        'all_initial_batch_keys_mutually_disjoint':True,'no_batch_has_generation_authority_without_separate_Root_review':True},budget.roots)
    value.update(status='ACTUAL_FULL_SOURCE_TASKS_FROZEN_NO_GENERATION',source_task_roster=roster_ref,imported32=imported_ref,batch_index=index_ref,
        imported_count=32,new_attempt_count=4599,batch_count=72,selected_count=4631,once_ledger_root=str(I.LEDGER),
        ledger_import_snapshot=[claims[key] for key in sorted(claims)],task_slices_mutually_disjoint=True,
        descriptive_linear_source_core_hours=review['descriptive_linear_4631_parent_core_hours'],descriptive_mean_not_tail_or_wave_runtime_bound=True)
    return value


def roster_rows(reference):
    I.source_check(reference)
    with pathlib.Path(reference['path']).open('rb') as stream:
        for raw in stream:
            C.need(len(raw)<=64<<10 and raw.endswith(b'\n'),'BOUNDED_COMPLETE_SOURCE_TASK_ROSTER_ROW');yield json.loads(raw)


def batch_input_references(prepared_path,batch_path,accounting_path,batch_review_path,pilot_review_path,quota_review_path):
    """Root metadata helper: enumerate refs without opening a task or packet."""
    prepared_ref=I.small_ref(prepared_path);batch_ref=I.small_ref(batch_path)
    C.need(prepared_ref['bytes']<=1<<20 and batch_ref['bytes']<=1<<20,'SMALL_FROZEN_PREPARED_AND_BATCH_HEADERS_ONLY')
    prepared=I.read(prepared_ref);batch=I.read(batch_ref)
    result=I.prepare_input_references(prepared['formal_config']['path'],quota_review_path,pilot_review_path)
    account_ref=I.small_ref(accounting_path);account=I.read(account_ref)
    extra=[prepared_ref,batch_ref,account_ref,account['raw_sacct_reference'],I.small_ref(batch_review_path),
        prepared['batch_index'],prepared['source_population_authority'],prepared['imported32'],
        *[row['task_reference'] for row in batch['tasks']],*[row['baseline_reference'] for row in batch['tasks']]]
    result.update(schema='N1_SOURCE_FULL_FINITE_BATCH_INPUT_LOCATORS_ONLY_V1',input_references=list({row['path']:row for row in [*result['input_references'],*extra]}.values()),
        source_population_mother=5105,source_eligible=4631,batch_tasks=batch['task_count'],no_task_packet_or_scientific_body_opened=True,
        Root_finite_batch_review_is_required=True)
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description='Pure small-metadata finite-batch locator helper; no science or submission')
    for name in ('prepared','batch','prepare-accounting','batch-review','pilot-review','quota-provider-review'):p.add_argument('--'+name,type=pathlib.Path,required=True)
    a=p.parse_args();print(json.dumps(batch_input_references(a.prepared,a.batch,a.prepare_accounting,a.batch_review,a.pilot_review,a.quota_provider_review),allow_nan=False))
