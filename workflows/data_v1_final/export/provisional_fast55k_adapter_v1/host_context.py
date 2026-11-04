"""Capture the live admitted GPU Parent; no new proof, process, lock or queue."""
from __future__ import annotations
import hashlib,json,os,socket,time
from pathlib import Path
from .common import need,reference,read,write

def capture(plan_path,output,*,check_host_resources,host_startup_proof_reference,
            host_request_reference,gpu_uuid,gpu_name,gpu_binding_evidence_reference,
            verified_visible_uuid_mapping,host_remaining_wall_seconds):
    """Caller passes its ORIGINAL live guard and its already verified GPU map.

    Call in the same GPU process, while the existing UUID lock is held. No
    exec/fork/subprocess handoff preserves this callback, so none is offered.
    """
    need(callable(check_host_resources),'EXISTING_LIVE_GPU_GUARD_CALLABLE_REQUIRED')
    check_host_resources();read(host_startup_proof_reference,2<<20);read(host_request_reference,2<<20)
    read(gpu_binding_evidence_reference,2<<20)
    visible=os.environ.get('CUDA_VISIBLE_DEVICES')
    need(type(gpu_uuid)is str and gpu_uuid.startswith('GPU-')and type(gpu_name)is str
      and type(host_remaining_wall_seconds)in(int,float)and host_remaining_wall_seconds>0,
      'ACTUAL_ALREADY_ADMITTED_GPU_AND_REMAINING_WALL')
    if visible!=gpu_uuid:
        need(verified_visible_uuid_mapping=={'cuda_visible_devices':visible,'gpu_uuid':gpu_uuid,
          'source_reference':gpu_binding_evidence_reference},'USE_EXISTING_VERIFIED_GPU_MAPPING_NOT_GUESSED_ZERO')
    argv=[a.decode()for a in Path('/proc/self/cmdline').read_bytes().split(b'\0')if a]
    return write(output,{'schema':'ACTUAL_MODEL_GPU_PARENT_IO_CONTEXT_V1','endpoint':'202.38.247.57:22',
      'host_purpose':'AUTHORIZED_GPU_VALIDATION_OR_ACTUAL_D3_PAYLOAD','io_plan_reference':reference(plan_path),
      'uid':os.getuid(),'job_id':os.environ['SLURM_JOB_ID'],'node':socket.gethostname().split('.')[0],
      'pid':os.getpid(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
      'process_start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
      'host_full_argv_sha256':hashlib.sha256(json.dumps(argv,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),
      'observed_monotonic_seconds':time.monotonic(),'host_remaining_wall_seconds':host_remaining_wall_seconds,
      'gpu_uuid':gpu_uuid,'gpu_name':gpu_name,'cuda_visible_devices':visible,
      'verified_visible_uuid_mapping':verified_visible_uuid_mapping,'gpu_binding_evidence_reference':gpu_binding_evidence_reference,
      'host_startup_proof_reference':host_startup_proof_reference,'host_request_reference':host_request_reference,
      'host_gpu_guard_already_admitted':True,'context_source_reference':reference(__file__)})

def capture_and_readback(plan_path,context_output,*,check_host_resources,**actual_host):
    from workflows.data_v1_final.export.provisional_d3_local_readback_v1.run import run
    ctx=capture(plan_path,context_output,check_host_resources=check_host_resources,**actual_host)
    return run(plan_path,ctx['path'],check_host_resources=check_host_resources)
