"""One explicit closed max-singleton run; shared v3 transport stays unchanged."""
from __future__ import annotations
import contextlib
import importlib.util
import sys
from pathlib import Path
HERE=Path(__file__).absolute().parent
V3=HERE.parent/'wandb_selective_sync50_v3'
sys.path.insert(0,str(V3))
import sync_common as base
from sync_common import *
HERE=Path(__file__).absolute().parent
SCOPE='NATIVE_MAX_SINGLETON_R1_LOG_ONLY'
RUN='pnugbb4q'
JOB='4524600'
FAMILY=HERE.parent/'performance_native_max_R1_v2'
CHILD=FAMILY/'child'
CODE='9e16d4c5a15c558051499d3dc0c55c9bd3787734'


def load(raw,name):
    bind(raw);spec=importlib.util.spec_from_file_location(name,raw['path'])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def descriptor(path,cap):
    path=Path(path).absolute();before=path.lstat()
    require(not any(p.is_symlink() for p in (path,*path.parents))
        and stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_nlink==1
        and 0<before.st_size<=cap,'Bounded owned ordinary descriptor required')
    return dict(path=str(path),bytes=before.st_size)


def verify(expected=None):
    pin=ref(HERE/'source_pins.json')
    if expected is not None:require(pin['sha256']==expected,'Explicit max-log source SHA differs')
    value=read(pin);require(value['schema']=='native_max_R1_log_sources_v1','Exact source family required')
    for row in value['files']:
        actual=ref(HERE/row['relative_path'])
        require((actual['bytes'],actual['sha256'])==(row['bytes'],row['sha256']),'Max-log source drift')
    deps=read(HERE/'dependencies.json')
    for raw in deps['sources'].values():bind(raw)
    require(base.verify(deps['base_manifest']['sha256'])==deps['base_manifest'],'Original v3 source drift')
    original=(V3/'one_run.py').read_bytes().replace(b'from sync_common import *',b'from max_common import *')
    require((HERE/'one_run_max.py').read_bytes()==original,'Only eligibility import may differ in original transport')
    require((HERE/'installed_sources.json').read_bytes()==(V3/'installed_sources.json').read_bytes(),
        'Actual installed source snapshot differs')
    return pin


def model_C0(raw):
    wanted=['sacct','-X','-n','-P','-j',JOB,'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
    rows=[x.split('|') for x in raw['stdout'].splitlines() if x.strip()]
    require(raw['argv']==wanted and raw['returncode']==0 and raw['stderr']==''
        and rows==[[JOB,'zixiao','COMPLETED','0:0','48','16','compute-0-21']],
        'Actual closed source-bound max parent C0 required')


def metadata_inputs(value):
    require(value['schema']=='native_max_R1_log_inputs_v1' and value['scope']==SCOPE
        and value['run_id']==RUN and value['model_job_id']==JOB,'One explicit max-log input only')
    scope=read(HERE/'scope.json')
    require(value['root_closure']==scope['root_closure'],'Exact actual Root proof required')
    root=read(value['root_closure']);model_C0(root['actual_sacct'])
    require(root['schema']=='model_v3_Root_native_max_singleton_R1_GPU_closure_v1'
        and root['status']=='ACTUAL_C0_NATIVE_MAX712_FULL_THREE_VIEWS_22_UPDATES_SOURCE_RESOURCE_CLOSED_SDK_AUDIT_PENDING'
        and root['job_id']==JOB and root['tracking_run_id']==RUN and root['real_optimizer_updates']==22
        and root['actual_dense_shape']==[3,712] and root['resident_models']==1
        and root['all_current_2131_sources_rehashed'] is True and root['NVML_memory_all_known'] is True
        and root['private_sampling_cleanup_closed'] is True
        and root['automatic_capacity_qualification'] is False and root['universal_8M_capacity_qualification'] is False
        and root['scientific_adoption'] is False,'Original source/resource C0 closure differs')
    names=('configuration','summary','run_status','supervisor','submission','selection','source_package','method_publication')
    require(set(value['refs'])==set(names) and all(value['refs'][k]==root[k] for k in names),
        'Actual closed metadata reference membership differs')
    metadata={k:read(value['refs'][k]) for k in names}
    c,s,r,sup=(metadata[k] for k in ('configuration','summary','run_status','supervisor'))
    require(value['expected_summary']==root['SDK_expected_summary']==s['SDK_expected_summary']==r['SDK_expected_summary']
        and value['expected_summary']['path']==str(CHILD/'SDK_expected_summary.json'), 'Explicit original summary differs')
    expected=read(value['expected_summary'])
    require(value['refs']['configuration']['path']==str(CHILD/'configuration.json')
        and c['job_id']==JOB and c['code_sha']==CODE and c['tracking_mode']=='offline'
        and c['resident_models']==1 and c['total_actual_updates']==22
        and c['source_package']==root['source_package'] and s['source_package']==root['source_package'],
        'Original full config/producer binding differs')
    digest=hashlib.sha256(json.dumps({k:v for k,v in c.items() if k!='configuration_sha256'},
        sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    require(digest==c['configuration_sha256'],'Complete saved configuration canonical hash differs')
    require(s['schema']=='model_v3_native_max_R1_summary_v1' and r['schema']=='model_v3_native_max_R1_status_v1'
        and s['status']==r['status']=='NATIVE_MAX_SINGLETON_R1_22_UPDATES_COMPLETED'
        and s['actual_updates']==r['completed_actual_updates']==r['durable_source_rows']==r['SDK_log_calls_returned']==22
        and s['warmup_updates']==2 and s['observed_updates']==20 and s['selected_base_exposures']==22
        and s['tracking_run_id']==r['tracking_run_id']==RUN and s['tracking_mode']==r['tracking_mode']=='offline'
        and s['SDK_finish_call_returned'] is r['SDK_finish_call_returned'] is True
        and type(s['SDK_finish_requested_exit_code']) is int and s['SDK_finish_requested_exit_code']==0
        and type(r['SDK_finish_requested_exit_code']) is int and r['SDK_finish_requested_exit_code']==0
        and r['failure'] is None and r['cleanup_errors']==[]
        and r['stream_cleanup']=={'input_descriptors_closed':True,'errors':[]}
        and s['numeric_20batch500step_acceptance'] is False and s['automatic_capacity_qualification'] is False,
        'Actual22 updates/SDK log/summary/finish or cleanup differs')
    require(sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['job_id']==JOB
        and sup['first_failure'] is None and sup['remaining_recorded_processes_before_retirement']==[]
        and sup['private_storage_cleanup_errors']==[] and sup['foreign_gpu_processes_signalled'] is False,
        'Actual source supervisor closure differs')
    terminal=expected['capacity_diagnostic']
    require(terminal['status']==r['status'] and terminal['failure'] is None and terminal['cleanup_errors']==[]
        and terminal['completed_actual_updates']==terminal['durable_source_rows']==terminal['SDK_log_calls_returned']==22
        and terminal['expected_actual_updates']==22 and terminal['configuration']==value['refs']['configuration']
        and terminal['source_package']==root['source_package'] and terminal['numeric_acceptance'] is False
        and terminal['automatic_capacity_qualification'] is False,'Original explicit summary terminal differs')
    wanted_sdk={k:root['SDK'][k] for k in ('path','bytes')}
    require(value['SDK']==wanted_sdk=={k:s['SDK'][k] for k in ('path','bytes')}
        =={k:r['SDK'][k] for k in ('path','bytes')} and descriptor(wanted_sdk['path'],128<<20)==wanted_sdk
        and Path(wanted_sdk['path']).name=='run-'+RUN+'.wandb'
        and Path(wanted_sdk['path']).parent.parent==CHILD/'wandb'
        and Path(wanted_sdk['path']).parent.name.startswith('offline-run-')
        and Path(wanted_sdk['path']).parent.name.endswith('-'+RUN), 'One exact original offline SDK differs')
    require(value['step_journal']['path']==str(CHILD/'steps.jsonl')
        and descriptor(value['step_journal']['path'],16<<20)==value['step_journal'],'Original steps stat differs')
    metadata['expected_summary']=expected
    return metadata


def bound_inputs(raw):
    value=read(raw);metadata_inputs(value)
    require(value['SDK']['bytes']+value['step_journal']['bytes']+sum(x['bytes'] for x in value['refs'].values())
        +value['expected_summary']['bytes']+value['root_closure']['bytes']<=256<<20,'Explicit input envelope exceeded')
    return value


def header_check(header):
    require(set(header)=={'run_id','display_name','project','entity'} and header['run_id']==RUN
        and header['display_name']=='native_S_max712_R1_'+JOB and header['project']=='mfm_model_v3_development'
        and type(header['entity']) is str,'Actual source RunRecord ID/name/project differs')


def proof_rows(manifest):
    require(manifest['schema']=='native_max_R1_sync_manifest_v1' and len(manifest['verifications'])==1,
        'Exactly one independently audited max run required')
    batch=read(manifest['audit_result']);sup=read(manifest['audit_supervisor'])
    terminal=terminal_C0(manifest['actual_audit_C0']);job=terminal['job_id']
    require(batch['schema']=='native_max_R1_log_audit_result_v1'
        and batch['status']=='ONE_MAX_RUN_FULL_LOG_MATCHED_PENDING_ACTUAL_CPU_C0'
        and batch['actual_job_id']==job==str(sup['job_id']) and batch['returncode']==0 and batch['failure'] is None
        and batch['verifications']==manifest['verifications'] and batch['source_pins']==ref(HERE/'source_pins.json')
        and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
        and sup['remaining']==[] and sup['private_storage']['first_sampling_failure'] is None
        and sup['command']==batch['actual_argv'],'Actual audit CPU C0/source/supervisor required')
    expected=[str(PYTHON),'-u','-B',str(HERE/'audit_max.py'),'--inputs',batch['inputs']['path'],
        '--inputs-sha256',batch['inputs']['sha256'],'--pins-sha256',batch['source_pins']['sha256'],
        '--output',str(Path(manifest['audit_result']['path']).parent)]
    require(batch['actual_argv']==expected and batch['actual_allocation']['uid']==1278,'Actual CPU audit argv/UID differs')
    inputs=bound_inputs(batch['inputs']);cert=read(manifest['verifications'][0]);h=cert['history']
    require(cert['schema']=='native_max_R1_full_log_verification_v1' and cert['scope']==SCOPE
        and cert['status']=='ALL_SAVED_NATIVE_MAX_LOG_FIELDS_MATCHED' and cert['run_id']==RUN
        and cert['model_job_id']==JOB and cert['source_pins']==batch['source_pins'] and cert['inputs']==batch['inputs']
        and cert['full_config_summary_typed_exact'] is True and cert['raw_before_after_binding_closed'] is True,
        'Exact max full-log certificate required')
    deps=read(HERE/'dependencies.json');header_check(cert['native_RunRecord'])
    require(cert['history_reader_source']==deps['sources']['literal_reader'] and cert['tap_source']==deps['sources']['tap']
        and h['schema']=='model_v3_native_mirror_verification_v7' and h['status']=='VERIFIED_COMMITTED_HISTORY'
        and h['sdk_run_ids']==[RUN] and h['sdk_exit_codes']==[0] and type(h['sdk_exit_codes'][0]) is int
        and h['clean_eof'] is True and h['native_closed'] is True and h['decode_error'] is None
        and type(h['uncommitted_native_requests']) is int and h['uncommitted_native_requests']==0
        and type(h['history_rows']) is int and h['history_rows']==22
        and h['first_explicit_step']==1 and h['last_explicit_step']==22,'Exact22 steps/exit0/fullfragment EOF required')
    require({k:cert['sdk'][k] for k in ('path','bytes')}==inputs['SDK']
        and {k:cert['journal'][k] for k in ('path','bytes')}==inputs['step_journal'], 'Original payload identity differs')
    for source in cert['source_refs'].values():bind(source)
    return [dict(run_id=RUN,SDK_raw_ref=cert['sdk'],native_RunRecord=cert['native_RunRecord'],native_exit_code=0,
        expected_API_state='finished',history_rows=22,first_explicit_step=1,last_explicit_step=22,
        model_job_id=JOB,verification=manifest['verifications'][0],scope=SCOPE)]


def manifest_metadata():
    raw=ref(os.environ['MODEL_V3_MAX_MANIFEST'])
    require(raw['sha256']==os.environ['MODEL_V3_MAX_MANIFEST_SHA'],'Explicit one-run manifest drift')
    value=read(raw);require(value['runs']==proof_rows(value),'Proof-derived eligible row differs')
    return raw,value


def eligible_rows():
    allocation();_,manifest=manifest_metadata();rows=proof_rows(manifest);entity_default=None
    if any(not r['native_RunRecord']['entity'] for r in rows):
        private=Path(os.environ['TMPDIR'])/('max_authenticated_route_'+str(os.getpid()));private.mkdir(mode=0o700)
        with (private/'stdout').open('x') as out,(private/'stderr').open('x') as err,contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            for item in read(HERE/'installed_sources.json')['files']:
                current=ref(item['original']);require((current['bytes'],current['sha256'])==(item['bytes'],item['sha256']),'Installed API drift')
            import wandb
            require(wandb.__version__=='0.28.1','Actual reviewed SDK0.28.1 required');api=wandb.Api(timeout=30)
            require(api.settings['base_url']=='https://api.wandb.ai','Actual destination differs')
            entity_default=api.viewer.entity
            require(type(entity_default) is str and entity_default and api.default_entity==entity_default,'Actual authenticated route missing')
    for row in rows:
        h=row['native_RunRecord'];row['routing']=dict(entity=h['entity'] or entity_default,project=h['project'],run_id=RUN,
            routing_ready=True,entity_origin='original_RunRecord' if h['entity'] else 'actual_authenticated_viewer_default',project_origin='original_RunRecord')
    return manifest,{r['run_id']:r for r in rows}


def request_gate(request):
    raw,manifest=manifest_metadata();rows=proof_rows(manifest)
    require(request['schema']=='native_max_R1_selective_sync_request_v1' and request['selected_run_ids']==[RUN]
        and request['eligible_manifest']==raw and request['source_manifest']==ref(HERE/'source_pins.json')
        and request['mode']=='batch' and request['maximum_batch_runs']==3 and request['child_seconds']==3000
        and request['CLI_timeout_seconds']==600 and request['API_verification_seconds']==180,
        'Only the one certified max SDK with original finite transport budgets is admitted')
    gate=request['pilot_gate'];terminal=terminal_C0(gate['actual_terminal']);pilot=read(gate['result']);sup=read(gate['supervisor'])
    require(terminal['job_id']==str(pilot['job_id'])==str(sup['job_id'])=='4521412'
        and pilot['source_manifest']==ref(V3/'source_pins.json') and pilot['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0'
        and len(pilot['records'])==1 and pilot['records'][0]['native_exit_code']==1
        and pilot['records'][0]['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED'
        and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None and sup['remaining']==[]
        and gate['native_exit_code']==1 and gate['actual_replay_verified'] is True,'Original actual v3 transport method gate required')
