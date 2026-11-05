"""Root-invoked source-bound fresh CPU launch-contract QA; no data/GPU."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
from common import *
sys.dont_write_bytecode=True

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--pins-sha256',required=True);a=p.parse_args(argv)
    require(int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16 and os.environ.get('CUDA_VISIBLE_DEVICES')==''
        and socket.gethostname()==os.environ['MODEL_V3_EXPECTED_NODE'],'Expected CPU-only allocation required')
    manifest,pins=verify_package(expected=a.pins_sha256);verify_package(V2,V2_PIN)
    job=os.environ['SLURM_JOB_ID'];contract=OLD/f'native_s_launch_METADATA_ONLY_{job}.json'
    from provenance import prepare_metadata
    combined,_=prepare_metadata(contract,OLD/'cpu_git_tools_v1/bin/git')
    sources={str(HERE/row['path']):row['sha256'] for row in pins['files']}
    sources[manifest['path']]=manifest['sha256'];sources[str(contract)]=binding(contract)['sha256']
    v2_ref,v2_pins=verify_package(V2,V2_PIN)
    sources[v2_ref['path']]=v2_ref['sha256'];sources.update({str(V2/x['path']):x['sha256'] for x in v2_pins['files']})
    sources.update({str(RUNTIME/x['relative_path']):x['sha256'] for x in combined['files']})
    sources.update({str(N/x):binding(N/x)['sha256'] for x in ('native_s_combined_immutable_runtime_v1.json',
        'native_integration_public_receipt_v1.json','root_native_s_precision_commit_v1.json')})
    for row in read(HERE/'dependency_pins.json')['references']:sources[row['path']]=row['sha256']
    request=dict(schema='model_v3_frozen_units_request_v1',tasks=[dict(name='native_s_profile_launch',root=str(RUNTIME),
        tests=[str(HERE/row['path']) for row in pins['files'] if row['path'].startswith('test_') and row['path'].endswith('.py')],
        sources=sources,environment={k:v for k,v in runtime_environment(cpu=True,contract=contract).items()
            if k in ('MODEL_V3_NATIVE_S_RUNTIME_CONTRACT','PYTHONPATH','PYTHONDONTWRITEBYTECODE','CUDA_VISIBLE_DEVICES','PYTEST_DISABLE_PLUGIN_AUTOLOAD')})])
    path=OLD/f'native_s_launch_actual_request_{job}.json';ref=write(path,request)
    env={**os.environ,'MODEL_V3_UNITS_REQUEST':str(path),'MODEL_V3_UNITS_REQUEST_SHA':ref['sha256']}
    command=[sys.executable,'-B',str(OLD/'run_cpu_test_supervised_v2.py'),'--output-root',str(OLD/f'frozen_units_{job}'),
        '--record',str(OLD/f'frozen_units_supervisor_{job}.json'),'--wall-seconds','800','--rss-limit-bytes',str(RSS),'--',
        sys.executable,'-B',str(OLD/'run_frozen_units_v1.py'),'--request',str(path),'--request-sha256',ref['sha256'],
        '--expected-node',os.environ['MODEL_V3_EXPECTED_NODE'],'--output',str(OLD/f'frozen_units_{job}')]
    return subprocess.run(command,env=env).returncode

if __name__=='__main__':raise SystemExit(main())
