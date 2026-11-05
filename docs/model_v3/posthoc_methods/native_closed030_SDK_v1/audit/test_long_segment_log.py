"""Only synthetic saved metadata/protobuf records; no SDK/data/CP/model reads."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import time
import pytest
sys.path.insert(0,str(Path(__file__).parent))
import long_segment_log as logic


def fixture(resume=False,seed=0):
    plan=dict(input_scope=logic.DATA_SCOPE,updates=20000,sample_budget=10240000,
        validation_updates=list(range(0,20001,500)),checkpoint_updates=[10000,20000],warmup_samples=0)
    storage=dict(purpose='FOUR_NATIVE_S_B_MEMBERS',configuration={'path':'/synthetic/config','sha256':'a'*64})
    contract=dict(plan=plan,source_scope=logic.DATA_SCOPE,code_sha=logic.CODE,prereg_sha=logic.PUBLIC,
        seed=seed,precision='fp32',source_files={'source.py':'b'*64},runtime={'device':'cuda'},
        data_version={'version':'original_TRAIN_only'},registry='c'*64,input_binding={'validation_records':1024},
        validation_role='PRETRAIN_VAL',validation_seed=0,validation_epoch=0,D5_authority=False,Root_storage_policy=storage)
    tracker=dict(id='fresh123',mode='offline',path='unit/project/fresh123')
    cfg=dict(contract=contract,source_inputs=contract['input_binding'],Root_storage_binding=storage,tracker=tracker,resume_parent=None)
    expected=dict(seed=seed,precision='fp32',scope=logic.DATA_SCOPE,code_sha=logic.CODE,prereg_sha=logic.PUBLIC,
        sources=contract['source_files'],runtime=contract['runtime'],plan=plan,Root_storage_binding=storage,
        fixed_checkpoint_updates=plan['checkpoint_updates'],resume_checkpoint=None,resume_output_root=None)
    frame=dict(seed=seed,precision='fp32',actual_sbatch_job_id='9001',start_update=0,target_update=1000,
        native_member=dict(sources=contract['source_files'],runtime=contract['runtime'],code_sha=logic.CODE,prereg_sha=logic.PUBLIC))
    rows=[dict(step=0,commit=True,row=dict(log_cursor=0,event='VALIDATION',optimizer_updates=0,samples_consumed=0,
        role='PRETRAIN_VAL',records=1024,validation_seed=0,validation_epoch=0,metrics={'value':.5}))]
    chain=logic.canonical(dict(scope=logic.DATA_SCOPE,seed=seed))
    for update in (1,2):
        chain=logic.canonical(dict(previous=chain,input='d'*64,samples=update*512,updates=update))
        rows.append(dict(step=update,commit=True,row=dict(log_cursor=update,event='TRAIN',optimizer_updates=update,
            samples_consumed=update*512,input_sha256='d'*64,committed_input_chain_sha256=chain,loss=.5,
            **{'loss/s_noise':.2})))
    member=dict(schema='existing_native_S_precision_member_v1',scope=logic.DATA_SCOPE,scientific_acceptance=False,D5_authority=False,
        member_contract=contract,common_binding={key:contract[key] for key in ('plan','data_version','registry','code_sha')},
        seed=seed,precision='fp32',tracker=tracker,resume_parent=None,optimizer_updates=2,samples_consumed=1024,
        training_input_chain_sha256=chain,validation={'0':{'unit_point':.5}})
    status=dict(schema='native_S_long_child_status_v1',status='CHILD_COMPLETE_PENDING_ROOT_SDK_AND_NUMERIC_GATES',failure=None,
        cleanup_errors=[],tracker_id=tracker['id'],start_update=0,target_update=1000,optimizer_updates=2)
    closure=dict(schema='native_S_long_segment_Root_closure_v1',status='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING',failure=None,
        optimizer_updates=2,checkpoint_directory='/closed/parent/checkpoint')
    meta=dict(submission=frame,configuration=cfg,expected_configuration=expected,member=member,status=status,closure=closure)
    parent_rows=None
    if resume:
        parent=deepcopy(dict(member=member,configuration=cfg,closure=closure,child_path='/closed/parent'));parent_rows=deepcopy(rows)
        tracker=dict(id='resumed9',mode='offline',path='unit/project/resumed9')
        cfg['tracker']=member['tracker']=tracker;cfg['resume_parent']=member['resume_parent']=deepcopy(parent['member']['tracker'])
        expected['resume_checkpoint']=closure['checkpoint_directory'];expected['resume_output_root']='/closed/parent'
        frame['start_update']=status['start_update']=2;frame['actual_sbatch_job_id']='9002';status['tracker_id']=tracker['id']
        rows=[]
        for update in (3,4):
            chain=logic.canonical(dict(previous=chain,input='d'*64,samples=update*512,updates=update))
            rows.append(dict(step=update,commit=True,row=dict(log_cursor=update,event='TRAIN',optimizer_updates=update,
                samples_consumed=update*512,input_sha256='d'*64,committed_input_chain_sha256=chain,
                loss=.4,resume_parent_run_id=parent['member']['tracker']['id'],**{'loss/s_noise':.1})))
        member.update(optimizer_updates=4,samples_consumed=2048,training_input_chain_sha256=chain)
        status['optimizer_updates']=closure['optimizer_updates']=4;meta['parent']=parent
    summary=logic.merged(rows);summary['native_B_segment']=dict(seed=seed,precision='fp32',optimizer_updates=member['optimizer_updates'],
        target_update=1000,full_20000=False,scientific_acceptance=False)
    meta['expected_summary']=summary
    return meta,rows,parent_rows


@pytest.fixture(scope='module')
def modules():
    deps=json.loads((Path(__file__).parent/'dependencies.json').read_text());values=[]
    import hashlib
    for key in ('reader','tap'):
        value=deps['sources'][key];path=Path(value['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==value['sha256']
        spec=importlib.util.spec_from_file_location('long_unit_'+key,path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);values.append(module)
    return values


def native(context,*,exit_code=0):
    from wandb.proto import wandb_internal_pb2 as pb
    records=[];header=pb.Record();header.run.run_id=context['run_id'];header.run.display_name=context['run_name'];header.run.project=context['project']
    for key,value in context['expected_config'].items():header.run.config.update.add(key=key,value_json=json.dumps(value))
    records.append(header)
    for row in context['mirror_rows']:
        record=pb.Record()
        for key,value in {'_step':row['step'],**row['row']}.items():record.history.item.add(key=key,value_json=json.dumps(value))
        records.append(record)
    record=pb.Record()
    for key,value in {'_step':context['last_cursor'],**context['expected_summary']}.items():record.summary.update.add(key=key,value_json=json.dumps(value))
    records.append(record)
    if exit_code is not None:
        record=pb.Record();record.exit.exit_code=exit_code;records.append(record)
    return records


def compare(modules,context,records=None):
    from wandb.proto import wandb_internal_pb2 as pb
    values=iter(native(context) if records is None else records)
    class Stream:
        def scan_data(self):
            record=next(values,None);return None if record is None else record.SerializeToString()
    return logic.compare(*modules,Stream(),pb.Record,context,deadline=time.monotonic()+30)


@pytest.mark.parametrize('resume',(False,True))
def test_fresh_and_resumed_global_cursor_full_native_fields(modules,resume):
    metadata,rows,parent=fixture(resume);context=logic.prepare(metadata,rows,parent_rows=parent)
    result=compare(modules,context)
    assert result['scope']=='LONG_SEGMENT_LOG_ONLY' and result['full_config_summary_typed_exact']
    assert result['first_global_cursor']==(3 if resume else 0) and result['last_global_cursor']==(4 if resume else 2)
    assert result['scientific_acceptance'] is False and result['parent_SDK_verification_not_claimed']


@pytest.mark.parametrize('damage',('seed','data','source','profile','summary','chain','cursor','population'))
def test_metadata_contract_drift_rejected(damage):
    metadata,rows,parent=fixture()
    if damage=='seed':metadata['expected_configuration']['seed']=1
    elif damage=='data':metadata['configuration']['source_inputs']={'wrong':1}
    elif damage=='source':metadata['expected_configuration']['code_sha']='f'*40
    elif damage=='profile':metadata['closure']['schema']='native_S_short_profile_Root_closure_v1'
    elif damage=='summary':metadata['expected_summary']['loss']=99
    elif damage=='chain':rows[-1]['row']['committed_input_chain_sha256']='f'*64
    elif damage=='cursor':rows[1]['step']=100
    else:rows[0]['row']['records']=1023
    with pytest.raises(ValueError):logic.prepare(metadata,rows,parent_rows=parent)


@pytest.mark.parametrize('damage',('parent_id','cursor_reset','parent_contract','parent_checkpoint'))
def test_resume_cannot_reset_or_alias_parent(damage):
    metadata,rows,parent=fixture(True)
    if damage=='parent_id':rows[0]['row']['resume_parent_run_id']='foreign'
    elif damage=='cursor_reset':
        for index,row in enumerate(rows):row['step']=row['row']['log_cursor']=index
    elif damage=='parent_contract':metadata['parent']['member']['member_contract']=dict(wrong=True)
    else:metadata['expected_configuration']['resume_checkpoint']='/different/CP'
    with pytest.raises(ValueError):logic.prepare(metadata,rows,parent_rows=parent)


@pytest.mark.parametrize('damage',('history','config','summary','step','run_id','no_exit','exit1'))
def test_native_complete_fields_identity_explicit_step_exit_rejected(modules,damage):
    metadata,rows,parent=fixture(True);context=logic.prepare(metadata,rows,parent_rows=parent);records=native(context)
    if damage=='history':records[1].history.item.add(key='unexpected/metric',value_json='1')
    elif damage=='config':records[0].run.config.update.add(key='extra',value_json='true')
    elif damage=='summary':records[-2].summary.update.add(key='extra',value_json='true')
    elif damage=='step':records[1].history.item[0].value_json='3.0'
    elif damage=='run_id':records[0].run.run_id='foreign'
    elif damage=='no_exit':records.pop()
    else:records[-1].exit.exit_code=1
    with pytest.raises((ValueError,AssertionError)):compare(modules,context,records)


def operational_fixture():
    metadata,rows,parent=fixture()
    sources=dict(long_child=dict(path='/synthetic/operational_v4/long_child.py',bytes=10,sha256='a'*64),
        NativeCore=dict(path='/synthetic/immutable/native.py',bytes=11,sha256='b'*64),
        quota_retry=dict(path='/synthetic/operational_v4/quota_retry.py',bytes=12,sha256='c'*64))
    retry=dict(scope='OPERATIONAL_ORIGINAL_QUOTA_REVALIDATION_ONLY',wait_seconds=30,max_rejected_snapshots=256,
        source_path=sources['quota_retry']['path'],source_sha256=sources['quota_retry']['sha256'],
        numeric_code_data_seed_precision_optimizer_RNG_unchanged=True)
    metadata['configuration'].update(operational_runner_source=sources['long_child'],
        scientific_core_source=sources['NativeCore'],operational_quota_revalidation=deepcopy(retry))
    metadata['expected_configuration']['operational_quota_revalidation']=deepcopy(retry)
    return metadata,rows,parent,sources


def test_v4_explicit_source_addition_is_fully_compared_in_native_config(modules):
    metadata,rows,parent,sources=operational_fixture()
    bound=logic.check_operational_sources(metadata['configuration'],metadata['expected_configuration'],sources)
    assert bound['source_sha256']==sources['quota_retry']['sha256']
    context=logic.prepare(metadata,rows,parent_rows=parent)
    result=compare(modules,context)
    assert result['full_config_summary_typed_exact'] and result['scope']=='LONG_SEGMENT_LOG_ONLY'
    assert result['scientific_acceptance'] is False


@pytest.mark.parametrize('damage',('path','hash','wait','count','config_only'))
def test_v4_operational_source_policy_or_saved_config_drift_is_rejected(damage):
    metadata,rows,parent,sources=operational_fixture()
    retry=metadata['configuration']['operational_quota_revalidation']
    if damage=='path':retry['source_path']='/foreign/quota_retry.py'
    elif damage=='hash':retry['source_sha256']='e'*64
    elif damage=='wait':retry['wait_seconds']=31
    elif damage=='count':retry['max_rejected_snapshots']=True
    else:metadata['expected_configuration']['operational_quota_revalidation']['wait_seconds']=29
    with pytest.raises(ValueError):logic.check_operational_sources(metadata['configuration'],metadata['expected_configuration'],sources)


def test_v4_native_quota_field_mutation_is_rejected_not_filtered(modules):
    metadata,rows,parent,sources=operational_fixture()
    logic.check_operational_sources(metadata['configuration'],metadata['expected_configuration'],sources)
    context=logic.prepare(metadata,rows,parent_rows=parent);records=native(context)
    items=records[0].run.config.update
    for item in items:
        if item.key=='operational_quota_revalidation':
            value=json.loads(item.value_json);value['source_sha256']='f'*64;item.value_json=json.dumps(value)
            break
    else:pytest.fail('Synthetic native config must contain actual v4 field')
    with pytest.raises((ValueError,AssertionError)):compare(modules,context,records)
