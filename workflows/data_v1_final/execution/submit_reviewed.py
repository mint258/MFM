"""Root-only submission of a pinned CPU request, preserving actual scheduler evidence."""
from __future__ import annotations
import argparse, datetime, fcntl, hashlib, json, os, re, socket, subprocess, time
from pathlib import Path
ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025")
PROJECT=ROOT.parent.parent

def fields(text):
    return dict(re.findall(r"(\w+)=([^\s]+)",text))

def memory_mib(value):
    m=re.fullmatch(r"(\d+)([KMGTP]?)",value)
    if not m: raise ValueError("Unrecognized scheduler memory: "+value)
    return int(m[1])*{"K":1/1024,"M":1,"G":1024,"T":1024**2,"P":1024**3}[m[2] or "M"]

def quota_available_bytes(text):
    rows=[line.split() for line in text.splitlines() if line.strip().startswith("/")]
    if len(rows)!=1 or len(rows[0])<4: raise ValueError("Unrecognized account quota")
    row=rows[0]; used,soft,hard=(int(row[i].rstrip("*")) for i in (1,2,3))
    limits=[x for x in (soft,hard) if x>0]
    if not limits: raise ValueError("Account quota is unknown")
    return (min(limits)-used)*1024

def query(argv):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
    if p.returncode: raise RuntimeError({"argv":argv,"returncode":p.returncode,"stderr":p.stderr})
    return p.stdout

def file_ref(path):
    raw=path.read_bytes()
    return {"path":str(path),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}

def write_new(path,value):
    with path.open("x",encoding="utf-8") as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write("\n");f.flush();os.fsync(f.fileno())

def wall_seconds(text):
    days=0
    if "-" in text:
        d,text=text.split("-",1);days=int(d)
    parts=[int(x) for x in text.split(":")]
    if len(parts)!=3 or parts[1]>=60 or parts[2]>=60: raise ValueError("Use HH:MM:SS Slurm time")
    return days*86400+parts[0]*3600+parts[1]*60+parts[2]

def validate_request(request):
    assert request["kind"] in {"conformer","qm","analysis"}
    node=request["node"]
    allowed={f"compute-0-{n}" for n in range(14,20)} if request["kind"] in {"conformer","qm"} else {"compute-0-20"}
    assert node in allowed, "Node is outside this task's authorized compute role"
    assert int(request["cpus"])>=16 and float(request["memory_gib"])>0
    assert 0<int(request["wall_seconds"])<=48*3600
    assert int(request["estimated_peak_output_bytes"])>=0
    assert request["root_review"]["status"]=="APPROVED"
    if not request["pilot"] and request.get("estimated_total_core_hours",0)>500:
        trial=request["root_review"]["accepted_pilot_reference"]
        assert file_ref(Path(trial["path"]))["sha256"]==trial["sha256"]
    for pin in [request["script_reference"]]+request["source_references"]:
        actual=file_ref(Path(pin["path"]))
        assert actual==pin, ("Pinned source changed",pin["path"])
    raw=Path(request["script_reference"]["path"]).read_bytes()
    assert b"\r" not in raw and raw.startswith(b"#!/bin/bash\n")
    directives={}
    for line in raw.decode().splitlines():
        m=re.fullmatch(r"#SBATCH --([\w-]+)=(\S+)",line)
        if m: directives[m[1]]=m[2]
    name=directives["job-name"]
    assert re.fullmatch(r"dv1_[A-Za-z0-9_]+",name)
    assert directives["nodelist"]==node
    assert int(directives["nodes"])==1 and int(directives["ntasks"])==1
    assert int(directives["cpus-per-task"])==request["cpus"]
    assert memory_mib(directives["mem"])==request["memory_gib"]*1024
    assert wall_seconds(directives["time"])==request["wall_seconds"]
    assert directives.get("partition") in ({"all","cpu"} if request["kind"] in {"conformer","qm"} else {"all","gpu"})
    assert not any(k in directives for k in ("gres","gpus","gpus-per-node"))
    return name

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--request",type=Path,required=True)
    args=p.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split(".")[0]=="sonmi"
    request=json.loads(args.request.read_text())
    name=validate_request(request); node_name=request["node"]
    submissions=ROOT/"control/submissions";submissions.mkdir(parents=True,exist_ok=True)
    receipt=submissions/(name+".json")
    intent=submissions/(name+".intent.json")
    with (submissions/"root.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert not receipt.exists() and not intent.exists(),"Submission already registered; audit before any retry"
        queue=query(["squeue","-h","-u","zixiao","-o","%i|%j|%N|%T"])
        assert all(line.split("|")[1]!=name for line in queue.splitlines()),"Duplicate active job"
        quota=query(["quota","-v","-u","zixiao"])
        free=quota_available_bytes(quota)
        assert free-request["estimated_peak_output_bytes"]>=200_000_000_000,"200 GB quota reserve would be breached"
        sinfo=query(["sinfo","--Node","--nodes="+node_name,"--noheader","--format=%N|%P|%t|%C|%m"])
        node_raw=query(["scontrol","show","node",node_name,"--oneliner"]);node=fields(node_raw)
        assert int(node["CPUTot"])-int(node["CPUAlloc"])>=request["cpus"],"WAIT_FOR_FREE_CPUS"
        ids=query(["squeue","-h","-w",node_name,"-t","RUNNING,COMPLETING","-o","%i"])
        declared=0.;jobs=[]
        for jid in ids.split():
            metadata=query(["scontrol","show","job",jid,"--oneliner"]);job=fields(metadata)
            if "MinMemoryNode" in job: mem=memory_mib(job["MinMemoryNode"])
            elif "MinMemoryCPU" in job:
                # Conservative on heterogeneous allocations: count all CPUs against this node.
                mem=memory_mib(job["MinMemoryCPU"])*int(job["NumCPUs"])
            else: raise ValueError("Existing all-user memory declaration unavailable")
            if mem==0: mem=float(node["RealMemory"])
            declared+=mem;jobs.append({"job_id":jid,"metadata":metadata,"memory_mib_budgeted_on_node":mem})
        committed=max(float(node["AllocMem"]),declared)
        assert committed+request["memory_gib"]*1024<=int(node["RealMemory"])*.85,"WAIT_FOR_DECLARED_MEMORY_BUDGET"
        record={"observed_at":datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
                "uid":os.getuid(),"request_reference":file_ref(args.request),"request":request,
                "queue_before":queue,"quota_raw":quota,"account_free_bytes":free,
                "sinfo":sinfo,"node_metadata":node_raw,"existing_jobs_all_users":jobs,
                "committed_memory_mib":committed}
        # Recheck pinned source immediately before recording the one permitted submission attempt.
        validate_request(request)
        write_new(intent,record)
        argv=["sbatch","--parsable","--chdir="+str(PROJECT),request["script_reference"]["path"]]
        try:
            proc=subprocess.run(argv,cwd=PROJECT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
            record.update(sbatch_argv=argv,sbatch_returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr)
        except subprocess.TimeoutExpired:
            record.update(sbatch_argv=argv,status="SUBMISSION_OUTCOME_UNKNOWN_NO_AUTOMATIC_RETRY")
            write_new(receipt,record);raise
        if proc.returncode==0:
            jid=proc.stdout.strip().split(";")[0]
            if not jid.isdecimal():
                record["status"]="UNRECOGNIZED_SUBMISSION_RESPONSE_NO_AUTOMATIC_RETRY"
                write_new(receipt,record)
                raise RuntimeError("Unrecognized sbatch response; inspect preserved receipt")
            record.update(job_id=jid,status="SUBMITTED_NOT_COMPLETED")
        else: record["status"]="SUBMISSION_FAILED_NO_AUTOMATIC_RETRY"
        # Persist the actual job ID before a controller readback can fail.
        write_new(receipt,record)
        if proc.returncode: raise RuntimeError("Slurm rejected the request; inspect preserved receipt")
        verification={"job_id":jid,"receipt_reference":file_ref(receipt)}
        try:
            actual=query(["scontrol","show","job",jid,"--oneliner"])
            verification["actual_job_metadata"]=actual;info=fields(actual)
            assert info["WorkDir"]==str(PROJECT) and info["ReqNodeList"]==node_name
            assert int(info["NumCPUs"])>=request["cpus"]
            verification["status"]="SUBMITTED_JOB_METADATA_VERIFIED"
        except Exception as exc:
            verification.update(status="POST_SUBMISSION_VERIFICATION_FAILED_NO_AUTOMATIC_RETRY",
                                exception_type=type(exc).__name__,exception=str(exc))
            write_new(submissions/(name+".verification.json"),verification)
            raise
        write_new(submissions/(name+".verification.json"),verification)
        print(json.dumps({"receipt":str(receipt),"status":record["status"],"job_id":jid}))

if __name__=="__main__":
    main()
