"""Three exact resource-only inverses and real original science object identity."""
import ast,inspect
from pathlib import Path
from secondary_pubchem_screening_alpha_v1 import run as O,kernel as K,runtime as R
from secondary_cpu_queue_v1 import common as Q
from . import contracts as C

def proof():
    from . import run as N
    old=inspect.getsource(O.run_group);new=inspect.getsource(N.run_group)
    restored=new.replace('if budget.stop.is_set():break','if budget.stop.is_set():worker_stop.set();break')
    restored=restored.replace('        while pending:\n            collect()','        while pending:\n            if budget.stop.is_set():worker_stop.set()\n            collect()')
    Q.need(restored==old and ast.dump(ast.parse(restored),include_attributes=False)==ast.dump(ast.parse(old),include_attributes=False),'RUN_GROUP_FULL_BYTE_AST_ONLY_TWO_RESOURCE_STOP_EVENT_REMOVALS')
    original=Path(R.__file__).read_text();current=(C.HERE/'runtime.py').read_text()
    restored=current.replace('from secondary_pubchem_screening_alpha_v1 import contracts as C','from . import contracts as C').replace('from secondary_pubchem_screening_alpha_v1.runtime import Stop','class Stop(RuntimeError):pass')
    restored=restored.replace("self.plan['wall_seconds']-900","self.plan['wall_seconds']-120").replace('if self.stop.is_set() and not drain:return','if self.stop.is_set() and not drain:raise Stop(self.reason)')
    Q.need(restored==original and ast.dump(ast.parse(restored),include_attributes=False)==ast.dump(ast.parse(original),include_attributes=False),'ORIGINAL_BUDGET_FULL_BYTE_AST_ONLY_IMPORT_DRAIN900_AND_SOFT_RETURN')
    from .resource import job_identity
    original_job=inspect.getsource(Q.job_identity);current_job=inspect.getsource(job_identity).replace("job.get('NumCPUs')=='32'","job.get('NumCPUs')=='16'")
    Q.need(current_job==original_job and ast.dump(ast.parse(current_job),include_attributes=False)==ast.dump(ast.parse(original_job),include_attributes=False),'ORIGINAL_JOB_IDENTITY_ONLY_REAL_CPU32_LITERAL')
    Q.need(N.kernel.chemical_task is K.chemical_task and N.journal.Writer is O.journal.Writer and N.materialize_shards.claim is O.materialize_shards.claim
      and N.source.iter_part is O.source.iter_part,'DIRECT_ORIGINAL_CHEMISTRY_WRITER_SOURCE_AND_ONCE_OBJECTS')
    return {'status':'FULL_SOURCE_BYTES_AST_RESOURCE_ONLY_INVERSE','original_run_reference':Q.ref(O.__file__),'original_runtime_reference':Q.ref(R.__file__),
      'original_chemical_task_reference':Q.ref(K.__file__),'new_scientific_formula':False,'original_pending':32,'new_cpu_count':32,
      'DATA_or_chemistry_in_this_proof':False,'old_modules_or_global_bindings_modified':False}
