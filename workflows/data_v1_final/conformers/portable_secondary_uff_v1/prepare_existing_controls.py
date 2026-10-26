"""Main CPU read-only export of16 existing334 packets for secondary software QA.

No run_one, embedding, UFF, QM, new main baseline, or production once-ledger call.
"""
from __future__ import annotations
import argparse,base64,gzip,json,math,os,sys
from collections import OrderedDict
from pathlib import Path
from .contract import canonical,sha,need,ref,load,control_selection_rule,CONTROL_MODE,MISSING_IDS
from .bridge import scientific_sha

SCOPE_KEY='secondary_existing334_control16_export'
PARAMETERS={'original_molecules':336,'existing_completed_packets':334,'software_qa_controls':16,
    'missing_molecules_forbidden':2,'new_population_members':0,'new_main_UFF_QM_calls':0,'new_logical_retries':0}


def select_metadata(closed):
    """Fixed Root caps; no auto-widening or science calls if fewer than16."""
    rule=control_selection_rule();eligible=[];excluded={};details=[]
    for row in closed:
        summary=row['summary'];mid=row['molecule_id'];reasons=[]
        if summary.get('status')!='SUCCESS':reasons.append('not_SUCCESS')
        if row['detail'].get('new_real_accepted_count',0)<1:reasons.append('no_new_real_accepted_geometry')
        heavy=summary.get('heavy_atoms');count=summary.get('expected_conformers');seconds=row.get('science_worker_seconds')
        valid=type(heavy) is int and heavy>0 and type(count) is int and count>0 and type(seconds) in (int,float) and math.isfinite(seconds) and seconds>=0
        if not valid:reasons.append('invalid_observed_selection_metadata')
        else:
            if heavy>rule['max_heavy_atoms']:reasons.append('heavy_atoms_over32')
            if count>rule['max_expected_conformers']:reasons.append('expectedN_over30')
            if seconds>rule['max_observed_main_elapsed_seconds']:reasons.append('observed_main_seconds_over60')
            if float(summary.get('elapsed_seconds',-1))!=float(seconds):reasons.append('observed_seconds_fields_disagree')
        for reason in reasons:excluded[reason]=excluded.get(reason,0)+1
        key=sha((rule['hash_domain']+mid).encode())
        details.append({'molecule_id':mid,'eligible':not reasons,'reasons':reasons,'heavy_atoms':heavy,
            'expected_conformers':count,'observed_main_elapsed_seconds':seconds,'selection_hash':key})
        if not reasons:eligible.append((key,mid,row))
    eligible.sort(key=lambda value:(value[0],value[1]));chosen=[row for _,_,row in eligible[:16]] if len(eligible)>=16 else []
    return chosen,{'selection_rule':rule,'existing_rows':len(closed),'eligible_count':len(eligible),
        'excluded_reason_counts_not_disjoint':excluded,'all_candidate_metadata':details,
        'chosen_molecule_ids':[row['molecule_id'] for row in chosen],
        'status':'EXACT_CONTROL16_METADATA_SELECTED' if chosen else 'ELIGIBLE_COUNT_BELOW16_NO_QA_SLICE',
        'science_called':False,'thresholds_automatically_widened':False}


def identity(path):
    st=Path(path).stat();return {'device':st.st_dev,'inode':st.st_ino,'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'uid':st.st_uid}


def write_json(path,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    need(len(raw)<=2<<20,'BOUNDED_CONTROL_METADATA_OUTPUT')
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('recovery-plan','control-authorization','root-preflight','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();plan_ref=ref(a.recovery_plan.absolute());auth_ref=ref(a.control_authorization.absolute());auth=load(auth_ref)
    need(auth.get('schema')=='ROOT_SECONDARY_EXISTING334_CONTROL16_AUTHORIZATION_V1' and
         auth.get('status')=='APPROVED_FOR_SECONDARY_SOFTWARE_COMPATIBILITY_ONLY' and auth.get('reviewer')=='root' and
         auth.get('mode')==CONTROL_MODE and auth.get('formal_generation_authorized') is False and
         auth.get('allowed_existing_control_count')==16 and set(auth['forbidden_missing_ids'])==MISSING_IDS and
         canonical(auth['selection_rule'])==canonical(control_selection_rule()),'EXACT_ROOT_EXISTING334_SOFTWARE_QA16_AUTHORIZATION_REQUIRED')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    producer=Path(__file__).absolute()
    expected=['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B','-m',
        'workflows.data_v1_final.conformers.portable_secondary_uff_v1.prepare_existing_controls',
        '--recovery-plan',str(a.recovery_plan.absolute()),'--control-authorization',str(a.control_authorization.absolute()),
        '--root-preflight',str(a.root_preflight.absolute()),'--output',str(a.output.absolute())]
    proof=require_startup(a.root_preflight,expected_scope_key=SCOPE_KEY,expected_scope_parameters=PARAMETERS,
        expected_execution_argv=expected,expected_source=producer,expected_kind='analysis',required_references=(plan_ref,auth_ref))
    need(proof['request']['estimated_peak_output_bytes']>=(1<<30)+(64<<20),'WHOLE_PORTABLE_EXPORT_BUDGET_REQUIRED')
    for path in [*producer.parent.glob('*.py'),producer.parent/'source_catalog.json']:
        need(ref(path) in proof['request']['source_references'],'ACTUAL_CONTROL_EXPORT_SOURCE_NOT_PINNED:'+path.name)
    run=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
    sys.path.insert(0,str(run/'repository/workflows/data_v1_final/conformers/recovery_v1'))
    from recovery_common import IO,load_plan,bind_inputs,small_load,named
    plan=load_plan(a.recovery_plan,approved=True)
    for rel in plan['required_additional_source_relative_paths']:
        need(IO.reference(run/'repository'/rel) in proof['request']['source_references'],'ORIGINAL_EXPORT_DEPENDENCY_NOT_PINNED:'+rel)
    audit,closed,tasks=bind_inputs(plan) # first full task/package metadata read is after actual CPU admission
    monitor=small_load(plan['partial_audit_monitor_closure'])
    need(audit['original_parent_state']=='TIMEOUT' and monitor['job_id']=='4520527' and
         monitor['status']=='COMPLETED_NO_MEMORY_DENIAL' and monitor['durable_evidence_exported'] is True,
         'ORIGINAL_TIMEOUT_AND_ACTUAL_C0_PARTIAL_AUDIT_AUTHORITY_REQUIRED')
    root=run/'artifacts/conformers/secondary_compatibility_controls_v1';out=a.output.absolute()
    need(root in out.parents and not out.exists() and not any(p.is_symlink() for p in (out,*out.parents)),'NEW_LITERAL_MAIN_QA_EXPORT_CHILD_REQUIRED')
    out.mkdir(parents=True,mode=0o700)
    chosen,selection=select_metadata(closed)
    selection.update(original_audit_reference=plan['partial_audit_report'],
        original_complete_packages_reference=named(audit['outputs'],'complete_packages.json'),
        partial_audit_monitor_closure_reference=plan['partial_audit_monitor_closure'],
        original_pilot_parent_state='TIMEOUT',partial_audit_parent_job_id='4520527',partial_audit_parent_state='COMPLETED')
    write_json(out/'eligible_count_report.json',selection)
    if len(chosen)<16:
        print(json.dumps({'status':selection['status'],'eligible_count':selection['eligible_count'],'report':ref(out/'eligible_count_report.json')}))
        return 0 # metadata inventory C0, no controls, no packet/LMDB body reads, no threshold widening
    marker_root=root/'qa_export_slices';marker_root.mkdir(parents=True,exist_ok=True)
    need(not any(p.is_symlink() for p in (marker_root,*marker_root.parents)),'LITERAL_QA_SLICE_NAMESPACE_REQUIRED')
    mids=[row['molecule_id'] for row in chosen];slice_id='software_qa16_'+sha(canonical({'endpoint_id':auth['endpoint_id'],
        'authorization_sha256':auth_ref['sha256'],'molecule_ids':mids}))
    marker=marker_root/(auth_ref['sha256']+'.json')
    write_json(marker,{'slice_id':slice_id,'endpoint_id':auth['endpoint_id'],'molecule_ids':mids,'mode':CONTROL_MODE,
        'main_export_job_id':str(proof['job_id']),'production_once_ledger':False,'automatic_retry':False})
    import lmdb
    handles=OrderedDict();expected_rows=[];total=0;task_path=out/'control_tasks.jsonl'
    try:
        with task_path.open('xb') as stream:
            for row in chosen:
                mid=row['molecule_id'];need(mid not in MISSING_IDS,'TWO_MISSING_MOLECULES_ALWAYS_FORBIDDEN_FOR_QA')
                task=tasks[mid];packet_ref=row['reference'];before=identity(packet_ref['path'])
                need(before==row['file_identity'],'ORIGINAL_BASELINE_PACKET_IDENTITY_CHANGED')
                IO.require_pin(packet_ref)
                with gzip.open(packet_ref['path'],'rb') as source:raw=source.read((1<<30)+1)
                need(len(raw)<=1<<30,'BOUNDED_EXISTING_BASELINE_PACKET_REQUIRED');packet=json.loads(raw)
                need(identity(packet_ref['path'])==before and packet['summary']['status']=='SUCCESS' and
                     packet['summary']['molecule_id']==mid and task['meta']['expected_conformers']==row['summary']['expected_conformers'],
                     'EXISTING_PACKET_TASK_OR_STATUS_CHANGED')
                payloads=[]
                for pointer in task['records']:
                    path=Path(pointer['source_path']);path=path if path.is_absolute() else Path('/share/home/zixiao/descriptor_analysis')/path
                    key=str(path)
                    if key not in handles:
                        if len(handles)>=4:handles.popitem(last=False)[1].close()
                        handles[key]=lmdb.open(key,subdir=False,readonly=True,lock=False,create=False,readahead=False,max_readers=1024)
                    env=handles.pop(key);handles[key]=env
                    with env.begin() as tx:payload=tx.get(f"{int(pointer['real_index']):09d}".encode())
                    need(payload is not None and sha(payload)==pointer['record_payload_sha256'],'ORIGINAL_LMDB_PAYLOAD_SHA_DIFFERS')
                    payloads.append({'pointer_sha256':sha(canonical(pointer)),'payload_bytes':len(payload),
                        'payload_sha256':sha(payload),'original_pickle_base64':base64.b64encode(payload).decode()})
                task_hash=sha(canonical(task));envelope={'task':task,'task_sha256':task_hash,'record_payloads':payloads}
                line=canonical(envelope)+b'\n';total+=len(line)
                need(len(line)<=64<<20 and total<=1<<30,'BOUNDED_PORTABLE_CONTROL_EXPORT_REQUIRED');stream.write(line)
                expected_rows.append({'molecule_id':mid,'task_sha256':task_hash,
                    'scientific_sha256_excluding_elapsed_seconds':scientific_sha(packet),'baseline_packet_reference':packet_ref,
                    'baseline_file_identity':before,'baseline_summary_status':'SUCCESS','heavy_atoms':row['summary']['heavy_atoms'],
                    'expected_conformers':row['summary']['expected_conformers'],'observed_main_elapsed_seconds':row['science_worker_seconds']})
            stream.flush();os.fsync(stream.fileno())
    finally:
        for env in handles.values():env.close()
    protected=sorted(tasks);allow=set(mids)
    prep={'schema':'MAIN_EXISTING334_SECONDARY_CONTROL16_PREPARATION_V1',
        'status':'ROOT_APPROVED_EXISTING_PACKETS_FOR_SECONDARY_SOFTWARE_QA_ONLY','reviewer':'root','mode':CONTROL_MODE,
        'slice_id':slice_id,'endpoint_id':auth['endpoint_id'],'molecule_ids':mids,'allowed_original_control_ids':mids,
        'protected_original_population_ids':protected,'forbidden_original_population_ids':sorted(set(protected)-allow),
        'golden_expected':expected_rows,'tasks_reference':IO.reference(task_path),'selection_rule':control_selection_rule(),
        'selection_report_reference':ref(out/'eligible_count_report.json'),'root_control_authorization_reference':auth_ref,
        'qa_slice_marker_reference':ref(marker),'original_audit_reference':plan['partial_audit_report'],
        'original_complete_packages_reference':named(audit['outputs'],'complete_packages.json'),
        'partial_audit_monitor_closure_reference':plan['partial_audit_monitor_closure'],'original_pilot_parent_state':'TIMEOUT',
        'partial_audit_parent_job_id':'4520527','partial_audit_parent_state':'COMPLETED','main_preparation_on_legal_cpu_allocation':True,
        'main_preparation_runtime':{'job_id':str(proof['job_id']),'uid':os.getuid(),'node':proof['request']['node']},
        'root_preflight_reference':ref(a.root_preflight.absolute()),'population_members_added':0,'new_main_science_baseline_computed':False,
        'current_main_recovery_2plus14_scope_changed':False,'main_production_once_ledger_accessed':False,
        'formal_generation_authorized':False,'automatic_retry':False,'pickle_decoded_or_reconstructed':False,'new_main_UFF_QM_calls':0}
    write_json(out/'control_preparation.json',prep)
    print(json.dumps({'status':prep['status'],'controls':16,'preparation':ref(out/'control_preparation.json')}));return 0


if __name__=='__main__':raise SystemExit(main())
