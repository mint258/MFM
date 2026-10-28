"""Explicit bounded operational receipts; never relax the global small guard."""
import json,pathlib,stat
from . import contract as C

ENTRY='ROOT_ACTUAL_TERMINAL_PACKED_PARENT_METADATA_ENTRY_V1'
HEADER='PACKED_ACTUAL_OPERATIONAL_RECEIPT_HEADER_V3'
PRODUCER_HEADER='PACKED_PRODUCER_OPERATIONAL_RECEIPT_HEADER_V3'
LIMIT=16<<20
REGISTRATION=('request_reference','submission_reference','producer_plan_reference','startup_proof_reference',
    'terminal_accounting_reference','source_archive_manifest_reference')
PROJECTION=('schema','status','actual_single_parent_job_id','uid','node','allocated_cpus','plan_reference','startup_proof_reference',
    'preflight_reference','original_plan_reference','inputs_review_reference','resolution_index_reference','complete_errors_reference',
    'state_counts','all_started_native_tasks_drained','child_Slurm_jobs_created','new_parent_C0_or_Common_quality_release_claimed','new_QM_calls')


def locator(value,root):
    root=pathlib.Path(root);wanted={'path','bytes','uid','inode','mtime_ns','ctime_ns','nlink','mode','regular','symlink'}
    C.need(type(value)is dict and set(value)==wanted and value['path']==str(root/'receipt.json')
        and all(type(value[k])is int for k in ('bytes','uid','inode','mtime_ns','ctime_ns','nlink','mode'))
        and (2<<20)<value['bytes']<=LIMIT and value['uid']==1278 and value['inode']>0 and value['mtime_ns']>0 and value['ctime_ns']>0
        and value['nlink']==1 and stat.S_ISREG(value['mode']) and value['regular']is True and value['symlink']is False,
        'EXACT_EXISTING_LARGE_OPERATIONAL_RECEIPT_LSTAT_NOT_A_FUTURE_SHA')
    return value


def expand(row):
    row=dict(row);ref=row.get('large_operational_metadata_entry_reference');header_ref=row.get('producer_receipt_header_reference');refs=[]
    if header_ref is not None:
        header=C.metadata_ref(header_ref)
        if header['schema']==HEADER:
            C.need(header['status']=='ACTUAL_CPU_WHOLE_RECEIPT_SHA_EOF_AND_PARENT_BINDING_VERIFIED','REAL_CPU_OPERATIONAL_HEADER_NOT_A_PLACEHOLDER')
            if ref is not None:C.need(ref==header['large_operational_metadata_entry_reference'],'CPU_HEADER_SAME_REAL_TERMINAL_METADATA_ENTRY')
            ref=header['large_operational_metadata_entry_reference']
        else:
            C.need(header['schema']==PRODUCER_HEADER and header['status']=='OWN_RECEIPT_DURABLE_ROOT_TERMINAL_ACCOUNTING_STILL_REQUIRED' and ref is not None,
                'REAL_PRODUCER_SMALL_HEADER_REQUIRES_SEPARATE_ACTUAL_TERMINAL_METADATA_ENTRY')
        refs.append(header_ref)
    if ref is None:return row,refs
    value=C.metadata_ref(ref);C.need(value['schema']==ENTRY
        and value['status']=='ACTUAL_SMALL_METADATA_AND_LSTAT_ONLY_LARGE_RECEIPT_CPU_DEFERRED' and value['reviewer']=='root'
        and value['large_body_not_opened_or_hashed_on_login']is True and value['raw_report_absence_claimed']is False
        and value['future_hash_claimed']is False and value['CPU_complete_SHA_EOF_and_same_FD_required']is True,
        'REAL_ROOT_TERMINAL_METADATA_ENTRY_WITHOUT_BODY_HASH_OR_ABSENCE_FICTION')
    for key in REGISTRATION:
        if key in row:C.need(row[key]==value[key],'DECLARED_REGISTRATION_CONFLICT_WITH_ACTUAL_SMALL_ENTRY:'+key)
        row[key]=value[key]
    row.update(large_operational_metadata_entry_reference=ref,actual_receipt_locator=value['actual_receipt_locator'],
        old_output_root=value['old_output_root'],declared_parent_job_id=value['job_id'],raw_accounting_reference=value['raw_accounting_reference'])
    row.setdefault('producer_receipt_reference',None);row.setdefault('producer_failure_reference',None)
    C.need(row['producer_failure_reference']is None and row.get('terminal_report_absence_reviewed')is not True,
        'EXISTING_LARGE_RECEIPT_NOT_AN_ABSENT_OR_FAILURE_REPORT')
    if header_ref is not None:
        actual=header['source_operational_receipt_reference'];C.reference_shape(actual)
        C.need(actual['path']==value['actual_receipt_locator']['path'] and actual['bytes']==value['actual_receipt_locator']['bytes'],
            'CPU_HEADER_FULL_RECEIPT_IDENTITY_MATCHES_REAL_LSTAT')
        if row['producer_receipt_reference']is not None:C.need(row['producer_receipt_reference']==actual,'FULL_RECEIPT_REFERENCE_CONFLICT')
        row['producer_receipt_reference']=actual
        if header['schema']==PRODUCER_HEADER:
            C.need(header['receipt_projection']['actual_single_parent_job_id']==value['job_id']
                and header['receipt_projection']['plan_reference']==value['producer_plan_reference']
                and header['receipt_projection']['startup_proof_reference']==value['startup_proof_reference'],'OWN_PRODUCER_HEADER_REAL_PARENT_PROOF_AND_PLAN')
    elif row['producer_receipt_reference']is not None:
        C.need(False,'LARGE_RECEIPT_SHA_REQUIRES_REAL_CPU_HEADER_NOT_A_LOGIN_HASH')
    refs.append(ref);return row,refs


def deferred(row):return row.get('large_operational_metadata_entry_reference')is not None


def describe(row,jid,old,proof,raw):
    C.need(row['declared_parent_job_id']==jid and row['old_output_root']==old['output_directory']
        and row['raw_accounting_reference']==raw and row['startup_proof_reference']['path']==proof['request']['startup_proof_path'],
        'OPERATIONAL_LOCATOR_HAS_SAME_REAL_TERMINAL_PARENT_AND_FIXED_OUTPUT_ROOT')
    return locator(row['actual_receipt_locator'],old['output_directory'])


def validate_receipt(value,origin):
    entry=origin['entry'];jid=origin['job_id'];plan=origin['plan'];cpus,node,version=C.origin_resources(plan)
    C.need(value['schema']=='SPRIME_PACKED_DAY_RECEIPT_V1' and value['actual_single_parent_job_id']==jid
        and value['uid']==1278 and value['node']==node and value['allocated_cpus']==cpus
        and value['plan_reference']==entry['producer_plan_reference'] and value['startup_proof_reference']==entry['startup_proof_reference']
        and value['original_plan_reference']==plan['original_plan_reference'] and value['inputs_review_reference']==plan['inputs_review_reference']
        and value['all_started_native_tasks_drained']is True and value['child_Slurm_jobs_created']==0 and value['new_QM_calls']==0
        and value['new_parent_C0_or_Common_quality_release_claimed']is False,'ACTUAL_COMPLETE_OPERATIONAL_RECEIPT_EXPECTED_PARENT_PROOF_AND_SCOPE')
    pre=C.metadata_ref(value['preflight_reference'])
    C.need(pre['tests_run']==9 and all(pre[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
        'ACTUAL_OLD_PACKED9_PREFLIGHT_NOT_INFERRED_FROM_C0')
    for key in ('resolution_index_reference','complete_errors_reference'):
        ref=C.reference_shape(value[key]);C.need(pathlib.Path(origin['root']) in pathlib.Path(ref['path']).parents,'RECEIPT_DATA_REFERENCE_IN_ITS_ACTUAL_OLD_ROOT')
    return value


def read(origin,reader,write_header,creator):
    """Only call after the real Parent preflight and first quota observation."""
    entry=origin['entry'];observed=entry.get('producer_receipt_reference')
    if not deferred(entry):return C.metadata_ref(observed) if observed is not None else None,observed,None
    expected=locator(entry['actual_receipt_locator'],origin['root']);path=reader.safe(expected['path']);before=path.lstat()
    actual_fields={'inode':before.st_ino,'bytes':before.st_size,'uid':before.st_uid,'mtime_ns':before.st_mtime_ns,
        'ctime_ns':before.st_ctime_ns,'nlink':before.st_nlink,'mode':before.st_mode}
    C.need(all(actual_fields[k]==expected[k] for k in actual_fields),'OLD_OPERATIONAL_RECEIPT_CURRENT_FRAME_MATCHES_ACTUAL_ROOT_LSTAT')
    ref=reader.reference(path)
    if observed is not None:C.need(ref==observed,'ACTUAL_PREVIOUS_CPU_HEADER_WHOLE_SHA_STILL_MATCHES')
    value=validate_receipt(reader.read(ref,LIMIT),origin);reader.require(ref)
    projection={k:value[k] for k in PROJECTION};resource=value.get('resource_report',{})
    header={'schema':HEADER,'status':'ACTUAL_CPU_WHOLE_RECEIPT_SHA_EOF_AND_PARENT_BINDING_VERIFIED',
        'large_operational_metadata_entry_reference':entry['large_operational_metadata_entry_reference'],
        'source_operational_receipt_reference':ref,'receipt_projection':projection,
        'source_terminal_parent':origin['owner_parent'],'header_creator':creator,
        'resource_stop_summary':{k:resource.get(k) for k in ('stop_new_native_tasks','observation_failure','reserved_packet_bytes','cost_policy')},
        'full_resource_tail_not_copied_but_original_report_retained':True,'original_large_receipt_modified':False,
        'original_parent_not_promoted_or_scientific_release_claimed':True}
    raw=C.F.canonical(header)+b'\n';C.need(len(raw)<=2<<20,'ACTUAL_OPERATIONAL_PROJECTION_MUST_REMAIN_SMALL')
    header_ref=write_header(origin['job_id'],raw);return value,ref,header_ref


def produced_header(value,ref,creator):
    """The producer already wrote/hash-counted these own bytes; not a C0 claim."""
    C.reference_shape(ref);header={'schema':PRODUCER_HEADER,'status':'OWN_RECEIPT_DURABLE_ROOT_TERMINAL_ACCOUNTING_STILL_REQUIRED',
        'source_operational_receipt_reference':ref,'receipt_projection':{k:value[k] for k in PROJECTION},'header_creator':creator,
        'resource_stop_summary':{k:value.get('resource_report',{}).get(k) for k in ('stop_new_native_tasks','observation_failure','reserved_packet_bytes','cost_policy')},
        'full_original_operational_report_retained':True,'actual_parent_C0_or_scientific_release_claimed':False}
    C.need(len(C.F.canonical(header))<=2<<20,'OWN_OPERATIONAL_HEADER_BOUND');return header
