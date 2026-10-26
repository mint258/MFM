"""Secondary alpha CPU-only fullCSV profile or separately reviewed plain SQL download."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,re,resource,socket,sys,time,traceback
from contracts import (SECONDARY_ROOT,ENDPOINT,UID,need,pin,load,verify,write_new,validate_alpha_authority,validate_startup,source_from_head,validate_primary_entry,parse_slurm_duration)
from transport import full_get,binary_reference,network_environment
from profile import profile_zip


def memory_observation():
    values={line.split(':',1)[0]:int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemAvailable:','MemTotal:'))}
    rss=int(pathlib.Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
    return {'observed_unix_seconds':time.time(),'self_RSS_bytes':rss,**values}


def main():
    validate_primary_entry(__file__,getattr(sys.modules.get('__main__'),'__file__',None),sys.argv)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=load(a.plan);review=load(verify(plan['root_review_reference']))
    need(os.getuid()==UID and os.environ.get('SLURM_JOB_ID','').isdecimal(),'SECONDARY_SLURM_OWNER_REQUIRED_BEFORE_WAIT')
    wait_started=time.monotonic();proof=None
    while proof is None:
        need(time.monotonic()-wait_started<=120,'NO_FRESH_SECONDARY_STARTUP_PROOF_WITHIN120_SECONDS')
        if not a.startup_proof.exists():time.sleep(.25);continue
        try:proof=load(a.startup_proof)
        except (FileNotFoundError,json.JSONDecodeError):time.sleep(.25)
    authority=load(verify(plan['resource_authority_reference']));validate_alpha_authority(authority)
    hostname=socket.gethostname().split('.')[0];node=os.environ.get('SLURMD_NODENAME') or os.environ.get('SLURM_JOB_NODELIST') or hostname
    boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    validate_startup(plan,pin(a.plan),review,pin(plan['root_review_reference']['path']),proof,uid=os.getuid(),node=node,
        hostname=hostname,env=dict(os.environ),boot_id=boot,now=time.time())
    need(pathlib.Path.cwd()==SECONDARY_ROOT and pathlib.Path(__file__).absolute()==SECONDARY_ROOT/'workflows/expansion/secondary_source_acquisition_v1/run_v1.py','ACTUAL_SECONDARY_CODE_AND_WORK_ROOT_REQUIRED')
    need(str(a.startup_proof)==plan['startup_proof_path'] and str(a.plan)==plan['plan_path'],'EXACT_ALPHA_PLAN_AND_PROOF_PATH_REQUIRED')
    for source in plan['source_references']:verify(source)
    need(source_from_head(load(plan['source_head_references'][plan['source']['source_id']]['path']),plan['source']['source_id'])==plan['source'],
        'EXACT_DEPLOYED_ACTUAL_HEAD_SOURCE_REQUIRED')
    need(plan['execution_argv'][1:]==['-B',str(pathlib.Path(__file__).absolute()),'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
        and sys.argv[1:]==plan['execution_argv'][3:],'EXACT_PRIMARY_OPTIONS_REQUIRED')
    need('.'.join(map(str,sys.version_info[:3]))==plan['python_version_expected'],'REVIEWED_BASE_PYTHON_VERSION_REQUIRED')
    need(pathlib.Path(sys.executable).absolute()==pathlib.Path(plan['execution_argv'][0]),'EXACT_REVIEWED_SECONDARY_PYTHON_EXECUTABLE_REQUIRED')
    out=pathlib.Path(plan['output_directory'])
    need(out.is_absolute() and SECONDARY_ROOT/'artifacts/source_acquisition' in out.parents and not out.exists(),'NEW_SECONDARY_OUTPUT_ONLY_NO_RESUME_OR_OVERWRITE')
    out.mkdir(parents=True,mode=0o700,exist_ok=False)
    started=time.monotonic();transfer=None;structural=None;error=None;memory=[];accepted=False;last_sample=[0.];last_retained=[0.];soft_stop=[None]
    memory_summary={'callback_observations_count':0,'max_self_RSS_bytes':0,'min_MemAvailable_bytes':None,'retention_maximum':2048,
        'retention_policy':'Retain first128 then at wall_seconds/1800 interval, plus separate final sample. Callback observes and updates extrema each second.'}
    runtime_fields=re.findall(r'(?:^|\s)RunTime=([^\s]+)',proof['job_metadata'])
    need(len(runtime_fields)==1,'ACTUAL_SCHEDULER_RUNTIME_REQUIRED_FOR_REMAINING_WALL')
    already_elapsed=parse_slurm_duration(runtime_fields[0])+max(0,time.time()-proof['observed_unix_seconds'])
    remaining=plan['wall_seconds']-already_elapsed
    need(remaining>330,'INSUFFICIENT_PARENT_WALL_FOR_NEW_GET_PROFILE')
    work_plan=dict(plan,curl_max_time_seconds=min(plan['curl_max_time_seconds'],int(remaining-300)))
    absolute_profile_deadline=started+remaining-30
    def observe_only():
        if time.monotonic()-last_sample[0]<1:return
        last_sample[0]=time.monotonic()
        try:
            row=memory_observation()
            if row['self_RSS_bytes']>plan['algorithm_self_rss_soft_limit_bytes']:soft_stop[0]='ALGORITHM_SELF_RSS_SOFT_LIMIT'
            if row['MemAvailable']<plan['minimum_mem_available_bytes']:soft_stop[0]='ACTUAL_MEMAVAILABLE_LOW'
        except Exception as exc:row={'metrics_available':False,'observation_error':repr(exc)};soft_stop[0]='ACTUAL_MEMORY_OBSERVATION_UNAVAILABLE'
        memory_summary['callback_observations_count']+=1
        if 'self_RSS_bytes' in row:
            memory_summary['max_self_RSS_bytes']=max(memory_summary['max_self_RSS_bytes'],row['self_RSS_bytes'])
            low=memory_summary['min_MemAvailable_bytes']
            memory_summary['min_MemAvailable_bytes']=row['MemAvailable'] if low is None else min(low,row['MemAvailable'])
        if len(memory)<2048 and (len(memory)<128 or time.monotonic()-last_retained[0]>=max(1,plan['wall_seconds']/1800)):
            memory.append(row);last_retained[0]=time.monotonic()
    def profile_checkpoint():
        observe_only();need(soft_stop[0] is None,'STOP_NEW_PROFILE_WORK_'+str(soft_stop[0]))
    software={'python':binary_reference(sys.executable),'python_version':sys.version,'curl':None}
    write_new(out/'started.json',{'schema':'SECONDARY_SOURCE_ACQUISITION_STARTED_V1','endpoint':ENDPOINT,'uid':UID,
        'job_id':os.environ['SLURM_JOB_ID'],'plan':pin(a.plan),'root_review':plan['root_review_reference'],
        'runtime_memory_environment':{k:os.environ.get(k) for k in ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},
        'memory_requested':False,'network_environment':network_environment(),'source_release_accepted':False})
    try:
        profile_checkpoint()
        transfer=full_get(work_plan,out,observe_only=observe_only);software['curl']=transfer.get('software')
        write_new(out/'transfer.json',transfer)
        need(transfer['payload_download_complete'],'FULL_GET_NOT_COMPLETE_KEEP_PARTIAL_NO_RETRY')
        profile_checkpoint()
        raw=pathlib.Path(transfer['payload_reference']['path'])
        if plan['stage']=='CSV_ZIP_PROFILE':
            structural=profile_zip(raw,plan['csv_limits'],absolute_profile_deadline,checkpoint=profile_checkpoint)
            write_new(out/'zip_csv_profile.json',structural)
        else:
            with raw.open('rb') as f:prefix=f.read(65536)
            need(not prefix.startswith((b'PK',b'\x1f\x8b',b'PGDMP',b'BZh',b'\xfd7zXZ')),'SQL_IS_PLAIN_NOT_ARCHIVE_OR_CUSTOM_DUMP')
            structural={'schema':'SECONDARY_PLAIN_SQL_PAYLOAD_MARKER_PROFILE_V1','read_prefix_bytes':len(prefix),
                'prefix_sha256':hashlib.sha256(prefix).hexdigest(),'postgres_dump_marker_observed':b'PostgreSQL database dump' in prefix,
                'CREATE_TABLE_marker_observed':b'CREATE TABLE' in prefix,'prefix_plaintext_persisted':False,
                'logical_database_rows_or_active_inactive_coverage_established':False}
            write_new(out/'sql_prefix_profile.json',structural)
        accepted=True
    except Exception as exc:error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    try:memory.append(memory_observation())
    except Exception as exc:memory.append({'metrics_available':False,'observation_error':repr(exc)})
    disk_bytes=sum(path.stat().st_size for path in out.rglob('*') if path.is_file())
    if disk_bytes+1024**2>plan['output_cap_bytes']:
        accepted=False;error={'type':'OutputBudget','message':'WHOLE_PROFILE_OUTPUT_CEILING_EXCEEDED','prior_error':error}
    result={'schema':'SECONDARY_COCONUT_ACQUISITION_RECEIPT_V1','status':('ACTUAL_CSV_ZIP_PROFILE_COMPLETE_NOT_IDENTITY_AUTHORITY' if plan['stage']=='CSV_ZIP_PROFILE' else 'ACTUAL_PLAIN_SQL_DOWNLOAD_COMPLETE_NOT_LOGICAL_COVERAGE') if accepted else 'SECONDARY_ACQUISITION_INCOMPLETE_OR_STOPPED',
        'stage':plan['stage'],'endpoint':ENDPOINT,'uid':os.getuid(),'username':'alpha','node':node,'hostname':hostname,'boot_id':boot,
        'job_id':os.environ['SLURM_JOB_ID'],'allocated_cpus_environment':os.environ.get('SLURM_CPUS_PER_TASK'),
        'network_workers':1,'CSV_parse_workers':1,'no_claim_of16_concurrent_downloads':True,
        'plan':pin(a.plan),'root_review':plan['root_review_reference'],'startup_proof':pin(a.startup_proof),
        'resource_authority':plan['resource_authority_reference'],'inherited_main_HEAD_evidence':plan['parent_evidence_references'],
        'source':plan['source'],'transfer':pin(out/'transfer.json') if (out/'transfer.json').is_file() else None,
        'payload_reference':transfer.get('payload_reference') if transfer else None,
        'payload_download_complete':bool(transfer and transfer.get('payload_download_complete')),
        'structural_profile':pin(out/('zip_csv_profile.json' if plan['stage']=='CSV_ZIP_PROFILE' else 'sql_prefix_profile.json')) if (out/('zip_csv_profile.json' if plan['stage']=='CSV_ZIP_PROFILE' else 'sql_prefix_profile.json')).is_file() else None,
        'software_references':software,'actual_memory_observations':memory,'memory_observation_summary':memory_summary,'memory_soft_stop':soft_stop[0],
        'self_resource_usage':{'user_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime,'system_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_stime,
           'max_RSS_bytes_linux':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'not_allocated_core_seconds':True},
        'wall_seconds_observed':time.monotonic()-started,'scheduler_elapsed_seconds_at_new_work_start':already_elapsed,
        'download_wall_seconds_observed':transfer.get('download_wall_seconds_observed') if transfer else None,
        'output_bytes_before_receipt':disk_bytes,'error':error,
        'HTTP403_429_retry_or_bypass_performed':False,'partial_files_preserved':True,'signals_sent':False,'automatic_retry':False,
        'inactive_coverage_proven':False,'clock_month_or_ETag_used_as_SHA_or_release_pin':False,
        'identity_normalization_performed':False,'candidate_pool_or_training_released':False,
        'allocated_core_seconds':None,'cost_status':'Root must attach this endpoint actual terminal sacct parent, including failures; no monetary-charge claim changes core accounting.',
        'SQL_auto_submission_or_promotion':False}
    write_new(out/'receipt.json',result)
    print(json.dumps({'status':result['status'],'receipt':pin(out/'receipt.json'),'endpoint':ENDPOINT,'uid':UID,'job_id':result['job_id']}))
    return 0 if accepted else 3
if __name__=='__main__':sys.exit(main())
