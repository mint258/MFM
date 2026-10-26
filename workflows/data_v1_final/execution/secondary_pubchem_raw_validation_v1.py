"""Alpha CPU verification of one exact Main public gzip copy; no chemistry."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,os,socket,stat,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q

ROOT=Path('/gfshome/alpha/codex_data_v1_20261026')
MAIN=Path('/share/home/zixiao/descriptor_analysis')
ENDPOINT='218.192.171.238:22';UID=1264
MODULE='secondary_pubchem_raw_validation_v1'
KEY='pubchem_original_raw_copy_validation_alpha_v1'
STAGE='PUBLIC_RAW_COPY_SHA_GZIP_EOF'
PLAN='SECONDARY_PUBLIC_RAW_PIN_VALIDATION_PLAN_V1'
PROOF='SECONDARY_PUBLIC_RAW_PIN_VALIDATION_STARTUP_V1'
URL='https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/CID-SMILES.gz'
COMPRESSED=1488715010;DECODED=8880849781;ROWS=124857440
SHA='2504bc00da1b0587ae208d8a5fb2a4fe6043c215436150f2023d59c57c5cd2b7'
CHUNK=4<<20;CAP=64<<20;SOFT_RSS=2<<30
PARAMETERS={'main_acquisition_job_id':'4520348','main_inventory_job_id':'4521093',
    'compressed_bytes':COMPRESSED,'compressed_sha256':SHA,'uncompressed_bytes':DECODED,'physical_rows':ROWS,
    'single_stream_reader':True,'new_network_requests':0,'chemical_parsing':False,
    'population_members_added':0,'feature_profile_authorized':False}


def need(ok,code):
    if not ok:raise ValueError(code)


def triple(value):
    need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and Path(value['path']).is_absolute() and
         type(value['bytes']) is int and value['bytes']>=0 and isinstance(value['sha256'],str) and
         len(value['sha256'])==64 and set(value['sha256'])<=set('0123456789abcdef'),'EXACT_FILE_REFERENCE_REQUIRED')
    return value


def source(value,declared):
    value=triple(value)
    need(ROOT in Path(value['path']).parents and declared.get(value['path'])==value,'DECLARED_ACTUAL_ALPHA_SMALL_TARGET_REQUIRED')
    return Q.verify(value)


def small(value,declared):return Q.load(source(value,declared))


def startup(plan_path,proof_path):
    plan=Q.load(plan_path);review=Q.load_ref(plan['root_review_reference']);proof=Q.load(proof_path)
    primary=ROOT/'code/secondary_pubchem_raw_validation_v1.py'
    argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    need(Path(__file__).absolute()==primary==Path(sys.modules['__main__'].__file__).absolute() and
         Path(sys.executable).absolute()==Path(plan['python']).absolute() and sys.argv==[str(primary),*argv[4:]],
         'ACTUAL_PRIMARY_INTERPRETER_AND_COMPLETE_ARGV_REQUIRED')
    need(plan.get('schema')==PLAN and plan.get('producer_key')==plan.get('scope_key')==KEY and
         plan.get('stage')==STAGE and plan.get('scope_parameters')==PARAMETERS and plan.get('endpoint')==ENDPOINT and
         plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node') in Q.NODES and
         plan.get('cpus')==16 and plan.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and plan.get('pilot') is False and
         plan.get('wall_seconds')==3600 and plan.get('output_cap_bytes')==CAP and plan['execution_argv']==argv and
         plan['startup_proof_path']==str(proof_path),'EXACT_PUBLIC_RAW_COPY_VALIDATION_PLAN_REQUIRED')
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and
         review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root','ROOT_EXACT_READONLY_REVIEW_REQUIRED')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot',
                'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references'):
        need(plan[key]==review[key],'EXACT_ROOT_REVIEW_FIELD_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'],'EXACT_ROOT_APPROVED_SOURCES_REQUIRED')
    need(proof.get('schema')==PROOF and proof.get('endpoint')==ENDPOINT and proof.get('uid')==os.getuid()==UID and
         proof['node']==plan['node']==socket.gethostname().split('.')[0] and
         proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'FRESH_ACTUAL_ALPHA_UID_NODE_BOOT_REQUIRED')
    env=os.environ
    need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and
         env.get('SLURM_CPUS_PER_TASK')=='16' and env.get('CUDA_VISIBLE_DEVICES')=='' and
         all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),
         'ACTUAL_CPU16_NO_GPU_ONE_LIBRARY_THREAD_REQUIRED')
    need(0<=time.time()-proof['observed_unix_seconds']<=120 and proof['plan_reference']==Q.ref(plan_path) and
         proof['root_review_reference']==plan['root_review_reference'],'FRESH_EXACT_ALPHA_READONLY_PROOF_REQUIRED')
    need(proof['request']=={'kind':'analysis','pilot':False,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
         'wall_seconds':3600,'execution_argv':argv} and proof['memory_limits_requested'] is False and
         proof['exclusive_requested'] is False and proof.get('bounded_readonly_scope_only') is True,
         'NO_MEMORY_EXCLUSIVITY_OR_GENERATION_AUTHORITY')
    declared={row['path']:triple(row) for row in proof['source_target_verification']}
    need(len(declared)==len(proof['source_target_verification']),'UNIQUE_SOURCE_TARGET_PATHS_REQUIRED')
    for value in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],Q.ref(plan_path)]:
        source(value,declared)
    for path in (primary,Path(Q.__file__).absolute(),Path(Q.__file__).absolute().parent/'__init__.py'):
        reference=Q.ref(path)
        need(reference in plan['source_references'],'IMPORTED_CODE_MUST_BE_ROOT_APPROVED_SOURCE')
        source(reference,declared)
    signer=proof['controller_evidence']
    need(signer['endpoint']==ENDPOINT and signer['uid']==UID and signer['hostname']=='sonmi' and
         signer['proof_is_not_created_by_scientific_worker'] is True and signer['actual_script_reference']==proof['script_reference'],
         'INDEPENDENT_ALPHA_LOGIN_CONTROLLER_REQUIRED')
    script=Q.read_small(Q.verify(proof['script_reference'])).decode()
    for line in script.splitlines():
        if line.strip().startswith('#SBATCH'):
            need(not any(s in line for s in ('--mem','--gres','--gpu','--exclusive')),'NO_EXPLICIT_MEMORY_GPU_EXCLUSIVE')
    job=Q.fields(proof['job_metadata'])
    need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and job.get('JobState')=='RUNNING' and
         job.get('NodeList')==plan['node'] and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16' and
         job.get('NumTasks')=='1' and job.get('Requeue')=='0' and job.get('Command')==proof['script_reference']['path'] and
         Q.duration(job.get('TimeLimit',''))==3600,'ACTUAL_RUNNING_CPU16_SCRIPT_AND_WALL_REQUIRED')
    gate=proof['actual_gate_process'];proc=Path('/proc/self');raw=(proc/'stat').read_text();tail=raw[raw.rfind(')')+2:].split()
    need(gate['pid']==os.getpid() and gate['uid']==UID and gate['start_ticks']==int(tail[19]) and
         gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0) and gate['cgroup_sha256']==Q.sha((proc/'cgroup').read_bytes()),
         'ATTESTED_EXEC_GATE_PROCESS_IDENTITY_REQUIRED')
    storage=proof['storage_observation'];Q.load_ref(proof['storage_observation_reference'])
    need(proof['account_free_bytes']==storage['effective_free_bytes'] and proof['account_free_bytes']-CAP>=200000000000 and
         0<=time.time()-storage['observed_unix_seconds']<=120 and storage['whole_output_caps_reserved_bytes']>=CAP,
         'ACTUAL_FRESH_STORAGE_ALL_CAPS_AND200GB_REQUIRED')
    authority=small(plan['resource_authority_reference'],declared)
    need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority.get('status')=='USER_AUTHORIZED' and
         authority.get('endpoint')==ENDPOINT and authority.get('observed_uid')==UID and
         authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED','ACTUAL_ALPHA_USER_AUTHORITY_REQUIRED')
    return plan,proof,declared


def metadata(inputs,declared):
    copies={}
    for row in inputs['metadata_copies']:
        origin,target=triple(row['origin_reference']),triple(row['target_locator'])
        need(MAIN in Path(origin['path']).parents and ROOT in Path(target['path']).parents and
             all(origin[k]==target[k] for k in ('bytes','sha256')),'UNCHANGED_MAIN_ORIGIN_ALPHA_SMALL_COPY_REQUIRED')
        key=Q.canonical(origin);need(key not in copies,'UNIQUE_MAIN_ORIGIN_REFERENCE_REQUIRED')
        source(target,declared);copies[key]=target
    def target(value):
        value=triple(value);need(Q.canonical(value) in copies,'MISSING_EXACT_MAIN_ORIGIN_ALPHA_COPY_LOCATOR')
        return copies[Q.canonical(value)]
    def load(value):return small(target(value),declared)
    return target,load


def main_parent(master,rows,jid,receipt,node,partition,read):
    parents=[row for row in master['actual_parents'] if row.get('JobIDRaw')==jid]
    raw=[row for row in rows if row.get('JobIDRaw')==jid]
    need(len(parents)==len(raw)==1,'ONE_ACTUAL_MAIN_PARENT_AND_RAW_ROW_REQUIRED')
    parent=parents[0]
    for key in ('JobIDRaw','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','Partition'):
        need(parent[key]==raw[0][key],'MAIN_PARENT_RAW_ACCOUNT_DIFFERS:'+key)
    need(parent['State']=='COMPLETED' and parent['ExitCode']=='0:0' and parent['AllocCPUS']=='16' and
         parent['NodeList']==node and parent['Partition']==partition and int(parent['ElapsedRaw'])>=0 and
         receipt['uid']==1278 and receipt['job_id']==jid,'ACTUAL_HISTORICAL_MAIN_C0_CPU16_REQUIRED')
    if 'UID' in raw[0]:need(raw[0]['UID']=='1278','HISTORICAL_MAIN_PARENT_UID_DIFFERS')
    submission=read(parent['receipt_reference'])
    need(submission['uid']==1278 and str(submission['job_id'])==jid and submission['sbatch_returncode']==0,
         'ACTUAL_MAIN_OWNED_SUCCESSFUL_SUBMISSION_REQUIRED')
    return {'endpoint':'202.38.247.57:22','uid':1278,'actual_parent':parent,
        'allocated_core_seconds':int(parent['ElapsedRaw'])*16,
        'historical_partition_preserved_not_current_alpha_admission':True,
        'raw_steps_retained_not_added_twice':[row for row in rows if row.get('JobIDRaw','').startswith(jid+'.')]}


def inputs_and_history(plan,declared):
    inputs=small(plan['inputs_reference'],declared)
    need(inputs.get('schema')=='SECONDARY_PUBLIC_RAW_COPY_VALIDATION_INPUTS_V1' and
         inputs.get('status')=='ROOT_STAGED_EXACT_MAIN_PUBLIC_RAW_COPY' and inputs.get('reviewer')=='root',
         'EXACT_ROOT_STAGED_PUBLIC_RAW_INPUTS_REQUIRED')
    target,read=metadata(inputs,declared)
    acquisition=read(inputs['main_source348_receipt_origin_reference'])
    inventory=read(inputs['main_inventory1093_receipt_origin_reference'])
    need(acquisition.get('schema')=='pubchem_download_complete_v1' and acquisition.get('status')=='RAW_ACQUIRED_NO_CHEMICAL_SCREENING' and
         acquisition['job_id']=='4520348' and acquisition['uid']==1278 and acquisition['hostname']=='compute-0-20' and
         acquisition['chemical_screening_performed'] is False and acquisition['network_bypass_attempted'] is False,
         'ACTUAL_MAIN348_ORIGINAL_PUBLIC_ACQUISITION_REQUIRED')
    original=triple(acquisition['file'])
    need(MAIN in Path(original['path']).parents and original['bytes']==COMPRESSED and original['sha256']==SHA and
         acquisition['gzip']['compressed_bytes']==COMPRESSED and acquisition['gzip']['sha256']==SHA and
         acquisition['gzip']['uncompressed_bytes_read']==DECODED and acquisition['gzip']['gzip_read_to_eof_crc_validated'] is True,
         'EXACT_ORIGINAL_MAIN_RAW_SHA_AND_EOF_BYTES_REQUIRED')
    source_pin=read(acquisition['pin']);intent=read(acquisition['root_submission'])
    need(source_pin['schema']=='pubchem_official_source_pin_v1' and source_pin['url']==URL and
         source_pin['content_length']==COMPRESSED and source_pin['last_modified']==acquisition['source_version'] and
         intent['uid']==1278,'ORIGINAL_OFFICIAL_SOURCE_VERSION_AND_MAIN_INTENT_REQUIRED')
    need(inventory.get('schema')=='SB5_PUBCHEM_RAW_INVENTORY_RECEIPT_V2' and
         inventory['status']=='RAW_FULL_EOF_INVENTORY_COMPLETE_NO_CHEMICAL_SCREENING' and
         inventory['job_id']=='4521093' and inventory['node']=='compute-0-13' and inventory['uid']==1278 and
         inventory['raw_source']==original and inventory['raw_complete_SHA_verified'] is True and
         inventory['gzip_EOF_CRC_revalidated'] is True and inventory['counts']['uncompressed_bytes']==DECODED and
         inventory['counts']['records']==inventory['counts']['cid_records']==ROWS and
         inventory['chemical_screening_performed'] is False and inventory['full_source_pool_release_authorized'] is False and
         inventory['decontamination_or_novelty_or_UFF_or_QM_or_training_performed'] is False,
         'ACTUAL_MAIN1093_RAW_FULL_BYTE_AND_ROW_INVENTORY_REQUIRED')
    old_startup=read(inventory['startup_proof'])
    need(old_startup['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and old_startup['uid']==1278 and
         str(old_startup['job_id'])=='4521093' and old_startup['node']=='compute-0-13',
         'HISTORICAL_MAIN1093_PROOF_NOT_CURRENT_ALPHA_ADMISSION')
    master=read(inputs['main_accounting_origin_reference'])
    need(master.get('schema')=='DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V2' and master['query_returncode']==0 and
         master['command_argv'][0]=='sacct','ACTUAL_MAIN_OWNED_ACCOUNTING_REQUIRED')
    raw=Q.read_small(source(target(master['raw_sacct_reference']),declared)).decode()
    rows=list(csv.DictReader(io.StringIO(raw),delimiter='|'))
    costs=[main_parent(master,rows,'4520348',acquisition,'compute-0-20','all',read),
           main_parent(master,rows,'4521093',inventory,'compute-0-13','cpu',read)]
    fee=read(inputs['fee_override_origin_reference'])
    need(fee['schema']=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1' and fee['status']=='USER_AUTHORIZED' and
         fee['on_overrun']=='REPORT_AND_CONTINUE' and fee['scientific_quality_thresholds_unchanged'] is True and
         fee['retain_actual_accounting_including_failures_and_startup'] is True,'UNCHANGED_ACTUAL_COST_OVERRIDE_REQUIRED')
    copy=inputs['raw_copy'];local=triple(copy['target_locator'])
    need(triple(copy['origin_reference'])==original and all(original[k]==local[k] for k in ('bytes','sha256')) and
         plan['data_references']==[local] and ROOT/'inputs' in Path(local['path']).parents and
         local['path'] not in declared,'ONE_EXACT_PUBLIC_GZIP_DATA_COPY_NOT_SMALL_METADATA_REQUIRED')
    return local,{'main_raw_origin_reference':original,'main_origin_fstat_historical_only':inventory['raw_current_frame'],
        'main_source348_receipt_origin_reference':inputs['main_source348_receipt_origin_reference'],
        'main_inventory1093_receipt_origin_reference':inputs['main_inventory1093_receipt_origin_reference'],
        'source_url':URL,'source_version':acquisition['source_version'],'main_actual_parent_costs':costs,
        'fee_override_origin_reference':inputs['fee_override_origin_reference'],
        'fee_override_actual_alpha_copy':target(inputs['fee_override_origin_reference']),
        'historical_receipts_have_explicit_trailing_newline_field':False,
        'row_count_basis':'physical LF boundaries plus one nonempty unterminated final line; no chemistry/CID parsing'}


class SoftStop(Exception):pass


class Budget:
    """One current reader process; per4MiB software guard, never a Slurm limit."""
    def __init__(self,started,prior_runtime):
        self.started=started;self.prior_runtime=prior_runtime;self.last_event=started;self.samples=0;self.peak=0;self.minimum=None;self.reason=None
    def check(self,phase,counts):
        status={row.split(':',1)[0]:row.split(':',1)[1].strip() for row in Path('/proc/self/status').read_text().splitlines() if ':' in row}
        memory={row.split(':',1)[0]:int(row.split(':',1)[1].split()[0])*1024 for row in Path('/proc/meminfo').read_text().splitlines() if ':' in row}
        rss=int(status['VmRSS'].split()[0])*1024;available=memory['MemAvailable'];total=memory['MemTotal']
        self.samples+=1;self.peak=max(self.peak,rss);self.minimum=available if self.minimum is None else min(self.minimum,available)
        reason=('SOFTWARE_READER_RSS_OVER2GiB' if rss>SOFT_RSS else
                'ACTUAL_NODE_MEMAVAILABLE_BELOW15PCT' if available*100<total*15 else
                'WALL_SOFTSTOP60SECOND_DRAIN_MARGIN' if self.prior_runtime+time.monotonic()-self.started>=3540 else None)
        if time.monotonic()-self.last_event>=20:
            print(json.dumps({'status':'RUNNING_SINGLE_READER_RAW_COPY_VALIDATION','phase':phase,**counts,
                'actual_current_RSS_bytes':rss,'actual_node_MemAvailable_bytes':available}),flush=True)
            self.last_event=time.monotonic()
        if reason:self.reason=reason;raise SoftStop(reason)
    def receipt(self):
        return {'samples':self.samples,'peak_sampled_current_reader_rss_bytes':self.peak,
            'minimum_sampled_actual_node_MemAvailable_bytes':self.minimum,'first_stop_reason':self.reason,
            'software_RSS_softcap_bytes':SOFT_RSS,'software_cap_is_scheduler_memory_request':False,
            'actual_MemAvailable_softguard_fraction':0.15,'chunk_bytes':CHUNK,'single_stream_reader_processes':1,
            'requested_CPUs':16,'sixteen_hash_or_gzip_workers_claimed':False,'forced_signals_sent':False,
            'SLURM_memory_environment_observed':{k:os.environ.get(k) for k in ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},
            'entry_wall_seconds':time.monotonic()-self.started,'actual_startup_job_RunTime_seconds':self.prior_runtime,
            'softstop_elapsed_basis':'actual startup Slurm RunTime plus entry monotonic elapsed; conservative overlap, not final cost'}


def frame(value):return {'device':value.st_dev,'inode':value.st_ino,'bytes':value.st_size,'mtime_ns':value.st_mtime_ns,'uid':value.st_uid}


def scan(reference,budget,counts):
    path=Q.literal(reference['path']);need(not path.is_symlink(),'REGULAR_ALPHA_RAW_COPY_REQUIRED')
    with path.open('rb') as stream:
        info=os.fstat(stream.fileno());identity=frame(info)
        need(stat.S_ISREG(info.st_mode) and info.st_uid==UID and info.st_size==COMPRESSED and frame(path.stat())==identity,
             'CURRENT_ALPHA_RAW_COPY_OWNER_SIZE_OR_IDENTITY_DIFFERS')
        digest=hashlib.sha256()
        while True:
            budget.check('COMPRESSED_SHA',counts);block=stream.read(CHUNK)
            if not block:break
            digest.update(block);counts['compressed_bytes_read']+=len(block)
            need(counts['compressed_bytes_read']<=COMPRESSED,'COMPRESSED_FILE_EXCEEDS_PIN')
            budget.check('COMPRESSED_SHA',counts)
        need(counts['compressed_bytes_read']==COMPRESSED and digest.hexdigest()==SHA==reference['sha256'] and
             frame(os.fstat(stream.fileno()))==frame(path.stat())==identity,'FULL_COMPRESSED_SHA_OR_ALPHA_FILE_IDENTITY_DIFFERS')
        counts['compressed_SHA_verified']=True;stream.seek(0);last=None
        with gzip.GzipFile(fileobj=stream,mode='rb') as decoded:
            while True:
                budget.check('GZIP_EOF_CRC',counts);block=decoded.read(CHUNK)
                if not block:break
                counts['uncompressed_bytes_read']+=len(block);counts['LF_bytes_observed']+=block.count(b'\n');last=block[-1]
                need(counts['uncompressed_bytes_read']<=DECODED,'DECODED_BYTES_EXCEED_MAIN_EOF_RECEIPT')
                budget.check('GZIP_EOF_CRC',counts)
        counts['gzip_EOF_CRC_verified']=True;counts['last_decoded_byte_is_LF']=(last==10)
        counts['physical_rows']=counts['LF_bytes_observed']+(1 if counts['uncompressed_bytes_read'] and last!=10 else 0)
        need(counts['uncompressed_bytes_read']==DECODED and counts['physical_rows']==ROWS and
             frame(os.fstat(stream.fileno()))==frame(path.stat())==identity,'FULL_DECODED_BYTES_ROWS_OR_ALPHA_IDENTITY_DIFFERS')
    return identity


def main():
    started=time.monotonic()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--startup-proof',type=Path,required=True)
    args=parser.parse_args();plan,proof,declared=startup(args.plan,args.startup_proof)
    reference,history=inputs_and_history(plan,declared)
    output=Q.literal(plan['output_directory'])
    need(ROOT/'artifacts' in output.parents and not output.exists(),'NEW_ALPHA_VALIDATION_OUTPUT_REQUIRED')
    output.mkdir(parents=True,mode=0o700)
    budget=Budget(started,Q.duration(Q.fields(proof['job_metadata'])['RunTime']))
    counts={'compressed_bytes_read':0,'compressed_SHA_verified':False,'uncompressed_bytes_read':0,
        'LF_bytes_observed':0,'gzip_EOF_CRC_verified':False,'last_decoded_byte_is_LF':None,'physical_rows':None}
    error=None;identity=None;exitcode=0
    try:identity=scan(reference,budget,counts)
    except SoftStop as exc:error={'kind':'COOPERATIVE_SOFT_STOP_NO_NEW_READS','message':str(exc)};exitcode=3
    except Exception as exc:error={'kind':type(exc).__name__,'message':str(exc)[:1000]};exitcode=1
    report={'schema':'SECONDARY_PUBLIC_RAW_COPY_VALIDATION_RECEIPT_V1',
        'status':'EXACT_MAIN_PUBLIC_RAW_COPY_SHA_GZIP_EOF_VALIDATED' if error is None else 'PUBLIC_RAW_COPY_VALIDATION_INCOMPLETE_NOT_ACCEPTED',
        'endpoint':ENDPOINT,'uid':os.getuid(),'job_id':str(proof['job_id']),'node':proof['node'],
        'plan_reference':Q.ref(args.plan),'startup_proof_reference':Q.ref(args.startup_proof),'inputs_reference':plan['inputs_reference'],
        'actual_alpha_raw_reference':reference,'actual_alpha_file_identity':identity,'counts':counts,'historical_main_evidence':history,
        'runtime_budget':budget.receipt(),'error':error,'main_original_fstat_read_on_alpha':False,
        'new_network_requests':0,'chemical_parsing_or_filtering_performed':False,'UFF_QM_pickle_LMDB_onceledger_calls':0,
        'population_members_added':0,'guide_one_million_sample_claimed':False,'feature_profile_authorized':False,
        'full_source_pool_release_authorized':False,'formal_generation_authorized':False,
        'actual_own_terminal_parent_cost':'PENDING_ROOT_ACTUAL_ALPHA_SACCT_PARENT_AND_STEPS',
        'historical_reports_or_sources_modified':False,'quality_thresholds_changed':False}
    receipt=Q.write_new(output/'receipt.json',report)
    need((output/'receipt.json').stat().st_size+output.stat().st_size<=CAP,'OWN_OUTPUT_CAP_EXCEEDED')
    print(json.dumps({'status':report['status'],'job_id':str(proof['job_id']),'receipt_reference':receipt,'error':error}),flush=True)
    if exitcode:raise SystemExit(exitcode)


if __name__=='__main__':main()
