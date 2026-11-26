"""One finite explicit controller sequence; no daemon or legacy dispatch."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from storage_20261122 import CONTROL as C

PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
POINTS=tuple((run,n) for run in ('S_B0_s0_9M','S_final_s0_9M')
             for n in range(1000000,9000000,1000000))
read=lambda path:json.loads(Path(path).read_text())


def invoke(script,*args):
    raw=subprocess.check_output([PY,'-B',str(C/script),*map(str,args)],text=True)
    value=json.loads(raw.strip().splitlines()[-1])
    print(json.dumps(dict(controller=script,result=value)),flush=True)
    return value


def advance(role,handle,node,uuid,*,cpu_node='compute-0-11',cores='50',
            control=invoke,load=read):
    if (role not in ('budget','fullft') or not re.fullmatch(r'S_[A-Za-z0-9_]+',handle)
            or node not in {'compute-0-'+str(i) for i in (*range(8),20,22)}
            or not re.fullmatch(r'GPU-[a-fA-F0-9-]+',uuid)):
        raise ValueError('Explicit registered own controller role/handle/node/UUID required')
    row=load(C/'execution.json')['statistics'][handle]
    if role=='budget':
        point=(row.get('run'),row.get('samples'))
        if row.get('role')!='budget' or point not in POINTS:raise ValueError('Not a registered original9M point')
        close='close_readout_resources_20261126.py'
    else:
        if row.get('mode') not in ('finetune','finetune_native'):raise ValueError('Not an owned full fit')
        close='close_fullft_resources_20261126.py'
    control(close,handle)
    path=C/(handle+'_resource_close.json')
    if not path.exists():return dict(status='WAITING_ACTUAL_RESOURCE_SETTLEMENT',handle=handle)
    proof=load(path)
    if (proof.get('status')!='OWN_RESOURCES_CLOSED' or proof.get('exit_code')!=0
            or proof.get('handle')!=handle):
        return dict(status='WAITING_SUCCESSFUL_COMPLETE_POINT',handle=handle)
    if role=='budget':
        control('launch_budget_statistics_native_20261126.py',*point,cpu_node,cores)
        index=POINTS.index(point)+1
        if index==len(POINTS):return dict(status='ALL_REGISTERED_GPU_POINTS_REQUESTED_CPU_PENDING')
        following=POINTS[index]
    control('observe_S_gpu_slots_20261122.py')
    result=(control('launch_readout_20261126.py','budget',*following,node,uuid) if role=='budget'
            else control('launch_fullft_20261124.py',node,uuid))
    return dict(status='EXPLICIT_CONTROLLER_SEQUENCE_RETURNED',completed_handle=handle,next_controller_result=result)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('role',choices=('budget','fullft'))
    p.add_argument('handle')
    p.add_argument('node')
    p.add_argument('gpu_uuid')
    p.add_argument('--cpu-node',default='compute-0-11')
    p.add_argument('--cores',default='50')
    a=p.parse_args()
    if os.getuid()!=1278:raise ValueError('Exact own account required')
    print(json.dumps(advance(a.role,a.handle,a.node,a.gpu_uuid,cpu_node=a.cpu_node,cores=a.cores)),flush=True)
