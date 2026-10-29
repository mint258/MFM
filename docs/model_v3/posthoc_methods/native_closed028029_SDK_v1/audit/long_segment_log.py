"""Pure closed long-segment metadata checks, not Profile20 or numerical acceptance."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import re
import time

SCOPE='LONG_SEGMENT_LOG_ONLY'
DATA_SCOPE='existing_native_S_original_TRAIN_record_sampler_not_D5'
CODE='3d9b1cc0c580dacc9398a5570b0c2fff3e257618'
PUBLIC='ce7cbf5776ff546cd47538b120c8f884e2e5867d'
MAX_ROWS=1104


def require(ok,message):
    if not ok:raise ValueError(message)


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def merged(rows):
    result={}
    def update(target,value):
        for key,item in value.items():
            if type(item) is dict:
                if type(target.get(key)) is not dict:target[key]={}
                update(target[key],item)
            else:target[key]=deepcopy(item)
    for row in rows:update(result,row['row'])
    return result


def mirror_envelopes(rows):
    require(0<len(rows)<=MAX_ROWS,'Bounded nonempty long-segment mirror required')
    first=rows[0]['step']
    require(type(first) is int and first>=0,'Explicit global first cursor required')
    for index,item in enumerate(rows):
        require(type(item) is dict and set(item)=={'step','commit','row'} and item['commit'] is True
            and type(item['step']) is int and item['step']==first+index and type(item['row']) is dict
            and type(item['row'].get('log_cursor')) is int and item['row']['log_cursor']==item['step'],
            'Committed continuous explicit global cursor/mirror envelope required')
    return first,rows[-1]['step']


def check_operational_sources(configuration,expected_configuration,sources):
    """Bind v4 operational addition without changing its numerical/native contract."""
    require(configuration['operational_runner_source']==sources['long_child']
        and configuration['scientific_core_source']==sources['NativeCore'],'Actual operational/Core producer source differs')
    retry=configuration.get('operational_quota_revalidation')
    require(type(retry) is dict and set(retry)=={'scope','wait_seconds','max_rejected_snapshots',
        'source_path','source_sha256','numeric_code_data_seed_precision_optimizer_RNG_unchanged'},
        'Exact explicit quota-revalidation metadata required')
    require(retry['scope']=='OPERATIONAL_ORIGINAL_QUOTA_REVALIDATION_ONLY'
        and type(retry['wait_seconds']) is int and retry['wait_seconds']==30
        and type(retry['max_rejected_snapshots']) is int and retry['max_rejected_snapshots']==256
        and retry['numeric_code_data_seed_precision_optimizer_RNG_unchanged'] is True,
        'Original bounded operational retry policy differs')
    require(type(retry['source_path']) is str and type(retry['source_sha256']) is str
        and retry['source_path']==sources['quota_retry']['path']
        and retry['source_sha256']==sources['quota_retry']['sha256'],
        'Actual quota-revalidation source path/SHA differs')
    require(canonical(expected_configuration.get('operational_quota_revalidation'))==canonical(retry),
        'Saved native SDK and child operational-revalidation metadata differ')
    return deepcopy(retry)


def prepare(metadata,rows,*,parent_rows=None):
    """All source/data/seed/parent facts are from bound closed metadata, not SDK headers."""
    frame=metadata['submission'];cfg=metadata['configuration'];config=metadata['expected_configuration']
    member=metadata['member'];status=metadata['status'];contract=cfg['contract'];closure=metadata['closure']
    require(closure['schema']=='native_S_long_segment_Root_closure_v1'
        and closure['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING' and closure['failure'] is None,
        'Actual closed C0 long segment required; no active/profile substitute')
    require(status['schema']=='native_S_long_child_status_v1' and status['failure'] is None and status['cleanup_errors']==[]
        and status['status']=='CHILD_COMPLETE_PENDING_ROOT_SDK_AND_NUMERIC_GATES','Clean actual long child closure required')
    require(member['schema']=='existing_native_S_precision_member_v1' and member['scope']==DATA_SCOPE
        and member['scientific_acceptance'] is False and member['D5_authority'] is False,'Long NativeCore result required')
    require(member['member_contract']==contract and cfg['source_inputs']==contract['input_binding']
        and all(contract[key]==value for key,value in member['common_binding'].items()),'Saved member/config/data contract differs')
    require(contract['code_sha']==CODE and contract['prereg_sha']==PUBLIC and contract['source_scope']==DATA_SCOPE
        and contract['D5_authority'] is False and contract['validation_role']=='PRETRAIN_VAL'
        and contract['validation_seed']==0 and contract['validation_epoch']==0,'Frozen source/data/validation identity differs')
    seed,precision=contract['seed'],contract['precision']
    require(contract['plan']==dict(input_scope=DATA_SCOPE,updates=20000,sample_budget=10240000,
        validation_updates=list(range(0,20001,500)),checkpoint_updates=[10000,20000],warmup_samples=0)
        and cfg['Root_storage_binding']['purpose']=='FOUR_NATIVE_S_B_MEMBERS','Exact long member plan/purpose required; not Profile20')
    require(type(seed) is int and seed in (0,1) and precision in ('fp32','bf16') and member['seed']==seed
        and member['precision']==precision and frame['seed']==seed and frame['precision']==precision,'Seed/precision binding differs')
    require(config['seed']==seed and config['precision']==precision and config['scope']==DATA_SCOPE
        and config['code_sha']==CODE and config['prereg_sha']==PUBLIC and config['sources']==contract['source_files']
        and config['runtime']==contract['runtime'] and config['plan']==contract['plan']
        and config['Root_storage_binding']==cfg['Root_storage_binding']==contract['Root_storage_policy']
        and config['fixed_checkpoint_updates']==contract['plan']['checkpoint_updates'],'Actual complete SDK configuration/source binding differs')
    native=frame['native_member']
    require(native['sources']==contract['source_files'] and native['runtime']==contract['runtime']
        and native['code_sha']==CODE and native['prereg_sha']==PUBLIC,'Source-bound submission differs')
    tracker=cfg['tracker'];require(tracker==member['tracker'] and tracker['mode']=='offline'
        and tracker['id']==status['tracker_id'],'Actual per-segment offline tracker differs')
    start,end,target=frame['start_update'],member['optimizer_updates'],frame['target_update']
    require(all(type(x) is int for x in (start,end,target)) and 0<=start<end<=target<=20000
        and status['start_update']==start and status['target_update']==target and status['optimizer_updates']==end
        and closure['optimizer_updates']==end,'Advancing committed segment endpoint differs')
    first,last=mirror_envelopes(rows);parent=metadata.get('parent')
    if start==0:
        require(parent is None and parent_rows is None and first==0 and cfg['resume_parent'] is None
            and member['resume_parent'] is None and config['resume_checkpoint'] is None
            and config['resume_output_root'] is None,'Fresh segment cannot pretend to resume')
        previous_samples=0;chain=canonical({'scope':DATA_SCOPE,'seed':seed});old_points={};parent_id=None
        require(rows[0]['row'].get('event')=='VALIDATION' and rows[0]['row']['optimizer_updates']==0,
            'Fresh NativeCore initial full validation required')
    else:
        require(parent is not None and parent_rows is not None,'Bound closed parent metadata/mirror required for resume')
        pm=parent['member'];pc=parent['configuration'];pr=parent['closure']
        _,parent_last=mirror_envelopes(parent_rows)
        require(pr['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING' and pr['failure'] is None
            and pm['optimizer_updates']==start and pm['member_contract']==contract==pc['contract']
            and pc['tracker']==pm['tracker'] and cfg['resume_parent']==member['resume_parent']==pm['tracker']
            and tracker['id']!=pm['tracker']['id'] and first==parent_last+1
            and config['resume_checkpoint']==pr['checkpoint_directory']
            and config['resume_output_root']==parent['child_path'],'Resume parent/source/global cursor differs')
        require(parent_rows[-1]['row']['optimizer_updates']==start
            and parent_rows[-1]['row']['samples_consumed']==pm['samples_consumed'],'Closed parent endpoint mirror differs')
        previous_samples=pm['samples_consumed'];chain=pm['training_input_chain_sha256']
        old_points=pm['validation'];parent_id=pm['tracker']['id']
    previous_update=start;validations=[];training_rows=0
    for item in rows:
        row=item['row'];update,samples=row['optimizer_updates'],row['samples_consumed']
        require(type(update) is int and type(samples) is int,'Integer physical consumed clocks required')
        if parent_id is None:require('resume_parent_run_id' not in row,'Fresh log cannot claim a parent')
        else:require(row.get('resume_parent_run_id')==parent_id,'Every resumed row must bind its actual parent run')
        if row['event']=='TRAIN':
            require(update in (previous_update,previous_update+1) and samples>previous_samples,'TRAIN cursor/update/base-draw drift')
            require(type(row['input_sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['input_sha256']), 'Input hash required')
            chain=canonical(dict(previous=chain,input=row['input_sha256'],samples=samples,updates=update))
            require(row['committed_input_chain_sha256']==chain,'Committed input-chain metadata differs')
            training_rows+=1
        elif row['event']=='VALIDATION':
            require(update==previous_update and samples==previous_samples and update in contract['plan']['validation_updates']
                and row['role']=='PRETRAIN_VAL' and type(row['records']) is int and row['records']==1024
                and type(row['validation_seed']) is int and row['validation_seed']==0
                and type(row['validation_epoch']) is int and row['validation_epoch']==0 and update not in validations,'Fixed validation population/cursor differs')
            validations.append(update)
        else:raise ValueError('Unknown long-segment mirror event')
        previous_update,previous_samples=update,samples
    require(training_rows>0 and previous_update==end and previous_samples==member['samples_consumed']
        and chain==member['training_input_chain_sha256'],'Final physical-draw/update/input-chain endpoint differs')
    require(all(member['validation'].get(key)==value for key,value in old_points.items())
        and set(member['validation'])-set(old_points)==set(map(str,validations)),'Validation continuation/point population differs')
    expected=merged(rows);expected['native_B_segment']=dict(seed=seed,precision=precision,optimizer_updates=end,
        target_update=target,full_20000=end==20000,scientific_acceptance=False)
    require(canonical(expected)==canonical(metadata['expected_summary']),'Saved full long summary differs from source merge')
    return dict(expected_config=config,expected_summary=metadata['expected_summary'],mirror_rows=rows,
        run_id=tracker['id'],run_name=f'nativeS_B_{precision}_seed{seed}_{frame["actual_sbatch_job_id"]}',
        project='mfm_model_v3_development',first_cursor=first,last_cursor=last,seed=seed,precision=precision,
        start_update=start,end_update=end,base_draws_end=previous_samples,
        source_data_contract_sha256=canonical(dict(code=CODE,public=PUBLIC,source=contract['source_files'],
            data_version=contract['data_version'],registry=contract['registry'],input_binding=cfg['source_inputs'])),
        parent_run_id=parent_id,parent_SDK_verification_not_claimed=True)


def compare(reader,tap,stream,record_class,context,*,deadline):
    audit=tap.Audit(reader,context)
    class Observed:
        def __init__(self):self.value=record_class()
        def ParseFromString(self,raw):self.value.ParseFromString(raw);audit.observe(self.value)
        def __getattr__(self,key):return getattr(self.value,key)
    class Sink:
        def write(self,raw):return len(raw)
    expected=[dict(step=row['step'],row=reader.flatten(row['row'])) for row in context['mirror_rows']]
    history=reader.verify_stream(stream,Observed,Sink(),expected_run_id=context['run_id'],expected_exit=0,
        expected_rows=len(expected),mirror_factory=lambda _:iter(expected),deadline=deadline,
        max_native_records=500000,max_history_rows=100000,max_record_bytes=4<<20,max_export_bytes=64<<20)
    audit.finish()
    require(history['native_closed'] and history['clean_eof'] and history['history_rows']==len(expected)
        and history['first_explicit_step']==context['first_cursor'] and history['last_explicit_step']==context['last_cursor'],
        'Actual complete segment native log did not close')
    return dict(schema='native_S_long_segment_full_log_comparison_v1',scope=SCOPE,
        status='ALL_SAVED_SCIENTIFIC_LOG_FIELDS_MATCHED',history=history,
        full_config_summary_typed_exact=True,expected_configuration_sha256=canonical(context['expected_config']),
        expected_summary_sha256=canonical(context['expected_summary']),expected_mirror_sha256=canonical(context['mirror_rows']),
        first_global_cursor=context['first_cursor'],last_global_cursor=context['last_cursor'],run_id=context['run_id'],
        source_data_contract_sha256=context['source_data_contract_sha256'],parent_run_id=context['parent_run_id'],
        parent_SDK_verification_not_claimed=True,numeric_model_or_B_acceptance=False,scientific_acceptance=False)
