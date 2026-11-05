#!/usr/bin/env python3
"""Prepare one Native endpoint's full frozen panel; no submission or registry writes."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import re
import socket
import stat
from native_admission import (B,N,LIMIT,NATIVE_PHASE,PANEL_SHA,bare,binding,read_ref,load,need,
    bridge_admission,native_admission,storage_admission,independent_root,REGISTRY,whole_output_bytes)
HERE=Path(__file__).absolute().parent

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(value,sort_keys=True,allow_nan=False,indent=2)+'\n').encode();need(len(raw)<=16*1024**2,'Bounded metadata required')
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return binding(path,16*1024**2)
def native_refs(inputs):
    if inputs.get('native') is not None:return inputs['native']
    draft=read_ref(inputs['native_binding']);p=draft['checkpoint'];refs=draft['refs'];payload=p['payload']
    return {'member_result':bare(refs['Native_member_result']),'completion':bare(refs['Native_COMPLETE']),
        'payload':{'path':payload['path'],'bytes':payload['bytes'],'sha256':payload.get('sha256',payload.get('sha256_from_closed_metadata'))},
        'segment_closure':bare(refs['Native_segment_closure'])}
def cpu_boundary(expected_node):
    require_node=socket.gethostname().split('.')[0]
    need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdigit()
        and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16
        and re.fullmatch(r'compute-0-(?:2|[89]|1[0-9])',expected_node)
        and require_node==os.environ.get('SLURMD_NODENAME')==expected_node
        and os.environ.get('CUDA_VISIBLE_DEVICES')=='',
        'Preparation hashes real payload/imports project: actual >=16CPU CUDA-hidden allowed CPU Slurm required')
    need(re.search(r'/job_'+re.escape(os.environ['SLURM_JOB_ID'])+r'(?:/|$)',Path('/proc/self/cgroup').read_text()),
         'Actual preparation job kernel cgroup differs')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path);p.add_argument('--inputs-sha256');p.add_argument('--expected-node')
    a=p.parse_args()
    need(a.inputs is not None and a.inputs_sha256 and a.expected_node,'Bound CPU preparation inputs and expected-node required')
    cpu_boundary(a.expected_node)
    inputs=read_ref({**binding(a.inputs),'sha256':a.inputs_sha256},16*1024**2)
    need(inputs['schema']=='model_v3_native_S_dev_panel_prepare_inputs_v1','Native-only explicit inputs required')
    from Root_control import source_map
    import panel_auto_resources as auto
    started_sources=source_map();auto.verify_publication(inputs['method_publication'])
    need(inputs['operations_source_pins']==auto.verify_sources(),'Exact new20k source input required')
    controls=load(HERE/'native_admission.py','native20k_unchanged_inline_controls').metadata_selfcheck()
    bridge=bridge_admission(inputs['bridge']);native=native_admission(native_refs(inputs));root=Path(bridge['repository_root'])
    need((native['seed'],native['precision'],native['optimizer_updates'])==(0,'fp32',20000),'Only real closed20k endpoint in this method')
    base=independent_root(inputs['output_base'],root)
    from Root_control import BASE
    need(base==BASE and base.is_dir() and not base.is_symlink(),'Explicit pre-reserved fresh20k family required')
    for fd in (1,2):
        target=Path(os.readlink('/proc/self/fd/'+str(fd)))
        need(target.is_absolute() and target.resolve()==base/('CPU_slurm_'+os.environ['SLURM_JOB_ID']+'.out'),
            'CPU job stdio must remain in the same whole panel family')
    info=(base/'control').lstat();need(stat.S_ISDIR(info.st_mode) and info.st_uid==1278,
        'Root control must remain an owned ordinary directory')
    parent=Path('/proc')/str(os.getppid())
    parent_argv=[part.decode() for part in (parent/'cmdline').read_bytes().split(b'\0') if part]
    cpu_supervisor=B/'runs/model_v3_20261025/run_cpu_supervised_v3.py'
    need(parent_argv.count(str(cpu_supervisor))==1,'Original CPU supervisor must be the actual direct parent')
    need('--' in parent_argv and parent_argv[parent_argv.index('--')+1:]==list(sys.orig_argv),
        'Actual supervised CPU child argv differs')
    for flag,expected in (('--output-root',str(base/'cpu_prepare')),('--record',str(base/'control'/('CPU_supervisor_'+os.environ['SLURM_JOB_ID']+'.json'))),
        ('--wall-seconds','900'),('--rss-limit-bytes',str(12<<30)),('--output-budget-bytes',str(2<<30))):
        need(parent_argv.count(flag)==1 and parent_argv[parent_argv.index(flag)+1]==expected,
            'Original exact CPU prep budgets/paths required')
    current_job=os.environ['SLURM_JOB_ID']
    allowed_top={'control','CPU_slurm_'+current_job+'.out'}
    need({path.name for path in base.iterdir()}<=allowed_top,'No old panel/cache/guard output allowed')
    allowed_control={'principal.json','Root_hold_actual_v1.json','CPU_PREPARE_INPUTS.json',
        'CPU_supervisor_'+current_job+'.json','CPU_supervisor_'+current_job+'.journal.jsonl',
        'CPU_supervisor_'+current_job+'.storage.json'}
    need({path.name for path in (base/'control').iterdir()}<=allowed_control,
        'Only this Root reservation and current CPU supervision metadata may precede preparation')
    for path in (base/'control').iterdir():
        info=path.lstat();need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_nlink==1,
            'Pre-existing control must be owned ordinary metadata only')
    preparation=base/'cpu_prepare';need(not preparation.exists() and not preparation.is_symlink(),'Fresh guarded CPU output required')
    preparation.mkdir(mode=0o700)
    need(binding(base/'control/CPU_PREPARE_INPUTS.json')['sha256']==a.inputs_sha256,'Exact pre-reserved Root inputs required')
    storage_admission(inputs['storage'],base)
    need(inputs['node']=='compute-0-21' and isinstance(inputs['gpu_uuid'],str) and inputs['gpu_uuid'].startswith('GPU-'),
         'Original node21 full UUID admission interface required')
    # Existing live registry is NOT frozen; only this independently reserved entry/principal is bound.
    need(inputs['storage']['registry_path']==str(REGISTRY) and inputs['storage']['reservation_id'],'Explicit independent existing-Root hold descriptor required')
    storage={'status':'NOT_RESOURCE_ADMITTED','actual_entry_and_quota_required_after_preparation':True}
    old=read_ref(inputs['original544_spec']);need(old['schema']=='model_v3_primary512_dev9_external_launch_v2'
        and old['preregistration_sha']==PANEL_SHA,'Frozen original544 panel authority required')
    sys.path.insert(0,str(root/'current'))
    prepare=load(root/'tools/model_v3/prepare_dev_evaluation.py','native_panel_original_preparer')
    runner=load(root/'tools/model_v3/evaluate_dev_panel.py','native_panel_original_evaluator')
    relative=sorted(Path(path).relative_to(root).as_posix() for path in bridge['source_inventory']
                    if Path(path).is_relative_to(root) and (path.endswith('.py') or path==str(root/'configs/dev_panel_v1.json')))
    need('current/phychem_mfm/phase1/v3_native_checkpoint_bridge.py' in relative,'Native reader source must be request-bound')
    output=base/'evaluation';cache=output/'h0_cache'
    args=dict(panel=root/'configs/dev_panel_v1.json',training_store=old['selected_store']['path'],
        model_configuration=native['configuration']['path'],checkpoint=native['checkpoint']['path'],
        code_sha=bridge['evaluation_code_sha'],preregistration_sha=PANEL_SHA,data_version=old['data_version'],
        pretraining_seed=native['seed'],output_root=output,cache_root=cache,run_id=inputs['run_id'],source_files=relative,
        state_key='model',reference_kind='primary',historical_reference=None,training_completion=native['completion']['path'],
        maximum_wall_seconds=3400,repository_root=root)
    # Actual CPU Slurm only: project/Torch import and full opaque payload hashing; no model or target decode.
    old_request=read_ref(old['request']);args['h0_packing']=old_request['h0_packing']
    need(binding(args['panel'])['sha256']==old_request['panel']['sha256'],'Original frozen panel configuration differs')
    initial=prepare.make_request(**args)
    initial_ref=write(preparation/'request.metadata_planning_only.json',initial)
    _,_,store,views,tasks,config=runner.load_plan(initial_ref['path'],initial_ref['sha256'],allow_unbound_packing=True)
    need(len(tasks)==9 and (config['backbone']['dim'],config['backbone']['layers'],config['backbone']['heads'])==(512,6,8),
         'Full nine tasks and original512x6x8 model required')
    from phychem_mfm.phase1.v3_h0_packing import packing_plans_for_views
    plans=packing_plans_for_views(store,views,initial['h0_packing'])
    original_plans=read_ref(old['packing_plans'])
    need(plans==original_plans,'Original selected TRAIN memberships/order/budget/packing policy differs')
    plan_ref=write(preparation/'packing_plans.json',plans)
    request=prepare.make_request(**args,h0_packing_plan_sha256={d:r['plan_sha256'] for d,r in plans.items()})
    request_ref=write(preparation/'request.bound.json',request)
    runner.load_plan(request_ref['path'],request_ref['sha256'])
    spec={**old,'schema':'model_v3_native_S_dev9_external_launch_v1','status':'PREPARED_NOT_RESOURCE_ADMITTED',
        'repository_root':str(root),'code_sha':bridge['evaluation_code_sha'],'public_code_sha':bridge['public_code_sha'],
        'bridge_tree_sha':bridge['tree_sha'],'bridge_validation':inputs['bridge'],'bridge_pins':bridge['tested_sources'],
        'native_authority':native_refs(inputs),'native_endpoint':native,'producer_code_sha':native['producer_code_sha'],
        'checkpoint_scope':'Native_S_closed20k_endpoint_descriptive_dev_panel_not_B_acceptance',
        'source_checkpoint':native['checkpoint'],'original_configuration':native['configuration'],
        'checkpoint_complete':native['completion'],'storage':inputs['storage'],'storage_snapshot':storage,
        'output_base':str(base),'node':inputs['node'],'gpu_uuid':inputs['gpu_uuid'],
        'external_guard':binding(HERE/'run_native_panel_guard.py'),'external_preparer':binding(__file__),
        'native_admission_implementation':binding(HERE/'native_admission.py'),
        'protected_dependencies':binding(HERE/'dependencies.json'),'sbatch_template':binding(HERE/'native_panel_GPU_v1.sbatch'),
        'request':request_ref,'packing_plans':plan_ref,
        'request_argv':[old['python_entry'],'-u','-B',str(root/'tools/model_v3/evaluate_dev_panel.py'),
                        '--request',request_ref['path'],'--request-sha256',request_ref['sha256']],
        'Root_resource_admission_required':True,'Root_resource_admission':None,
        'Root_resource_guard_source':inputs['resource_guard_source'],
        'supervisor_source':inputs['supervisor_source'],'identity_dependencies':inputs['identity_dependencies'],
        'maximum_child_wall_seconds':3500,'total_allocation_target_seconds':3600,
        'maximum_process_group_rss_bytes':28*1024**3,'maximum_output_and_cache_bytes':LIMIT,
        'requested_memory_bytes':None,'software_memory_budget_bytes':32*1024**3,'Slurm_memory_mode':'automatic_default',
         'method_publication':inputs['method_publication'],'operations_source_pins':inputs['operations_source_pins'],
         'formal_pretraining_complete':False,'architecture_selection_claimed':False}
    for obsolete in ('export_ready','export_terminal_admission','export_code_sha','export_job_id','export_admission_implementation'):
        spec.pop(obsolete,None)
    # Recheck complete tested/current tree after project planning and payload hashes.
    bridge_admission(inputs['bridge'])
    sb=(HERE/'native_panel_GPU_v1.sbatch').read_text()
    sb=sb.replace('#SBATCH --time=01:00:00','#SBATCH --time=01:00:00\n#SBATCH --output='+str(base/'slurm-%j.out')+'\n#SBATCH --error='+str(base/'slurm-%j.out'))
    target=preparation/'native_panel_GPU_v1.sbatch'
    with target.open('xb') as stream:stream.write(sb.encode());stream.flush();os.fsync(stream.fileno())
    spec['prepared_sbatch']=binding(target)
    ref=write(preparation/'launch_spec.json',spec)
    finished_sources=source_map();need(started_sources==finished_sources,'Preparation source-before/after changed')
    write(preparation/'CPU_PREPARATION.json',{'status':'CPU_PREPARED_FULL9_NATIVE20K_SOURCE_AND_PAYLOAD_CHECKS_COMPLETED',
        'actual_job_id':os.environ['SLURM_JOB_ID'],'actual_argv':list(sys.orig_argv),'actual_supervisor_argv':parent_argv,'inputs':binding(a.inputs),
        'prepared_spec':ref,'source_before':started_sources,'source_after':finished_sources,'inline_metadata_controls':controls,
        'Root_login_payload_read':False,'payload_SHA_checked_by_allocated_CPU':True,'target_payload_or_model_forward_run':False})
    print(json.dumps({'status':'PREPARED_NOT_RESOURCE_ADMITTED','spec':ref,'output_base':str(base),'no_submission':True}))
    return 0
if __name__=='__main__':raise SystemExit(main())