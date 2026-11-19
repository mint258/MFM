"""Capacity lease for bounded writes through the existing SSHFS connection."""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import time
from .acquire import guard, quota_headroom, safe_asset

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--datasets",nargs="+",required=True)
    p.add_argument("--attempt",required=True)
    p.add_argument("--quota-snapshot",type=Path)
    a=p.parse_args()
    if not a.attempt.isalnum():raise ValueError("invalid transfer identity")
    plan=json.loads(a.plan.read_text());root=Path(plan["data_root"])
    expected={(group,safe_asset(asset)):asset for group in a.datasets
              for asset in plan["assets"][group]["files"]}
    peak=2*sum(x["bytes"] for x in expected.values())+16777216
    def quota():
        if a.quota_snapshot:
            snap=json.loads(a.quota_snapshot.read_text())
            age=time.time()-snap["observed_epoch"]
            if (snap["uid"]!=os.getuid() or snap["returncode"]!=0
                    or not 0<=age<=90 or snap["generation"]!="benchmarkB020261119"):
                raise RuntimeError("quota publisher missing, stale or mismatched")
            return quota_headroom(snap["raw"],os.getuid()),time.monotonic()
        raw=subprocess.check_output(["ssh","-n","-o","BatchMode=yes","-o","ConnectTimeout=10",
             "sonmi","quota","-v","-u","zixiao"],text=True,timeout=60)
        return quota_headroom(raw,os.getuid()),time.monotonic()
    remaining,observed=quota()
    guard(root,peak,remaining,observed,114569896448)
    control=root/"transfer_control"/a.attempt
    control.mkdir(parents=True,exist_ok=False)
    seq=0
    print("TRANSFER_GUARD",os.getpid(),control,flush=True)
    while True:
        if time.monotonic()-observed>45:
            remaining,observed=quota()
        seq+=1
        try:
            guard(root,peak,remaining,observed,114569896448)
            admitted=True;reason=None
        except RuntimeError as error:
            admitted=False;reason=str(error)
        lease={"attempt":a.attempt,"seq":seq,"pid":os.getpid(),"admitted":admitted,
               "reason":reason,"state":"RUNNING","reserved_new_bytes":peak}
        (control/"lease.json").write_text(json.dumps(lease))
        progress=control/"progress.json"
        if progress.is_file():
            try:s=json.loads(progress.read_text())
            except (ValueError,OSError):s={}
            if s.get("attempt")==a.attempt and s.get("done"):
                if not admitted:raise RuntimeError("capacity unknown at closure; files preserved")
                closed={(x["dataset"],x["name"]) for x in s["closed"]}
                if closed!=set(expected):raise ValueError("incomplete client closed-source catalog")
                for key,asset in expected.items():
                    q=root/"raw"/key[0]/key[1];info=q.lstat()
                    if not stat.S_ISREG(info.st_mode) or info.st_size!=asset["bytes"]:
                        raise ValueError("client transport closure/size differs")
                out=root/"acquisition";out.mkdir(exist_ok=True)
                for group in a.datasets:
                    source=plan["assets"][group]
                    rows=[dict(asset,path=str(root/"raw"/group/asset["name"]),
                         status="DOWNLOADED_VIA_GUARDED_SSHFS") for asset in source["files"]]
                    report={"status":"SOURCE_ASSETS_ACQUIRED","dataset":group,
                        "source_commit":source.get("source_commit"),"source_release":source.get("source_release"),
                        "source_revisions":source.get("source_revisions"),"files":rows,"files_count":len(rows),
                        "declared_bytes":sum(x["bytes"] for x in rows),"numerical_payload_readback":False,
                        "new_content_hashes":False,"filtering_or_training_ready":False,
                        "transport":"official HTTPS and SSHFS; CPU-node live disk/inode/quota lease"}
                    (out/(group+".json")).write_text(json.dumps(report,indent=2)+"\n")
                    print("SOURCE_GROUP_CLOSED",group,len(rows),report["declared_bytes"],flush=True)
                lease.update(state="COMPLETE",admitted=False)
                (control/"lease.json").write_text(json.dumps(lease))
                return
        time.sleep(1)

if __name__=="__main__":main()
