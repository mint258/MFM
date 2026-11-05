"""Join actual R1v3 four-SDK/audit/sync/report JSON; never read payloads."""
from __future__ import annotations
import argparse, datetime, hashlib, importlib.util, json, os, re, socket
from pathlib import Path
B=Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
HERE=Path(__file__).absolute().parent;ROLES=('reference','candidate','candidate','reference')
SCOPE='REMAINING_R1V3_ABBA_LOG_AND_EXISTING_SPEED_REPORT_ONLY'

def need(value,message):
    if not value:raise ValueError(message)

def bootstrap(pin_sha):
    # This existing pure-stdlib module supplies the already reviewed bounded JSON
    # guard, exact rawref reader and fresh output writer. Its close/main are unused.
    old=N/'routing7_paired_SDK_Root_closer_v2_source/close_metadata.py'
    raw=old.read_bytes()
    need(hashlib.sha256(raw).hexdigest()=='0e0125cb4366bb98e4f5a3eac48ad8aa632fa9046f7e73d14a5c830d83762a94',
         'Frozen pure JSON guard must match before import')
    spec=importlib.util.spec_from_file_location('remaining_R1_root_JSON_primitives',old)
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    pins,pref=p.read(HERE/'source_pins.json');need(pref['sha256']==pin_sha
        and pins['schema']=='model_v3_remaining_R1v3_SDK_Root_closer_sources_v1'
        and len(pins['files'])==3,'Exact frozen Root closer package required')
    for ref in pins['files']:need(Path(ref['path']).parent==HERE,'Own source path differs');p.bound(ref,False)
    deps,_=p.read(HERE/'dependencies.json')
    need(hashlib.sha256(raw).hexdigest()==deps['sources']['JSON_primitives']['sha256'],'Original metadata guard changed before import')
    for ref in deps['sources'].values():p.bound(ref,False)
    r=deps['sources']['R1_admission'];spec=importlib.util.spec_from_file_location('remaining_R1v3_pure_metadata',r['path'])
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.verify_package(deps['sources']['R1_source_pins']['sha256'])
    sdk=p.bound(deps['sources']['SDK_source_pins'])
    for row in sdk['files']:
        ref=p.reference(Path(deps['sources']['SDK_source_pins']['path']).parent/row['relative_path'])
        need((ref['bytes'],ref['sha256'])==(row['bytes'],row['sha256']),'Frozen original four-SDK producer changed')
    pub=p.bound(deps['sources']['SDK_method_publication'])
    need(pub['schema']=='model_v3_exact_tree_publication_actual_v1' and pub['repository_full_name']=='mint258/MFM'
        and pub['branch']=='model-v3' and pub['public_branch_readback_verified'] is True
        and pub['public_Git_API_tree_readback_verified'] is True,'Actual SDK source publication/readbacks required')
    table={r['path']:r for r in pub['files']};need(len(table)==len(pub['files']),'Duplicate publication blobs')
    sdk_dir=Path(deps['sources']['SDK_source_pins']['path']).parent
    for name in [r['relative_path'] for r in sdk['files']]+['source_pins.json']:
        body=(sdk_dir/name).read_bytes();blob=table[sdk['method_prefix']+name]
        need(blob['type']=='blob' and blob['sha']==hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest(),
             'Published original SDK source blob differs')
    return p,m,deps,pref

def identity(sup,job):
    row=sup['launch_identity'];need(row['uid']==1278 and str(row['slurm_job_id'])==job
        and type(row['pid']) is int and row['pid']>0 and type(row['start_ticks']) is int and row['start_ticks']>0
        and row['pgid']==row['sid']==row['pid'] and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',row['boot_id'])
        and re.search(r'(?:job[_/-])'+re.escape(job)+r'(?:/|\n|$)',row['cgroup'])
        and row['argv']==sup['command'],'Original owned kernel identity/argv/job binding differs')

def accounting(raw,expected,m):
    columns='JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList';argv=raw['argv'];jobs=set(expected)
    if len(argv)==7 and argv[:5]==['sacct','-X','-n','-P','-j'] and argv[6]=='--format='+columns:selection=argv[5]
    elif len(argv)==8 and argv[:3]==['sacct','-X','-j'] and argv[4:]==['-n','-P','-o',columns]:selection=argv[3]
    else:raise ValueError('Exact original seven-column sacct argv required')
    need(len(jobs)==7 and len(selection.split(','))==7 and set(selection.split(','))==jobs,
        'Actual exact seven distinct R1 GPU/audit/sync parents required')
    need(raw['returncode']==0 and raw['stderr']=='','Actual seven-parent accounting failed')
    rows=[r.split('|') for r in raw['stdout'].splitlines() if r.strip()]
    need(len(rows)==7 and all(len(r)==7 for r in rows) and {r[0] for r in rows}==jobs,'Exact seven actual parent rows required')
    result={}
    for row in rows:
        node=expected[row[0]]
        need(row[1:4]==['zixiao','COMPLETED','0:0'] and row[4].isdigit() and int(row[4])>0
            and row[5]=='16' and (node is None or row[6]==node),'Actual owned C0/16CPU/positive elapsed/node differs')
        if node is None:need(re.fullmatch(r'compute-0-(?:[2-9]|1[0-9])',row[6]),'Actual SDK CPU node required')
        result[row[0]]=dict(job_id=row[0],node=row[6],elapsed_seconds=int(row[4]),state='COMPLETED',exit_code='0:0',CPUs=16)
    return result

def close(args,p,m,deps,pref):
    a,ar=p.explicit(args.audit_result,args.audit_result_sha256);asu,asr=p.explicit(args.audit_supervisor,args.audit_supervisor_sha256)
    s12,s12r=p.explicit(args.sync12_result,args.sync12_result_sha256);u12,u12r=p.explicit(args.sync12_supervisor,args.sync12_supervisor_sha256)
    s34,s34r=p.explicit(args.sync34_result,args.sync34_result_sha256);u34,u34r=p.explicit(args.sync34_supervisor,args.sync34_supervisor_sha256)
    sacct,sacctref=p.explicit(args.parent_sacct_json,args.parent_sacct_sha256)
    sdk_pin=deps['sources']['SDK_source_pins'];sdk_root=Path(sdk_pin['path']).parent
    need(a['schema']=='performance_manual_R1_ABBA_log_batch_v1' and a['scope']==SCOPE
        and a['status']=='ALL_FOUR_STANDALONE_LOGS_AND_ORIGINAL_SPEED_REPORT_CLOSED_PENDING_ROOT_C0'
        and a['failure'] is None and a['returncode']==0 and m.exact(a['source_pins'],sdk_pin)
        and m.exact(a['source_refs_before'],a['source_refs_after']),'Actual complete original four-SDK/report audit required')
    inputs=p.bound(a['inputs']);members=inputs['members'];cohort=inputs['cohort'];series=inputs['series_id']
    need(inputs['schema']=='performance_manual_R1_ABBA_log_inputs_v1' and inputs['scope']==SCOPE
        and len(members)==4 and [x['position'] for x in members]==[1,2,3,4]
        and [x['role'] for x in members]==list(ROLES) and len(a['verifications'])==4,
        'One actual ordered four-member ABBA input and exactly four certificates required')
    template=p.bound(deps['sources']['R1_PLAN']);routing=p.bound(deps['sources']['routing_PLAN'])
    need(cohort in template['cohorts'],'Original six-cohort selector required');decl=template['cohorts'][cohort]
    cases=[r for r in routing['cases'] if r['old_job_id']==cohort];need(len(cases)==1,'Unique original routed case required');case=cases[0]
    need(series==decl['series_id'],'Actual fresh R1v3 series required')
    contexts=[];gpu_jobs=[];configs=[];pub_ref=None;qual_ref=None;runs=[]
    for item,role in zip(members,ROLES):
        pos=item['position'];job=item['job_id'];rid=item['run_id'];refs=item['refs']
        selector=p.bound(item['root']);c=p.bound(refs['configuration']);summary=p.bound(refs['summary'])
        status=p.bound(refs['run_status']);sup=p.bound(refs['supervisor']);sub=p.bound(refs['submission']);bound=p.bound(refs['bound_cohort'])
        family=Path(decl['family'])/('member_'+str(pos))
        need(selector['schema']=='model_v3_remaining_R1v3_SDK_member_selector_v1' and selector['cohort']==cohort
            and selector['position']==pos and selector['role']==role and selector['refs']==refs
            and refs['configuration']['path']==str(family/'child/configuration.json')
            and refs['supervisor']['path']==str(family/'supervisor.json'),'Actual original member selector/location differs')
        need(sub['schema']=='model_v3_remaining_Av2_R1_Root_single_submission_v1' and sub['status']=='SUBMITTED'
            and sub['job_id']==job and sub['cohort']==cohort and sub['position']==pos and sub['role']==role
            and m.exact(sub['source_package'],deps['sources']['R1_source_pins'])
            and sub['bound_cohort']==refs['bound_cohort'] and sub['qualification']==refs['qualification'],
            'Actual frozen R1v3 single-submission identity differs')
        m.verify_method(sub['method_publication'])
        if pub_ref is None:pub_ref=sub['method_publication'];qual_ref=sub['qualification']
        need(sub['method_publication']==pub_ref and sub['qualification']==qual_ref
            and bound['method_publication']==pub_ref and bound['qualification_input']==qual_ref,
            'Same actual v3 method and R2 qualification required for all four')
        need(c['job_id']==str(sup['job_id'])==job and c['role']==summary['role']==role
            and c['abba_position']==summary['abba_position']==pos and c['series_id']==summary['series_id']==series
            and c['code_sha']==summary['code_sha']==m.CODE and c['prereg_sha']==summary['prereg_sha']==m.PUBLIC
            and c['gpu_uuid']==summary['gpu_uuid']==sup['gpu_uuid']==case['gpu_uuid']
            and c['node'].split('.')[0]==case['expected_node'] and c['seed']==summary['seed']==0
            and c['input']==summary['input']=='native_s' and c['smoke'] is summary['smoke'] is False
            and c['warmup_updates']==summary['warmup_updates']==2 and c['measured_updates']==summary['measured_updates']==20
            and 'performance_execution' not in c and 'performance_execution_request' not in c,
            'Actual ordinary same-card/source/seed/ABBA2+20 identity differs')
        need(summary['status']==status['status']=='STANDALONE_TIMING_COMPLETED' and status['failure'] is None
            and status['cleanup_errors']==[] and status['stream_cleanup']['errors']==[]
            and status['stream_cleanup']['input_descriptors_closed'] is True
            and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
            and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[]
            and sup['foreign_gpu_processes_signalled'] is False,'Actual original process/trainer/SDK/input cleanup required')
        identity(sup,job)
        private=sup['private_storage_final']
        need(sup['supervisor_source_sha256']==deps['sources']['GPU_supervisor']['sha256']
            and sup['output_budget_bytes']==2<<30 and private['budget_bytes']==2<<30
            and private['first_sampling_failure'] is None and private['exact_peak'] is False
            and 0<=private['sampled_max_bytes']<=2<<30,'Original GPU source/whole/private closure differs')
        need(m.canonical({k:v for k,v in c.items() if k!='configuration_sha256'})==c['configuration_sha256']==summary['configuration_sha256']
            and summary['tracking_run_id']==rid,'Actual complete configuration/tracking identity differs')
        cert_refs=[r for r in a['verifications'] if p.bound(r)['position']==pos];need(len(cert_refs)==1,'One original typed certificate per position required')
        cr=cert_refs[0];cert=p.bound(cr);h=cert['history'];head=cert['native_RunRecord']
        need(cert['schema']=='performance_manual_R1_ABBA_log_verification_v1' and cert['scope']==SCOPE
            and cert['status']=='ALL_SAVED_STANDALONE_LOG_FIELDS_MATCHED' and cert['run_id']==rid
            and cert['model_job_id']==job and cert['position']==pos and cert['role']==role
            and m.exact(cert['source_pins'],sdk_pin) and m.exact(cert['inputs'],a['inputs'])
            and cert['full_config_summary_typed_exact'] is True and cert['raw_before_after_binding_closed'] is True
            and m.exact(cert['history_reader_source'],deps['sources']['literal_reader']) and m.exact(cert['tap_source'],deps['sources']['tap'])
            and cert['expected_config_sha256']==m.digest(c) and re.fullmatch('[0-9a-f]{64}',cert['expected_summary_sha256']),
            'Actual original full typed config/summary/role/source digest proof differs')
        need(head['run_id']==rid and head['project']=='mfm_model_v3_development' and head['display_name']=='A_speed_'+role+'_'+job
            and h['schema']=='model_v3_native_mirror_verification_v7' and h['status']=='VERIFIED_COMMITTED_HISTORY'
            and type(h['history_rows']) is int and h['history_rows']==22 and h['first_explicit_step']==1 and h['last_explicit_step']==22
            and h['clean_eof'] is h['native_closed'] is True and h['decode_error'] is None
            and type(h['uncommitted_native_requests']) is int and h['uncommitted_native_requests']==0
            and h['sdk_exit_codes']==[0] and h['sdk_run_ids']==[rid], 'Original complete22/typed/framing/EOF/exit0 proof required')
        contexts.append((item,cert,cr));gpu_jobs.append(job);configs.append(c)
        runs.append(dict(run_id=rid,role=role,position=pos,job_id=job,verification=cr,history_rows=22,
            configuration=refs['configuration'],summary=refs['summary'],run_status=refs['run_status'],supervisor=refs['supervisor']))
    need(len(set(gpu_jobs))==len({r['run_id'] for r in runs})==4,'Distinct actual four GPU jobs and runs required')
    q=p.bound(qual_ref);numeric_ref=q['Root_numeric_closure'];r2sdk_ref=q['SDK_closure']
    numeric=p.bound(numeric_ref);r2sdk=p.bound(r2sdk_ref)
    need(q['schema']=='model_v3_remaining_Av2_R1_qualification_inputs_v1' and q['cohort']==cohort
        and numeric_ref==inputs['numeric_gate']['Root_closure'] and numeric['old_job_id']==cohort
        and numeric['status']=='CURRENT_SOURCE_FULL20_AND500_V2_PASS_ROOT_CLOSED' and numeric['failure'] is None
        and numeric['full_A_numeric_acceptance'] is True and numeric['actual_code_sha']==m.CODE
        and r2sdk['numeric_Root_closure']==numeric_ref and r2sdk['old_job_id']==cohort
        and r2sdk['status']=='NATIVE_FULL500_AND_OFFICIAL_SELECTIVE_SYNC_CLOUD_READBACK_CLOSED' and r2sdk['failure'] is None,
        'Original full R2 numeric and independent SDK qualifications must remain linked')
    aj=a['actual_job_id'];m.cpu_supervisor(asr,job=aj,entry=sdk_root/'audit_abba.py');identity(asu,aj)
    python=str(m.B/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python')
    audit_argv=[python,'-u','-B',str(sdk_root/'audit_abba.py'),'--inputs',a['inputs']['path'],
        '--inputs-sha256',a['inputs']['sha256'],'--pins-sha256',sdk_pin['sha256'],'--output',str(Path(ar['path']).parent)]
    need(asu['command']==a['actual_argv']==audit_argv and asu['launch_identity']['uid']==1278,'Actual audit CPU command/UID/input differs')
    need(a['actual_allocation']['job_id']==aj and a['actual_allocation']['uid']==1278
        and re.fullmatch(r'compute-0-(?:[2-9]|1[0-9])',a['actual_allocation']['node']), 'Actual original audit CPU allocation differs')
    expected={j:case['expected_node'] for j in gpu_jobs};expected[aj]=a['actual_allocation']['node']
    sync_refs=[];sync_sup_refs=[];seen=set();readback_refs=[]
    for s,sr,sup,supr,positions in ((s12,s12r,u12,u12r,[1,2]),(s34,s34r,u34,u34r,[3,4])):
        sj=s['actual_job_id'];need(sj not in expected,'Distinct actual seven parents required');expected[sj]=None
        m.cpu_supervisor(supr,job=sj,entry=sdk_root/'sync_abba.py');identity(sup,sj)
        need(s['schema']=='performance_manual_R1_ABBA_sync_result_v1' and s['scope']==SCOPE
            and s['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0' and s['failure'] is None
            and m.exact(s['source_manifest'],sdk_pin) and m.exact(s['source_refs_before'],s['source_refs_after'])
            and sup['command']==s['actual_argv'] and len(s['records'])==2,'Actual original selective2+2 sync closure required')
        request=p.bound(s['request']);manifest=p.bound(request['eligible_manifest'])
        ids=[runs[k-1]['run_id'] for k in positions]
        need(request['schema']=='performance_manual_R1_ABBA_selective_sync_request_v1' and request['mode']=='batch'
            and request['maximum_batch_runs']==3 and request['child_seconds']==3000
            and request['CLI_timeout_seconds']==600 and request['API_verification_seconds']==180
            and manifest['schema']=='performance_manual_R1_ABBA_sync_manifest_v1'
            and request['selected_positions']==positions and request['selected_run_ids']==s['requested_ids']==ids
            and request['source_manifest']==sdk_pin and manifest['audit_result']==ar and manifest['audit_supervisor']==asr
            and manifest['verifications']==a['verifications'],'Exact certified positions1+2 then3+4 request/manifest required')
        sync_argv=[python,'-u','-B',str(sdk_root/'sync_abba.py'),'--request',s['request']['path'],
            '--request-sha256',s['request']['sha256'],'--pins-sha256',sdk_pin['sha256'],'--output',str(Path(sr['path']).parent)]
        need(s['actual_argv']==sync_argv,'Original official2+2 sync actual request/argv differs')
        for item in s['records']:
            rid=item['run_id'];need(rid in ids and rid not in seen,'Unique actual selected readback required');seen.add(rid)
            rr=item['result'];rb=p.bound(rr);remote=rb['actual_remote_metadata'];idx=next(i for i,r in enumerate(runs) if r['run_id']==rid)
            cert=contexts[idx][1]
            need(rb['schema']=='model_v3_one_WandB_sync_readback_v1' and rb['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED'
                and rb['run_id']==rid and rb['failure'] is None and rb['native_exit_code']==0
                and rb['source_hash_before_after_equal'] is True and rb['original_sync_marker_unchanged'] is True
                and rb['original_SDK_repaired_or_deleted'] is False and m.exact(remote,rb['expected_remote_metadata'])
                and m.exact(rb['source_manifest'],sdk_pin) and m.exact(rb['original_source'],cert['sdk'])
                and remote['entity']=='mint_leaf258' and remote['project']=='mfm_model_v3_development' and remote['run_id']==rid
                and remote['state']=='finished' and remote['history_rows']==22 and remote['first_step']==1 and remote['last_step']==22
                and m.exact(item['actual_remote_metadata'],remote),'Original official full22 cloud route/state/readback proof differs')
            invocation=p.bound(item['actual_invocation'])
            need(str(invocation['job_id'])==sj and invocation['returncode']==0 and str(sdk_root/'one_run_abba.py') in invocation['argv']
                and invocation['argv'][invocation['argv'].index('--run-id')+1]==rid,'Actual original one-file invocation differs')
            runs[idx]['sync_result']=rr;runs[idx]['sync_batch']=sr;runs[idx]['actual_remote_metadata']=remote;readback_refs.append(rr)
        sync_refs.append(sr);sync_sup_refs.append(supr)
    need(seen=={r['run_id'] for r in runs},'All four actual cloud readbacks required')
    parents=accounting(sacct,expected,m)
    report=p.bound(a['speed_report']);inv=p.bound(a['speed_report_invocation']);gate=inputs['numeric_gate']
    report_path=Path(ar['path']).parent/'ORIGINAL_A_SPEED_REPORT.json'
    argv=[str(m.B/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'),'-B',deps['sources']['speed_report']['path'],
        '--runs',*[str(Path(x['refs']['configuration']['path']).parent) for x in members],
        '--supervisors',*[x['refs']['supervisor']['path'] for x in members],'--numeric-gate',gate['directory'],'--output',str(report_path)]
    member_refs=[{k:{'path':x['refs'][k]['path'],'sha256':x['refs'][k]['sha256']} for k in ('summary','configuration','run_status','supervisor')} for x in members]
    gate_refs={k:{'path':v['path'],'sha256':v['sha256']} for k,v in gate['files'].items()}
    need(inv['returncode']==0 and inv['job_id']==aj and inv['argv']==argv and inv['source']==deps['sources']['speed_report']
        and inv['report']==a['speed_report'] and a['speed_report']['path']==str(report_path)
        and report['schema']=='model_v3_A_ABBA_speed_v1' and report['has_matched_A_numeric_acceptance'] is True
        and report['numeric_acceptance_granted_by_this_report'] is False and report['member_file_bindings']==member_refs
        and report['numeric_gate_file_bindings']==gate_refs and report['report_source_sha256']==deps['sources']['speed_report']['sha256'],
        'Original speed CLI/report/source/input binding differs; no metrics are recomputed here')
    qa,_=p.read(Path(ar['path']).parent/'INLINE_METADATA_QA.json');need(qa['count']==6 and len(qa['checks'])==6,'Original six audit controls required')
    for sr in sync_refs:
        qa,_=p.read(Path(sr['path']).parent/'INLINE_METADATA_QA.json');need(qa['count']==4 and len(qa['checks'])==4,'Original four sync controls required')
    for r in runs:r['actual_GPU_parent']=parents[r['job_id']]
    body=dict(schema='model_v3_remaining_R1v3_ABBA_Root_closure_v1',
        status='FOUR_C0_NATIVE_SDK_AND_ORIGINAL_SPEED_REPORT_OFFICIAL_SYNC_CLOUD_READBACK_CLOSED',failure=None,
        cohort=cohort,series_id=series,code_sha=m.CODE,gpu_uuid=case['gpu_uuid'],model_GPU_jobs=gpu_jobs,
        SDK_audit_CPU_job=aj,SDK_sync_CPU_jobs=[s12['actual_job_id'],s34['actual_job_id']],actual_sacct=sacct,
        actual_sacct_rawref=sacctref,audit=ar,audit_supervisor=asr,verifications=a['verifications'],syncs=sync_refs,
        sync_supervisors=sync_sup_refs,sync_run_results=readback_refs,runs=runs,all_GPU_supervisors=[r['supervisor'] for r in runs],
        history_rows_each=22,warmup_updates=2,measured_updates=20,speed_report=a['speed_report'],speed_report_invocation=a['speed_report_invocation'],
        qualification_input=qual_ref,numeric_Root_closure=numeric_ref,R2_SDK_Root_closure=r2sdk_ref,method_publication=pub_ref,
        source_pins=sdk_pin,Root_closer_source_pins=pref,scientific_acceptance=False,scientific_adoption=False,speedup_adopted=False,
        full_guide_completed=False,original_SDKs_retained=True,Root_SDK_steps_resource_journal_large_gate_or_model_body_read=False,
        captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    pub=p.bound(pub_ref);csv_rows=[]
    for c,r in zip(configs,runs):
        snapshot=c['data_version']['original_shard_snapshot']
        csv_rows.append(dict(csv_fields=dict(run_id=r['run_id'],stage='2',config_sha256=r['configuration']['sha256'],code_sha=m.CODE,
            data_version='original_NativeS_not_D5_snapshot_sha256:'+snapshot['sha256'],seed=0,gpu_model=c['gpu_name'],gpu_uuid=c['gpu_uuid'],
            elapsed_seconds=r['actual_GPU_parent']['elapsed_seconds'],status='COMPLETED',preregistration_sha=pub['public_code_sha']),
            binding=r,source_snapshot_identity={k:snapshot[k] for k in ('path','bytes','sha256')},speed_authority=a['speed_report']))
    return body,csv_rows

def main():
    need(os.getuid()==os.geteuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID'),
        'Explicit Root small-metadata login action only')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-pins-sha256',required=True)
    for name in ('audit-result','audit-supervisor','sync12-result','sync12-supervisor','sync34-result','sync34-supervisor','parent-sacct-json'):
        parser.add_argument('--'+name,type=Path,required=True)
        parser.add_argument('--'+('parent-sacct-sha256' if name=='parent-sacct-json' else name+'-sha256'),required=True)
    parser.add_argument('--output-json',type=Path,required=True);parser.add_argument('--csv-index-json',type=Path);args=parser.parse_args()
    p,m,deps,pref=bootstrap(args.source_pins_sha256);output=p.fresh_json(args.output_json)
    index=p.fresh_json(args.csv_index_json) if args.csv_index_json is not None else None
    need(index!=output,'Separate output paths required');body,rows=close(args,p,m,deps,pref)
    for path,ref in tuple(p.SEEN.items()):need(p.reference(path)==ref,'Metadata/source changed before Root closure')
    rr=p.write_json(output,body);ir=None
    if index is not None:ir=p.write_json(index,dict(schema='model_v3_remaining_R1v3_standard_CSV_inputs_v1',Root_closure=rr,
        records=rows,metrics_recomputed=False,elapsed_semantics='Actual single-member GPU parent including setup/finalization',
        data_scope='Existing NativeS source snapshot, not Data D5 or another pretraining seed',cost_ledger_or_daily_report=False))
    print(json.dumps(dict(status=body['status'],Root_closure=rr,CSV_input_index=ir),sort_keys=True));return 0

if __name__=='__main__':raise SystemExit(main())
