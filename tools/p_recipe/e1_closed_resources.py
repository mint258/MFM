"""Settle one actually closed E1 output component; never delete any output."""
import argparse,json,os,stat,time
from pathlib import Path
from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import require_cpu_admission,atomic_json
import shared_guard

def run(c):
    with CooperativeStop() as stop:
        set_actual_deadline(c,stop);require_cpu_admission(c)
        Path(c["output"]).mkdir(parents=True,exist_ok=True)
        observations=json.loads(Path(c["owned_closure_proof"]).read_text())
        closed={}
        for item in observations:
            if item["code"]!=0:raise ValueError("Actual owned exit observation failed")
            for row in json.loads(item["stdout"])["closures"]:
                reap=[x for x in row["events"] if x["phase"]=="OWNED_TREE_REAPED"]
                terminal=[x for x in row["events"] if x["phase"]=="RESIDENT_TERMINAL"]
                if (len(reap)==1 and reap[0]["root_returncode"]==0 and len(terminal)==1 and
                        terminal[0]["returncode"]==0 and terminal[0]["remaining_children"]==[] and
                        row["actual_roots_absent"] and all(row["actual_roots_absent"].values())):
                    closed[row["job"]]=True
        if not set(c["closed_GPU_jobs"])<=closed.keys():raise ValueError("All twelve owned closures required")
        seen=set();rows=[]
        for config in c["component_configurations"]:
            native=json.loads(Path(config).read_text());root=Path(native["output"])
            summary=json.loads((root/"summary.json").read_text())
            if summary.get("status")!="COMPLETE" or int(summary["job_id"]) not in c["closed_GPU_jobs"]:
                raise ValueError("Only exact closed F outputs may settle")
            total=0
            for p in [root,*root.rglob("*")]:
                s=p.lstat()
                if s.st_uid!=1278:raise ValueError("Closed output owner differs")
                identity=(s.st_dev,s.st_ino)
                if (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)) and identity not in seen:
                    total+=s.st_blocks*512;seen.add(identity)
            rows.append(dict(run=native["run"],path=str(root),allocated_physical_bytes=total))
        scope_path=Path(c["claim_scope"]);scope=json.loads(scope_path.read_text())
        settled=scope.setdefault("E1_closed_components",{})
        if c["component"] in settled:raise ValueError("This closed component has already settled; reuse receipt")
        entry=next(x for x in scope["fixed_entries"] if x["id"]=="P_E1_NFS_future")
        cap=scope.setdefault("E1_total_peak_bytes",entry["bytes"]+sum(x["allocated_physical_bytes"] for x in settled.values()))
        allocated=sum(x["allocated_physical_bytes"] for x in rows)
        settled[c["component"]]=dict(allocated_physical_bytes=allocated,rows=rows,closed_GPU_jobs=c["closed_GPU_jobs"])
        future=cap-sum(x["allocated_physical_bytes"] for x in settled.values())
        if future<0:raise ValueError("Original total E1 peak requires explicit revision")
        before=entry["bytes"];entry["bytes"]=future
        entry["basis"]="Original32GiB total E1 peak minus actually closed own component allocations; live writer/atomic-replacement peaks and all files preserved"
        for row in scope["fixed_entries"]:
            if row["id"] in c["release_unused_future_ids"]:row["bytes"]=0
        if stop.requested:return 75
        atomic_json(scope_path,scope)
        claim_path=shared_guard.REGISTRY/"p-recipe.json";claim=json.loads(claim_path.read_text())
        changed={x["id"]:x["bytes"] for x in scope["fixed_entries"] if x["id"]=="P_E1_NFS_future" or x["id"] in c["release_unused_future_ids"]}
        for row in claim["entries"]:
            if row["id"] in changed:row["bytes"]=changed[row["id"]]
        shared_guard.claim("p-recipe",claim["entries"])
        result=dict(status="COMPLETE",job=os.environ["SLURM_JOB_ID"],component=c["component"],
            total_E1_peak_bytes=cap,closed_component_allocated_bytes=allocated,
            old_remaining_future_bytes=before,new_remaining_future_bytes=future,
            released_unused_future_ids=c["release_unused_future_ids"],rows=rows,
            physical_bytes_deleted=0,all_outputs_preserved=True,live_peaks_and_peer_reserves_changed=False,
            settled_at=time.time())
        atomic_json(Path(c["output"])/"summary.json",result);print(json.dumps(result),flush=True);return 0

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",type=Path,required=True)
    a=p.parse_args()
    if os.environ.get("CUDA_VISIBLE_DEVICES")!="":raise ValueError("CPU metadata only")
    raise SystemExit(run(json.loads(a.configuration.read_text())))
