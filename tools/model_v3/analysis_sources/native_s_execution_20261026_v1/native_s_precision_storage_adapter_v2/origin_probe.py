"""CPU metadata-only origin probe; never constructs Inputs or models."""
from __future__ import annotations
import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import types
import runtime_origin as origin


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,required=True)
    parser.add_argument('--mode',choices=('fresh','native-first','075-first-metadata','075-bare-first-metadata'),required=True)
    parser.add_argument('--metadata-only',action='store_true')
    args=parser.parse_args()
    origin.require(not os.environ.get('CUDA_VISIBLE_DEVICES'),'Origin probe requires CPU-only GPU-hidden environment')
    contract=origin.read_contract(args.contract,metadata_only=args.metadata_only)
    negative=args.mode.startswith('075-')
    if negative:
        # Foreign-origin metadata is sufficient to reject before executing any
        # old code. This does not claim an actual075 model was instantiated.
        foreign=Path(contract['runtime_root']).parent/'metadata_foreign_075_tree'
        name='phychem_mfm' if args.mode=='075-first-metadata' else 'a_execution_runtime'
        value=types.ModuleType(name)
        value.__file__=str(foreign/('current/phychem_mfm/__init__.py' if name=='phychem_mfm' else 'tools/model_v3/a_execution_runtime.py'))
        if name=='phychem_mfm': value.__path__=[str(foreign/'current/phychem_mfm')]
        else: value.REPO=foreign
        origin.require(name not in sys.modules,'Negative metadata probe must start fresh')
        sys.modules[name]=value
    elif args.mode=='native-first':
        origin.configure_paths(contract)
        importlib.import_module('phychem_mfm.phase1.v3_native_s_precision')
    try:
        _,report=origin.import_runtime(contract)
    except ValueError as error:
        if not negative: raise
        print(json.dumps(dict(status='FOREIGN_ORIGIN_REJECTED_METADATA_ONLY',mode=args.mode,message=str(error),
            data_inputs_constructed=False,CUDA_or_training_acceptance=False)))
        return
    origin.require(not negative,'Foreign-origin metadata was not rejected')
    print(json.dumps(dict(mode=args.mode,**report)))


if __name__=='__main__': main()
