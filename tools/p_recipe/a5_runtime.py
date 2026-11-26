"""A5 execution routing; original encoder/features/probe protocol stays unchanged."""
import csv,fcntl,json,math,os,socket,time
from pathlib import Path
import exit_lifecycle as lifecycle
import shared_guard
from finetune_entry import (ROOT,REPO,CooperativeStop,validate_output_filesystem,
    set_actual_deadline as slurm_deadline,native_query as slurm_query)
GPU_NODES={"compute-0-"+str(i) for i in range(8)}|{"compute-0-20","compute-0-22"}

def execution_handle():
    if os.environ.get("SLURM_JOB_ID"):return os.environ["SLURM_JOB_ID"]
    value=os.environ.get("P_GPU_SSH_EXECUTION_ID")
    if not value or not value.startswith("ssh:P_A5_"):raise ValueError("Actual A5 execution handle required")
    return value

def set_actual_deadline(c,stop):
    if os.environ.get("SLURM_JOB_ID"):return slurm_deadline(c,stop)
    from gpu_ssh_runtime import verified_deadline
    return verified_deadline(c)

def native_query(argv,stop):
    if os.environ.get("SLURM_JOB_ID"):return slurm_query(argv,stop)
    import subprocess
    current=lifecycle.identity(os.getpid())
    scope=next(line for line in current.cgroup.splitlines() if line.startswith("0::"))
    until=time.monotonic()+min(15,max(0,float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"])-time.time()))
    child=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    bound=lifecycle.identity(child.pid);interrupted=False
    while True:
        try:out,error=child.communicate(timeout=.2);break
        except subprocess.TimeoutExpired:
            if stop.requested or time.monotonic()>=until:
                interrupted=True
                if bound is not None:lifecycle.signal_owned(bound,__import__("signal").SIGTERM,uid=os.getuid(),scope=scope)
                try:out,error=child.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    print(json.dumps(dict(phase="ADMIN_REQUIRED_A5_QUERY_EXIT",pid=child.pid)),flush=True)
                    out,error=child.communicate()
                break
    if interrupted or child.returncode:raise RuntimeError("Actual A5 query did not close normally: "+error.decode("utf8","replace")[-500:])
    return out.decode("utf8")

def admission(c):
    if c.get("kind")!="A5_READOUT":raise ValueError("Only registered A5 readouts")
    node = socket.gethostname().split(".")[0]
    if node != c["node"] or node not in GPU_NODES:
        raise ValueError("A5 requires its actual configured healthy GPU node")
    parent = lifecycle.identity(os.getppid())
    current = lifecycle.identity(os.getpid())
    if (os.environ.get("D_EXIT_OUTER_SUPERVISION") != "1"
            or os.getppid() != int(os.environ["D_RESIDENT_SUPERVISOR_PID"])
            or parent is None or parent.uids != (1278,)*4 or current is None
            or parent.start_ticks != int(os.environ["D_RESIDENT_SUPERVISOR_START_TICKS"])
            or parent.cgroup != current.cgroup):
        raise ValueError("Exact existing-provider parent UID/start/job cgroup is not verified")
    scope = json.loads((shared_guard.REGISTRY / "p-recipe.json").read_text())
    if scope["line"] != "p-recipe" or scope["expires"] < time.time():
        raise ValueError("Current own reservation is absent or expired")
    entries = scope["entries"]
    own = {e["id"]: e for e in entries}
    if not c["reservation_ids"] or not set(c["reservation_ids"]) <= own.keys():
        raise ValueError("Coordinator has not registered this run's future writes/RAM")
    # Own-line simultaneous requests are summed; canonical guard adds all peers.
    paths = shared_guard._same_device("node_disk", "/tmp")
    local = sum(e["bytes"] for e in entries if e["kind"] == "node_disk"
                and e.get("node") == node and e.get("path") in paths)
    ram = sum(e["bytes"] for e in entries if e["kind"] == "node_ram" and e.get("node") == node)
    mount = c["output_mount"]
    validate_output_filesystem(c["output"], mount)
    future = sum(e["bytes"] for e in entries if e["kind"] == "shared_fs" and e.get("path") == mount)
    if local < 32 * 2**20 + 65536 or ram < c["ram_peak_bytes"] or future < c["remaining_output_bytes"]:
        raise ValueError("Own aggregate reservation does not contain this actual run")
    shared_guard.check_with_timeout("p-recipe", "node_disk", local, path="/tmp", node=node)
    # MemAvailable already excludes this worker's allocated anonymous pages.
    # Keep the registered peak, but reserve only its still-unallocated portion.
    owned_anon=next(int(line.split()[1])*1024 for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("RssAnon:"))
    if owned_anon>ram:
        raise shared_guard.AdmissionRefused("Actual own anonymous RAM exceeds registered peak")
    ram_future=ram-owned_anon
    shared_guard.check_with_timeout("p-recipe", "node_ram", ram_future, node=node)
    # The coordinator binds a producer's fresh UID snapshot when one exists.
    # A stale/missing snapshot is not passed as a fictional available-byte value.
    quota = None
    descriptor = c.get("uid_quota_snapshot")
    if descriptor is not None:
        try:
            snapshot = json.loads(Path(descriptor["path"]).read_text())
            age = time.time() - float(snapshot[descriptor["timestamp_field"]])
            if 0 <= age <= descriptor["fresh_seconds"]:
                quota = int(snapshot[descriptor["available_field"]])
        except (OSError, ValueError, KeyError):
            pass  # No fresh optional snapshot; canonical df+registry still apply.
    shared_guard.check_with_timeout("p-recipe", "shared_fs", future,
                                    path=mount, quota_available=quota)
    cache=Path(c["output"])/"cuda_cache";cache.mkdir(parents=True,exist_ok=True)
    os.environ["CUDA_CACHE_PATH"]=str(cache)
    os.environ["TORCH_EXTENSIONS_DIR"]=str(Path(c["output"])/"torch_extensions")
    return node

def gpu_lock_and_check(c,stop):
    node=socket.gethostname().split(".")[0]
    path=ROOT/"docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks"/(c["gpu_uuid"]+".lock")
    lock=path.open("a")
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        text=native_query([c["nvidia_smi"],"--id="+c["gpu_uuid"],
            "--query-gpu=uuid,name,memory.used,memory.total","--format=csv,noheader,nounits"],stop)
        rows=list(csv.reader(text.splitlines()))
        if len(rows)!=1 or rows[0][0].strip()!=c["gpu_uuid"]:raise ValueError("Actual A5 GPU UUID differs")
        uuid,name,used,total=[x.strip() for x in rows[0]];used,total=float(used),float(total)
        if total<24000 or total-used<c["minimum_free_gpu_mib"]:raise ValueError("Actual minimum24GiB capacity/free allowance unavailable")
        contexts=native_query([c["nvidia_smi"],"--query-compute-apps=gpu_uuid,pid","--format=csv,noheader,nounits"],stop)
        if node in {"compute-0-20","compute-0-22"}:
            if used/total>.30:raise ValueError("Initial native GPU memory occupancy exceeds30%")
        elif any(r and r[0].strip()==uuid for r in csv.reader(contexts.splitlines())):
            raise ValueError("0–7 require an empty actual GPU")
        if c.get("handoff_requires_worker_ready") and os.environ.get("P_GPU_SSH_EXECUTION_ID"):
            worker=lifecycle.identity(os.getpid())
            payload=dict(execution_id=c["ssh_execution_id"],worker=worker.__dict__)
            ready=Path(c["ssh_runtime_receipt"]+".worker_ready.json")
            temporary=ready.with_suffix(".tmp");temporary.write_text(json.dumps(payload));temporary.replace(ready)
        return lock,dict(uuid=uuid,name=name,memory_used_mib=used,memory_total_mib=total)
    except BaseException:lock.close();raise
