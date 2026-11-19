"""One SSH channel for multiple bounded B0 source groups."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .acquire import quota_headroom, safe_asset, guard

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--datasets", nargs="+", required=True)
    p.add_argument("--concurrent-reserve-bytes", type=int, required=True)
    a=p.parse_args()
    if len(set(a.datasets))!=len(a.datasets):
        raise ValueError("duplicate dataset group")
    plan=json.loads(a.plan.read_text())
    expected={(group,safe_asset(asset)):asset for group in a.datasets
              for asset in plan["assets"][group]["files"]}
    root=Path(plan["data_root"])
    ancestor=root
    while not ancestor.exists(): ancestor=ancestor.parent
    quota=subprocess.check_output(["ssh","-n","-o","BatchMode=yes","-o","ConnectTimeout=10",
        "sonmi","quota","-v","-u","zixiao"],text=True,timeout=60)
    left=quota_headroom(quota,os.getuid())
    observed=time.monotonic()
    peak=2*sum(x["bytes"] for x in expected.values())+1048576
    guard(ancestor,peak,left,observed,a.concurrent_reserve_bytes)
    received={}
    for line in sys.stdin:
        message=json.loads(line)
        key=(message["dataset"],message["name"])
        asset=expected[key]
        if key in received: raise ValueError("duplicate source frame")
        data=base64.b64decode(message["data"],validate=True)
        if len(data)!=asset["bytes"]: raise ValueError("source frame size differs")
        guard(root,peak,left,observed,a.concurrent_reserve_bytes)
        folder=root/"raw"/key[0]
        folder.mkdir(parents=True,exist_ok=True)
        target=folder/key[1]
        if target.exists():
            if target.stat().st_size!=len(data):raise ValueError("preserve mismatched file")
            status="EXISTING_CLOSED_SIZE_MATCH"
        else:
            with target.open("xb") as stream:stream.write(data)
            left-=len(data)
            status="DOWNLOADED_VIA_SSH"
        received[key]=dict(asset,path=str(target),status=status)
        print("CLOSED",*key,len(data),flush=True)
    missing=set(expected)-set(received)
    manifests=root/"acquisition"
    manifests.mkdir(parents=True,exist_ok=True)
    for group in a.datasets:
        rows=[received[key] for key in received if key[0]==group]
        pending=[name for g,name in sorted(missing) if g==group]
        if pending:
            print("INCOMPLETE",group,pending,flush=True)
            continue
        guard(root,1048576,left,observed,a.concurrent_reserve_bytes)
        path=manifests/(group+".json")
        source=plan["assets"][group]
        path.write_text(json.dumps({
            "status":"SOURCE_ASSETS_ACQUIRED","dataset":group,
            "source_commit":source.get("source_commit"),
            "source_release":source.get("source_release"),
            "source_revisions":source.get("source_revisions"),
            "files":rows,"files_count":len(rows),"declared_bytes":sum(x["bytes"] for x in rows),
            "numerical_payload_readback":False,"new_content_hashes":False,
            "filtering_or_training_ready":False,
            "transport":"official HTTPS and single guarded SSH channel"
        },indent=2)+"\n")
        print("MANIFEST",path,flush=True)
    if missing:raise SystemExit(1)

if __name__=="__main__":main()
