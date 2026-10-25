"""Root metadata-only full-file equivalence proof; does not execute retention."""
from __future__ import annotations
import argparse,hashlib,json,os,pathlib,sys
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO=ROOT/'repository';HERE=REPO/'workflows/data_v1_final/pprime/queued_retention_v1'
sys.path.insert(0,str(HERE))
from binding_v1 import prove_runtime_copy

def read(path):
    need(path.is_absolute() and not path.is_symlink() and path.is_file(),'SMALL_SOURCE_REQUIRED')
    with path.open('rb') as f:
        a=os.fstat(f.fileno());need(a.st_size<=2*1024**2 and a.st_uid==1278,'SMALL_SOURCE_OWNER_LIMIT')
        raw=f.read(2*1024**2+1);b=os.fstat(f.fileno())
    need(len(raw)==a.st_size and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'SOURCE_CHANGED')
    return raw

def need(ok,message):
    if not ok:raise ValueError(message)

def ref(path,raw=None):
    raw=read(path) if raw is None else raw
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    need(pathlib.Path(__file__).absolute()==HERE/'verify_binding_v1.py','ACTUAL_ROOT_PROOF_SOURCE_REQUIRED')
    old=REPO/'workflows/data_v1_final/pprime/retention_v1/prepare_v1.py'
    new=old.with_name('prepare_cpu_queued_v2.py')
    before,after=read(old),read(new);result=prove_runtime_copy(before,after)
    result.update(schema='QUEUED_RETENTION_CPU_BINDING_SOURCE_PROOF_V1',status='PASS_SOURCE_ONLY_NOT_RETENTION_EXECUTED',
        original_source=ref(old,before),variant_source=ref(new,after),proof_source=ref(pathlib.Path(__file__).absolute()),
        pure_boundary_source=ref(HERE/'binding_v1.py'),declared_edit={'from':'observed=IO.runtime(prepare=True)','to':'observed=IO.runtime()'},
        old_node_binding='legacy prepare=True required node20',new_node_binding='ordinary IO.runtime() allows14-19; new wrapper requires fresh CPU16/64G analysis admission',
        original_selection_or_science_or_export_changed=False,tests_or_science_executed=False,new_UFF_QM_calls=0,
        wrapper_AST_equals_old_prepare_AST=False,
        limits='Exact original preparation body except node binding. New wrapper admission and independent readback are additional code and not claimed AST-identical.')
    need(a.output.is_absolute() and ROOT/'control' in a.output.parents and not a.output.exists(),'NEW_ROOT_CONTROL_PROOF_REQUIRED')
    raw=(json.dumps(result,indent=2)+'\n').encode()
    with a.output.open('xb') as f:f.write(raw)
    print(json.dumps({'status':result['status'],'proof':ref(a.output),'new_UFF_QM_calls':0}))
if __name__=='__main__':main()
