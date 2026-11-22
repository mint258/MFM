"""Metadata-only recovery of owned native jobs before scientific startup."""
import copy
import json
import re

def native_fields(detail):
    return dict(re.findall(r"(?:^|\s)([A-Za-z][A-Za-z0-9_]*)=([^\s]+)",detail))

def require_owned_pending(detail):
    value=native_fields(detail)
    if value.get("UserId")!="zixiao(1278)" or value.get("JobState")!="PENDING" or value.get("RunTime")!="00:00:00":
        raise ValueError("Only the owned pending zero-runtime boundary can be changed")
    return value

def clean_dependency(value):
    if not value or value=="(null)":return None
    value=re.sub(r"\((?:unfulfilled|satisfied|failed)\)","",value)
    if not re.fullmatch(r"(?:afterok|afterany|aftercorr|afternotok|after):[0-9_:]+(?:[?,](?:afterok|afterany|aftercorr|afternotok|after):[0-9_:]+)*",value):
        raise ValueError("Unrecognized native dependency; do not silently rewrite")
    return value

def remap_dependency(value,mapping):
    value=clean_dependency(value)
    if value is None:return None
    mapping={str(k):str(v) for k,v in mapping.items()}
    return re.sub(r"(?<=:)[0-9]+",lambda m:mapping.get(m.group(),m.group()),value)

def remap_c1_specs(specs,mapping):
    mapping={int(k):int(v) for k,v in mapping.items()}
    if (any(k<=0 or v<=0 or k==v for k,v in mapping.items())
        or len(set(mapping.values()))!=len(mapping) or not mapping):
        raise ValueError("Use distinct actual replacement IDs")
    result=copy.deepcopy(specs);counts={key:0 for key in mapping}
    for row in result:
        old=int(row["job"])
        if old not in mapping:continue
        counts[old]+=1;new=mapping[old]
        if row["learner"]!="LightGBM" or row["feature_group"] not in {"Pprime","Pprime_plus_D"}:
            raise ValueError("This zero-native recovery covers only the declared CPU model groups")
        token="/job_"+str(old)
        if not row["folder"].endswith(token):
            raise ValueError("The original native folder must match the old source")
        row["job"]=new;row["folder"]=row["folder"][:-len(token)]+"/job_"+str(new)
        row["infrastructure_continuation_of_job"]=old
    if any(count!=1 for count in counts.values()):
        raise ValueError("Every declared CPU source must occur exactly once")
    if len({(r["dataset"],r["feature_group"],r["learner"],r["job"]) for r in result})!=len(result):
        raise ValueError("Replacement introduced duplicate source configurations")
    return result

def replace_primary_specs(script,specs):
    matches=list(re.finditer(r"(?m)^c1_specs=json\.loads\(.*\)$",script))
    if len(matches)!=1:raise ValueError("Exactly one original C1 source binding literal is required")
    line="c1_specs=json.loads("+json.dumps(json.dumps(specs,separators=(",",":")))+")"
    item=matches[0]
    return script[:item.start()]+line+script[item.end():]

def raw_batch(script):
    if not script.startswith("#!"):raise ValueError("Preserve the captured raw native script")
    return script

def zero_model_processes(probe,expected_daemons):
    """The probe uses comm names, not a string search through shell arguments."""
    rows=[line.split(maxsplit=3) for line in probe.splitlines() if line.startswith("PROC ")]
    seen={}
    for row in rows:
        if len(row)!=4:raise ValueError("Incomplete process metadata")
        _,pid,state,comm=row
        if comm.lower().startswith(("python","torch","lightgbm")):
            raise ValueError("A scientific process has started; recovery must not replay it")
        if int(pid) in expected_daemons:
            if not state.startswith("D") or comm!="slurmstepd":
                raise ValueError("The declared old daemon left its pre-launch blocked boundary")
            seen[int(pid)]=True
    children={int(m.group(1)):m.group(2).strip() for m in re.finditer(r"(?m)^CHILDREN ([0-9]+):(.*)$",probe)}
    if set(seen)!=set(expected_daemons) or set(children)!=set(expected_daemons) or any(children.values()):
        raise ValueError("Every old owned batch daemon must still have no child process")
    return True

def closed_atomic_prerequisite(manifest,accounting,job=4537644):
    """A completed source is a fulfilled condition, not a future completion event."""
    if (str(manifest.get("job"))!=str(job)
        or manifest.get("status")!="APPROVED_PKA_ATOMIC_SUPPLEMENT_CLOSED"
        or manifest.get("B1_task_screen_modified") is not False
        or manifest.get("all_required_neural_confirmations_closed") is not True
        or manifest.get("predeclared_result_role")!="APPENDIX"):
        raise ValueError("The registered atomic source has not closed its required work")
    records=[line.split("|") for line in accounting.splitlines() if line.split("|")[0]==str(job)]
    if len(records)!=1 or records[0][1:3]!=["COMPLETED","0:0"]:
        raise ValueError("Native accounting must prove the registered producer completed successfully")
    return dict(kind="ALREADY_CLOSED_NATIVE_SOURCE",job=job,state="COMPLETED",exit_code="0:0",
                source_status=manifest["status"],native_future_dependency_required=False)
