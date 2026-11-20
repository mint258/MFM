"""GPU execution admission for authorized downstream neural models only.

B0's CPU-only producer admission remains unchanged. This runtime uses the same
UID quota and model reserve, checks actual node root/tmp capacity, and holds the
existing cross-window GPU UUID flock for its entire native process lifetime.
"""
import ast
import csv
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from workflows.benchmark_data.acquire import guard, quota_headroom

GPU_NODES=frozenset("compute-0-"+str(i) for i in range(8))|{"compute-0-20","compute-0-22"}
LOCK_ROOT=Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks")
MODEL_RESERVE=114569896448
GIB=1024**3

def gpu_admission(card, contexts, expected_uuid, minimum_free_mib=18432):
    if card["uuid"]!=expected_uuid:
        raise RuntimeError("Actual GPU UUID differs from the scheduled card")
    used,total=float(card["used_mib"]),float(card["total_mib"])
    if total<=0 or used<0 or used/total>.30 or total-used<minimum_free_mib:
        raise RuntimeError("Actual free GPU memory does not cover the planned neural job")
    if float(card.get("utilization_percent",0))>5:
        raise RuntimeError("Actual GPU activity is not idle for this small-task launch")
    if any(row["gpu_uuid"]==expected_uuid for row in contexts):
        raise RuntimeError("An existing compute context owns this small-task GPU")
    return dict(card)

def root_capacity(stat, needed, same_root_filesystem=True):
    total=stat.f_blocks*stat.f_frsize;available=stat.f_bavail*stat.f_frsize
    reserve=max(10*GIB,.10*total) if same_root_filesystem else max(GIB,.10*total)
    if available<reserve+needed or stat.f_favail<2000:
        raise RuntimeError("Native root/tmp bytes or inodes would cross system/Slurm reserve")
    return dict(total_bytes=total,available_bytes=available,reserved_bytes=int(reserve),
                future_local_bytes=needed,available_inodes=stat.f_favail)

def quota_observation(record, uid, now):
    if (record.get("uid")!=uid or record.get("generation")!="benchmarkB020261119" or
            record.get("returncode")!=0 or not 0<=now-record.get("observed_epoch",-1)<=90):
        raise RuntimeError("Missing/stale/mismatched native UID quota observation")
    return quota_headroom(record["raw"],uid)

def validate_model_selector(selected,learner):
    if selected and not (selected=="Chemprop-v2" if learner=="Chemprop-v2" else selected.startswith("C1-TabPFN-")):
        raise RuntimeError("Scheduled native model selector does not match its authorized neural GPU learner")

class GpuRuntime:
    def __init__(self, root, snapshot, *, gpu_uuid, expected_node, learner, minimum_free_mib=18432):
        if learner not in ("Chemprop-v2","TabPFN"):raise ValueError("A neural GPU learner is required")
        self.root=Path(root);self.snapshot=Path(snapshot)
        self.node=socket.gethostname().split(".")[0];self.job=os.environ.get("SLURM_JOB_ID")
        if self.node not in GPU_NODES or self.node!=expected_node or not self.job:
            raise RuntimeError("A matching actual development GPU-node Slurm allocation is required")
        if int(os.environ.get("SLURM_CPUS_PER_TASK","0"))<1:
            raise RuntimeError("Actual demand-based Slurm CPU allocation is required")
        validate_model_selector(os.environ.get("BENCHMARK_MODEL",""),learner)
        self.gpu_uuid=gpu_uuid;self.learner=learner
        self.protect(self.root,16*1024**2,self.snapshot,own_concurrent_bytes=40*GIB)
        if not LOCK_ROOT.is_dir():
            raise RuntimeError("The established cross-window GPU lock root is unavailable")
        self.lock=(LOCK_ROOT/(gpu_uuid+".lock")).open("a")
        fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        raw=subprocess.check_output(["nvidia-smi","--query-gpu=uuid,memory.used,memory.total,name,utilization.gpu",
                    "--format=csv,noheader,nounits"],text=True,timeout=30)
        cards=[dict(uuid=r[0].strip(),used_mib=float(r[1]),total_mib=float(r[2]),name=r[3].strip(),utilization_percent=float(r[4]))
               for r in csv.reader(raw.splitlines()) if len(r)>=5]
        matches=[c for c in cards if c["uuid"]==gpu_uuid]
        if len(matches)!=1:raise RuntimeError("Scheduled physical GPU UUID is absent")
        raw=subprocess.check_output(["nvidia-smi","--query-compute-apps=gpu_uuid,pid",
                    "--format=csv,noheader,nounits"],text=True,timeout=30)
        contexts=[dict(gpu_uuid=r[0].strip(),pid=r[1].strip()) for r in csv.reader(raw.splitlines()) if len(r)>=2]
        card=gpu_admission(matches[0],contexts,gpu_uuid,minimum_free_mib)
        self.started_epoch=time.time();self.started_monotonic=time.monotonic()
        self.folder=self.root.parent/"benchmark_B1_20261119"/"gpu_runtime"/("job_"+self.job)
        self.protect(self.root,64*1024**2,self.snapshot,own_concurrent_bytes=40*GIB)
        self.folder.mkdir(parents=True,exist_ok=False);temporary=self.folder/"tmp";temporary.mkdir()
        for key in ("TMPDIR","TMP","TEMP","XDG_CACHE_HOME","MPLCONFIGDIR","CUDA_CACHE_PATH"):
            os.environ[key]=str(temporary/key.lower())
            Path(os.environ[key]).mkdir()
        os.environ["CUDA_VISIBLE_DEVICES"]=gpu_uuid
        self.record=dict(status="ADMITTED_FOR_AUTHORIZED_NEURAL_GPU_JOB",job=self.job,node=self.node,
            gpu_uuid=gpu_uuid,learner=learner,pid=os.getpid(),uid=os.getuid(),
            cpus=int(os.environ["SLURM_CPUS_PER_TASK"]),started_epoch=self.started_epoch,
            initial_GPU=card,existing_compute_contexts=[],shared_GPU_lock=str(LOCK_ROOT/(gpu_uuid+".lock")),
            Slurm_GPU_GRES_requested=False,Slurm_exclusive_requested=False,
            GPU_used_by_recipe9M=False,root_tmp_reserve=self.local_capacity(),
            output_filesystem=str(self.root),quota_snapshot=str(self.snapshot),
            model_reserve_bytes=MODEL_RESERVE,own_concurrent_peak_bytes=40*GIB,
            temporary_outputs=str(temporary),scientific_hyperparameters_or_labels_changed=False,
            CPU_statistics_deferred=True,unit_tests_executed_on_GPU_node=False,
            CPU_program_preparation='Compiled on an owned CPU-node step; GPU task loads the closed prepared program')
        self.manifest=self.folder/"admission.json"
        self.manifest.write_text(json.dumps(self.record,indent=2)+"\n")
        print("DOWNSTREAM_GPU_ADMITTED",self.job,self.node,self.gpu_uuid,learner,flush=True)

    def local_capacity(self):
        root_stat=os.statvfs("/")
        root_device=os.stat("/").st_dev
        result={"/":root_capacity(root_stat,16*1024**2)}
        result["/tmp"]=root_capacity(os.statvfs("/tmp"),16*1024**2,os.stat("/tmp").st_dev==root_device)
        return result

    def quantum_future(self):
        forecast=0
        for folder in (self.root/"labels/Pprime/shared_v1",
                       self.root/"directive19/uniform_Sprime/labels/Pprime/shared_v1"):
            access_path=folder/"access.json"
            if not access_path.is_file():
                raise RuntimeError("Native concurrent quantum-write capacity declaration is missing")
            access=json.loads(access_path.read_text())
            if access.get("immutable") and access.get("cross_node_read_allowed"):continue
            existing=sum(p.stat().st_size for p in folder.glob("*.sqlite"))
            forecast+=max(0,80000000000-existing)
        return forecast

    def protect(self, root, needed, snapshot, own_concurrent_bytes=40*GIB):
        if Path(root).resolve()!=self.root.resolve():
            raise ValueError("GPU model output guard was called for an undeclared filesystem root")
        self.local_capacity()
        observation=json.loads(Path(snapshot).read_text())
        remaining=quota_observation(observation,os.getuid(),time.time())
        guard(self.root,needed+self.quantum_future(),remaining,time.monotonic(),
              MODEL_RESERVE+max(40*GIB,own_concurrent_bytes))

    def finish(self, status, error=None, torch_module=None):
        self.protect(self.root,1024**2,self.snapshot,own_concurrent_bytes=40*GIB)
        values=dict(self.record,status=status,finished_epoch=time.time(),
            native_GPU_owned_seconds=time.monotonic()-self.started_monotonic,error=error)
        if torch_module is not None:
            values["torch_version"]=torch_module.__version__
            values["CUDA_runtime_version"]=torch_module.version.cuda
            values["actual_CUDA_context_initialized"]=torch_module.cuda.is_initialized()
            values["maximum_CUDA_allocated_bytes"]=torch_module.cuda.max_memory_allocated() if torch_module.cuda.is_initialized() else None
        (self.folder/"finished.json").write_text(json.dumps(values,indent=2)+"\n")
        print("DOWNSTREAM_GPU_NATIVE_BODY_CLOSED",self.job,status,values["native_GPU_owned_seconds"],flush=True)
        # Keep the lock descriptor alive until the native process exits.

def prepare_neural_source(source, learner):
    """Route the actual neural call to GPU and defer bootstrap/report statistics."""
    if learner not in ("Chemprop-v2","TabPFN"):
        raise ValueError("Only the explicitly authorized neural GPU learners may use this adapter")
    class Adapter(ast.NodeTransformer):
        def visit_ImportFrom(self,node):
            if node.module=="workflows.benchmark_data.admission":
                other=[a for a in node.names if a.name!="protect"]
                nodes=[]
                if other:nodes.append(ast.ImportFrom(module=node.module,names=other,level=node.level))
                if any(a.name=="protect" for a in node.names):
                    nodes.append(ast.Assign(targets=[ast.Name(id="protect",ctx=ast.Store())],
                        value=ast.Attribute(value=ast.Name(id="_gpu_runtime",ctx=ast.Load()),attr="protect",ctx=ast.Load())))
                return nodes
            return node
        def visit_FunctionDef(self,node):
            if node.name in ("score","mean_reference_metrics"):
                replacement=ast.parse("def "+node.name+"(*args, **kwargs):\n"
                    "    return dict(metric_status='PENDING_CPU_STATISTICS', n_test_rows=len(args[0]), bootstrap_draws=0, CPU_statistics_deferred=True)\n").body[0]
                return ast.copy_location(replacement,node)
            return self.generic_visit(node)
        def visit_If(self,node):
            if any(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute)
                   and x.func.attr=="TextTestRunner" for x in ast.walk(node.test)):
                return ast.copy_location(ast.Pass(),node)
            return self.generic_visit(node)
        def visit_Call(self,node):
            node=self.generic_visit(node)
            for keyword in node.keywords:
                if isinstance(keyword.value,ast.Constant) and keyword.value.value=="cpu":
                    if learner=="Chemprop-v2" and keyword.arg=="accelerator":keyword.value=ast.Constant(value="gpu")
                    if learner=="TabPFN" and keyword.arg=="device":keyword.value=ast.Constant(value="cuda")
            if (learner=="Chemprop-v2" and isinstance(node.func,ast.Attribute) and node.func.attr=="Trainer"
                    and not any(k.arg=="precision" for k in node.keywords)):
                node.keywords.append(ast.keyword(arg="precision",value=ast.Constant(value="32-true")))
            return node
        def visit_Assign(self,node):
            node=self.generic_visit(node)
            if any(isinstance(t,ast.Name) and t.id in ("official_score","official_value") for t in node.targets):
                node.value=ast.Constant(value=None)
            return node
    tree=Adapter().visit(ast.parse(source));ast.fix_missing_locations(tree)
    answer=ast.unparse(tree)+"\n"
    # Validate the generated program only; no scientific payload is executed here.
    compile(answer,"authorized_downstream_neural_GPU_program","exec")
    return answer
