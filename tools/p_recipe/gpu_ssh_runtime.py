"""Bounded, pinned GPU SSH execution; never fabricates a Slurm job identity."""
import argparse
from dataclasses import asdict
import fcntl
import json
import math
import os
from pathlib import Path
import resource
import socket
import sys
import time
import exit_lifecycle as life

UID = 1278
CPU_NODES = {"compute-0-20","compute-0-22"}

def execution_handle():
    if os.environ.get("SLURM_JOB_ID"):
        return os.environ["SLURM_JOB_ID"]
    value = os.environ.get("P_GPU_SSH_EXECUTION_ID")
    if not value or not value.startswith("ssh:P_"):
        raise ValueError("A real Slurm or explicitly recorded SSH handle is required")
    return value

def execution_backend():
    return "ssh_gpu" if os.environ.get("P_GPU_SSH_EXECUTION_ID") else "slurm_cpu"

def atomic(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+".tmp."+str(os.getpid()))
    with temporary.open("x") as stream:
        json.dump(value,stream,allow_nan=False,indent=2)
        stream.write("\n");stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)

def verified_deadline(c):
    if os.environ.get("SLURM_JOB_ID") or c.get("execution_backend") != "ssh_gpu":
        raise ValueError("SSH execution must not impersonate a Slurm job")
    handle = execution_handle()
    path = c["ssh_runtime_receipt"]
    if handle != c["ssh_execution_id"] or path != os.environ.get("P_GPU_SSH_RECEIPT"):
        raise ValueError("SSH configuration/receipt handle mismatch")
    record = json.loads(Path(path).read_text())
    parent,current = life.identity(os.getppid()),life.identity(os.getpid())
    bound = record["supervisor"]
    node = socket.gethostname().split(".")[0]
    if (record["status"] != "RUNNING" or record["execution_id"] != handle
        or node != c["node"] or node != record["node"] or node not in CPU_NODES
        or parent is None or current is None or parent.uids != (UID,)*4
        or current.uids != (UID,)*4 or parent.pid != bound["pid"]
        or parent.start_ticks != bound["start_ticks"]
        or parent.cgroup != bound["cgroup"] or current.cgroup != parent.cgroup
        or set(os.sched_getaffinity(0)) != set(record["cores"])
        or set(os.sched_getaffinity(parent.pid)) != set(record["cores"])):
        raise ValueError("Actual SSH parent UID/start/cgroup/CPU affinity differs")
    reserve,unit = c["cleanup_seconds"],c["work_unit_seconds"]
    end = record["hard_end_epoch"]
    if (type(reserve) is not int or reserve < 180 or not isinstance(unit,(int,float))
        or not math.isfinite(unit) or unit <= 0 or not math.isfinite(end)
        or end-time.time() <= reserve
        or not 1800 <= record["timeout_seconds"] <= 8*3600):
        raise ValueError("Finite SSH deadline and cleanup window required")
    os.environ["P_MANAGED_HARD_END"] = str(end)
    os.environ["P_MANAGED_STOP_NEW_UNITS_AT"] = str(end-reserve)
    os.environ["P_MANAGED_UNIT_SECONDS"] = str(unit)
    return end

def cpu_snapshot():
    found={}
    for line in Path("/proc/stat").read_text().splitlines():
        fields=line.split()
        if fields and fields[0].startswith("cpu") and fields[0][3:].isdigit():
            values=list(map(int,fields[1:9]))
            found[int(fields[0][3:])]=(sum(values),values[3])
    return found

def run(c):
    node=socket.gethostname().split(".")[0]
    if (os.getuid()!=UID or node!=c["node"] or node not in CPU_NODES
        or os.environ.get("SLURM_JOB_ID")):
        raise ValueError("Actual non-Slurm CPU host/UID required")
    print(json.dumps(dict(phase="GPU_SSH_PREFLIGHT_IDENTITY",supervisor=asdict(life.identity(os.getpid())),execution_id=c["execution_id"])),flush=True)
    cores=c["cores"]
    if not cores or len(cores)>16 or len(set(cores))!=len(cores):
        raise ValueError("One distinct actually idle core per requested CPU")
    if set(os.sched_getaffinity(0))!=set(cores):
        raise ValueError("taskset affinity does not match the registered cores")
    timeout=c["timeout_seconds"]
    if timeout!=min(8*3600,max(2*c["expected_seconds"],1800)):
        raise ValueError("SSH timeout differs from the user scheduling rule")
    runtime_lock=open(c["receipt"]+".owner.lock","a")
    fcntl.flock(runtime_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if Path(c["receipt"]).exists():
        raise ValueError("Original SSH attempt already recorded; inspect it, do not relaunch")
    locks=[]
    for core in cores:
        stream=open("/tmp/P_GPU_SSH_1278_core%d.lock"%core,"a")
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(stream)
    before=cpu_snapshot();time.sleep(5);after=cpu_snapshot()
    idle={core:(after[core][1]-before[core][1])/max(1,after[core][0]-before[core][0])
          for core in cores}
    # GPU20/22 hybrid CPU sharing is explicitly user-authorized; actual load is recorded.
    mem={line.split(":")[0]:int(line.split()[1])*1024
         for line in Path("/proc/meminfo").read_text().splitlines()
         if line.startswith("MemAvailable:")}
    root=os.statvfs("/")
    reserve=max(10*2**30,(root.f_blocks*root.f_frsize+9)//10)
    if (mem["MemAvailable"] < c["ram_peak_bytes"]+4*2**30
        or root.f_bavail*root.f_frsize < reserve+c["root_future_bytes"]
        or root.f_favail<10000 or os.stat("/tmp").st_dev!=os.stat("/").st_dev):
        raise ValueError("Actual node RAM/root filesystem allowance unavailable")
    life.enable_subreaper()
    me=life.identity(os.getpid())
    if me is None or me.uids!=(UID,)*4:
        raise ValueError("Actual SSH supervisor identity unavailable")
    scope=next(line for line in me.cgroup.splitlines() if line.startswith("0::"))
    os.environ["P_CPU_SSH_EXECUTION_ID"]=c["execution_id"]  # existing lifecycle explicit-SSH opt-in
    started=time.time()
    record=dict(schema="P_GPU_SSH_RUNTIME_20261126_V1",status="RUNNING",
        execution_id=c["execution_id"],node=node,supervisor=asdict(me),
        parent=asdict(life.identity(os.getppid())),session_id=os.getsid(0),launcher=asdict(life.identity(os.getsid(0))),gpu_uuid=c["gpu_uuid"],
        cores=cores,idle_fraction=idle,MemAvailable=mem["MemAvailable"],
        started_at=started,hard_end_epoch=started+timeout-10,
        timeout_seconds=timeout,cleanup_seconds=c["cleanup_seconds"],
        original_pending_job=c.get("original_pending_job"),
        worker_argv=c["worker_argv"],scientific_code_and_outputs_preserved=True)
    for key in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"):
        os.environ[key]=str(len(cores))
    os.environ["CUDA_VISIBLE_DEVICES"]=c["gpu_uuid"]
    os.environ["D_EXIT_OUTER_SUPERVISION"]="1"
    os.environ["D_RESIDENT_SUPERVISOR_PID"]=str(me.pid)
    os.environ["D_RESIDENT_SUPERVISOR_START_TICKS"]=str(me.start_ticks)
    os.environ["P_GPU_SSH_EXECUTION_ID"]=c["execution_id"]
    os.environ["P_GPU_SSH_RECEIPT"]=c["receipt"]
    atomic(c["receipt"],record)
    print(json.dumps(dict(phase="SSH_RESIDENT_STARTED",**record)),flush=True)
    baseline=resource.getrusage(resource.RUSAGE_CHILDREN)
    events=[]
    def report(event):
        events.append(event);print(json.dumps(event),flush=True)
    def request_stop():
        for pid in life.children(os.getpid()):
            owned=life.identity(pid)
            if owned is not None:life.signal_owned(owned,__import__("signal").SIGUSR1,uid=UID,scope=scope)
    result=life.supervise(c["worker_argv"],end_epoch=record["hard_end_epoch"],
        scope=scope,grace_seconds=c["cleanup_seconds"],ssh_identity=me,report=report,request_stop=request_stop)
    source_exit=next((e["root_returncode"] for e in reversed(events) if e.get("phase")=="OWNED_TREE_REAPED"),None)
    if result==75 and source_exit not in (0,75):result=source_exit if source_exit is not None else 1
    if result==75 and source_exit==0 and (Path(c["output"])/"primary_complete.json").exists():result=0
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    remaining=sorted(life.children(os.getpid()))
    record.update(status="COMPLETE" if result==0 and not remaining else
        ("CURSOR_SAVED_NOT_COMPLETE" if result==75 else "FAILED"),
        returncode=result,ended_at=time.time(),wall_seconds=time.time()-started,
        user_cpu_seconds=usage.ru_utime-baseline.ru_utime,
        system_cpu_seconds=usage.ru_stime-baseline.ru_stime,
        actual_cpu_seconds=(usage.ru_utime+usage.ru_stime-
                            baseline.ru_utime-baseline.ru_stime),
        peak_child_RSS_KiB=usage.ru_maxrss,remaining_children=remaining,
        owned_tree_reaped=any(e.get("phase")=="OWNED_TREE_REAPED" for e in events))
    atomic(c["receipt"],record)
    print(json.dumps(dict(phase="SSH_RESIDENT_TERMINAL",**record)),flush=True)
    return 128-result if result<0 else result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--configuration",required=True)
    arguments=parser.parse_args()
    return run(json.loads(Path(arguments.configuration).read_text()))

if __name__=="__main__":
    raise SystemExit(main())
