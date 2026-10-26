"""Independent close/index entry using frozen V3 kernels without importing the finalizer."""
from __future__ import annotations
import argparse,pathlib,sys
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as C,runtime_io as R
from workflows.data_v1_final.conformers.formal_cpu_auto_v3.close_index import terminal_batch,completion
OPTIONS=('config','root-preflight','quota-reuse-review','descriptor','catalog','output')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('close','index'))
 for name in OPTIONS:p.add_argument('--'+name,type=pathlib.Path,required=name in {'config','root-preflight','quota-reuse-review','output'})
 args=p.parse_args();value,proof,session,config_ref=R.admit(__file__,args,args.mode,OPTIONS)
 here=pathlib.Path(__file__).absolute().parent;R.authorized(proof,[C.ref(here/'run.py'),C.ref(here/'__init__.py')])
 C.need(C.ref(C.HERE/'close_index.py')['sha256']=='8ec4e1add3ffc224f6030d8457f1b2a54605d8d97b291095c70d304be1c3b108','UNCHANGED_REAL_TERMINAL_CLASSIFICATION_AND_INDEX_SOURCE')
 R.new_output_directory(args.output,value);budget=R.Budget(proof,session,value,R.OUT)
 C.need(budget.observe() is None,'FRESH_SHARED_ACCOUNT_QUOTA_REQUIRED');budget.start_monitor()
 try:
  if args.mode=='close':terminal_batch(C.read(R.input_ref(args.root_preflight,args.descriptor)),config_ref,value,proof)
  else:completion(C.read(R.input_ref(args.root_preflight,args.catalog)),config_ref,value,proof)
 finally:
  budget.close_monitor();R.write_json_new(R.OUT/'resource_observations.json',budget.report())
if __name__=='__main__':main()