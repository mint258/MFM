"""Root-only join of actual closed paired-SDK JSON; no SDK/journal/model access."""
from __future__ import annotations
import argparse, datetime, hashlib, importlib.util, json, os, re, socket, stat
from pathlib import Path

B=Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
HERE=Path(__file__).absolute().parent;META=2<<20
FILES={'close_metadata.py','dependencies.json','README.md'}
SEEN={}

def need(value,message):
    if not value:raise ValueError(message)

def reference(path):
    path=Path(path).absolute();a=path.lstat()
    need(path.resolve()==path and path.is_relative_to(B) and stat.S_ISREG(a.st_mode)
         and a.st_uid==1278 and a.st_nlink==1 and 0<a.st_size<=META,
         'Owned canonical bounded metadata/source required: '+str(path))
    need(path.suffix in ('.json','.py','.md','.sbatch') and not {'wandb','stage'}&set(path.parts),
         'Metadata/source only; SDK, staging payload, journals and arrays are forbidden')
    raw=path.read_bytes();z=path.lstat()
    need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns),
         'Metadata/source changed while read')
    ref=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    if str(path) in SEEN:need(SEEN[str(path)]==ref,'Metadata/source changed during closure')
    SEEN[str(path)]=ref
    return ref

def read(path):
    ref=reference(path);need(Path(path).suffix=='.json','Only JSON metadata is decoded')
    def pairs(items):
        result={}
        for key,value in items:need(key not in result,'Duplicate JSON key');result[key]=value
        return result
    value=json.loads(Path(path).read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    need(reference(path)==ref,'Metadata changed while parsed');return value,ref

def bound(ref,parse=True):
    need(type(ref) is dict and set(ref)=={'path','bytes','sha256'} and type(ref['bytes']) is int
         and type(ref['sha256']) is str and re.fullmatch('[0-9a-f]{64}',ref['sha256'])
         and reference(ref['path'])==ref,'Exact small rawref differs')
    return read(ref['path'])[0] if parse else ref

def explicit(path,sha):
    value,ref=read(path);need(ref['sha256']==sha,'Explicit actual metadata rawSHA differs');return value,ref

def package(expected):
    pins,pref=read(HERE/'source_pins.json')
    need(pref['sha256']==expected and pins['schema']=='model_v3_routing7_SDK_Root_closer_source_pins_v1'
         and len(pins['files'])==3 and {Path(r['path']).name for r in pins['files']}==FILES,'Exact three-leaf source package required')
    for row in pins['files']:need(Path(row['path']).parent==HERE,'Own source path differs');bound(row,False)
    deps,_=read(HERE/'dependencies.json')
    for row in deps['sources'].values():bound(row,False)
    for key in ('R1_consumer_pins','SDK_source_pins'):
        inventory=bound(deps['sources'][key]);parent=Path(deps['sources'][key]['path']).parent
        for row in inventory['files']:
            if 'path' in row:bound(row,False)
            else:
                current=reference(parent/row['relative_path'])
                need((current['bytes'],current['sha256'])==(row['bytes'],row['sha256']),'Frozen consumer/producer source differs')
    spec=importlib.util.spec_from_file_location('routing7_actual_R1_metadata_consumer',deps['sources']['R1_admission']['path'])
    consumer=importlib.util.module_from_spec(spec);spec.loader.exec_module(consumer)
    # Only parents/cpu_supervisor/exact/canonical are called, never qualify/routing/policy.
    return pref,deps,consumer

def actual_parent_nodes(raw,gpu_job,gpu_node,audit_job,audit_node,sync_job):
    columns='--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'
    argv=raw['argv'];jobs={gpu_job,audit_job,sync_job}
    need(type(argv) is list and len(argv)==7 and argv[:5]==['sacct','-X','-n','-P','-j'] and argv[6]==columns
         and len(argv[5].split(','))==3 and set(argv[5].split(','))==jobs,
         'Exact real GPU/audit/sync three-parent seven-column capture required')
    rows=[r.split('|') for r in raw['stdout'].splitlines() if r.strip()]
    need(len(jobs)==3 and len(rows)==3 and all(len(r)==7 for r in rows) and {r[0] for r in rows}==jobs,
         'Exactly the distinct GPU, SDK audit and SDK sync parents required; no metadata CPU or unrelated row')
    nodes={r[0]:r[6] for r in rows}
    need(nodes[gpu_job]==gpu_node and nodes[audit_job]==audit_node
         and re.fullmatch(r'compute-0-(?:[2-9]|1[0-9])',audit_node)
         and re.fullmatch(r'compute-0-(?:[2-9]|1[0-9])',nodes[sync_job]),'Actual original GPU/SDK CPU nodes differ')
    return nodes

def close(args,pref,deps,r1):
    numeric,nref=explicit(args.numeric_root,args.numeric_root_sha256)
    audit,aref=explicit(args.audit_result,args.audit_result_sha256)
    audit_sup,asref=explicit(args.audit_supervisor,args.audit_supervisor_sha256)
    sync,sref=explicit(args.sync_result,args.sync_result_sha256)
    sync_sup,ssref=explicit(args.sync_supervisor,args.sync_supervisor_sha256)
    accounting,account_ref=explicit(args.parent_sacct_json,args.parent_sacct_sha256)
    sdk_pin=deps['sources']['SDK_source_pins'];sdk_root=Path(sdk_pin['path']).parent
    plan=bound(deps['sources']['routing_plan']);cohort=numeric['old_job_id'];job=numeric['job_id']
    cases=[x for x in plan['cases'] if x['old_job_id']==cohort]
    need(plan['routing_version']==7 and len(cases)==1,'One of the original six routing7 cohorts required');case=cases[0]
    need(numeric['schema']=='model_v3_routing7_current_full_A_v2_Root_closure_v1'
         and numeric['status']=='CURRENT_SOURCE_FULL20_AND500_V2_PASS_ROOT_CLOSED' and numeric['failure'] is None
         and numeric['full_A_numeric_acceptance'] is True and numeric['actual_code_sha']==r1.CODE,
         'Actual positive numeric Root authority required')
    numeric_result=bound(numeric['metadata_CPU_result'])
    matches=[x for x in numeric_result['cases'] if x['old_job_id']==cohort and x['job_id']==job]
    need(len(matches)==1 and numeric_result['status']=='ALL_SELECTED_ROUTING7_FULL20_AND500_METADATA_VERIFIED_PENDING_ROOT_CPU_C0'
         and numeric_result['failure'] is None,'Numeric Root must join an actual positive same-case metadata result')
    numeric_case=matches[0];cfg=bound(numeric_case['closed_metadata']['configuration'])
    need(cfg['job_id']==job and cfg['configuration_sha256']==numeric['configuration_sha256']
         and cfg['gpu_uuid']==case['gpu_uuid'] and cfg['node'].split('.')[0]==case['expected_node'],
         'Actual numeric cohort/configuration/device binding differs')
    need(audit['schema']=='performance_routing7_Av2_R2_paired_log_batch_v1'
         and audit['scope']=='ROUTING7_AV2_R2_LOG_ONLY'
         and audit['status']=='ALL_TWO_PAIRED_LOGS_MATCHED_PENDING_ROOT_C0' and audit['failure'] is None
         and audit['returncode']==0 and r1.exact(audit['source_pins'],sdk_pin)
         and r1.exact(audit['source_refs_before'],audit['source_refs_after']),
         'Original full two-SDK audit/source closure required')
    audit_job=audit['actual_job_id'];sync_job=sync['actual_job_id']
    need(type(audit_job) is str and audit_job.isdigit() and type(sync_job) is str and sync_job.isdigit(),
         'Actual SDK audit and sync job IDs required')
    need(numeric_result['allocation']['job_id'] not in (audit_job,sync_job),
         'SDK audit/sync parents must be independent of the original metadata CPU parent')
    r1.cpu_supervisor(asref,job=audit_job,entry=sdk_root/'audit_paired.py')
    r1.cpu_supervisor(ssref,job=sync_job,entry=sdk_root/'sync_paired.py')
    need(audit_sup['command']==audit['actual_argv'] and sync_sup['command']==sync['actual_argv']
         and str(audit_sup['launch_identity']['slurm_job_id'])==audit_job
         and str(sync_sup['launch_identity']['slurm_job_id'])==sync_job
         and audit_sup['launch_identity']['uid']==sync_sup['launch_identity']['uid']==1278,
         'Actual SDK CPU launch/job/result binding differs')
    audit_node=audit['actual_allocation']['node']
    need(audit['actual_allocation']['job_id']==audit_job and audit['actual_allocation']['uid']==1278,
         'Actual SDK audit allocation/job/UID differs')
    nodes=actual_parent_nodes(accounting,job,case['expected_node'],audit_job,audit_node,sync_job)
    r1.parents(accounting,nodes)  # Same published R1 v2 C0/UID/16CPU/positive elapsed/node rule.
    inputs=bound(audit['inputs']);need(len(inputs['cases'])==1 and r1.exact(inputs['source_pins'],sdk_pin),
         'Actual source-bound one-pair audit input required')
    original=inputs['cases'][0]
    need(original['job_id']==job and original['old_job_id']==cohort and r1.exact(original['refs']['root'],nref),
         'Audit must consume this exact numeric Root rawref')
    audit_argv=[str(r1.B/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'),
        '-u','-B',str(sdk_root/'audit_paired.py'),'--inputs',audit['inputs']['path'],
        '--inputs-sha256',audit['inputs']['sha256'],'--pins-sha256',sdk_pin['sha256'],'--output',str(Path(aref['path']).parent)]
    need(audit['actual_argv']==audit_argv,'Original full audit actual argv differs')
    audit_qa,_=read(Path(aref['path']).parent/'INLINE_METADATA_QA.json')
    need(audit_qa['count']==6 and len(audit_qa['checks'])==6,'Original six actual audit controls required')
    need(sync['schema']=='performance_R2_paired_sync_result_v1' and sync['scope']==audit['scope']
         and sync['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0' and sync['failure'] is None
         and r1.exact(sync['source_manifest'],sdk_pin)
         and r1.exact(sync['source_refs_before'],sync['source_refs_after']),
         'Original official sync source/readback closure required')
    request=bound(sync['request']);manifest=bound(request['eligible_manifest'])
    need(request['schema']=='performance_routing7_Av2_R2_paired_selective_sync_request_v1'
         and r1.exact(request['source_manifest'],sdk_pin) and request['mode']=='batch'
         and manifest['schema']=='performance_routing7_Av2_R2_paired_sync_manifest_v1'
         and r1.exact(manifest['audit_result'],aref) and r1.exact(manifest['audit_supervisor'],asref)
         and r1.exact(manifest['verifications'],audit['verifications']),
         'Official sync must join these exact actual audit results/certificates')
    sync_argv=[str(r1.B/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'),
        '-u','-B',str(sdk_root/'sync_paired.py'),'--request',sync['request']['path'],
        '--request-sha256',sync['request']['sha256'],'--pins-sha256',sdk_pin['sha256'],'--output',str(Path(sref['path']).parent)]
    need(sync['actual_argv']==sync_argv,'Original official sync actual argv differs')
    sync_qa,_=read(Path(sref['path']).parent/'INLINE_METADATA_QA.json')
    need(sync_qa['count']==4 and len(sync_qa['checks'])==4,'Original four actual sync controls required')
    certs={};roles={}
    need(len(audit['verifications'])==2,'Exactly two original typed verification certificates required')
    for ref in audit['verifications']:
        cert=bound(ref);rid=cert['run_id'];role=cert['paired_role'];history=cert['history']
        need(cert['schema']=='performance_R2_paired_log_verification_v1' and cert['scope']==audit['scope']
             and cert['status']=='ALL_SAVED_PAIRED_LOG_FIELDS_MATCHED' and cert['model_job_id']==job
             and rid not in certs and role in ('reference','candidate')
             and r1.exact(cert['source_pins'],sdk_pin) and r1.exact(cert['inputs'],audit['inputs'])
             and cert['full_config_summary_typed_exact'] is True and cert['raw_before_after_binding_closed'] is True
             and r1.exact(cert['history_reader_source'],deps['sources']['SDK_literal749'])
             and r1.exact(cert['tap_source'],deps['sources']['SDK_tap2'])
             and cert['expected_config_sha256']==r1.digest({**cfg,'paired_role':role}),
             'Actual typed full-config/role/source certificate differs')
        header=cert['native_RunRecord']
        need(header['run_id']==rid and header['project']=='mfm_model_v3_development'
             and header['display_name']=='A_'+role+'_'+job and history['schema']=='model_v3_native_mirror_verification_v7'
             and history['status']=='VERIFIED_COMMITTED_HISTORY' and history['history_rows']==500
             and history['first_explicit_step']==1 and history['last_explicit_step']==500
             and history['clean_eof'] is history['native_closed'] is True and history['decode_error'] is None
             and type(history['uncommitted_native_requests']) is int and history['uncommitted_native_requests']==0
             and history['sdk_exit_codes']==[0] and history['sdk_run_ids']==[rid],
             'Actual original complete500/CRC+EOF/exit0 proof metadata differs')
        certs[rid]=(ref,cert);roles[rid]=role
    need(sorted(roles.values())==['candidate','reference']
         and audit['actual_native_role_mapping']=={rid:dict(model_job_id=job,paired_role=role) for rid,role in roles.items()},
         'Both independently decoded Native roles must join actual audit mapping')
    need(len(sync['records'])==2 and len(sync['requested_ids'])==2 and set(sync['requested_ids'])==set(certs)
         and request['selected_run_ids']==sync['requested_ids'],'Original exactly both audited IDs must be synchronized')
    runs=[];seen=set()
    for item in sync['records']:
        rid=item['run_id'];need(rid in certs and rid not in seen,'Unique actual sync/readback ID required');seen.add(rid)
        readback=bound(item['result']);actual=readback['actual_remote_metadata'];expected=readback['expected_remote_metadata']
        cert_ref,cert=certs[rid]
        need(readback['schema']=='model_v3_one_WandB_sync_readback_v1' and readback['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED'
             and readback['run_id']==rid and readback['failure'] is None and readback['native_exit_code']==0
             and readback['source_hash_before_after_equal'] is True and readback['original_sync_marker_unchanged'] is True
             and readback['original_SDK_repaired_or_deleted'] is False and r1.exact(actual,expected)
             and r1.exact(readback['source_manifest'],sdk_pin) and r1.exact(readback['original_source'],cert['sdk'])
             and actual['run_id']==rid and actual['entity']=='mint_leaf258' and actual['project']=='mfm_model_v3_development'
             and actual['state']=='finished' and actual['history_rows']==500 and actual['first_step']==1 and actual['last_step']==500
             and r1.exact(item['actual_remote_metadata'],actual) and item['native_exit_code']==0,
             'Actual original official selective readback/route/state/500 population differs')
        invocation=bound(item['actual_invocation'])
        need(str(invocation['job_id'])==sync_job and invocation['returncode']==0
             and str(sdk_root/'one_run_paired.py') in invocation['argv']
             and invocation['argv'].count('--run-id')==1
             and invocation['argv'][invocation['argv'].index('--run-id')+1]==rid,
             'Actual original one-file transport invocation differs')
        # SDK/journal/staged/log rawrefs remain opaque: no payload opens or rescans.
        runs.append(dict(run_id=rid,role=roles[rid],verification=cert_ref,sync_result=item['result'],history_rows=500))
    need(seen==set(certs),'Both actual readbacks must close')
    for path,ref in tuple(SEEN.items()):need(reference(path)==ref,'Input/source changed before Root closure')
    body=dict(schema='model_v3_routing7_current_paired_SDK_Root_closure_v1',
        status='NATIVE_FULL500_AND_OFFICIAL_SELECTIVE_SYNC_CLOUD_READBACK_CLOSED',failure=None,
        job_id=job,old_job_id=cohort,numeric_Root_closure=nref,audit_result=aref,audit_supervisor=asref,
        sync_result=sref,sync_supervisor=ssref,actual_sacct=accounting,actual_sacct_rawref=account_ref,runs=runs,
        scientific_acceptance=False,Root_SDK_journal_checkpoint_array_or_large_gate_payload_opened=False,
        source_package=pref,SDK_producer_source_pins=sdk_pin,R1_consumer_source_pins=deps['sources']['R1_consumer_pins'],
        captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    need(all(r1.contains_ref(body,ref) for ref in [nref,*[x['verification'] for x in runs],*[x['sync_result'] for x in runs]]),
         'Root must preserve every full original authority rawref')
    return body

def qualification_template(body,args,deps,r1):
    numeric=bound(body['numeric_Root_closure']);audit=bound(numeric['metadata_CPU_result']);cpu=audit['allocation']
    actual,actual_ref=explicit(args.metadata_cpu_parent_sacct,args.metadata_cpu_parent_sacct_sha256)
    r1.parents(actual,{cpu['job_id']:cpu['node']})
    r1.cpu_supervisor(numeric['metadata_CPU_supervisor'],job=cpu['job_id'],entry=Path(deps['sources']['numeric_audit_entry']['path']))
    return dict(schema='model_v3_remaining_Av2_R1_qualification_inputs_v1',cohort=body['old_job_id'],
        metadata_audit_result=numeric['metadata_CPU_result'],metadata_audit_supervisor=numeric['metadata_CPU_supervisor'],
        metadata_audit_parent_sacct=actual_ref,Root_numeric_closure=body['numeric_Root_closure'],SDK_closure=None,
        SDK_verifications=[r['verification'] for r in body['runs']],SDK_sync_results=[r['sync_result'] for r in body['runs']],
        SDK_CPU_supervisors=[body['audit_supervisor'],body['sync_supervisor']],SDK_parent_sacct=body['actual_sacct_rawref'])

def fresh_json(path):
    path=Path(path).absolute()
    need(path.parent==N and path.suffix=='.json' and path.resolve()==path and not path.exists(),
         'Fresh independent direct N Root JSON required')
    return path

def write_json(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();need(len(raw)<=META,'Compact Root output required')
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return reference(path)

def main():
    need(os.getuid()==os.geteuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
         and not os.environ.get('SLURM_JOB_ID'),'Root login small-metadata action only')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-pins-sha256',required=True)
    for name in ('numeric-root','audit-result','audit-supervisor','sync-result','sync-supervisor','parent-sacct-json'):
        parser.add_argument('--'+name,type=Path,required=True)
        sha='parent-sacct-sha256' if name=='parent-sacct-json' else name+'-sha256'
        parser.add_argument('--'+sha,required=True)
    parser.add_argument('--output-json',type=Path,required=True)
    parser.add_argument('--qualification-output',type=Path)
    parser.add_argument('--metadata-cpu-parent-sacct',type=Path);parser.add_argument('--metadata-cpu-parent-sacct-sha256')
    args=parser.parse_args();output=fresh_json(args.output_json);qpath=None
    if args.qualification_output is not None:
        need(args.metadata_cpu_parent_sacct is not None and args.metadata_cpu_parent_sacct_sha256 is not None,
             'Actual independent one-row metadata CPU C0 capture required for qualification input')
        qpath=fresh_json(args.qualification_output);need(qpath!=output,'Independent Root closure and qualification files required')
    else:need(args.metadata_cpu_parent_sacct is args.metadata_cpu_parent_sacct_sha256 is None,'Unused qualification parent inputs rejected')
    pref,deps,consumer=package(args.source_pins_sha256);body=close(args,pref,deps,consumer)
    q=qualification_template(body,args,deps,consumer) if qpath is not None else None
    for path,ref in tuple(SEEN.items()):need(reference(path)==ref,'Metadata/source changed before output commit')
    root_ref=write_json(output,body);qref=None
    if q is not None:q['SDK_closure']=root_ref;qref=write_json(qpath,q)
    print(json.dumps(dict(status=body['status'],Root_closure=root_ref,qualification_input=qref,
        R1_admission_or_submission_executed=False,job_id=body['job_id'],old_job_id=body['old_job_id']),sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
