"""Fresh CPU metadata-only canonical package/origin probe; no input ctor."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
from common import *
sys.dont_write_bytecode=True

def main():
    p=argparse.ArgumentParser();p.add_argument('--contract',type=Path,required=True)
    p.add_argument('--configuration-output',type=Path);a=p.parse_args()
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','Metadata probe must hide GPUs')
    import runtime_origin
    contract=runtime_origin.read_contract(a.contract,allow_candidate_profile=True)
    require(contract['status']=='PUBLISHED_IMMUTABLE_RUNTIME' and contract['production_20k_allowed'] is True,
        'Actual full-runtime gate required; this probe still admits no scientific20k')
    runtime_origin.configure_paths(contract)
    _,origin=runtime_origin.import_runtime(contract)
    if a.configuration_output is not None:
        import native_s_storage,operational
        write(a.configuration_output,operational.configuration(native_s_storage,contract))
    print(json.dumps(dict(status='CANDIDATE_PROFILE_ONLY_ORIGIN_VERIFIED',
        origin=origin,Inputs_constructed=False,production_20k_allowed=False)),flush=True)

if __name__=='__main__':main()
