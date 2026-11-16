"""Resolve the CUDA-visible allocated device without assuming NVML ordinals.

Called only inside the paid Slurm allocation, after its disk admission guard.
PyTorch2.8 exposes the CUDA UUID as sixteen bytes (torch/csrc/cuda/Module.cpp).
"""
import json
import os
import socket
import sys
import uuid

import torch


if __name__=='__main__':
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('A real Slurm GPU allocation is required')
    visible=os.environ.get('CUDA_VISIBLE_DEVICES')
    if not visible or torch.cuda.device_count()!=1:
        raise RuntimeError('Expected exactly one Slurm-visible CUDA GPU; CUDA_VISIBLE_DEVICES='+str(visible))
    properties=torch.cuda.get_device_properties(0)
    selected='GPU-'+str(uuid.UUID(bytes=bytes(properties.uuid.bytes)))
    print(json.dumps(dict(node=socket.gethostname(),job_id=os.environ['SLURM_JOB_ID'],
        slurm_job_gpus=os.environ.get('SLURM_JOB_GPUS'),
        slurm_step_gpus=os.environ.get('SLURM_STEP_GPUS'),
        cuda_visible_devices_before=visible,selected_uuid=selected,
        device_name=properties.name,total_memory=properties.total_memory,
        pci_domain_id=properties.pci_domain_id,pci_bus_id=properties.pci_bus_id,
        pci_device_id=properties.pci_device_id)),file=sys.stderr,flush=True)
    print(selected,flush=True)
