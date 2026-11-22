"""I1-only runtime controls; native P training and checkpoint math stay unchanged."""
import json
import os
from pathlib import Path
import threading
import time


def request_handoff(configuration,job_id,reason):
    path=Path(configuration["handoff_request"])
    request=dict(run=configuration["run"],action="SAVE_AND_EXIT",
        request_id=configuration["run"]+"__"+str(job_id)+"__managed_boundary",
        job_id=str(job_id),reason=reason)
    if path.exists():
        saved=json.loads(path.read_text())
        if saved["run"]!=request["run"] or saved["job_id"]!=request["job_id"]:
            raise ValueError("Existing handoff belongs to a different actual run/job")
        return saved
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+".new."+str(os.getpid()))
    with temporary.open("x") as stream:
        json.dump(request,stream);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
    return request


def watch(configuration,job_id,*,done,stop_requested,stop_new_at,
          guard,telemetry,interval=2.,guard_interval=30.,now=time.time):
    """Only request the original complete-state boundary; never signal workers."""
    checked=now()
    while not done.wait(interval):
        if stop_requested() or now()>=stop_new_at:
            request_handoff(configuration,job_id,"actual_own_allocation_cleanup_window")
            continue
        if now()-checked>=guard_interval:
            checked=now()
            try:guard()
            except Exception as exc:
                request_handoff(configuration,job_id,"actual_storage_or_node_admission:"+type(exc).__name__)
                continue
            try:telemetry()
            except Exception:
                # Telemetry absence is not a changed scientific outcome.
                pass
