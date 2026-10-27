"""Single closed Native dev-panel metadata adapter; old transport is unchanged."""
from __future__ import annotations
import contextlib
import importlib.util
import os
from pathlib import Path
import re
import sys

HERE=Path(__file__).absolute().parent
V3=HERE.parent/'wandb_selective_sync50_v3'
sys.path.insert(0,str(V3))
import sync_common as base
from sync_common import *
HERE=Path(__file__).absolute().parent
RUN='vcxcfx54'
MODEL_JOB='4524476'
SCOPE='DEV_PANEL_LOG_ONLY'
EVALUATION=BASE/'runs/model_v3_20261026/Native_S10000_seed0_fp32_dev9_v2/panel/evaluation'
TASKS=('cyp.3A4','cyp.2D6','exp.LogD','exp.LogS','exp.Log_HLM_CLint','qm9.U0','qm9.homo','qm9.lumo','qm9.alpha')
METRIC=re.compile(r'(candidate|reference)/([^/@]+)@(ridge|linear64_relu)/(validation_error|readout/(?:loss|epoch|observed_labels|update))\Z')


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
    require(value['schema']=='native_S10000_panel_log_sync_sources_v1','Exact source inventory required')
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
    require(inputs['schema']=='native_S10000_panel_log_inputs_v1' and inputs['scope']==SCOPE
        and inputs['run_id']==RUN and inputs['model_job_id']==MODEL_JOB,'Only actual4476 panel is eligible')
    require(closure['schema']=='model_v3_Native_S10000_panel_GPU_Root_metadata_closure_v1'
        and closure['status']=='ACTUAL_GPU_C0_NATIVE10000_FULL9_18CELL_H0_SOURCE_RESOURCE_CLOSED_SDK_PENDING'
        and closure['job_id']==MODEL_JOB and closure['result']==inputs['refs']['result']
        and closure['request']==inputs['refs']['request'] and closure['spec']==inputs['refs']['spec']
        and closure['supervisor']==inputs['refs']['supervisor'],'Exact actual Root4476 closure binding required')
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
    require(request['run_id']=='native_S10000_seed0_fp32_dev9_v2' and request['wandb_project']=='phychem-model-v3'
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


def bound_inputs(raw):
    value=read(raw)
    require(value['sdk_descriptor']['path']==str(EVALUATION/'wandb/offline-run-20261028_003550-vcxcfx54/run-vcxcfx54.wandb')
        and value['journal_descriptor']['path']==str(EVALUATION/'history.jsonl'),'Only the exact closed4476 SDK and journal descriptors are allowed')
    refs=value['refs'];metadata={name:read(item) for name,item in refs.items()}
    expected=metadata_gate(value,metadata['closure'],metadata['result'],metadata['guard'],metadata['request'],metadata['spec'])
    release=metadata['hold_release']
    require(release['status']=='ACTUAL_NATIVE10000_PANEL_HOLD_RELEASED_AFTER_ROOT_CLOSURE_AND_FINAL_CENSUS'
        and release['closure']==refs['closure'] and release['remaining_bytes']==0,'Actual completed old hold release receipt differs')
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
    require(manifest['schema']=='native_S10000_panel_sync_manifest_v1' and manifest['run_ids']==[RUN],
        'One explicit panel proof only')
    cert=read(manifest['verification']);result=read(manifest['audit_result']);sup=read(manifest['audit_supervisor'])
    terminal=terminal_C0(manifest['actual_audit_C0']);job=terminal['job_id']
    require(cert['schema']=='native_S_dev_panel_full_log_comparison_v1' and cert['scope']==SCOPE
        and cert['status']=='ALL_SAVED_PANEL_LOG_FIELDS_MATCHED' and cert['run_id']==RUN
        and cert['raw_before_after_binding_closed'] is True and cert['full_config_summary_typed_exact'] is True,
        'Complete independent panel certificate required')
    require(result['schema']=='native_S10000_panel_SDK_audit_result_v1' and result['failure'] is None
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
    require(request['schema']=='native_S10000_panel_selective_sync_request_v1' and request['eligible_manifest']==raw
        and request['mode']=='pilot' and request['selected_run_ids']==[RUN] and request['maximum_batch_runs']==1
        and request['source_manifest']==ref(HERE/'source_pins.json')
        and request['CLI_timeout_seconds']==600 and request['API_verification_seconds']==180
        and request['child_seconds']==3000,'Only exact bounded single-run transport request accepted')
