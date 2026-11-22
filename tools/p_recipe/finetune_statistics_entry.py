"""CPU-only primary F statistics; resume the same molecular draws, never refit."""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import socket
import time

from finetune_entry import (CooperativeStop, set_actual_deadline,
                            validate_output_filesystem)
import exit_lifecycle as lifecycle
import shared_guard
from finetune_statistics import summarize, TASKS


def require_cpu_admission(c):
    node = socket.gethostname().split(".")[0]
    if node != c["node"] or node not in {"compute-0-"+str(i) for i in range(8,20)}:
        raise ValueError("Statistics must run on the configured CPU node")
    if node in set(c["excluded_nodes"]):
        raise ValueError("Known fault channel excluded")
    parent, current = lifecycle.identity(os.getppid()), lifecycle.identity(os.getpid())
    if (os.environ.get("D_EXIT_OUTER_SUPERVISION") != "1"
            or os.getppid() != int(os.environ["D_RESIDENT_SUPERVISOR_PID"])
            or parent is None or current is None or parent.uids != (1278,)*4
            or parent.start_ticks != int(os.environ["D_RESIDENT_SUPERVISOR_START_TICKS"])
            or parent.cgroup != current.cgroup):
        raise ValueError("Resident supervisor identity/cgroup not verified")
    claim = json.loads((shared_guard.REGISTRY/"p-recipe.json").read_text())
    own = {e["id"]:e for e in claim["entries"]}
    if claim["expires"] <= time.time() or not set(c["reservation_ids"]) <= own.keys():
        raise ValueError("Current own CPU statistics claims absent")
    entries = list(own.values())
    paths = shared_guard._same_device("node_disk","/tmp")
    disk = sum(e["bytes"] for e in entries if e["kind"]=="node_disk"
               and e.get("node")==node and e.get("path") in paths)
    ram = sum(e["bytes"] for e in entries if e["kind"]=="node_ram" and e.get("node")==node)
    mount = c["output_mount"]
    validate_output_filesystem(c["output"],mount)
    future = sum(e["bytes"] for e in entries if e["kind"]=="shared_fs" and e.get("path")==mount)
    if ram<c["ram_peak_bytes"] or future<c["remaining_output_bytes"]:
        raise ValueError("Own aggregate future does not contain this statistics phase")
    shared_guard.check_with_timeout("p-recipe","node_disk",disk,path="/tmp",node=node)
    shared_guard.check_with_timeout("p-recipe","node_ram",ram,node=node)
    shared_guard.check_with_timeout("p-recipe","shared_fs",future,path=mount)


def fingerprint(path):
    p=Path(path);s=p.stat()
    return dict(path=str(p),bytes=s.st_size,mtime_ns=str(s.st_mtime_ns))


def bindings(c):
    def tasks(table):
        if set(table)!=set(TASKS):
            raise ValueError("Exact registered four-task coverage required")
        return {task:[fingerprint(p) for p in paths] for task,paths in table.items()}
    return dict(scratch=tasks(c["scratch"]),random_reference=tasks(c["reference"]),
                conditions={k:tasks(v) for k,v in c["groups"].items()},
                frozen={k:tasks(v) for k,v in c["frozen"].items()},
                scientific_protocol="F_20261122B_fixed")


def atomic_json(path,value):
    temporary=path.with_name(path.name+".new")
    with temporary.open("w") as stream:
        json.dump(value,stream,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


def run(c):
    # All imports of heavy scientific packages happen after CPU/resource admission.
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop)
        require_cpu_admission(c)
        output=Path(c["output"])
        output.mkdir(parents=True,exist_ok=True)
        with (output/"owner.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (output/"primary_complete.json").exists():
                raise ValueError("This primary producer is closed; do not repeat")
            identity=bindings(c)
            import torch
            from phychem_mfm.phase1.v3_dev_evaluation_v2 import _unpack
            torch.set_num_threads(1)
            cache={}
            def load_prediction(path):
                if path not in cache:
                    raw=torch.load(path,map_location="cpu",weights_only=False)
                    cache[path]=_unpack(raw["prediction"] if "prediction" in raw else raw)
                return cache[path]
            def load_many(table,count):
                result={}
                for task,paths in table.items():
                    if len(paths)!=count:
                        raise ValueError("Missing registered seed or duplicated frozen seed")
                    result[task]=[load_prediction(path) for path in paths]
                return result
            for path in c["required_complete_summaries"]:
                if json.loads(Path(path).read_text()).get("status")!="COMPLETE":
                    raise ValueError("A source fine-tune is not complete")
            groups={name:load_many(tasks,3) for name,tasks in c["groups"].items()}
            scratch=load_many(c["scratch"],3)
            reference={t:values[0] for t,values in load_many(c["reference"],1).items()}
            frozen={name:{t:values[0] for t,values in load_many(tasks,1).items()}
                    for name,tasks in c["frozen"].items()}
            if bindings(c)!=identity:
                raise ValueError("Source files changed during the primary load")
            checkpoint=output/"primary_checkpoint.json"
            state=json.loads(checkpoint.read_text()) if checkpoint.exists() else None
            started=time.time()
            def should_stop():
                return (stop.requested or time.time()+c["work_unit_seconds"] >=
                        float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"]))
            result=summarize(groups,scratch,reference,input_identity=identity,
                frozen=frozen,state=state,checkpoint=lambda s:atomic_json(checkpoint,s),
                should_stop=should_stop)
            if result["status"]!="COMPLETE":
                return 75
            atomic_json(output/"primary.json",result)
            tmp=output/"rows.csv.new"
            with tmp.open("w",newline="") as stream:
                writer=csv.DictWriter(stream,fieldnames=list(result["rows"][0]))
                writer.writeheader();writer.writerows(result["rows"])
                stream.flush();os.fsync(stream.fileno())
            os.replace(tmp,output/"rows.csv")
            summary=dict(status="COMPLETE",run=c["run"],job_id=os.environ["SLURM_JOB_ID"],
                node=c["node"],cpu_seconds_this_attempt=time.time()-started,
                rows=len(result["rows"]),bootstrap_draws=1000,bootstrap_seed=20261025,
                estimator="three_seed_point_mean_and_mean_prediction_molecular_CI_separate",
                frozen_reused_seed0=True,new_frozen_fits=0,input_identity=identity)
            atomic_json(output/"primary_complete.json",summary)
            print(json.dumps({k:v for k,v in summary.items() if k!="input_identity"}),flush=True)
            return 0


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--configuration",type=Path,required=True)
    args=parser.parse_args()
    c=json.loads(args.configuration.read_text())
    if c.get("ready") is not True or os.environ.get("CUDA_VISIBLE_DEVICES")!="":
        raise ValueError("Activated CPU-only configuration required")
    return run(c)


if __name__=="__main__":
    raise SystemExit(main())
