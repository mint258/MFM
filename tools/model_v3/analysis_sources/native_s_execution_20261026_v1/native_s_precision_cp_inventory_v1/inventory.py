"""Bounded CPU-only safe-checkpoint inventory; no model, inference or training.

Outputs contain tensor metadata, never tensor values or member/target lists.
This child does not claim its own outer Slurm terminal or authorize B training.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import zipfile

CODE='3d9b1cc0c580dacc9398a5570b0c2fff3e257618'
PUBLIC='ce7cbf5776ff546cd47538b120c8f884e2e5867d'
SCOPE='existing_native_S_original_TRAIN_record_sampler_not_D5'
MODEL=dict(dim=512,layers=6,heads=8,ff_mult=2)
PLAN=dict(input_scope=SCOPE,updates=20000,sample_budget=10240000,
          validation_updates=list(range(0,20001,500)),checkpoint_updates=[10000,20000],warmup_samples=0)
MAX_PAYLOAD=512<<20
MAX_REPORT=2<<20
MAX_TENSORS=4096
MAX_CHECKPOINTS=216
RUNTIME=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_native_s_runtime_v1')
GROWTH_SOURCES=('current/phychem_mfm/phase1/v3_native_s_precision.py',
    'current/phychem_mfm/phase1/v3_training.py','current/phychem_mfm/phase1/full_corpus_loader.py',
    'current/phychem_mfm/model/v3_performance.py')


def require(value,message):
    if not value: raise ValueError(message)


def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def same_json(left,right):
    # The safe payload retains tuples; its original JSON config uses arrays.
    return encoded(left)==encoded(right)


def unique(pairs):
    value={}
    for key,item in pairs:
        require(key not in value,'Duplicate JSON key')
        value[key]=item
    return value


def signature(value):
    return tuple(getattr(value,key) for key in ('st_dev','st_ino','st_uid','st_mode','st_nlink','st_size','st_mtime_ns'))


def bound(path,maximum=MAX_REPORT):
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts,'Absolute bounded input path required')
    for ancestor in (path,*path.parents):
        require(not ancestor.is_symlink(),'Input ancestry symlink rejected')
    before=path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1
            and 0<before.st_size<=maximum,'Input owner/type/size/link count differs')
    digest=hashlib.sha256()
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as stream:
        require(signature(os.fstat(stream.fileno()))==signature(before),'Input changed before hashing')
        for block in iter(lambda:stream.read(1<<20),b''): digest.update(block)
        require(signature(os.fstat(stream.fileno()))==signature(before),'Input changed during hashing')
    require(signature(path.lstat())==signature(before),'Input path changed during hashing')
    return dict(path=str(path),bytes=before.st_size,sha256=digest.hexdigest())


def check_ref(ref,maximum=MAX_REPORT):
    require(type(ref) is dict and set(ref)=={'path','bytes','sha256'},'Exact raw reference required')
    require(bound(ref['path'],maximum)==ref,'Raw input reference differs')
    return ref


def read(ref):
    check_ref(ref)
    raw=Path(ref['path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest()==ref['sha256'],'JSON changed before parsing')
    return json.loads(raw,object_pairs_hook=unique,
        parse_constant=lambda token:(_ for _ in ()).throw(ValueError('Nonfinite JSON token')))


def write(path,value):
    raw=encoded(value); require(len(raw)<=MAX_REPORT,'Inventory output exceeds2MiB')
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return bound(path)


def tensor_row(value,torch):
    require(isinstance(value,torch.Tensor) and value.layout==torch.strided and value.device.type=='cpu',
            'Only actual dense CPU tensors admitted')
    require(value.dtype in (torch.float32,torch.float64,torch.int64,torch.int32,torch.uint8,torch.bool),
            'Unknown checkpoint tensor dtype')
    require(value.dim()<=8 and value.numel()<=100000000,'Tensor dimension/numel bound exceeded')
    return dict(shape=list(value.shape),dtype=str(value.dtype),numel=value.numel(),
                logical_bytes=value.numel()*value.element_size(),storage_bytes=value.untyped_storage().nbytes())


def metadata_summary(value,torch,*,depth=0,counters=None):
    """Bound metadata traversal without emitting any scalar value or ID list."""
    counters=Counter() if counters is None else counters
    require(depth<=32,'Checkpoint metadata nesting exceeds32')
    counters['nodes']+=1; require(counters['nodes']<=200000,'Checkpoint metadata node cap exceeded')
    if isinstance(value,torch.Tensor):
        counters['tensors']+=1; counters['tensor_bytes']+=tensor_row(value,torch)['logical_bytes']
    elif type(value) is dict:
        for key,item in value.items():
            require(type(key) in (str,int),'Unknown metadata key type')
            if type(key) is str:
                require(len(key.encode())<=2048,'Unbounded metadata key')
                counters['string_bytes']+=len(key.encode())
            metadata_summary(item,torch,depth=depth+1,counters=counters)
    elif type(value) in (tuple,list):
        require(len(value)<=10000,'Unbounded metadata list')
        for item in value: metadata_summary(item,torch,depth=depth+1,counters=counters)
    elif type(value) is str:
        require(len(value.encode())<=16384,'Unbounded metadata string')
        counters['string_bytes']+=len(value.encode())
    elif type(value) is float:
        require(math.isfinite(value),'Nonfinite metadata scalar')
    elif type(value) is int:
        require(abs(value)<1<<128,'Unbounded integer metadata')
    else:
        require(value is None or type(value) is bool,'Unknown metadata value type')
    return dict(counters)


def inspect(payload,torch,*,max_complete_checkpoints=MAX_CHECKPOINTS):
    require(type(payload) is dict and set(payload)=={'schema','bindings','runtime','model','optimizer','sampler','clock','rng','extra_state'}
        and payload['schema']=='model_v3_training_checkpoint_v1','Unknown safe checkpoint schema')
    model=payload['model']; require(type(model) is dict and 0<len(model)<=MAX_TENSORS,'Bounded model-state mapping required')
    model_rows={name:tensor_row(value,torch) for name,value in model.items()}
    require(all(type(name) is str and len(name.encode())<=1024 for name in model),'Model name bound differs')
    # State dict may include buffers. Including them yields an upper bound on
    # all possible parameter moments without guessing unnamed/uninitialized IDs.
    numel=sum(row['numel'] for row in model_rows.values())
    require(all(row['dtype']=='torch.float32' for row in model_rows.values()),'Model state is not entirely fp32')
    optimizer=payload['optimizer']
    require(type(optimizer) is dict and set(optimizer)=={'state','param_groups'},'Unknown optimizer schema')
    groups=optimizer['param_groups']; states=optimizer['state']
    require(type(groups) is list and len(groups)==1 and type(states) is dict,'One ordinary AdamW group required')
    group=groups[0]; ids=group.get('params')
    require(set(group)<=set(('params','lr','betas','eps','weight_decay','amsgrad','foreach','maximize',
        'capturable','differentiable','fused','decoupled_weight_decay','initial_lr')),
        'Unknown optimizer group keys')
    metadata_summary({key:value for key,value in group.items() if key!='params'},torch)
    require(not any(isinstance(value,torch.Tensor) for key,value in group.items() if key!='params'),
        'Unknown tensor-valued optimizer group option')
    require(type(ids) is list and ids and len(ids)<=len(model_rows) and len(ids)==len(set(ids))
        and all(type(key) is int and key>=0 for key in ids),'Optimizer parameter IDs differ')
    require(set(states)<=set(ids),'Optimizer state has unknown parameter ID')
    require(group.get('amsgrad') is False and group.get('fused') in (None,False)
        and group.get('differentiable') is False and group.get('capturable') is False
        and group.get('maximize') is False,
        'Unknown AdamW variant; no guessed future bound')
    state_rows={}; initialized_numel=0
    for key,state in states.items():
        require(type(state) is dict and set(state)=={'step','exp_avg','exp_avg_sq'},'Unknown Adam state keys')
        rows={name:tensor_row(value,torch) for name,value in state.items()}
        require(rows['step']['numel']==1 and rows['step']['dtype'] in ('torch.float32','torch.float64'),
                'Unknown Adam step tensor')
        require(rows['exp_avg']['shape']==rows['exp_avg_sq']['shape']
            and rows['exp_avg']['dtype']==rows['exp_avg_sq']['dtype']=='torch.float32','Unknown Adam moments')
        initialized_numel+=rows['exp_avg']['numel']; state_rows[str(key)]=rows
    require(initialized_numel<=numel,'Initialized Adam population exceeds model-state bound')
    sampler=payload['sampler']
    require(type(sampler) is dict and set(sampler)=={'schema_version','contract_sha256','epoch','block_position',
        'item_offset','batches_consumed','samples_consumed','content_sha256'},'Unknown provider/sampler state')
    clock=payload['clock']
    require(type(clock) is dict and set(clock)=={'schema','sample_budget','milestones','samples_consumed',
        'optimizer_updates','saved_milestones'} and clock['schema']=='model_v3_consumed_sample_clock_v1'
        and clock['sample_budget']==PLAN['sample_budget'] and not clock['milestones'] and not clock['saved_milestones'],
        'Unknown native consumed-clock state')
    require(clock['samples_consumed']==sampler['samples_consumed'],'Committed sampler/clock differ')
    extra=payload['extra_state']; require(type(extra) is dict and set(extra)=={'contract','scheduler','points',
        'saved_updates','log_cursor','input_chain','tracker','model_training','dtype_observations'},'Unknown native extra state')
    require(same_json(extra['contract']['plan'],PLAN),'Frozen20000-update plan differs')
    require(type(extra['points']) is dict and set(extra['points'])<=set(map(str,PLAN['validation_updates']))
        and type(extra['saved_updates']) is list and len(extra['saved_updates'])<=max_complete_checkpoints,
        'Validation/saved-update collection is unbounded')
    for point in extra['points'].values():
        require(len(encoded(point))<=16384,'Curve point exceeds frozen16KiB scalar envelope')
        require(type(point) is dict and set(point)=={'metrics','population','input_population_sha256',
            'validation_noise_seed','validation_epoch','role'},'Unknown curve-point schema')
    metadata=metadata_summary({key:payload[key] for key in ('bindings','runtime','sampler','clock','rng','extra_state')},torch)
    require(metadata.get('string_bytes',0)<1<<20 and metadata.get('nodes',0)<20000,
            'Actual non-model metadata exceeds source-derived envelope')
    # A deliberately loose additive bound: all future moments counted again,
    # even when already materialized. Adam state count cannot exceed the model
    # state count. 4096 bytes per new tensor/container plus a4MiB structural
    # margin exceeds the pinned2.10 uncompressed ZIP/pickle record envelope.
    raw_moments=2*4*numel
    raw_steps=8*len(ids)
    optimizer_overhead=4*4096*len(model_rows)+(4<<20)
    optimizer_growth=raw_moments+raw_steps+optimizer_overhead
    #41 scalar points each<=16KiB, bounded saved-update list, fixed-size RNG,
    #scalar clock/cursor and unchanged contract; caches/prefetch are not saved.
    provider_growth=(4<<20)+41*16384+max_complete_checkpoints*256
    return dict(model=model_rows,optimizer_state=state_rows,
        optimizer_group_keys=sorted(group),parameter_ids=len(ids),initialized_parameter_states=len(states),
        uninitialized_parameter_states=len(ids)-len(states),model_state_numel=numel,
        initialized_moment_numel=initialized_numel,metadata_summary=metadata,
        raw_moment_upper_bytes=raw_moments,raw_step_upper_bytes=raw_steps,
        optimizer_structural_reserve_bytes=optimizer_overhead,
        provider_future_state_bound_bytes=provider_growth,
        optimizer_future_state_bound_bytes=optimizer_growth,unknown_assumptions=[])


def profile_context(inputs):
    require(inputs['schema']=='native_S_evidence_inputs_v2' and inputs['role']=='future_state',
            'Exact future_state input manifest required')
    require(set(inputs['artifacts'])=={'profile_result','checkpoint'},'Exact two actual artifacts required')
    profile=read(inputs['artifacts']['profile_result']); context=inputs['context']
    require(profile['schema']=='existing_native_S_storage_profile_result_v2' and profile['scope']==SCOPE
        and profile['native_code_sha']==CODE and profile['prereg_sha']==PUBLIC and profile['D5_authority'] is False
        and profile['observed_profile_updates']==20 and profile['failure'] is None and profile['cleanup_errors']==[]
        and profile['checkpoint_ref']==inputs['artifacts']['checkpoint'],'Actual successful native20 profile required')
    require(context['model']==MODEL and context['plan']==PLAN
        and context['checkpoint_cap_bytes']==384<<20 and context['max_complete_checkpoints']==MAX_CHECKPOINTS,
        'Frozen native model/finite future plan/cap differs')
    require(set(context['growth_source_refs'])==set(GROWTH_SOURCES),'Complete frozen growth source inventory required')
    for name,ref in context['growth_source_refs'].items():
        check_ref(ref)
        require(Path(ref['path'])==RUNTIME/name and ref['sha256']==profile['native_sources'][name],
                'Growth proof source differs from actually profiled source')
    closure=read(context['Root_profile_closure']); terminal=read(context['actual_terminal'])
    require(closure['status']=='PROFILE_OUTER_C0_SCIENCE_HOLD' and closure['actual_terminal']==context['actual_terminal']
        and terminal['status']=='COMPLETED' and terminal['exit_code']==0 and terminal['exit_code_raw']=='0:0'
        and terminal['profile_result']==inputs['artifacts']['profile_result'],'Actual matching profile parent C0 required')
    raw=read(terminal['raw_sacct']); job=str(terminal['job_id'])
    require(raw['returncode']==0 and raw['argv']==['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,State,ExitCode']
        and raw['stdout'].strip()==job+'|COMPLETED|0:0','Actual raw profile terminal differs')
    config=read(context['profile_configuration']); marker=read(context['checkpoint_complete'])
    require(marker['schema']=='model_v3_training_checkpoint_v1' and marker['optimizer_updates']==20
        and marker['payload_bytes']==inputs['artifacts']['checkpoint']['bytes']
        and marker['payload_sha256']==inputs['artifacts']['checkpoint']['sha256'],'Raw COMPLETE binding differs')
    return profile,context,config,marker


def run(input_path,output):
    require(os.environ.get('SLURM_JOB_ID') and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16,
            'Actual owned>=16CPU readiness allocation required')
    require(not os.environ.get('CUDA_VISIBLE_DEVICES'),'CPU-only hidden-CUDA inventory required')
    output=Path(output).absolute(); require(not output.exists(),'Fresh outside-Git inventory output required')
    require(not any(part.startswith('MFM_model_v3') for part in output.parts),'Inventory output cannot be a Git worktree')
    inputs_ref=bound(Path(input_path).absolute()); inputs=read(inputs_ref)
    profile,context,configuration,marker=profile_context(inputs)
    checkpoint=check_ref(inputs['artifacts']['checkpoint'],MAX_PAYLOAD)
    require(Path(context['checkpoint_complete']['path']).parent==Path(checkpoint['path']).parent,
            'COMPLETE is not checkpoint sibling')
    started=time.monotonic()
    import torch
    require(str(torch.__version__).startswith('2.10.') and not torch.cuda.is_initialized(),
            'Pinned Torch2.10 CPU-only safe loader required')
    torch.set_num_threads(8)
    with zipfile.ZipFile(checkpoint['path']) as archive:
        entries=archive.infolist()
        require(0<len(entries)<=16384 and all(row.compress_type==zipfile.ZIP_STORED
            and len(row.filename.encode())<=256 and row.file_size<=MAX_PAYLOAD for row in entries)
            and sum(row.file_size for row in entries)<=MAX_PAYLOAD,
            'Unknown Torch ZIP framing/compression/expanded size')
    before=signature(Path(checkpoint['path']).lstat())
    with Path(checkpoint['path']).open('rb') as stream:
        require(signature(os.fstat(stream.fileno()))==before,'Checkpoint changed before safe load')
        payload=torch.load(stream,map_location='cpu',weights_only=True)
        require(signature(os.fstat(stream.fileno()))==before,'Checkpoint changed during safe load')
    require(bound(checkpoint['path'],MAX_PAYLOAD)==checkpoint,'Checkpoint changed after safe load')
    require(payload['bindings']==marker['bindings'] and payload['clock']['optimizer_updates']==marker['optimizer_updates']
        and payload['clock']['samples_consumed']==marker['samples_consumed']
        and same_json(payload['extra_state']['contract'],configuration['contract']), 'Actual safe payload/header/config differ')
    inventory=inspect(payload,torch,max_complete_checkpoints=context['max_complete_checkpoints'])
    require(inventory['model_state_numel']>=profile['actual_parameter_count']==22352859,
            'Actual fixed model population differs')
    output.mkdir(mode=0o700)
    shape=write(output/'shape_report.json',dict(schema='native_S_actual_safe_checkpoint_shape_v2',
        checkpoint=checkpoint,profile_result=inputs['artifacts']['profile_result'],safe_weights_only_load=True,
        native_sources=profile['native_sources'],model=MODEL,inventory=inventory,
        tensor_values_exported=False,training_performed=False,source=bound(Path(__file__).absolute()),
        inputs=inputs_ref,torch=str(torch.__version__),cuda_initialized=torch.cuda.is_initialized()))
    total=checkpoint['bytes']+inventory['provider_future_state_bound_bytes']+inventory['optimizer_future_state_bound_bytes']
    admissible=total<=context['checkpoint_cap_bytes']
    calculation=write(output/'future_bound.json',dict(schema='native_S_frozen_state_growth_bound_v2',
        raw_shape_report=shape,plan=PLAN,provider_future_state_bound_bytes=inventory['provider_future_state_bound_bytes'],
        optimizer_future_state_bound_bytes=inventory['optimizer_future_state_bound_bytes'],
        original_checkpoint_bytes=checkpoint['bytes'],future_checkpoint_bound_bytes=total,
        checkpoint_cap_bytes=context['checkpoint_cap_bytes'],fits_finite_checkpoint_cap=admissible,
        maximum_complete_checkpoints=context['max_complete_checkpoints'],unknown_assumptions=inventory['unknown_assumptions'],
        derivation='all-model-state fp32 moments added again + all Adam steps + bounded serialization reserve; '
            '41 scalar validation points + finite saved-update list + fixed scalar sampler/RNG; no future model training',
        source=bound(Path(__file__).absolute()),inputs=inputs_ref,actual_outer_C0_claimed=False,
        B_acceptance=False,D5_authority=False))
    del payload
    write(output/'RESULT.json',dict(schema='native_S_CPU_checkpoint_inventory_result_v1',
        status='CHILD_AUDIT_COMPLETE_PENDING_ACTUAL_OUTER_C0' if admissible else 'FINITE_CAP_EXCEEDED',
        shape_report=shape,future_bound_calculation=calculation,inputs=inputs_ref,
        elapsed_seconds=time.monotonic()-started,actual_job_id=os.environ['SLURM_JOB_ID'],
        model_values_exported=False,scientific_acceptance=False))
    require(admissible,'Conservative future checkpoint exceeds original384MiB cap; original remains unchanged')
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); originally_existing=args.output.exists()
    try: return run(args.inputs,args.output)
    except BaseException as error:
        output=args.output.absolute()
        if not originally_existing and not any(part.startswith('MFM_model_v3') for part in output.parts) and output.parent.is_dir():
            if not output.exists(): output.mkdir(mode=0o700)
            if output.is_dir() and not output.is_symlink() and not (output/'FAILED.json').exists():
                write(output/'FAILED.json',dict(schema='native_S_CPU_checkpoint_inventory_failure_v1',
                    status='HOLD_UNKNOWN_OR_INVALID_STATE',failure=dict(type=type(error).__name__,message=str(error)),
                    source=bound(Path(__file__).absolute()),actual_outer_C0_claimed=False,
                    unknown_state_admitted=False,B_acceptance=False))
        raise


if __name__=='__main__': raise SystemExit(main())
