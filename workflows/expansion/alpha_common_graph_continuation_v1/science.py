"""Original function objects; new initializer writes honest Alpha worker proof."""
import importlib,os,sys,time
from pathlib import Path
from . import io as I


def load(plan):
    for ref in plan['scientific_source_references']:I.read_source(ref)
    from rdkit import rdBase
    import numpy,pyarrow
    I.need(sys.version_info[:3]==(3,11,14) and rdBase.rdkitVersion=='2025.09.5' and numpy.__version__=='2.2.6' and pyarrow.__version__=='17.0.0','ORIGINAL_SCIENTIFIC_AND_ALPHA_PARQUET_ENVIRONMENT')
    from workflows.expansion.common_molecular_fp_main_v1 import scan,kernel,io
    from workflows.expansion.common_molecular_fp_main_v1.run import Dispatch
    from workflows.expansion.common_molecular_fp_candidate_v1 import worker,projection,census,selection
    FUN,proof=worker.load_kernel()
    I.need(scan.S.select is selection.select and kernel.W.derive is worker.derive and kernel.P.reduce_variants is projection.reduce_variants,'UNCHANGED_ORIGINAL_SCANNER_AND_REDUCER_OBJECTS')
    declared={r['path']:r for r in plan['scientific_source_references']}
    for name,module in list(sys.modules.items()):
        if name.startswith(('workflows.expansion.common_molecular_fp_','workflows.data_v1_final.','workflows.expansion.marcel_drugs_keys_main_v1.')) or name in ('workflows.expansion.common','workflows.expansion.screen','workflows.expansion.features_legacy_compatible_v2','workflows.expansion.features_generic_candidate_v1'):
            file=getattr(module,'__file__',None)
            if file and file.endswith('.py'):I.need(declared.get(str(Path(file).absolute()))==I.pin(file),'ORIGINAL_CURRENT_IMPORTED_SOURCE:'+name)
    return dict(scan=scan,kernel=kernel,Dispatch=Dispatch,worker=worker,projection=projection,census=census,io=io,FUN=FUN,proof=proof)


def initialize(plan,barrier,directory):
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    objects=load(plan);objects['kernel'].FUN=objects['FUN']
    I.save(Path(directory)/('worker_%s.json'%os.getpid()),dict(worker_pid=os.getpid(),uid=os.getuid(),job_id=os.environ['SLURM_JOB_ID'],
      kernel_source_scope_proof=objects['proof'],original_function_objects_checked_in_this_worker=True,original_Main_initialize_IO_not_called=True))
    barrier.wait(timeout=180)
