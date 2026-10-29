"""Single closed Native dev-panel metadata adapter; old transport is unchanged."""
from __future__ import annotations
import contextlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import socket
import stat

HERE=Path(__file__).absolute().parent
V3=HERE.parent/'wandb_selective_sync50_v3'
sys.path.insert(0,str(V3))
import sync_common as base
from sync_common import *
HERE=Path(__file__).absolute().parent
RUN='i59ur33t'
MODEL_JOB='4525060'
SCOPE='DEV_PANEL_LOG_ONLY'
EVALUATION=BASE/'runs/model_v3_20261026/Native_S20000_seed0_fp32_dev9_auto_v1/panel/evaluation'
TASKS=('cyp.3A4','cyp.2D6','exp.LogD','exp.LogS','exp.Log_HLM_CLint','qm9.U0','qm9.homo','qm9.lumo','qm9.alpha')
METRIC=re.compile(r'(candidate|reference)/([^/@]+)@(ridge|linear64_relu)/(validation_error|readout/(?:loss|epoch|observed_labels|update))\Z')


def allocation():
    # Explicit local adapter, not a monkeypatch of sync_common/base globals.
    # Original job/16CPU/CUDA/node/cgroup gates remain; only fixed MEM=16384
    # is removed. Scheduler memory defaults are observed, never fabricated.
    job=os.environ.get('SLURM_JOB_ID','');node=os.environ.get('MODEL_V3_EXPECTED_NODE','')
    require(job.isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16
        and os.environ.get('CUDA_VISIBLE_DEVICES')==''
        and socket.gethostname()==node and re.fullmatch(r'compute-0-(?:2|[89]|1[0-9])',node),
        'Actual owned CPU16 allocation/node with CUDA hidden required')
    group=Path('/proc/self/cgroup').read_text()
    require(re.search(r'(?:job[_/-])'+re.escape(job)+r'(?:/|\n|$)',group),'Actual own job cgroup required')
    require(os.getuid()==os.geteuid()==1278,'Actual owned UID1278 required')
    pid=os.getpid();raw_stat=Path('/proc/self/stat').read_text();tail=raw_stat.rsplit(')',1)[1].split()
    start_ticks=int(tail[19]);pgid=os.getpgid(pid);sid=os.getsid(pid)
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    argv=[part.decode('utf-8') for part in Path('/proc/self/cmdline').read_bytes().split(b'\0') if part]
    require(int(raw_stat.split(' ',1)[0])==pid and start_ticks>0
        and int(tail[2])==pgid and int(tail[3])==sid and argv==list(sys.orig_argv)
        and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',boot_id),
        'Actual PID/start_ticks/boot/PGID/SID/argv identity differs')
    private=Path(os.environ['TMPDIR'])
    require(private.is_absolute() and not any(path.is_symlink() for path in (private,*private.parents))
        and stat.S_ISDIR(private.stat().st_mode) and private.stat().st_uid==1278,
        'Original supervisor-owned ordinary private root required')
    return dict(job_id=job,node=node,uid=os.getuid(),cgroup=group,pid=pid,start_ticks=start_ticks,
        boot_id=boot_id,pgid=pgid,sid=sid,argv=argv,private_root=str(private),
        scheduler_memory_environment={key:os.environ.get(key) for key in
            ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},
        software_working_memory_budget_bytes=16<<30,scheduler_reserved_memory_bytes_claimed=None,
        resource_policy='AUTOMATIC_SCHEDULER_MEMORY_ACTUAL_ENV_RECORDED_OR_NULL',
        original_supervisor_RSS_whole_private_identity_guards_unchanged=True)


def load(raw,name):
    bind(raw)
    spec=importlib.util.spec_from_file_location(name,raw['path'])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def verify(expected=None):
    pin=ref(HERE/'source_pins.json')
    if expected is not None:require(pin['sha256']==expected,'Panel source manifest differs')
    value=read(pin)
    require(value['schema']=='native_S20000_panel_log_sync_sources_v1','Exact source inventory required')
    for item in value['files']:
        actual=ref(HERE/item['relative_path'])
        require((actual['bytes'],actual['sha256'])==(item['bytes'],item['sha256']),'Panel source drift')
    deps=read(HERE/'dependencies.json')
    for raw in deps['sources'].values():bind(raw)
    base.verify(deps['base_manifest']['sha256'])
    original=(V3/'one_run.py').read_bytes()
    require(original.count(b'from sync_common import *')==1,'Frozen transport import changed')
    require((HERE/'one_run_panel.py').read_bytes()==original.replace(b'from sync_common import *',b'from panel_common import *'),
        'Transport may only change its explicit eligible-input import')
    require((HERE/'installed_sources.json').read_bytes()==(V3/'installed_sources.json').read_bytes(),'Installed-source inventory changed')
    return pin


def descriptor(path,cap):
    path=Path(path).absolute()
    require(not any(p.is_symlink() for p in (path,*path.parents)),'Descriptor must be physical')
    info=path.stat()
    require(path.is_file() and info.st_uid==os.getuid() and info.st_nlink==1 and 0<=info.st_size<=cap,
        'Owned bounded ordinary descriptor required')
    return dict(path=str(path),bytes=info.st_size)


def metadata_gate(inputs,closure,result,guard,request,spec):
    require(inputs['schema']=='native_S20000_panel_log_inputs_v1' and inputs['scope']==SCOPE
        and inputs['run_id']==RUN and inputs['model_job_id']==MODEL_JOB,'Only actual5060 panel is eligible')
    require(closure['schema']=='model_v3_Native_S20000_panel_GPU_Root_metadata_closure_v1'
        and closure['status']=='ACTUAL_GPU_C0_NATIVE20000_FULL9_18CELL_H0_SOURCE_RESOURCE_CLOSED_SDK_PENDING'
        and closure['job_id']==MODEL_JOB and closure['result']==inputs['refs']['result']
        and closure['request']==inputs['refs']['request'] and closure['spec']==inputs['refs']['spec']
        and closure['supervisor']==inputs['refs']['supervisor'],'Exact actual Root5060 closure binding required')
    require(closure['closer_source']==read(ref(HERE/'dependencies.json'))['sources']['Root_metadata_closer'],
        'Actual Root closure producer must be this frozen metadata-only closer')
    endpoint=closure['Native_endpoint'];native=result['encoder_pair']['native_checkpoint']
    require(endpoint['optimizer_updates']==native['optimizer_updates']==20000
        and endpoint['samples_consumed']==native['samples_consumed']==8151040
        and endpoint['seed']==0 and endpoint['precision']==native['pretraining_precision']=='fp32'
        and spec['operations_source_pins']['sha256']=='0324c7933cd129af8c5740c64bf34f880083dbf386b6e0fa4b18b6aa53a50d05'
        and spec['requested_memory_bytes'] is None and spec['software_memory_budget_bytes']==32<<30
        and spec['maximum_process_group_rss_bytes']==28<<30 and spec['Slurm_memory_mode']=='automatic_default',
        'Exact actual20k checkpoint and reviewed GPU-auto operational source required')
    fields=closure['actual_parent_fields']
    require(fields['JobIDRaw']==MODEL_JOB and fields['User']=='zixiao' and fields['State']=='COMPLETED'
        and fields['ExitCode']=='0:0' and fields['AllocCPUS']=='16' and fields['NodeList']=='compute-0-21',
        'Original actual model C0 allocation missing')
    raw=closure['actual_parent'];require(raw['returncode']==0 and raw['stdout'].strip().split('|')[:7]
        ==[MODEL_JOB,'zixiao','COMPLETED','0:0','16','compute-0-21',fields['ElapsedRaw']],
        'Root actual raw accounting differs')
    resources=closure['resource_closure']
    require(resources['remaining_owned_processes']==[] and resources['private_cleanup_errors']==[]
        and resources['foreign_processes_signalled'] is False
        and resources['private_storage_final']['first_sampling_failure'] is None,'Original cleanup/resource proof differs')
    require(result['schema']=='model_v3_dev_evaluation_result_v1' and result['status']=='COMPLETED'
        and result['job_id']==guard['job_id']==MODEL_JOB and result['wandb_run_id']==RUN
        and guard['status']=='COMPLETED' and guard['child_returncode']==0
        and guard['result']==inputs['refs']['result'],'Actual complete result/guard required')
    require(result['code_sha']==guard['code_sha'] and result['gpu_uuid']==guard['gpu_uuid']==spec['gpu_uuid'],'Core/guard physical execution identity differs')
    require(result['request_sha256']==guard['request_sha256']==inputs['refs']['request']['sha256']
        and guard['spec_sha256']==inputs['refs']['spec']['sha256']
        and spec['request']==inputs['refs']['request'],'Request/spec bytes differ')
    require(request['run_id']=='Native_S20000_seed0_fp32_dev9_auto_v1' and request['wandb_project']=='phychem-model-v3'
        and result['code_sha']==request['code_sha']==spec['code_sha']=='17f975bb094c9c3ec010d7f8134c5700adcc85e4'
        and spec['producer_code_sha']=='3d9b1cc0c580dacc9398a5570b0c2fff3e257618'
        and result['preregistration_sha']==request['preregistration_sha']=='39cf4929299cd227a3c361183a4b26c8b1405900',
        'Exact Native producer/evaluator/public panel identity required')
    require(closure['bridge_identity']['public_code_sha']==spec['public_code_sha']
        and closure['bridge_identity']['tree_sha']==spec['bridge_tree_sha'],'Root public bridge mapping differs')
    for key in ('architecture_sha256','data_version','pretraining_seed'):
        require(result[key]==request[key],'Actual source/config/seed differs')
    require(result['encoder_pair']['H0_dimension']==512 and result['panel_sha256']==request['panel']['sha256'],
        'Panel/H0 binding differs')
    require(set(result['summaries'])=={'primary_18_cells','ridge','linear64_relu'},'All three aggregate populations required')
    for name,n in (('primary_18_cells',18),('ridge',9),('linear64_relu',9)):
        summary=result['summaries'][name]
        require(summary['complete'] is True and summary['bootstrap_samples']==1000
            and len(summary['tasks'])==n,'Complete9x2/1000 bootstrap result required')
    require(type(result['journal_records']) is int and 0<result['journal_records']<=100000
        and result['journal_records']==closure['journal_records_as_saved_not_SDK_record_count'],
        'Producer history count must come from actual result, not native packet count')
    return {**{key:request[key] for key in ('code_sha','preregistration_sha','data_version','architecture_sha256','pretraining_seed')},
        'request_sha256':inputs['refs']['request']['sha256'],'job_id':MODEL_JOB,'gpu_uuid':result['gpu_uuid'],
        'panel_sha256':result['panel_sha256'],'random_reference_initialization_seed':result['random_reference_initialization_seed'],
        'readout_seed':result['readout_seed']}


def inputs_SDK_path():
    value=read(ref(HERE/'inputs.template.json'))
    descriptor_value=value['sdk_descriptor']
    expected=EVALUATION/'wandb'
    path=Path(descriptor_value['path'])
    require(path.parent.parent==expected and path.parent.name.startswith('offline-run-')
        and path.parent.name.endswith('-'+RUN) and path.name=='run-'+RUN+'.wandb',
        'Exactly the actual20k offline directory and run are eligible')
    return str(path)

def bound_inputs(raw):
    value=read(raw)
    require(value['sdk_descriptor']['path']==inputs_SDK_path()
        and value['journal_descriptor']['path']==str(EVALUATION/'history.jsonl'),'Only exact closed5060 SDK and journal descriptors allowed')
    refs=value['refs'];metadata={name:read(item) for name,item in refs.items()}
    expected=metadata_gate(value,metadata['closure'],metadata['result'],metadata['guard'],metadata['request'],metadata['spec'])
    # The new20k hold stays exclusively Root-owned; no release is inferred or performed.
    sup=metadata['supervisor']
    require(sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
        and sup['remaining_recorded_processes_before_retirement']==[]
        and sup['private_storage_cleanup_errors']==[],'Original GPU supervisor not closed')
    require(descriptor(value['sdk_descriptor']['path'],128<<20)==value['sdk_descriptor']
        and descriptor(value['journal_descriptor']['path'],32<<20)==value['journal_descriptor'],
        'Exact SDK/journal descriptor changed; prepare never hashes either body')
    return value,metadata,expected


def check_header(header,request):
    require(set(header)=={'run_id','display_name','project','entity'}
        and header['run_id']==RUN and header['display_name']==request['run_id']
        and header['project']==request['wandb_project'] and type(header['entity']) is str,
        'Original RunRecord ID/name/project required; entity is never inferred from project')


def row_from_proof(manifest):
    require(manifest['schema']=='native_S20000_panel_sync_manifest_v1' and manifest['run_ids']==[RUN],
        'One explicit panel proof only')
    cert=read(manifest['verification']);result=read(manifest['audit_result']);sup=read(manifest['audit_supervisor'])
    terminal=terminal_C0(manifest['actual_audit_C0']);job=terminal['job_id']
    require(cert['schema']=='native_S_dev_panel_full_log_comparison_v1' and cert['scope']==SCOPE
        and cert['status']=='ALL_SAVED_PANEL_LOG_FIELDS_MATCHED' and cert['run_id']==RUN
        and cert['raw_before_after_binding_closed'] is True and cert['full_config_summary_typed_exact'] is True,
        'Complete independent panel certificate required')
    require(result['schema']=='native_S20000_panel_SDK_audit_result_v1' and result['failure'] is None
        and result['returncode']==0 and result['verification']==manifest['verification']
        and result['actual_job_id']==job==str(sup['job_id']) and sup['status']=='COMPLETED'
        and sup['exit_code']==0 and sup['first_failure'] is None and sup['remaining']==[]
        and sup['private_storage']['first_sampling_failure'] is None and sup['command']==result['actual_argv'],
        'Actual same-job independent audit C0/supervisor required')
    require(cert['inputs']==result['inputs'] and cert['source_pins']==result['source_pins']
        and cert['source_pins']==ref(HERE/'source_pins.json'),'Audit source/input inventory differs')
    expected_argv=[str(PYTHON),'-u','-B',str(HERE/'audit_panel.py'),'--inputs',cert['inputs']['path'],
        '--inputs-sha256',cert['inputs']['sha256'],'--pins-sha256',cert['source_pins']['sha256'],
        '--output',str(Path(manifest['verification']['path']).parent)]
    require(result['actual_argv']==expected_argv and result['actual_allocation']['job_id']==job
        and result['actual_allocation']['uid']==1278,'Actual independent CPU producer argv/UID differs')
    deps=read(HERE/'dependencies.json')
    require(cert['history_reader_source']==deps['sources']['literal_reader'] and cert['tap_source']==deps['sources']['tap'],
        'Actual full comparison reader/tap provenance differs')
    inputs,metadata,_=bound_inputs(cert['inputs']);history=cert['history'];header=cert['native_RunRecord']
    check_header(header,metadata['request'])
    require(history['schema']=='model_v3_native_mirror_verification_v7'
        and history['status']=='VERIFIED_COMMITTED_HISTORY' and history['sdk_run_ids']==[RUN]
        and history['sdk_exit_codes']==[0] and type(history['sdk_exit_codes'][0]) is int and history['native_closed'] is True and history['clean_eof'] is True
        and history['decode_error'] is None and history['uncommitted_native_requests']==0
        and type(history['history_rows']) is int and history['history_rows']==metadata['result']['journal_records']
        and history['first_explicit_step']==0 and history['last_explicit_step']==history['history_rows']-1,
        'Native history/step/exit/complete-fragment EOF differs')
    require({k:cert['sdk'][k] for k in ('path','bytes')}==inputs['sdk_descriptor']
        and Path(cert['sdk']['path']).name=='run-'+RUN+'.wandb','Exact one original SDK required')
    for raw in cert['source_refs'].values():bind(raw)
    for raw in manifest.values():
        if isinstance(raw,dict) and set(raw)=={'path','bytes','sha256'}:bind(raw)
    return dict(run_id=RUN,SDK_raw_ref=cert['sdk'],native_exit_code=0,expected_API_state='finished',
        history_rows=history['history_rows'],first_explicit_step=0,last_explicit_step=history['last_explicit_step'],
        native_RunRecord=header,original_model_status='COMPLETED',verification=manifest['verification'],scope=SCOPE)


def manifest_metadata():
    raw=ref(os.environ['MODEL_V3_PANEL_MANIFEST'])
    require(raw['sha256']==os.environ['MODEL_V3_PANEL_MANIFEST_SHA'],'Panel explicit manifest changed')
    value=read(raw);require(value['runs']==[row_from_proof(value)],'Manifest must preserve exact certificate row')
    return raw,value


def eligible_rows():
    allocation();_,value=manifest_metadata();row=row_from_proof(value);header=row['native_RunRecord']
    entity=header['entity'];origin='original_RunRecord'
    if not entity:
        private=Path(os.environ['TMPDIR'])/('panel_authenticated_route_'+str(os.getpid()))
        private.mkdir(mode=0o700)
        with (private/'stdout').open('x') as out,(private/'stderr').open('x') as err,contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            for item in read(HERE/'installed_sources.json')['files']:
                current=ref(item['original'])
                require((current['bytes'],current['sha256'])==(item['bytes'],item['sha256']),'Installed authenticated API source drift')
            import wandb
            require(wandb.__version__=='0.28.1','Reviewed transport version required')
            api=wandb.Api(timeout=30)
            require(api.settings['base_url']=='https://api.wandb.ai','Unexpected W&B cloud destination')
            entity=api.viewer.entity
            require(type(entity) is str and entity and api.default_entity==entity,'Actual authenticated viewer/default entity missing')
        origin='actual_authenticated_API_viewer_default_for_empty_native_entity'
    row['routing']=dict(entity=entity,project=header['project'],run_id=RUN,routing_ready=True,
        entity_origin=origin,project_origin='original_RunRecord_exact_saved_request')
    return value,{RUN:row}


def request_gate(request):
    raw,value=manifest_metadata()
    require(request['schema']=='native_S20000_panel_selective_sync_request_v1' and request['eligible_manifest']==raw
        and request['mode']=='pilot' and request['selected_run_ids']==[RUN] and request['maximum_batch_runs']==1
        and request['source_manifest']==ref(HERE/'source_pins.json')
        and request['CLI_timeout_seconds']==600 and request['API_verification_seconds']==180
        and request['child_seconds']==3000,'Only exact bounded single-run transport request accepted')
