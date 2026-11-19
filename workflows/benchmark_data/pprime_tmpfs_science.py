"""Original WP5 loader/Adapter, with explicitly admitted owned tmpfs scratch."""
import json
import os
from pathlib import Path
import socket
import sys
import threading
from rdkit import rdBase
from .pprime_science import Adapter,WP5,PROTOCOL_SHA,module

def load(scratch,deadline,stop_event=None):
    node=socket.gethostname().split('.')[0]
    if node not in {'compute-0-'+str(i) for i in range(8,20)} or not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Actual development CPU-node Slurm allocation required')
    if rdBase.rdkitVersion!='2025.09.5':raise RuntimeError('Original RDKit version required')
    scratch=Path(scratch).resolve()
    if not scratch.is_dir() or not scratch.is_relative_to(Path('/dev/shm')) or scratch.stat().st_uid!=os.getuid():
        raise ValueError('Owned node-local scratch required')
    scripts=WP5/'scripts';sys.path.insert(0,str(scripts))
    engine=module('_benchmark_original_wp5_engine',scripts/'wp5_engine_v3.py')
    if engine.sha(WP5/'configs/protocol.json')!=PROTOCOL_SHA:raise ValueError('Original WP5 protocol changed')
    protocol=engine.load_protocol()
    contract=json.loads((WP5/'configs/production_contract_v7.json').read_text())
    package=json.loads(Path(contract['reproduction_package']['path']).read_text())
    for family,version in package['software_versions'].items():
        if version['version']!=protocol['expected_versions'][family] or engine.sha(protocol[family+'_executable'])!=version['sha256']:
            raise ValueError('Original quantum executable version/binary differs: '+family)
    if engine.sha(protocol['registry']['path'])!=protocol['registry']['sha256']:
        raise ValueError('Original label registry changed')
    native=engine.pinned_module('_benchmark_original_wp5_native',protocol['frozen_dependencies']['native_lifecycle'])
    parser=module('_benchmark_original_wp5_parser',scripts/'wp5_parser_v2.py')
    native.MULLIKEN=engine.pinned_module('_benchmark_original_wp5_mulliken',protocol['frozen_dependencies']['mulliken'])
    protocol['scratch_base']=str(scratch)
    native.CONFIG=protocol;native.PARSER=parser;native.DEADLINE=float(deadline)
    native.STOP_EVENT=stop_event if stop_event is not None else threading.Event()
    native.OUTPUT=scratch
    engine.CONFIG=protocol;engine.NATIVE=native;engine.PARSER=parser
    engine.REGISTRY=json.loads(Path(protocol['registry']['path']).read_text())['entries']
    engine.PACKAGE=package
    engine.WIRE=module('_benchmark_original_wp5_registry_wire',scripts/'wp5_parquet_v2.py')
    return Adapter(engine,scratch,contract['reproduction_package'])


