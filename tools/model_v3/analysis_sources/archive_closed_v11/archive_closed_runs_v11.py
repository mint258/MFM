"""Append two failed pretrajectory A cases, retaining distinct exit domains."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import fcntl
import hashlib
import html
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import time

BASE=Path("/share/home/zixiao/descriptor_analysis")
TASK=BASE/"runs/model_v3_20261025"
PRODUCER=BASE/"MFM_model_v3_a_checkpoint/tools/model_v3/paired_a_acceptance.py"
PRODUCER_SHA="b8b4ad10a848561d69352fe5729a5ace9060a28125775c2f219df9b47dd29ebd"
CASES={
    "4520589":{"phase":"A_a07_tf32_4520589","scope":"FIXED_BATCH_NUMERIC_REJECTED_NO_TRAJECTORY","child_exit":2},
    "4520590":{"phase":"A_a02_distance_off_4520590","scope":"GPU_CAPACITY_ABORT_CLEANUP_FAILED_NO_TRAJECTORY","child_exit":-6},
}
ABSENT=("reference_history.jsonl","candidate_history.jsonl","history.jsonl","summary.json","trajectory_gate.json","stream_reset.json","candidate_h0")


def load_source(path,sha,name):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError("Frozen dependency source differs")
    sys.path.insert(0,str(path.parent))
    if name in sys.modules:
        if Path(sys.modules[name].__file__).absolute()!=path.absolute():raise ValueError("Readonly source identity differs")
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


v10=load_source(TASK/"archive_closed_v10_source/archive_closed_runs_v10.py","9526910a5c3943a012dc577f1a801bfa38a9201cff9be7e39cce46d48c9a0ad9","archive_closed_readonly_v10")
v7,reader=v10.v7,v10.reader
require=reader.require


def producer_contract(text):
    tree=ast.parse(text)
    logs=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
        and isinstance(node.func.value,ast.Subscript) and isinstance(node.func.value.value,ast.Name)
        and node.func.value.value.id=="trackers" and node.func.attr=="log"]
    require(len(logs)==1,"Frozen paired logger count differs")
    log=logs[0]
    gates=[node for node in ast.walk(tree) if isinstance(node,ast.If) and ast.dump(node.test)==ast.dump(ast.parse('not fixed_gate["pass"]',mode="eval").body)]
    require(len(gates)==1 and any(isinstance(node,ast.Return) and isinstance(node.value,ast.Constant) and node.value.value==2
        for node in ast.walk(gates[0])) and gates[0].lineno<log.lineno,"Fixed-gate rejection must precede the only scientific logger")
    loops=[node for node in ast.walk(tree) if isinstance(node,ast.For) and isinstance(node.target,ast.Name) and node.target.id=="update"]
    require(len(loops)==1 and any(node is log for node in ast.walk(loops[0])),"Scientific logger must remain inside trajectory loop")
    require(any(kw.arg=="step" and isinstance(kw.value,ast.Name) and kw.value.id=="update" for kw in log.keywords)
        and any(kw.arg=="commit" and isinstance(kw.value,ast.Constant) and kw.value.value is True for kw in log.keywords),
        "Frozen paired explicit step/commit differs")


def bounded_rows(path,maximum_rows=20):
    ref=v7.file_ref(path,4<<20);rows=[]
    with Path(path).open("rb") as stream:
        for raw in stream:
            require(len(rows)<maximum_rows and len(raw)<=131072 and raw.endswith(b"\n"),"Bounded pretrajectory source journal required")
            rows.append(reader.strict_json(raw))
    require(v7.file_ref(path)==ref,"Source journal changed while reading")
    return rows,ref


def validate_failure(job,config,status,supervisor,gate,consumption,resources,*,slurm_state="FAILED",slurm_exit="1:0"):
    require(job in CASES and slurm_state=="FAILED" and slurm_exit=="1:0","Actual outer Slurm FAILED1:0 required, distinct from child/SDK exit")
    spec=CASES[job]
    require(config["code_sha"]=="8ece64c685fe287d6863fbbe2f6f52006632a5cc"
        and config["prereg_sha"]=="61658a4c1f472de035601dbedc17809315774784"
        and config["configuration_sha256"]==v10.canonical({k:v for k,v in config.items() if k!="configuration_sha256"}),"Original paired configuration source/seal differs")
    require(config["job_id"]==status["job_id"]==supervisor["job_id"]==job and config["input"]=="native_s"
        and config["smoke"] is False and config["fixed_batches"]==20 and config["trajectory_updates"]==500
        and config["candidate"]["precision"]=="fp32","Actual native paired request differs")
    require(config["checkpoint_export"]["requested"] is True and status["checkpoint_export"] is None,
            "Rejected case must not grant checkpoint export")
    require(supervisor["status"]=="FAILED" and supervisor["exit_code"]==spec["child_exit"]
        and supervisor["remaining_recorded_processes_before_retirement"]==[]
        and supervisor["foreign_gpu_processes_signalled"] is False,"Actual failed child/supervisor closure differs")
    require(all(row["phase"]=="fixed_batch" and row["batch"]==i for i,row in enumerate(consumption))
        and all(row["phase"]=="fixed_batch" and row["batch"]==i for i,row in enumerate(resources)),"Only saved fixed-batch prefix is admitted")
    require(len(consumption)<=20 and len(resources)<=len(consumption) and len(consumption)-len(resources)<=1,
        "Saved fixed-batch guard/consumption prefix differs")
    consumed=0
    for row in consumption:
        receipt=row["input"]
        require(receipt["receipt_sha256"]==v10.canonical({k:v for k,v in receipt.items() if k!="receipt_sha256"})
            and type(receipt["base_records"]) is int and receipt["base_records"]>0,"Saved failed-case receipt differs")
        consumed+=receipt["base_records"]
        require(row["committed_stream"]["committed_base_samples"]==consumed,"Saved failed-case committed clock differs")
    if job=="4520589":
        require(config["candidate"]["tf32"] is True and status["status"]=="FIXED_BATCH_GATE_FAILED"
            and status["failure"] is None and status["cleanup_errors"]==[]
            and status["stream_cleanup"]["input_descriptors_closed"] is True and status["stream_cleanup"]["errors"]==[],
            "TF32 gate rejection is distinct from an exception/cleanup failure")
        require(supervisor["first_failure"]=={"phase":"child_exit","exit_code":2},"TF32 child2 must not become outer Slurm2")
        require(gate is not None and gate["gate"]=="A_fixed_batch_equivalence" and gate["batches"]==20 and gate["pass"] is False
            and len(gate["results"])==len(consumption)==len(resources)==20,"Actual20-batch numeric rejection required")
        for i,row in enumerate(gate["results"]):
            require(row["batch"]==i and row["input_receipt"]==consumption[i]["input"]
                and row["pass"] is (row["forward"]["pass"] and row["gradient"]["pass"]),"Saved gate/result/input binding differs")
        require(any(row["pass"] is False for row in gate["results"]),"Rejected numeric gate cannot become PASS")
        evidence={"saved_fixed_batch_results":20,"saved_failed_batch_count":sum(row["pass"] is False for row in gate["results"]),
            "primary_cause":"SAVED_FIXED_BATCH_NUMERIC_GATE_REJECTED"}
    else:
        require(config["candidate"]["distance_checkpointing"] is False and gate is None and len(consumption)<20
            and status["status"]=="FAILED" and status["failure"]["type"]=="MemoryError"
            and status["failure"]["message"]=="A diagnostic exceeded85% of physical GPU capacity",
            "Distance-off failure is the85% soft GPU cap, not an inferred numeric result/CUDA OOM")
        require(supervisor["first_failure"]["type"]=="MemoryError"
            and supervisor["first_failure"]["message"]=="Owned GPU process memory exceeded 85% of physical capacity"
            and status["stream_cleanup"]["input_descriptors_closed"] is False
            and status["stream_cleanup"]["errors"] and {row["component"] for row in status["cleanup_errors"]}=={"stream","reference","candidate"},
            "Capacity/abort/input/SDK cleanup failure must be retained")
        require(supervisor["retirement"]["remaining"]==[],"Aborted child retains owned processes")
        evidence={"saved_fixed_batch_results":None,"saved_failed_batch_count":None,"primary_cause":"GPU85_PERCENT_CAP_THEN_ABORT_AND_CLEANUP_FAILURE"}
    return {"scope":spec["scope"],"outer_slurm":{"state":slurm_state,"exit_code":slurm_exit},
        "child_exit_code":supervisor["exit_code"],"failure":status["failure"],"supervisor_first_failure":supervisor["first_failure"],
        "cleanup_errors":status["cleanup_errors"],"stream_cleanup":status["stream_cleanup"],
        "requested_fixed_batches":20,"requested_trajectory_updates":500,"actual_trajectory_updates":0,
        "saved_fixed_batch_consumption_rows":len(consumption),"saved_resource_rows":len(resources),"saved_consumed_base_records":consumed,
        "actual_numeric_acceptance":False,"trajectory_gate_available":False,"summary_available":False,"checkpoint_exported":False,
        "speed_or_recipe_adopted":False,**evidence}


def scan_native(data,record_class,*,run_id,config,job,deadline=None,max_packets=500000):
    """Observe all packets before setting a history-count/closure expectation."""
    from google.protobuf.message import DecodeError
    deadline=time.monotonic()+180 if deadline is None else deadline
    capture=v10.NativeConfigCapture(data,record_class);kinds=Counter();ids=[];exits=[];rows=0;steps=[];partial=0
    eof=False;error=None
    try:
        while True:
            if time.monotonic()>deadline:raise reader.BudgetError("Native preflight wall budget exhausted")
            raw=capture.scan_data()
            if raw is None:eof=True;break
            require(capture.packets<=max_packets,"Native preflight packet budget exhausted")
            record=record_class();record.ParseFromString(raw);kind=record.WhichOneof("record_type");kinds[kind or "none"]+=1
            if kind=="run":ids.append(record.run.run_id)
            elif kind=="exit":exits.append(int(record.exit.exit_code))
            elif kind=="request" and "partial_history" in record.request.DESCRIPTOR.fields_by_name and record.request.HasField("partial_history"):partial+=1
            elif kind=="history":
                require(rows<100000,"Native preflight history budget exhausted")
                values=reader.native_items(record.history.item)
                require("_step" in values and type(values["_step"]) is int,"Native preflight explicit step required")
                if len(steps)<2:steps.append(values["_step"])
                else:steps[-1]=values["_step"]
                rows+=1
            role=capture.configuration.get("paired_role")
            require(role is None or role in {"reference","candidate"},"Unexpected native paired role")
            if role is not None:capture.expected=reader.flatten({**config,"paired_role":role})
            if capture.expected is not None:
                for key,value in capture.configuration.items():
                    if key=="_wandb" or key.startswith("_wandb/"):continue
                    require(key in capture.expected,"Unexpected native scientific configuration")
                    reader.typed_like(value,capture.expected[key])
    except (EOFError,OSError,AssertionError,DecodeError) as exc:error=type(exc).__name__+": "+str(exc)[:200]
    require(len(ids)<=1 and all(value==run_id for value in ids),"Failed SDK native identity differs")
    require(len(exits)<=1 and all(value==1 for value in exits),"Failed producer SDK exit must be1 when recorded")
    role=capture.configuration.get("paired_role")
    full_config=False
    if role is not None:
        expected=reader.flatten({**config,"paired_role":role})
        scientific={key for key in capture.configuration if key!="_wandb" and not key.startswith("_wandb/")}
        full_config=scientific==set(expected)
        require(capture.names==["A_"+role+"_"+job],"Failed SDK native name/role differs")
    else:require(not capture.names,"Native run name without bound role is not admitted")
    closed=eof and error is None and ids==[run_id] and exits==[1] and partial==0
    require(not closed or full_config,"Closed failed SDK lacks full scientific config")
    return {"native_packets":capture.packets,"record_types":dict(kinds),"history_rows":rows,"native_run_ids":ids,
        "native_exit_codes":exits,"clean_eof":eof,"decode_error":error,"uncommitted_native_requests":partial,
        "native_closed_failed_exit":closed,"paired_role":role,"native_full_configuration_verified":full_config,
        "first_explicit_step":steps[0] if steps else None,"last_explicit_step":steps[-1] if steps else None}


def verify_scans(data_factory,record_class,destination,*,run_id,config,job):
    data=data_factory()
    try:
        observed=scan_native(data,record_class,run_id=run_id,config=config,job=job)
    finally:data.close()
    require(observed["history_rows"]==0,"Native science rows without saved pretrajectory history cannot be invented or discarded")
    data=data_factory()
    try:
        details=reader.verify_stream(data,record_class,destination,expected_run_id=run_id,
            expected_exit=1 if observed["native_closed_failed_exit"] else None,expected_rows=observed["history_rows"],
            mirror_factory=lambda native:iter(()),allow_incomplete=not observed["native_closed_failed_exit"])
    finally:data.close()
    require(details["history_rows"]==observed["history_rows"] and details["native_packets"]==observed["native_packets"]
        and details["clean_eof"]==observed["clean_eof"] and details["sdk_run_ids"]==observed["native_run_ids"]
        and details["sdk_exit_codes"]==observed["native_exit_codes"],"Native two-pass observations changed")
    details.update(bounded_reader_status=details["status"],
        status="FAILED_SOURCE_SDK_CLOSED_WITH_EXIT1" if observed["native_closed_failed_exit"] else "FAILED_SOURCE_SDK_INCOMPLETE_RAW_PRESERVED",
        observed_preflight=observed,comparison="code-derivedsavedoutputs_pretrajectory_empty",
        expected_rows_from_saved_source=0,original_fsync_history_mirror_exists=False,paired_role=observed["paired_role"],
        successful_run_or_exit_claimed=False,actual_A_numeric_acceptance=False,trajectory_updates=0,
        native_full_configuration_verified=observed["native_full_configuration_verified"])
    return details


def verify_sdk(path,destination,*,run_id,config,job):
    from wandb.proto import wandb_internal_pb2 as pb
    from wandb.sdk.internal.datastore import DataStore
    def factory():
        data=DataStore()
        try:data.open_for_scan(str(path))
        except BaseException:
            data.close();raise
        return data
    return verify_scans(factory,pb.Record,destination,run_id=run_id,config=config,job=job)


def make_case(helper,pending,job):
    phase=TASK/CASES[job]["phase"]
    require(all(not (phase/name).exists() and not (phase/name).is_symlink() for name in ABSENT),"Unexpected trajectory/summary/export artifact in failed case")
    config,config_ref=v7.read_json(phase/"configuration.json");status,status_ref=v7.read_json(phase/"run_status.json")
    supervisor,supervisor_ref=v7.read_json(TASK/("A_candidate_supervisor_"+job+".json"))
    gate,gate_ref=v7.read_json(phase/"fixed_batch_gate.json") if (phase/"fixed_batch_gate.json").exists() else (None,None)
    consumption,consumption_ref=bounded_rows(phase/"consumption.jsonl");resources,resources_ref=bounded_rows(phase/"resources.jsonl")
    evidence=validate_failure(job,config,status,supervisor,gate,consumption,resources)
    attachments=[config_ref,status_ref,supervisor_ref,consumption_ref,resources_ref,v7.file_ref(PRODUCER)]
    if gate_ref is not None:attachments.append(gate_ref)
    for suffix in (".log",):attachments.append(v7.file_ref(TASK/("A_candidate_"+job+suffix)))
    for suffix in (".json.jsonl",".json.storage.json"):
        attachments.append(v7.file_ref(TASK/("A_candidate_supervisor_"+job+suffix)))
    runs=sorted((phase/"wandb").glob("offline-run-*"));require(len(runs)==2,"Actual two failed-case SDK files required")
    inventories=[(run,helper.source_manifest(run)) for run in runs]
    require(sum(ref["bytes"] for ref in attachments)+sum(row["bytes"] for _,inventory in inventories for row in inventory)<=128<<20,
        "Failed-case selected source exceeds128MiB")
    for ref in attachments:v7.copy_ref(ref,pending/"case_files"/Path(ref["path"]).name)
    evidence.update(primary_cause_bound_sources={"status":status_ref,"supervisor":supervisor_ref,
        "stdout":next(ref for ref in attachments if Path(ref["path"]).name=="A_candidate_"+job+".log"),"fixed_gate":gate_ref},
        producer_source_sha256=PRODUCER_SHA,absent_original_artifacts=list(ABSENT))
    helper.atomic_json(pending/"failure_evidence.json",evidence)
    SDKs=[];entries=[]
    for run,inventory in inventories:
        run_id=run.name.rsplit("-",1)[1];raw=pending/"wandb"/run.name
        for row in inventory:v7.copy_ref({"path":row["read_path"],"bytes":row["bytes"],"sha256":row["sha256"]},raw/row["relative_path"])
        output=pending/"sdk_exports"/run_id;output.mkdir(parents=True)
        with (output/"history.normalized.jsonl").open("xb") as stream:
            details=verify_sdk(raw/("run-"+run_id+".wandb"),stream,run_id=run_id,config=config,job=job)
        details.update(outer_slurm={"state":"FAILED","exit_code":"1:0"},child_exit_code=supervisor["exit_code"],
            filename_run_id=run_id,scope=evidence["scope"],saved_source_refs={"configuration":config_ref,"run_status":status_ref,"fixed_gate":gate_ref},
            producer_source_sha256=PRODUCER_SHA,online_sync_performed=False)
        details["CSV_scalar_rows"]=v10.v9.scalar_exports(output/"history.normalized.jsonl",output)
        helper.atomic_json(output/"verification.json",details)
        helper.atomic_bytes(output/"index.html",('<!doctype html><meta charset="utf-8"><h1>Failed A '+job+'</h1><p>'+evidence["scope"]+'. Slurm FAILED1:0; child exit '+str(supervisor["exit_code"])+'. Native SDK closure and role are observed separately; no trajectory/summary/export or acceptance is invented.</p><a href="verification.json">full native/EOF/exit certificate</a> | <a href="history.scalars.csv">all committed scalar CSV</a>').encode())
        require(helper.source_manifest(run)==inventory,"Original failed SDK changed")
        SDKs.append({"run_id":run_id,"source_run":str(run),"source_files":inventory,"verification":details})
        entries.append({"job_id":job,"run_id":run_id,"name":job+" "+evidence["scope"]+" / "+str(details["paired_role"] or "native role unavailable"),
            "slurm_state":"FAILED","exit_code":"1:0","child_exit_code":supervisor["exit_code"],"offline_unsynced":True})
    roles=[sdk["verification"]["paired_role"] for sdk in SDKs]
    require(len([role for role in roles if role is not None])==len(set(role for role in roles if role is not None)),"Duplicate observed failed SDK role")
    require(all(not (phase/name).exists() and not (phase/name).is_symlink() for name in ABSENT)
        and all(v7.file_ref(ref["path"])==ref for ref in attachments),"Failed original artifacts/source changed")
    return {"schema":"model_v3_failed_pretrajectory_A_archive_v11","job_id":job,"slurm_state":"FAILED","exit_code":"1:0",
        "child_exit_code":supervisor["exit_code"],"source_attachments":attachments,"failure_evidence":evidence,"SDK_runs":SDKs,
        "actual_numeric_acceptance":False,"trajectory_acceptance":False,"timing_acceptance":False,"checkpoint_exported":False,
        "original_files_preserved":True,"online_sync_performed":False},entries


def verify_pins(path,sha):
    value,reference=v7.read_json(path)
    require(reference["sha256"]==sha and value["schema"]=="model_v3_archive_closed_sources_v11","Frozen v11 inventory differs")
    for ref in value["files"]:require(v7.file_ref(ref["path"])==ref,"Frozen v11/source bytes differ")
    require(v7.file_ref(PRODUCER)["sha256"]==PRODUCER_SHA,"Actual frozen paired producer differs")
    producer_contract(PRODUCER.read_text())
    return reference


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pins",type=Path,required=True);parser.add_argument("--source-pins-sha256",required=True)
    parser.add_argument("--quota-closed-receipt",type=Path,required=True);parser.add_argument("--quota-closed-sha256",required=True)
    parser.add_argument("--expected-node",required=True);parser.add_argument("--expected-partition",default="cpu")
    parser.add_argument("--jobs",nargs="+",choices=tuple(CASES),default=list(CASES));args=parser.parse_args()
    require(os.getuid()==1278 and os.environ.get("SLURM_JOB_ID") and int(os.environ.get("SLURM_CPUS_PER_TASK","0"))>=16
        and socket.gethostname().split(".")[0]==args.expected_node and os.environ.get("SLURM_JOB_PARTITION")==args.expected_partition=="cpu"
        and os.environ.get("CUDA_VISIBLE_DEVICES")=="" and args.expected_node not in {"compute-0-20","compute-0-21","compute-0-22"},
        "Expected owned>=16CPU CPU-node binding required")
    source_ref=verify_pins(args.source_pins,args.source_pins_sha256)
    jobs=[(job,"FAILED","1:0") for job in dict.fromkeys(args.jobs)]
    v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs)
    helper=load_source(v7.HELPER,v7.HELPER_SHA,"fixed_archive_helper_v11")
    descriptor=os.open(v7.DEST/".archive.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);info=helper.owned(v7.DEST/".archive.lock")
    require((os.fstat(descriptor).st_dev,os.fstat(descriptor).st_ino)==(info.st_dev,info.st_ino),"Task lock identity changed")
    with os.fdopen(descriptor,"a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);old=v7.read_json(v7.DEST/"index.json")[0]
        root=v7.DEST/"closed_v11";root.mkdir(mode=0o700,exist_ok=True);helper.owned(root,True)
        for job in dict.fromkeys(args.jobs):
            receipt,receipt_ref=v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs);target=root/("job"+job)
            if target.exists():
                helper.owned(target,True);manifest=v7.read_json(target/"manifest.json")[0]
                require(manifest["job_id"]==job and manifest["archive_source_pins"]==source_ref,"Existing v11 identity differs")
                v7.recheck_manifest(helper,manifest,target);entries=manifest["task_index_entries"]
            else:
                pending=root/(".job"+job+".archive_job"+os.environ["SLURM_JOB_ID"]+".pending");pending.mkdir(mode=0o700)
                manifest,entries=make_case(helper,pending,job)
                for entry in entries:entry["path"]=str(target.relative_to(v7.ARCHIVE))
                manifest.update(archive_source_pins=source_ref,archive_helper_sha256=v7.HELPER_SHA,quota_closed_receipt=receipt_ref,
                    actual_closed_job_lines={j:receipt["closed_jobs"][j] for j,_,_ in jobs},task_index_entries=entries)
                links=''.join('<li><a href="sdk_exports/'+html.escape(entry["run_id"])+'/index.html">'+html.escape(entry["name"])+'</a></li>' for entry in entries)
                helper.atomic_bytes(pending/"index.html",('<!doctype html><meta charset="utf-8"><h1>Failed A '+job+'</h1><p>Outer Slurm FAILED1:0, child and native SDK exits remain separate. No trajectory/summary/export or acceptance is fabricated. Originals preserved, offline unsynced.</p><ul>'+links+'</ul><a href="failure_evidence.json">cause/source/cleanup evidence</a> | <a href="manifest.json">full manifest</a>').encode())
                files=list(pending.rglob("*"));require(len(files)<=10000,"v11 entry cap exceeded")
                for path in files:helper.owned(path,path.is_dir())
                manifest["archived_files"]=[{"relative_path":str(path.relative_to(pending)),**{k:v for k,v in v7.file_ref(path).items() if k!="path"}} for path in files if path.is_file()]
                helper.atomic_json(pending/"manifest.json",manifest)
                require(sum(path.stat().st_size for path in pending.rglob("*") if path.is_file())<=256<<20,"v11 per-case256MiB cap exceeded")
                v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs);verify_pins(args.source_pins,args.source_pins_sha256)
                os.rename(pending,target)
            old={**old,"entries":v7.merge_entries(old["entries"],entries),"offline_unsynced":True,"updated_Asia_Shanghai":helper.stamp()}
            helper.atomic_json(v7.DEST/"index.json",old)
            links=''.join('<li><a href="../'+html.escape(entry["path"])+'/index.html">'+html.escape(entry["name"]+' / '+entry["job_id"]+' / '+entry["run_id"])+'</a></li>' for entry in old["entries"])
            helper.atomic_bytes(v7.DEST/"index.html",('<!doctype html><meta charset="utf-8"><h1>Model v3 offline archive</h1><p>Originals and prior entries preserved. Failed and incomplete evidence retains its actual state; no numeric, speed or recipe acceptance is implied.</p><ul>'+links+'</ul>').encode())
        print(json.dumps({"status":"ARCHIVED","processed_jobs":args.jobs,"index_entries":len(old["entries"]),"online_sync_performed":False}))


if __name__=="__main__":main()
