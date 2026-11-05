"""Original fill scope.freeze body with a declared metadata-only IO context.

SOURCE ONLY candidate. Root supplies real generic100 startup and resource refs.
"""
import argparse,ast,collections,contextlib,hashlib,importlib.util,itertools,json,os,pathlib,stat,sys,types
from workflows.data_v1_final.labels.full_logical_owner_plan_v2.io import opened
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import need
from workflows.data_v1_final.conformers.formal_cpu_auto_v3.identity import fixed_random_ids
from workflows.data_v1_final.conformers.ordinary_postprocess_resume_v1.reuse import common_component
from workflows.data_v1_final.execution.cpu_account100_queue_v1.runtime import require_startup
P=pathlib.Path
KEY='pprime_fill_scope_only_v1'
MODULE='workflows.data_v1_final.pprime.fill_scope_only_v1.run'


def triple(r):return {k:r[k]for k in ('path','bytes','sha256')}

def unique(refs):
    result={}
    for ref in refs:
        ref=triple(ref);need(ref['path']not in result or result[ref['path']]==ref,'CONFLICTING_DECLARED_REFERENCE');result[ref['path']]=ref
    return list(result.values())

def small(ref):
    need(ref['bytes']<=8<<20,'SMALL_METADATA_OR_CODE_ONLY')
    with opened(ref,hash_content=True)as(f,_):return f.read()

def pin_small(path):
    p=P(path);s=p.lstat();need(stat.S_ISREG(s.st_mode)and s.st_uid==1278 and s.st_size<=8<<20,'OWN_SMALL_METADATA')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb')as f:
        first=os.fstat(f.fileno());raw=f.read();last=os.fstat(f.fileno())
        frame=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(frame(first)==frame(last)==frame(p.lstat())and len(raw)==s.st_size,'SMALL_METADATA_SAME_FD_FRAME')
    return dict(path=str(p.absolute()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def original_functions(ref,names,namespace):
    """Compile only unchanged original function ASTs, not module imports/main.

    This keeps the original source filename/line locations and avoids importing
    the old preparation/Native/bootstrap layer merely to use its scope body.
    """
    tree=ast.parse(small(ref).decode('utf-8-sig'),filename=ref['path'])
    wanted=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))and node.name in names]
    need({node.name for node in wanted}==set(names),'EXACT_ORIGINAL_FUNCTION_DEFINITIONS')
    exec(compile(ast.Module(body=wanted,type_ignores=[]),ref['path'],'exec'),namespace)
    return {name:namespace[name]for name in names}


class MetadataContext:
    def __init__(self,plan,budget):
        self.plan=plan;self.budget=budget;self.held={}
        self.metadata={r['path']:triple(r)for r in plan['metadata_references']}
        self.data={r['path']:triple(r)for r in plan['data_references']}
    def meta(self,ref):
        need(self.metadata.get(ref['path'])==triple(ref),'EXACT_DECLARED_SMALL_METADATA:'+ref['path'])
        return json.loads(small(ref).decode('utf-8-sig'))
    def hold(self,ref):
        ref=triple(ref);need(self.data.get(ref['path'])==ref,'EXACT_DECLARED_CLOSED_DATA:'+ref['path'])
        if ref['path']not in self.held:
            manager=opened(ref,hash_content=False);stream,frame=manager.__enter__();self.held[ref['path']]=(manager,stream,frame)
        self.budget.check();return ref['path']
    def check(self):self.budget.check()
    def close(self):
        for manager,stream,frame in reversed(list(self.held.values())):manager.__exit__(None,None,None)
        self.held.clear()


class LogicalOutput:
    """Explicit own named files plus one own spill directory; no quota credit."""
    def __init__(self,plan,monitor,root,scratch):
        self.monitor=monitor;self.root=root;self.scratch=scratch;self.cap=plan['logical_output_cap_bytes'];self.local_cap=plan['local_temp_cap_bytes']
        need(0<self.cap<=8<<30 and 0<self.local_cap<=8<<30,'ROOT_BOUND_SCOPE_LOGICAL_CAPS')
        folder=root/'closed_scope';self.paths={folder/name for name in ('scope.duckdb','scope.duckdb.wal','members.parquet','fixed_random.parquet','tasks.parquet')}
        self.last=None;self.next=0
    def observe(self,additional=0):
        total=0
        for path in self.paths:
            try:st=path.lstat()
            except FileNotFoundError:continue
            need(stat.S_ISREG(st.st_mode)and st.st_uid==1278 and st.st_nlink==1,'OWN_REGISTERED_OUTPUT_FILE')
            total+=st.st_size
        local=0;count=0
        # Only this exact job-owned DuckDB spill directory, never the scope tree.
        with os.scandir(self.scratch)as entries:
            for entry in entries:
                count+=1;need(count<=4096,'BOUNDED_OWN_SPILL_FILE_METADATA')
                try:st=entry.stat(follow_symlinks=False)
                except FileNotFoundError:continue
                need(stat.S_ISREG(st.st_mode)and st.st_uid==1278 and st.st_nlink==1,'OWN_SPILL_FILE_NOT_ALIAS')
                local+=st.st_size
        need(total+additional<=self.cap and local<=self.local_cap,'SCOPE_OR_LOCAL_LOGICAL_OUTPUT_CAP')
        self.last=dict(Lustre_logical_bytes=total,local_temp_logical_bytes=local,Lustre_logical_cap_bytes=self.cap,local_temp_cap_bytes=self.local_cap,allocation_credit_bytes=0)
        return self.last
    def check(self):
        self.monitor.check()
        if __import__('time').monotonic()>=self.next:self.observe();self.next=__import__('time').monotonic()+5
    def reserve(self,path,n):
        self.paths.add(P(path));self.monitor.check();self.observe(n)
    def report(self):return self.observe()


def run(plan,proof,budget):
    """Freeze and close actual reusable scope directly on persistent Lustre."""
    need(os.getuid()==1278 and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('SLURM_JOB_ID')==str(proof['job_id'])
      and os.uname().nodename.split('.')[0]=='compute-0-18','ACTUAL_16CPU_NODE18_SAME_PARENT')
    root=P(plan['output_directory']);need(str(root)=='/lfshome/zixiao/data_v1_20261025/Pprime_fill_scope_20261105_v1','EXACT_ADMITTED_LUSTRE_SCOPE_ROOT')
    need(not root.exists(),'FRESH_SCOPE_OUTPUT_ROOT');root.mkdir(parents=True,mode=0o700)
    prefix=plan['local_temp_directory_prefix'];need(prefix=='/dev/shm/pp_fill_scope_v1_' and str(proof['job_id']).isdecimal(),'ACTUAL_JOBID_PRIVATE_LOCAL_SCRATCH')
    scratch=P(prefix+str(proof['job_id']));need(not scratch.exists(),'FRESH_PRIVATE_NODE_SCRATCH')
    v=os.statvfs(scratch.parent);need(v.f_bavail*v.f_frsize>=plan['local_temp_cap_bytes'],'ACTUAL_NODE_SHM_FREE_FOR_THIS_LOCAL_SOFT_CAP')
    scratch.mkdir(mode=0o700)
    marker=dict(uid=os.getuid(),pid=os.getpid(),job_id=str(proof['job_id']),node=os.uname().nodename,
      start_ticks=P('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],boot_id=P('/proc/sys/kernel/random/boot_id').read_text().strip(),
      input_scope_only=True,new_QM_UFF_calls=0)
    with(scratch/'owner.json').open('xb')as f:f.write(json.dumps(marker,sort_keys=True).encode());f.flush();os.fsync(f.fileno())
    logical=LogicalOutput(plan,budget,root,scratch);ctx=MetadataContext(plan,logical)
    # Pure original output-pin function, privately bound to the exact new output
    # root. No Native/conda/shared-pool/bootstrap module is imported or called.
    C=types.SimpleNamespace(need=need,meta=ctx.meta,unique=unique)
    pin_space=dict(C=C,pathlib=pathlib,os=os,stat=stat,hashlib=hashlib)
    functions=original_functions(plan['output_pin_source_reference'],('stamp','pin'),pin_space)
    original_output_pin=functions['pin']
    def output_pin(path,roots):
        logical.reserve(path,0);return original_output_pin(path,roots)
    class Store:
        def json(self,path,value):
            path=P(path);need(root in path.parents and not path.exists(),'FRESH_OWN_SCOPE_METADATA')
            raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();logical.reserve(path,len(raw))
            with path.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
            return output_pin(path,[root])
    class Reader:
        def __init__(self,actual_plan,b,budget):need(actual_plan is plan,'SAME_SCOPE_PLAN')
        def hold(self,ref):return ctx.hold(ref)
        def close(self):return ctx.close()
    def q(value):return "'"+str(value).replace("'","''")+"'"
    # Only resource IO differs: one real owned scratch path. The original freeze
    # function AST, SQL, complete ordering and first-two selection stay intact.
    import builtins,duckdb
    native_import=builtins.__import__
    def connect(*args,**kwargs):
        need(str(args[0])==str(root/'closed_scope/scope.duckdb'),'SINGLE_OWN_SCOPE_DUCKDB')
        db=duckdb.connect(*args,**kwargs);db.execute('SET temp_directory='+q(scratch));db.execute("SET max_temp_directory_size='8GiB'");return db
    private_duckdb=types.SimpleNamespace(**{k:v for k,v in vars(duckdb).items()if k!='connect'},connect=connect)
    def private_import(name,*args,**kwargs):return private_duckdb if name=='duckdb'else native_import(name,*args,**kwargs)
    namespace=dict(C=C,SourceIO=Reader,I=types.SimpleNamespace(pin=output_pin),itertools=itertools,json=json,pathlib=pathlib,
      common_component=common_component,fixed_random_ids=fixed_random_ids,q=q,__builtins__=dict(vars(builtins),__import__=private_import))
    funcs=original_functions(plan['scope_source_reference'],('references','freeze'),namespace)
    # A mapping with only actual legacy key1, not a fabricated per-population
    # object or empty/NULL roster. These are the two actual metadata authorities.
    native=plan['native_record_index_reference'];molecules=plan['molecule_index_reference']
    b=dict(pilot=dict(record_index=native['path']),data=[native],population={1:molecules})
    common=ctx.meta(plan['closed_common_manifest_reference'])
    selection=plan['selection_source_reference'];need(selection==common['random_order_algorithm'],'ORIGINAL_STABLE_RANDOM_SOURCE_REFERENCE')
    with opened(selection,hash_content=True):pass
    try:
        logical.check();reference,manifest=funcs['freeze'](plan,proof,root/'closed_scope',b,logical,Store());logical.check()
        return dict(schema='PPRIME_SCOPE_ONLY_CLOSED_NO_NATIVE_V1',status='CLOSED_REUSABLE_FILL_FIXED_RANDOM_SCOPE_NO_INPUT_HASH_OR_QM',
          scope_manifest_reference=reference,actual_chosen_MIDs=manifest['actual_chosen_MIDs'],actual_first2_records=manifest['actual_first2_records'],
          component_references=manifest['component_references'],actual_scope_job_id=str(proof['job_id']),logical_output=logical.report(),
          actual_local_temp_directory=str(scratch),local_owner_reference=pin_small(scratch/'owner.json'),production_once_written=False,
          Native_initialized=False,NoInvoke_or_input_hashes_performed=False,new_QM_UFF_calls=0,
          old_parent_4525659_upgraded=False,final_Common_or_training_release=False)
    finally:ctx.close()

def load_resource(plan,proof):
    ref=plan['resource_module_reference'];small(ref) # Actual deployment pin, never a fixed control-path assumption.
    spec=importlib.util.spec_from_file_location('_actual_fill_scope_resource',ref['path']);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    spec.loader.exec_module(module);return module


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True);parser.add_argument('--startup-proof',required=True);a=parser.parse_args()
    plan_ref=pin_small(a.plan);proof_ref=pin_small(a.startup_proof);plan=json.loads(small(plan_ref).decode('utf-8-sig'))
    need(plan['schema']=='PPRIME_FILL_SCOPE_ONLY_PLAN_V1','EXACT_SCOPE_ONLY_PLAN')
    argv=[plan['python_executable'],'-B','-m',MODULE,'--plan',a.plan,'--startup-proof',a.startup_proof]
    proof=require_startup(a.startup_proof,expected_kind='analysis',expected_scope_key=KEY,expected_scope_parameters=plan['scope_parameters'],
      expected_execution_argv=argv,expected_source=P(__file__).absolute(),required_references=[plan_ref,*plan['source_references']])
    need(proof['request']['cpus']==16 and proof['request']['node']=='compute-0-18' and proof['request']['data_references']==plan['data_references'],'SAME_REAL_SCOPE_CPU_AND_INPUTS')
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    resource=load_resource(plan,proof);budget=resource.start(plan,proof,plan_reference=plan_ref,proof_reference=proof_ref);result=None
    try:result=run(plan,proof,budget)
    finally:budget.finish()
    result['resource_report']=budget.report();control=P(plan['control_directory']);path=control/'scope_only_receipt.json'
    need(control.is_dir()and not path.exists(),'ACTUAL_NEW_MAIN_METADATA_RECEIPT')
    raw=(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();need(len(raw)<1<<20,'SMALL_MAIN_RESULT')
    with path.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
    print(json.dumps(dict(receipt_reference=pin_small(path),scope_manifest_reference=result['scope_manifest_reference'])),flush=True)
if __name__=='__main__':main()