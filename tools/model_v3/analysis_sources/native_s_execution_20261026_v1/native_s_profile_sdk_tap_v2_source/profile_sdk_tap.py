"""Small metadata comparison kernel; callers bind actual files and execution graph."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import time

PURPOSE='PROFILE_ONLY_NO_B_ACCEPTANCE'
SCOPE='existing_native_S_original_TRAIN_record_sampler_not_D5'
LIMITS={'max_native_records':500000,'max_history_rows':100000,'max_record_bytes':4<<20,
    'max_export_bytes':64<<20,'max_wall_seconds':180,'max_source_bytes':128<<20,'max_profile_mirror_rows':102}


def require(value,message):
    if not value: raise ValueError(message)


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def digest(value): return hashlib.sha256(encoded(value)).hexdigest()


def merged_summary(rows):
    """Same recursive last-value merge as frozen profile_lifecycle.summary_from_mirror."""
    destination={}
    def merge(target,value):
        for key,item in value.items():
            if isinstance(item,dict):
                if not isinstance(target.get(key),dict): target[key]={}
                merge(target[key],item)
            else: target[key]=deepcopy(item)
    for row in rows: merge(destination,row['row'])
    return destination


def prepare(profile,configuration,summary,mirror_rows,*,job_id,expectations):
    """Pure saved-metadata contract checks. This does not open any source/SDK."""
    require(profile['schema']=='existing_native_S_storage_profile_result_v2'
        and profile['status']=='PROFILE_CHILD_COMPLETED_PENDING_OUTER_AND_NATIVE_SDK'
        and profile['purpose']==PURPOSE and profile['observed_profile_updates']==20
        and profile['scope']==SCOPE
        and profile['production_20k_allowed'] is False and profile['scientific_acceptance'] is False
        and profile['D5_authority'] is False and profile['failure'] is None and profile['cleanup_errors']==[]
        and profile['native_SDK_verification']=='REQUIRED_INDEPENDENTLY','Only completed short20 profile metadata; no B/D5 authority')
    require(set(expectations)=={'sdk','mirror','configuration','summary'} and profile['SDK_expectations']==expectations,
        'Exact saved four-artifact expectation references required')
    require(set(configuration)=={'purpose','callback','Root_storage_binding','profile_runner_source'}
        and configuration['purpose']==PURPOSE,'Saved SDK config differs from fixed profile source schema')
    callback=configuration['callback']
    require(callback['seed']==0 and type(callback['seed']) is int and callback['precision']==profile['precision']
        and callback['scope']==SCOPE
        and callback['precision'] in ('fp32','bf16') and callback['sources']==profile['native_sources']
        and callback['code_sha']==profile['native_code_sha'] and callback['prereg_sha']==profile['prereg_sha'],
        'Profile config precision/seed/source/commit identity differs')
    require(type(job_id) is str and job_id.isdigit() and type(profile['tracker_id']) is str and profile['tracker_id'],
        'Actual job/run identity required')
    require(21<=len(mirror_rows)<=LIMITS['max_profile_mirror_rows'],'Bounded complete short-profile mirror population required')
    previous_updates=previous_samples=0
    for index,row in enumerate(mirror_rows):
        require(type(row) is dict and set(row)=={'step','commit','row'} and row['commit'] is True
            and type(row['step']) is int and row['step']==index,'Exact committed continuous mirror envelope required')
        payload=row['row']
        require(type(payload) is dict and payload and payload['log_cursor']==index and type(payload['log_cursor']) is int,
            'Native acknowledged log_cursor differs from mirror step')
        update,samples=payload['optimizer_updates'],payload['samples_consumed']
        require(type(update) is int and type(samples) is int,'Integer committed clocks required')
        if index==0:
            require(payload['event']=='VALIDATION' and payload['role']=='PRETRAIN_VAL' and payload['records']==1024
                and update==0 and samples==0,'Original initial full PRETRAIN_VAL population required')
        else:
            require(payload['event']=='TRAIN' and update in (previous_updates,previous_updates+1)
                and samples>previous_samples,'Actual native training clocks differ')
        previous_updates,previous_samples=update,samples
    require(previous_updates==20,'Mirror does not reach observed20 optimizer updates')
    expected_summary=merged_summary(mirror_rows)
    expected_summary['profile_v2']={'purpose':PURPOSE,'completed_requested_short_target':True,'optimizer_updates':20,
        'native_code_sha':profile['native_code_sha'],'D5_authority':False}
    require(encoded(summary)==encoded(expected_summary),'Saved full expected summary differs from source mirror merge')
    return {'expected_config':configuration,'expected_summary':summary,'mirror_rows':mirror_rows,
        'run_id':profile['tracker_id'],'run_name':f"nativeS_storage_PROFILE_ONLY_{profile['precision']}_{job_id}",
        'project':'mfm_model_v3_development','job_id':job_id,'expectations':expectations,
        'profile_scope':PURPOSE,'source_mirror_or_model_math_independence_not_asserted':True}


class Sink:
    def write(self,raw): return len(raw)


class Audit:
    def __init__(self,reader,context):
        self.reader,self.context=reader,context; self.config={}; self.summary={}; self.headers=[]; self.history_started=False

    def update(self,target,value):
        updates=self.reader.native_items(value.update)
        for item in (*value.remove,*value.update):
            require(not (item.key and item.nested_key),'Ambiguous native config/summary key')
            key=self.reader.canonical_native_key(item); require(key,'Empty native config/summary key')
            for previous in tuple(target):
                if previous==key or previous.startswith(key+'/'): target.pop(previous)
        target.update(updates)

    @staticmethod
    def public(values):
        result={}
        for key,value in values.items():
            if key.startswith('_'):
                require(key in ('_step','_runtime','_timestamp','_wandb') or key.startswith('_wandb/') or key.startswith('_wandb~1'),
                    'Unexpected private native config/summary key')
            else: result[key]=value
        return result

    def exact_fields(self,actual,expected,kind):
        expected=self.reader.flatten(expected); actual=self.public(actual)
        require(set(actual)==set(expected),'Missing or extra native '+kind+' field')
        for key,value in expected.items(): self.reader.typed_like(actual[key],value)

    def observe(self,record):
        kind=record.WhichOneof('record_type')
        if kind=='run':
            self.headers.append({'run_id':record.run.run_id,'display_name':record.run.display_name,'project':record.run.project})
            self.update(self.config,record.run.config)
            if self.history_started: self.exact_fields(self.config,self.context['expected_config'],'config')
        elif kind=='config':
            self.update(self.config,record.config)
            if self.history_started: self.exact_fields(self.config,self.context['expected_config'],'config')
        elif kind=='summary': self.update(self.summary,record.summary)
        elif kind=='history':
            self.exact_fields(self.config,self.context['expected_config'],'config'); self.history_started=True

    def finish(self):
        self.exact_fields(self.config,self.context['expected_config'],'config')
        require(self.headers==[{'run_id':self.context['run_id'],'display_name':self.context['run_name'],'project':self.context['project']}],
            'Native RunRecord runID/name/project differs')
        self.exact_fields(self.summary,self.context['expected_summary'],'summary')
        require(type(self.summary.get('_step')) is int and self.summary['_step']==self.context['mirror_rows'][-1]['step'],
            'Native final summary explicit step differs')


def compare(reader,data,record_class,context,*,deadline=None,**limits):
    """Return actual v7 history verdict + exact full-config/summary tap, no rows."""
    started=time.monotonic()
    deadline=started+LIMITS['max_wall_seconds'] if deadline is None else deadline
    require(type(deadline) in (int,float) and math.isfinite(deadline) and started<deadline<=started+LIMITS['max_wall_seconds'],
        'Deadline may only tighten the inclusive180-second verification bound')
    allowed=('max_native_records','max_history_rows','max_record_bytes','max_export_bytes')
    require(set(limits)<=set(allowed) and all(type(v) is int and 0<v<=LIMITS[k] for k,v in limits.items()),
        'Limits may only tighten the frozen bounds')
    actual_limits={key:limits.get(key,LIMITS[key]) for key in allowed}; audit=Audit(reader,context)
    class TappedRecord:
        def __init__(self): self.record=record_class()
        def ParseFromString(self,raw): self.record.ParseFromString(raw); audit.observe(self.record)
        def __getattr__(self,key): return getattr(self.record,key)
    expected=[{'step':row['step'],'row':reader.flatten(row['row'])} for row in context['mirror_rows']]
    history=reader.verify_stream(data,TappedRecord,Sink(),expected_run_id=context['run_id'],expected_exit=0,
        expected_rows=len(expected),mirror_factory=lambda _:iter(expected),deadline=deadline,**actual_limits)
    audit.finish()
    require(history['native_closed'] and history['clean_eof'] and history['sdk_run_ids']==[context['run_id']]
        and history['sdk_exit_codes']==[0] and history['history_rows']==len(expected)
        and history['first_explicit_step']==0 and history['last_explicit_step']==len(expected)-1,
        'Full native committed-history population did not close')
    tap={'schema':'native_S_config_summary_verification_v2','status':'VERIFIED_ALL_SCIENTIFIC_CONFIG_AND_SUMMARY',
        'sdk':context['expectations']['sdk'],'expectations':context['expectations'],'run_id':context['run_id'],
        'missing':[],'extra_scientific':[],'different':[],'run_name_and_project_exact':True,
        'configuration_exact_before_every_history_and_afterwards':True,'summary_exact':True,
        'scientific_key_encoding':reader.KEY_ENCODING,
        'expected_config_sha256':digest(context['expected_config']),'expected_summary_sha256':digest(context['expected_summary']),
        'expected_mirror_sha256':digest(context['mirror_rows']),'history_rows':len(expected),
        'scientific_acceptance':False,'production_20k_allowed':False,'D5_authority':False,
        'file_open_raw_SHA_source_bindings_and_actual_parent_closure_must_be_verified_by_caller':True}
    return {'raw_history_verification':history,'raw_config_summary_verification':tap,
        'is_full_execution_or_storage_projection_certificate':False,'SDK_or_metric_values_exported':False}
