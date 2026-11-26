"""Same-task Slurm takeover after actual SSH checkpoint/exit, without double running."""
import argparse,json,os,signal,socket,sys,time
from pathlib import Path
import exit_lifecycle as lifecycle
from finetune_entry import CooperativeStop
from a5_runtime import set_actual_deadline

def same(bound,current):
    return current is not None and current.pid==bound["pid"] and current.start_ticks==bound["start_ticks"] and current.uids==(1278,)*4 and current.cgroup==bound["cgroup"]

def wait_for_source(c,stop,*,identity=lifecycle.identity,poll=.2):
    sent=False;receipt=Path(c["ssh_runtime_receipt"])
    while True:
        if stop.requested or time.time()+c["work_unit_seconds"]>=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"]):return "WAIT_NOT_COMPLETE"
        record=json.loads(receipt.read_text())
        if (record["execution_id"]!=c["ssh_execution_id"] or record["node"]!=c["node"]
            or record["gpu_uuid"]!=c["gpu_uuid"]):raise ValueError("Different SSH source identity")
        bound=record["supervisor"];current=identity(bound["pid"])
        closed=not same(bound,current) and not same(record["launcher"],identity(record["launcher"]["pid"]))
        if record["status"] in ("COMPLETE","CURSOR_SAVED_NOT_COMPLETE"):
            if (closed and record["owned_tree_reaped"] and not record["remaining_children"]):
                if record["status"]=="COMPLETE" and record["returncode"]==0:return "ALREADY_COMPLETE"
                if record["status"]=="CURSOR_SAVED_NOT_COMPLETE" and record["returncode"]==75:return "RESUME_READY"
            time.sleep(poll);continue
        if record["status"]!="RUNNING" or not same(bound,current):
            raise RuntimeError("Source outcome/owned exit is not proven; never start a duplicate")
        if c.get("handoff_requires_worker_ready"):
            ready=Path(c["ssh_runtime_receipt"]+".worker_ready.json")
            if not ready.exists():time.sleep(poll);continue
            worker=json.loads(ready.read_text())
            if worker["execution_id"]!=c["ssh_execution_id"]:raise ValueError("Different ready worker")
            if not same(worker["worker"],identity(worker["worker"]["pid"])):
                time.sleep(poll);continue
        if not sent:
            scope=next(line for line in current.cgroup.splitlines() if line.startswith("0::"))
            if not lifecycle.signal_owned(current,signal.SIGUSR1,uid=1278,scope=scope):
                raise RuntimeError("SSH source identity changed; no second signal or duplicate")
            sent=True
            print(json.dumps(dict(phase="A5_SAME_TASK_HANDOFF_REQUESTED",source=bound,
                Slurm_job=os.environ.get("SLURM_JOB_ID"),at=time.time())),flush=True)
        time.sleep(poll)

def main():
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True);a=p.parse_args()
    c=json.loads(Path(a.configuration).read_text())
    if not os.environ.get("SLURM_JOB_ID") or socket.gethostname().split(".")[0] not in {"compute-0-20","compute-0-22"}:
        raise ValueError("A5 standby requires its real configured Slurm GPU node")
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop)
        result=wait_for_source(c,stop)
        if result=="WAIT_NOT_COMPLETE":return 75
        if result=="ALREADY_COMPLETE":
            path=Path(c["output"])/"primary_complete.json"
            if not path.exists() or json.loads(path.read_text())["status"]!="GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS":
                raise RuntimeError("Source complete receipt without actual A5 original result")
            print(json.dumps(dict(phase="SSH_ALREADY_FINISHED_NO_REPEAT",job=os.environ["SLURM_JOB_ID"])),flush=True)
            return 0
        os.environ.pop("P_GPU_SSH_EXECUTION_ID",None)
        os.environ.pop("P_CPU_SSH_EXECUTION_ID",None)
        os.execv(sys.executable,[sys.executable,"-B",str(Path(__file__).with_name("a5_readout_entry.py")),"--configuration",a.configuration])
if __name__=="__main__":raise SystemExit(main())
