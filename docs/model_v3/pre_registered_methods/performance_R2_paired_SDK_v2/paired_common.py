"""Exactly two closed R2 cases/four SDKs; shared v3 transport primitives only."""
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
HERE=Path(__file__).absolute().parent
V3=HERE.parent/'wandb_selective_sync50_v3'
sys.path.insert(0,str(V3))
import sync_common as base
from sync_common import *
HERE=Path(__file__).absolute().parent
SCOPE='PAIRED_R2_LOG_ONLY'
CODE='9e16d4c5a15c558051499d3dc0c55c9bd3787734'
PUBLIC='8147f44baa1ea1ecc3822af7affd0a95401ed248'
IDS={'z4ts32w5','dr7zahoj','5thxuhw5','zotxsoay'}


def load(raw,name):
    bind(raw);spec=importlib.util.spec_from_file_location(name,raw['path'])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def descriptor(path,cap):
    path=Path(path).absolute();info=path.stat()
    require(not any(p.is_symlink() for p in (path,*path.parents)) and path.is_file()
        and info.st_uid==1278 and info.st_nlink==1 and 0<=info.st_size<=cap,'Physical owned bounded descriptor required')
    return dict(path=str(path),bytes=info.st_size)


def verify(expected=None):
    pin=ref(HERE/'source_pins.json')
    if expected is not None:require(pin['sha256']==expected,'Explicit paired source SHA differs')
    pins=read(pin);require(pins['schema']=='performance_R2_paired_log_sources_v1','Paired source inventory required')
    for item in pins['files']:
        actual=ref(HERE/item['relative_path']);require((actual['bytes'],actual['sha256'])==(item['bytes'],item['sha256']),'Paired source drift')
    deps=read(HERE/'dependencies.json')
    for raw in deps['sources'].values():bind(raw)
    require(base.verify(deps['base_manifest']['sha256'])==deps['base_manifest'],'Original v3 source identity differs')
    wanted=(V3/'one_run.py').read_bytes().replace(b'from sync_common import *',b'from paired_common import *')
    require((HERE/'one_run_paired.py').read_bytes()==wanted,'Only explicit eligible-input import may differ in v3 transport')
    require((HERE/'installed_sources.json').read_bytes()==(V3/'installed_sources.json').read_bytes(),'Installed source snapshots differ')
    return pin


def metadata_case(case):
    refs=case['refs'];m={key:read(raw) for key,raw in refs.items()};cfg=m['configuration'];summary=m['summary'];status=m['status'];root=m['root'];job=case['job_id']
    require(job in ('4523976','4524551') and cfg['job_id']==status['job_id']==job
        and cfg['code_sha']==summary['code_sha']==CODE and cfg['prereg_sha']==summary['prereg_sha']==PUBLIC
        and cfg['fixed_batches']==20 and cfg['trajectory_updates']==500 and cfg['input']=='native_s'
        and cfg['smoke'] is False and type(cfg['seed']) is int and cfg['seed']==0 and cfg['tracking_mode']=='offline'
        and cfg['downstream_data_read'] is False and cfg['original_lmdb_written'] is False,'Exact closed20/500 case source/config required')
    require(summary['status']==status['status']=='PAIRED_GATES_PASS' and summary['full_A_numeric_acceptance'] is True
        and summary['fixed_batch_pass'] is True and summary['trajectory_pass'] is True and status['failure'] is None
        and status['cleanup_errors']==[] and status['stream_cleanup']['errors']==[], 'Actual paired GPU child not closed')
    projection={k:v for k,v in cfg.items() if k!='configuration_sha256'}
    digest=hashlib.sha256(json.dumps(projection,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    require(digest==cfg['configuration_sha256']==summary['configuration_sha256'],'Original pre-self-field canonical configuration differs')
    sup=m['supervisor'];require(str(sup['job_id'])==job and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
        and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[],'Actual GPU supervisor not closed')
    if job=='4523976':
        require(root['schema']=='model_v3_manual_R2_and_consumer_Root_closure_v1'
            and root['status']=='ROOT_CLOSED_MANUAL_R2_VALID_AND_ACTUAL_CPU_CONSUMER_C0'
            and root['source_GPU_job']==job and root['source_Gpu_numeric20batch500update_passed'] is True
            and root['GPU_summary']==refs['summary'] and root['GPU_status']==refs['status'] and root['GPU_supervisor']==refs['supervisor']
            and root['profile']==refs['profile'],'Actual manual R2 Root source closure differs')
        require(m['profile']['observations'][0]['configuration']==refs['configuration'],'Root manual profile configuration differs')
        actual=root['actual_sacct']
    else:
        require(root['schema']=='model_v3_Root_auto_R2_full_A_numeric_closure_v1'
            and root['status']=='ACTUAL_GPU_C0_AUTO_PROFILE_R2_FULL20_500_NUMERIC_SOURCE_RESOURCE_CLOSED'
            and root['job_id']==job and root['all_current_source_maps_equal_saved'] is True
            and root['artifact_refs']['configuration.json']==refs['configuration']
            and root['artifact_refs']['summary.json']==refs['summary'] and root['artifact_refs']['run_status.json']==refs['status']
            and root['supervisor']==refs['supervisor'],'Actual auto R2 Root source closure differs')
        actual=root['actual_sacct']
    rows=[line.split('|') for line in actual['stdout'].splitlines() if line.strip() and line.split('|')[0]==job]
    require(actual['returncode']==0 and len(rows)==1 and len(rows[0])==7
        and rows[0][1:4]==['zixiao','COMPLETED','0:0'] and rows[0][5:]==['16','compute-0-21'], 'Exact actual GPU parent C0/UID/CPU/node required')
    require(root['code_sha']==CODE and root['public_prereg_sha']==PUBLIC and root['resident_models']==2,'Same public R2 code/residency binding required')
    require(set(case['journals'])=={'reference','candidate'} and len(case['sdks'])==2,'Exactly two role journals/twoSDK descriptors required')
    for role,raw in case['journals'].items():require(descriptor(raw['path'],32<<20)==raw,'Original role journal descriptor drift')
    for raw in case['sdks']:require(descriptor(raw['descriptor']['path'],128<<20)==raw['descriptor'],'Original SDK descriptor drift')
    return m


def bound_inputs(raw):
    inputs=read(raw);require(inputs['schema']=='performance_R2_paired_log_inputs_v1' and inputs['scope']==SCOPE
        and len(inputs['cases'])==2 and {c['job_id'] for c in inputs['cases']}=={'4523976','4524551'},'Fixed two actual paired cases required')
    ids=[s['run_id'] for c in inputs['cases'] for s in c['sdks']]
    require(len(ids)==4 and set(ids)==IDS,'Exactly fixed four SDK IDs required')
    expected={'4523976':{'z4ts32w5','dr7zahoj'},'4524551':{'5thxuhw5','zotxsoay'}}
    selected_bytes=0
    for case in inputs['cases']:
        require({item['run_id'] for item in case['sdks']}==expected[case['job_id']],'SDK cross-case membership differs')
        metadata_case(case)
        selected_bytes+=sum(item['descriptor']['bytes'] for item in case['sdks'])+sum(v['bytes'] for v in case['journals'].values())+sum(v['bytes'] for v in case['refs'].values())
    require(selected_bytes<=128<<20,'Explicit selected original sources exceed128MiB')
    return inputs


def header_check(header,job,role):
    require(role in ('reference','candidate') and header['run_id'] in IDS
        and header['project']=='mfm_model_v3_development' and header['display_name']==f'A_{role}_{job}'
        and type(header['entity']) is str,'Actual paired Native role/name/project differs')


def proof_rows(manifest):
    require(manifest['schema']=='performance_R2_paired_sync_manifest_v1' and len(manifest['verifications'])==4,'Four explicit independently audited proofs required')
    batch=read(manifest['audit_result']);sup=read(manifest['audit_supervisor']);terminal=terminal_C0(manifest['actual_audit_C0']);job=terminal['job_id']
    require(batch['schema']=='performance_R2_paired_log_batch_v1' and batch['status']=='ALL_FOUR_PAIRED_LOGS_MATCHED_PENDING_ROOT_C0'
        and batch['actual_job_id']==job==str(sup['job_id']) and batch['returncode']==0 and batch['failure'] is None
        and batch['verifications']==manifest['verifications'] and sup['status']=='COMPLETED' and sup['exit_code']==0
        and sup['first_failure'] is None and sup['remaining']==[] and sup['private_storage']['first_sampling_failure'] is None
        and sup['command']==batch['actual_argv'],'Actual paired audit CPU C0/supervisor required')
    require(batch['source_pins']==ref(HERE/'source_pins.json'),'Actual batch source identity differs')
    expected_argv=[str(PYTHON),'-u','-B',str(HERE/'audit_paired.py'),'--inputs',batch['inputs']['path'],
        '--inputs-sha256',batch['inputs']['sha256'],'--pins-sha256',batch['source_pins']['sha256'],
        '--output',str(Path(manifest['audit_result']['path']).parent)]
    require(batch['actual_argv']==expected_argv and batch['actual_allocation']['uid']==1278,'Actual source-bound CPU audit argv/UID differs')
    inputs=bound_inputs(batch['inputs']);case_map={c['job_id']:c for c in inputs['cases']};rows=[];roles={k:set() for k in case_map}
    deps=read(HERE/'dependencies.json')
    for raw in manifest['verifications']:
        cert=read(raw);key=cert['run_id'];case=case_map[cert['model_job_id']];h=cert['history'];role=cert['paired_role']
        require(cert['schema']=='performance_R2_paired_log_verification_v1' and cert['scope']==SCOPE
            and cert['status']=='ALL_SAVED_PAIRED_LOG_FIELDS_MATCHED' and cert['source_pins']==batch['source_pins']
            and cert['inputs']==batch['inputs'] and cert['full_config_summary_typed_exact'] is True
            and cert['raw_before_after_binding_closed'] is True and cert['history_reader_source']==deps['sources']['literal_reader']
            and cert['tap_source']==deps['sources']['tap'],
            'Exact paired typed/fullstream certificate required')
        require(cert['native_RunRecord']['run_id']==key,'Certificate/native SDK ID differs')
        header_check(cert['native_RunRecord'],case['job_id'],role)
        require(h['schema']=='model_v3_native_mirror_verification_v7' and h['status']=='VERIFIED_COMMITTED_HISTORY'
            and h['sdk_run_ids']==[key] and h['sdk_exit_codes']==[0] and type(h['sdk_exit_codes'][0]) is int
            and h['clean_eof'] is True and h['native_closed'] is True and h['decode_error'] is None
            and type(h['uncommitted_native_requests']) is int and h['uncommitted_native_requests']==0
            and type(h['history_rows']) is int and h['history_rows']==500 and h['first_explicit_step']==1 and h['last_explicit_step']==500,
            'Original exact500steps1..500/exit/fullfragmentEOF proof required')
        require(key in {s['run_id'] for s in case['sdks']} and role not in roles[case['job_id']]
            and {k:cert['sdk'][k] for k in ('path','bytes')}==next(s['descriptor'] for s in case['sdks'] if s['run_id']==key)
            and {k:cert['journal'][k] for k in ('path','bytes')}==case['journals'][role],'Role/SDK/journal cross-case identity differs')
        roles[case['job_id']].add(role)
        for source in cert['source_refs'].values():bind(source)
        rows.append(dict(run_id=key,SDK_raw_ref=cert['sdk'],native_RunRecord=cert['native_RunRecord'],native_exit_code=0,
            expected_API_state='finished',history_rows=500,first_explicit_step=1,last_explicit_step=500,
            original_model_status='PAIRED_GATES_PASS',paired_role=role,model_job_id=case['job_id'],verification=raw,scope=SCOPE))
    require({r['run_id'] for r in rows}==IDS and all(v=={'reference','candidate'} for v in roles.values()),'Both exact roles of both cases must close')
    return rows


def manifest_metadata():
    raw=ref(os.environ['MODEL_V3_PAIRED_MANIFEST']);require(raw['sha256']==os.environ['MODEL_V3_PAIRED_MANIFEST_SHA'],'Explicit paired manifest drift')
    value=read(raw);require(value['runs']==proof_rows(value),'Proof-derived manifest rows differ');return raw,value


def eligible_rows():
    allocation();_,manifest=manifest_metadata();rows=proof_rows(manifest);entity_default=None
    if any(not r['native_RunRecord']['entity'] for r in rows):
        private=Path(os.environ['TMPDIR'])/('paired_authenticated_route_'+str(os.getpid()));private.mkdir(mode=0o700)
        with (private/'stdout').open('x') as out,(private/'stderr').open('x') as err,contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            for item in read(HERE/'installed_sources.json')['files']:
                current=ref(item['original']);require((current['bytes'],current['sha256'])==(item['bytes'],item['sha256']),'Installed API source drift')
            import wandb
            require(wandb.__version__=='0.28.1','Reviewed actual SDK version required');api=wandb.Api(timeout=30)
            require(api.settings['base_url']=='https://api.wandb.ai','Actual destination differs')
            entity_default=api.viewer.entity
            require(type(entity_default) is str and entity_default and api.default_entity==entity_default,'Authenticated viewer/default entity missing')
    for row in rows:
        header=row['native_RunRecord'];row['routing']=dict(entity=header['entity'] or entity_default,project=header['project'],run_id=row['run_id'],
            routing_ready=True,entity_origin='original_RunRecord' if header['entity'] else 'actual_authenticated_viewer_default',project_origin='original_RunRecord')
    return manifest,{r['run_id']:r for r in rows}


def request_gate(request):
    raw,manifest=manifest_metadata();selected=request['selected_run_ids']
    require(request['schema']=='performance_R2_paired_selective_sync_request_v1' and request['eligible_manifest']==raw
        and request['source_manifest']==ref(HERE/'source_pins.json') and request['mode']=='batch'
        and request['maximum_batch_runs']==3 and 1<=len(selected)<=3 and len(set(selected))==len(selected) and set(selected)<=IDS
        and request['child_seconds']==3000 and request['CLI_timeout_seconds']==600 and request['API_verification_seconds']==180,
        'Exact explicit max3 original transport batch required')
    gate=request['pilot_gate'];terminal=terminal_C0(gate['actual_terminal']);pilot=read(gate['result']);sup=read(gate['supervisor'])
    require(terminal['job_id']==str(pilot['job_id'])==str(sup['job_id'])=='4521412'
        and pilot['source_manifest']==ref(V3/'source_pins.json') and pilot['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0'
        and len(pilot['records'])==1 and pilot['records'][0]['native_exit_code']==1
        and pilot['records'][0]['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED'
        and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None and sup['remaining']==[]
        and gate['native_exit_code']==1 and gate['actual_replay_verified'] is True,'Original identical-v3 actual transport method C0 missing')
