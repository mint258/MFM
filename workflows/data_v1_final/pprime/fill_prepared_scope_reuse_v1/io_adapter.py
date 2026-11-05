"""Output/storage-only adapters, original source and software hash readers."""
import ast,hashlib,json,os,pathlib,stat,types,uuid
from workflows.data_v1_final.pprime.formal_packed_sharded_day_v2 import io as OriginalIO,prepare as OriginalPrepare,contract as Science
from workflows.data_v1_final.pprime.fill_scope_only_v1.run import small,pin_small,triple,unique
P=pathlib.Path
need=Science.need


def meta(ref):return json.loads(small(ref).decode('utf-8-sig'))

def clone(f,**values):
    g=types.FunctionType(f.__code__,dict(f.__globals__,**values),f.__name__,f.__defaults__,f.__closure__);g.__kwdefaults__=f.__kwdefaults__;return g


def definitions(ref,names,namespace):
    tree=ast.parse(small(ref).decode('utf-8-sig'),filename=ref['path'])
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))and n.name in names]
    need({n.name for n in nodes}==set(names),'EXACT_FROZEN_ORIGINAL_SOURCE_DEFINITIONS')
    exec(compile(ast.Module(body=nodes,type_ignores=[]),ref['path'],'exec'),namespace)
    return {name:namespace[name]for name in names}


class Store:
    def __init__(self,root,limit,budget=None):self.root=P(root);self.limit=limit;self.budget=budget;self.charged=0
    def reserve(self,n):
        self.charged+=n;need(self.charged+(1<<20)<self.limit,'FINITE_OWN_OUTPUT_PARTITION')
        if self.budget:self.budget.check()
    def write(self,path,body):
        path=P(path);need(self.root in path.parents and not path.exists()and not any(p.is_symlink()for p in(path,*path.parents)),'FRESH_OWN_OUTPUT')
        self.reserve(len(body)+4096);path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_name(path.name+'.partial_'+uuid.uuid4().hex)
        with temp.open('xb')as f:f.write(body);f.flush();os.fsync(f.fileno())
        os.replace(temp,path);fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        return dict(path=str(path),bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
    def json(self,path,value):return self.write(path,Science.O.canonical(value)+b'\n')


class Budget:
    """Compatibility calls only; actual quota/Parent/time remains the monitor."""
    def __init__(self,monitor,plan,proof,local,persistent):
        self.monitor=monitor;self.plan=plan;self.proof=proof;self.local_workspace_directory=P(local);self.persistent=P(persistent)
        self.local_cap=plan['resource_binding']['local_workspace_cap_bytes'];self.persistent_cap=plan['persistent_cap_bytes'];self.last=None;self.forecast_records=max(1,plan['maximum_assigned_records'])
    def check(self,*args,**kwargs):
        self.monitor.check()
        from workflows.data_v1_final.labels.normalization_compact_runtime_v2.runtime import remaining_wall
        import time
        elapsed=self.monitor.cfg['wall_seconds']-remaining_wall(self.monitor.clock,time.monotonic())
        need(16*elapsed<=2*self.forecast_records*(9.328+2.144),'USER_CONFIRMATION_REQUIRED_ABOVE_TWO_TIMES_SCOPE_FORECAST')
        # Only newly owned work/output trees, metadata stat, no DB connection.
        def sizes(root,cap):
            total=0;count=0;stack=[root];seen=set()
            while stack:
                directory=stack.pop()
                with os.scandir(directory)as entries:
                    for e in entries:
                        try:s=e.stat(follow_symlinks=False)
                        except FileNotFoundError:continue
                        count+=1;need(count<=65536 and s.st_uid==1278,'BOUNDED_OWN_STAGING_METADATA')
                        if stat.S_ISDIR(s.st_mode):stack.append(P(e.path))
                        else:
                            need(stat.S_ISREG(s.st_mode)and s.st_nlink==1,'OWN_STAGING_FILE_NO_ALIAS')
                            inode=(s.st_dev,s.st_ino)
                            if inode not in seen:total+=s.st_size;seen.add(inode)
                        need(total<=cap,'OWN_STAGING_LOGICAL_CAP')
            return total
        import time
        if time.monotonic()<getattr(self,'next',0):return
        self.next=time.monotonic()+5
        self.last=dict(local_logical_bytes=self.monitor.local_bytes(),Lustre_logical_bytes=sizes(self.persistent,self.persistent_cap),allocation_credit_bytes=0)
    def report(self):self.next=0;self.check();return self.last