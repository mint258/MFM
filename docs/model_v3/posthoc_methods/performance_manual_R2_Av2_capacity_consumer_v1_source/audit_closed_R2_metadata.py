"""CPU-only existing CLOSED-R2 consumer audit; never CUDA selection or training."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import sys

BASE=Path('/share/home/zixiao/descriptor_analysis')
CODE=BASE/'MFM_model_v3_A_acceptance_v2_candidate_v1'
HERE=Path(__file__).resolve().parent
FAMILY=BASE/'runs/model_v3_20261026/performance_manual_R2_Av2_v1'

def need(ok,message):
    if not ok:raise ValueError(message)

def digest(path):
    path=Path(path)
    need(path.is_file() and not path.is_symlink() and path.resolve()==path.absolute(),
         'Ordinary bounded source/metadata path required')
    before=path.stat();need(before.st_uid==os.getuid() and before.st_nlink==1 and before.st_size<=2*1024**2,
        'Owned source/metadata exceeds bound')
    raw=path.read_bytes();after=path.stat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Source/metadata changed')
    return {'path':str(path.absolute()),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def read_json(path):
    return json.loads(Path(path).read_bytes())

def verify_package(expected_sha):
    pin=HERE/'source_pins.json';need(digest(pin)['sha256']==expected_sha,'Exact package pin differs')
    pins=read_json(pin)
    need(pins['schema']=='model_v3_current_Av2_R2_capacity_consumer_sources_v1'
         and len(pins['files'])==4 and {Path(r['path']).name for r in pins['files']}==
         {'bind_closed_R2_metadata.py','audit_closed_R2_metadata.py','dependencies.json','README.md'},'Exact package scope differs')
    for ref in pins['files']:need(Path(ref['path']).parent==HERE and digest(ref['path'])==ref,'Frozen source differs')
    spec=importlib.util.spec_from_file_location('current_R2_capacity_binder',HERE/'bind_closed_R2_metadata.py')
    binder=importlib.util.module_from_spec(spec);spec.loader.exec_module(binder)
    _,deps=binder.verify_package(expected_sha);return binder,deps

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pins-sha256',required=True)
    parser.add_argument('--expected-node',required=True,choices=['compute-0-'+str(i) for i in (2,*range(8,20))])
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--bound-metadata-root',type=Path,required=True)
    args=parser.parse_args()
    need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdigit()
        and os.environ.get('SLURM_JOB_PARTITION')=='cpu' and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16
        and os.environ.get('CUDA_VISIBLE_DEVICES')=='','Owned CPU-only Slurm allocation with>=16CPUs required')
    need(socket.gethostname().split('.')[0]==args.expected_node,'Actual/expected CPU node differs')
    out=args.output_root.absolute()
    need(not out.exists() and not out.is_symlink() and out.resolve()==out
        and out.is_relative_to(BASE/'runs') and not out.is_relative_to(FAMILY)
        and not out.is_relative_to(HERE),'Fresh independent audit output required')
    out.mkdir(parents=True,exist_ok=False)
    result={'schema':'model_v3_closed_R2_capacity_metadata_audit_v1','status':'FAILED_HOLD',
        'job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname(),'failure':None,
        'current_CUDA_capacity_queried':False,'automatic_policy_selected':False,
        'new_auto_GPU_numeric_acceptance':False,'standalone_R1_or_ABBA_acceptance':False,
        'outer_CPU_C0_not_asserted_by_child':True,'models_or_data_or_SDK_or_weights_read':False}
    try:
        binder,deps=verify_package(args.source_pins_sha256)
        binding,binding_ref=binder.validate_bound(args.bound_metadata_root,args.source_pins_sha256)
        sys.path.insert(0,str(CODE/'current'))
        import torch
        from phychem_mfm.model import v3_checkpoint_policy as policy
        from phychem_mfm.model.v3_performance import PerformanceOptions
        need(policy.ROOT==CODE and Path(policy.__file__).resolve()==CODE/'current/phychem_mfm/model/v3_checkpoint_policy.py',
             'Actual consumer namespace/ROOT differs')
        need(not torch.cuda.is_initialized(),'CUDA must remain uninitialized in metadata audit')
        result['audit_runtime']={'logical_python':sys.executable,'python_version':sys.version,
            'torch_version':str(torch.__version__),'torch_build_cuda_version':torch.version.cuda,
            'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),
            'CPU_environment_is_not_current_GPU_capacity_evidence':True,
            'SLURM_MEM_PER_NODE_actual':os.environ.get('SLURM_MEM_PER_NODE'),
            'SLURM_MEM_PER_CPU_actual':os.environ.get('SLURM_MEM_PER_CPU'),
            'memory_request_set_by_this_script':False}
        manifest_path=args.bound_metadata_root.absolute()/'closed_R2_capacity_profile_v1.json'
        manifest=policy.read_bound(policy.file_reference(manifest_path,2*1024**2))
        need(set(manifest)=={'schema','observations'} and manifest['schema']=='model_v3_closed_checkpoint_capacity_profiles_v1'
             and len(manifest['observations'])==1,'One exact closed-R2 profile required')
        requested=policy.PerformanceExecution(**read_json(args.bound_metadata_root.absolute()/'auto_R2_execution_DRAFT_v1.json'))
        options=PerformanceOptions(**read_json(args.bound_metadata_root.absolute()/'auto_R2_options_DRAFT_v1.json'))
        need(requested.checkpoint_policy=='auto_closed_profile_v1' and requested.resident_models==2
             and requested.padding is None and requested.batch_padded_cost==8000000
             and requested.capacity_profile==policy.file_reference(manifest_path,2*1024**2),
             'Exact auto-request metadata/residency/profile binding differs')
        need(options.backbone_checkpointing is None and options.distance_checkpointing is True
             and options.head_checkpointing is True,'Auto must not override explicit checkpoint booleans')
        item=manifest['observations'][0]
        config=policy.read_bound(item['configuration'])
        need(str(config['job_id'])==deps['source_GPU_job_id'] and config['code_sha']==deps['runtime_code_sha']
             and config['prereg_sha']==deps['public_prereg_sha'],'Actual source run identity differs')
        workload=policy.workload_identity(config['model'],seed=config['seed'],input_kind=config['input'],
            snapshot=config['original_shard_snapshot_prejob_sha256'],binding=config)
        need(workload==requested.workload_sha256==deps['workload_sha256'],'Exact native-S workload binding differs')
        # No synthetic hardware/current-CUDA predicate is supplied. This existing
        # consumer validates actual closed source/argv/gates/500 resource rows.
        sources=policy.implementation_sources()
        source_before=policy.canonical(sources)
        observation=policy.load_closed_observation(item,requested,config['model'],options,sources)
        need(not torch.cuda.is_initialized(),'Metadata reader unexpectedly initialized CUDA')
        source_after=policy.implementation_sources()
        need(source_after==sources,'Mandatory source membership/bytes changed during audit')
        policy.verify_observed_sources(config['source_sha256'],source_after)
        for name,ref in item.items():
            limit=16*1024**2 if name=='steps' else 2*1024**2
            need(policy.file_reference(ref['path'],limit)==ref,'Closed input changed before metadata audit closure')
        verify_package(args.source_pins_sha256)
        result.update(status='CLOSED_R2_OBSERVATION_METADATA_VALIDATED_PENDING_ACTUAL_CPU_OUTER_C0',
            capacity_profile=policy.file_reference(manifest_path,2*1024**2),
            auto_execution_DRAFT=digest(args.bound_metadata_root.absolute()/'auto_R2_execution_DRAFT_v1.json'),
            auto_options_DRAFT=digest(args.bound_metadata_root.absolute()/'auto_R2_options_DRAFT_v1.json'),
            workload_sha256=workload,resident_models=2,
            mandatory_source_count=len(sources),mandatory_source_sha256=source_before,
            current_mandatory_and_saved_source_graph_rehashed=True,
            complete_packaging_2131_source_graph_rehashed=False,
            current_full_QA_graph_rehashed_by_original_manual_guard=True,actual_bound_metadata=binding_ref,
            actual_source_run_numeric_gates_validated_by_existing_consumer=True,
            six_closed_rawrefs_after= item,closed_observation=observation,
            CUDA_initialized_after=False,
            scope='Existing pure-metadata CLOSED-R2 consumer only. No current CUDA/environment selection, model allocation, new numeric gate, R1/ABBA speed or adoption.')
    except BaseException as exc:
        result['failure']={'type':type(exc).__name__,'message':str(exc)}
    with (out/'RESULT.json').open('x') as stream:
        json.dump(result,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'status':result['status'],'job_id':result['job_id'],
        'result':str(out/'RESULT.json'),'failure':result['failure']},sort_keys=True))
    return int(result['failure'] is not None)

if __name__=='__main__':raise SystemExit(main())
