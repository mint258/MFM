"""Resume unchanged D7 math with an optional completed physical input cache."""
import argparse,json,os,types
from pathlib import Path
from workflows.data_v1_final.conformers.window2_d7_runtime_v1 import run as runtime
from .keep_source_map import install_native_reader

def initialize(science_path):
    runtime.initialize(science_path)
    install_native_reader(runtime.original,os.environ.get('DATA_V1_COMPLETED_SOURCE_CACHE_PLAN'))

def run(plan):
    function=runtime.run
    namespace=dict(function.__globals__,initialize=initialize)
    current=types.FunctionType(function.__code__,namespace,function.__name__,function.__defaults__,function.__closure__)
    current.__kwdefaults__=function.__kwdefaults__
    return current(plan)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args();run(json.loads(Path(a.plan).read_text()))
