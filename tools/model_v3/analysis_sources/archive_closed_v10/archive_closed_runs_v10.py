"""Timing-only native ABBA SDK archive; preserve slower/no-adoption outcome."""
from __future__ import annotations

import argparse
import ast
import fcntl
import hashlib
import html
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import sys
import time

BASE=Path("/share/home/zixiao/descriptor_analysis")
TASK=BASE/"runs/model_v3_20261025"
PRODUCER=BASE/"MFM_model_v3_a_checkpoint/tools/model_v3/single_a_benchmark.py"
LOGGER_SHA="e44d33276226de8920f51eabb1e7d35003ddb216ec3d182eef7846cda7f3154a"
REPORT_SOURCE=PRODUCER.with_name("a_speed_report.py")
REPORT_SHA="d3a970530a58bc2582b3423adb7760398fed889afdf64044af2b2d4803ca3f66"
MEMBERS={"4520576":(1,"reference"),"4520579":(2,"candidate"),"4520580":(3,"candidate"),"4520583":(4,"reference")}
PENDING_PAIRED={"4520589":{"phase":"A_a07_tf32_4520589","candidate":"TF32"},
                "4520590":{"phase":"A_a02_distance_off_4520590","candidate":"distance_checkpoint_off"}}


def load_source(path,sha,name):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError("Readonly implementation SHA differs")
    sys.path.insert(0,str(path.parent))
    if name in sys.modules:
        if Path(sys.modules[name].__file__).absolute()!=path.absolute():raise ValueError("Imported source identity differs")
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


v9=load_source(TASK/"archive_closed_v9_source/archive_closed_runs_v9.py","ca0d63ceba1f80c43ac05d3606cc95c77bc4bc96d343346ea5a15279cc46e856","archive_closed_readonly_v9")
v7,reader=v9.v7,v9.reader
require=reader.require


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def paired_case_adapter(job,actual_closed_line=None):
    """Explicit future adapter: closure alone never supplies rows/numeric PASS."""
    require(job in PENDING_PAIRED,"Unknown paired-case adapter")
    require(type(actual_closed_line) is str,"Paired case blocked pending actual closed receipt")
    values=actual_closed_line.split("|")
    require(len(values)>=3 and values[0]==job and values[1] in {"COMPLETED","FAILED","TIMEOUT","OUT_OF_MEMORY","CANCELLED"},
            "Paired case lacks actual terminal state")
    require(":" in values[2],"Actual paired exit code required")
    return {"job_id":job,**PENDING_PAIRED[job],"slurm_state":values[1],"exit_code":values[2],
            "history_rows":None,"numeric_pass":None,"artifact_review_required":True,
            "archive_enabled_in_this_batch":False}


def logger_contract(text):
    tree=ast.parse(text)
    calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
           and isinstance(node.func.value,ast.Name) and node.func.value.id=="tracker" and node.func.attr=="log"]
    require(len(calls)==1,"Fixed standalone logger count differs")
    call=calls[0];value=call.args[0]
    keys={key.value for key in value.keys if isinstance(key,ast.Constant)} if isinstance(value,ast.Dict) else set()
    require(keys=={"optimizer_updates","loss","compute_seconds","loader_seconds","base_records","native_atoms","consumed_base_records"},
            "Standalone source scalar projection differs")
    expansions=[item for key,item in zip(value.keys,value.values) if key is None]
    require(len(expansions)==1 and isinstance(expansions[0],ast.DictComp)
            and isinstance(expansions[0].key,ast.BinOp) and isinstance(expansions[0].key.left,ast.Constant)
            and expansions[0].key.left.value=="valid_label_count/","Standalone dynamic label-count projection differs")
    require(any(kw.arg=="commit" and isinstance(kw.value,ast.Constant) and kw.value.value is True for kw in call.keywords),"Source standalone commits differ")
    step=next(kw.value for kw in call.keywords if kw.arg=="step")
    require(ast.dump(step)==ast.dump(ast.parse("ordinal+1",mode="eval").body),"Source explicit standalone step differs")


def project_steps(rows,config,summary,position,role):
    require(len(rows)==22 and config["warmup_updates"]==summary["warmup_updates"]==2
            and config["measured_updates"]==summary["measured_updates"]==20,"All22 rows including2warmup required")
    require(config["role"]==summary["role"]==role and config["abba_position"]==summary["abba_position"]==position,
            "Actual standalone role/ABBA position differs")
    require(config["configuration_sha256"]==summary["configuration_sha256"]==canonical({k:v for k,v in config.items() if k!="configuration_sha256"}),
            "Standalone original configuration seal differs")
    expected=[];consumed=0
    for ordinal,row in enumerate(rows,1):
        require(type(row["optimizer_updates"]) is int and row["optimizer_updates"]==ordinal
                and row["measured"] is (ordinal>2),"Saved step/warmup flags differ")
        receipt=row["input"]
        require(receipt["receipt_sha256"]==canonical({k:v for k,v in receipt.items() if k!="receipt_sha256"}),"Raw saved input receipt hash differs")
        for value in (receipt["base_records"],receipt["native_atoms"]):require(type(value) is int and value>0,"Positive native consumed counters required")
        consumed+=receipt["base_records"]
        require(row["consumed_base_records"]==row["committed_stream"]["committed_base_samples"]==consumed,
                "Standalone consumed clock differs")
        require(row["resources"]["foreign_gpu_risk_observed"] is False,"Saved timing row observed foreign GPU risk")
        for key in ("loss","compute_seconds","loader_seconds"):
            require(type(row[key]) is float and math.isfinite(row[key]) and (key=="loss" or row[key]>=0),"Finite source scalar required")
        counts=row["valid_label_counts"]
        require(type(counts) is dict and counts and all(type(key) is str and key and type(value) is int and value>=0 for key,value in counts.items()),
                "Native valid-label counters differ")
        payload={"optimizer_updates":ordinal,"loss":row["loss"],"compute_seconds":row["compute_seconds"],"loader_seconds":row["loader_seconds"],
                 "base_records":receipt["base_records"],"native_atoms":receipt["native_atoms"],"consumed_base_records":consumed,
                 **{"valid_label_count/"+key:value for key,value in counts.items()}}
        expected.append({"step":ordinal,"row":payload})
    measured=rows[2:]
    require(summary["measured_base_records"]==sum(row["input"]["base_records"] for row in measured)
            and summary["measured_native_atoms"]==sum(row["input"]["native_atoms"] for row in measured)
            and summary["input_receipts_sha256"]==canonical([row["input"]["receipt_sha256"] for row in measured]),
            "Measured input/population binding differs")
    require(summary["numeric_acceptance"] is False and summary["adoption_eligible"] is False,"Standalone timing cannot grant numeric/adoption gates")
    return expected


class NativeConfigCapture:
    """Read only; forward identical native bytes to the tested bounded reader."""
    def __init__(self,data,record_class,expected=None):
        self.data,self.record_class=data,record_class
        self.configuration,self.names={},[]
        self.expected=None if expected is None else reader.flatten(expected)
        self.packets=0

    def apply(self,record):
        for item in record.update:
            require(not (item.key and item.nested_key),"Ambiguous native configuration key")
            key=item.key or "/".join(item.nested_key)
            values=reader.flatten(reader.strict_json(item.value_json),prefix=key)
            if self.expected is not None:
                for name,value in values.items():
                    if name in self.expected:reader.typed_like(value,self.expected[name])
            self.configuration.update(values)
        for item in record.remove:
            prefix=item.key or "/".join(item.nested_key)
            require(self.expected is None or not any(key==prefix or key.startswith(prefix+"/") for key in self.expected),
                    "Scientific native configuration was removed")
            for key in tuple(self.configuration):
                if key==prefix or key.startswith(prefix+"/"):self.configuration.pop(key)
        require(len(self.configuration)<=10000 and len(reader.encoded(self.configuration))<=2<<20,"Native configuration budget exhausted")

    def scan_data(self):
        raw=self.data.scan_data()
        if raw is None:return None
        if self.packets>=500000 or len(raw)>4<<20:raise reader.BudgetError("Config-capture packet budget exhausted")
        self.packets+=1;record=self.record_class();record.ParseFromString(raw)
        kind=record.WhichOneof("record_type")
        if kind=="run":self.names.append(record.run.display_name);self.apply(record.run.config)
        elif kind=="config":self.apply(record.config)
        return raw

    def verify(self,configuration,job):
        fields=tuple(configuration)
        expected=reader.flatten(configuration)
        require(self.names==["A_speed_"+configuration["role"]+"_"+job],"Native standalone display name/role differs")
        scientific={key for key in self.configuration if key!="_wandb" and not key.startswith("_wandb/")}
        require(set(expected)==scientific,"Native standalone scientific config missing/extra fields")
        for key,value in expected.items():reader.typed_like(self.configuration[key],value)
        return list(fields)


def validate_report_scope(report):
    require(report["scientific_speed_comparison"] is True and report["same_measured_inputs"] is True
            and report["foreign_gpu_risk_observed"] is False and report["has_matched_A_numeric_acceptance"] is True
            and report["numeric_acceptance_granted_by_this_report"] is False
            and type(report["speedup_candidate_over_reference"]) is float and 0<report["speedup_candidate_over_reference"]<1,
            "Actual slower/no-adoption A03 timing scope differs")


def verify_report(helper):
    root=TASK/"A03_ABBA_report_4520588"
    report,reference=v7.read_json(root/"ABBA_report.json")
    closure,closure_ref=v7.read_json(root/"closure.json")
    supervisor,supervisor_ref=v7.read_json(TASK/"A03_ABBA_report_supervisor_4520588.json")
    require(supervisor["status"]=="COMPLETED" and supervisor["exit_code"]==0 and supervisor["first_failure"] is None
            and supervisor["remaining"]==[],"Actual588 outer report process not closed")
    require(closure["job_id"]=="4520588" and closure["report"]==reference and closure["timing_adoption_claimed"] is False,
            "Actual588 report closure differs")
    report_request,request_ref=v7.read_json(closure["request"]["path"],closure["request"])
    for ref in report_request["source_files"]:require(v7.file_ref(ref["path"])==ref,"Root ABBA raw-point source binding differs")
    speed=load_source(REPORT_SOURCE,REPORT_SHA,"archive_readonly_speed_report")
    members=[speed.load_member(Path(item["root"]),Path(item["supervisor"])) for item in report_request["members"]]
    gate_root=Path(report_request["numeric_gate"])
    gate={name:v7.read_json(gate_root/(name+".json"))[0] for name in ("summary","configuration","run_status","fixed_batch_gate","trajectory_gate")}
    computed=speed.summarize_abba(members,numeric_gate=gate)
    require(all(report[key]==value for key,value in computed.items()),"Recomputed all-four-raw-point ABBA report differs")
    require(report["member_file_bindings"]==[item["file_bindings"] for item in members] and report["report_source_sha256"]==REPORT_SHA,
            "Frozen report/member bindings differ")
    for ref in report["numeric_gate_file_bindings"].values():require(v7.file_ref(ref["path"])["sha256"]==ref["sha256"],"Matched549 gate raw source differs")
    validate_report_scope(report)
    attachments=[v7.file_ref(path) for path in root.iterdir() if path.is_file()]+[request_ref,supervisor_ref]
    point_sources=[]
    for item in report_request["members"]:
        position,role=MEMBERS[item["job_id"]]
        require(item["position"]==position,"Root report member ordinal differs")
        for name in ("configuration.json","run_status.json","summary.json","steps.jsonl"):
            point_sources.append((v7.file_ref(Path(item["root"])/name),Path("position"+str(position))/name))
        point_sources.append((v7.file_ref(item["supervisor"]),Path("position"+str(position))/"supervisor.json"))
    require({item["job_id"] for item in report_request["members"]}==set(MEMBERS),"Root report lacks all4 raw points")
    return report,reference,attachments,point_sources


def make_member(helper,pending,job,report,report_ref,report_attachments,point_sources):
    position,role=MEMBERS[job];phase=TASK/("A03_ABBA_"+str(position)+"_"+job)
    config,config_ref=v7.read_json(phase/"configuration.json");summary,summary_ref=v7.read_json(phase/"summary.json")
    status,status_ref=v7.read_json(phase/"run_status.json");supervisor,supervisor_ref=v7.read_json(TASK/("A03_ABBA_supervisor_"+job+".json"))
    require(config["source_sha256"]["tools/model_v3/single_a_benchmark.py"]==LOGGER_SHA
            and config["code_sha"]=="8ece64c685fe287d6863fbbe2f6f52006632a5cc" and config["prereg_sha"]=="61658a4c1f472de035601dbedc17809315774784",
            "Frozen8ece standalone source/prereg differs")
    require(status["status"]==summary["status"]=="STANDALONE_TIMING_COMPLETED" and status["failure"] is None and status["cleanup_errors"]==[]
            and supervisor["status"]=="COMPLETED" and supervisor["exit_code"]==0 and supervisor["first_failure"] is None,
            "Actual standalone child/supervisor not complete")
    require(status["stream_cleanup"]["input_descriptors_closed"] is True and status["stream_cleanup"]["errors"]==[],
            "Actual standalone native input cleanup not closed")
    require(supervisor.get("remaining",supervisor.get("remaining_recorded_processes_before_retirement"))==[],"Standalone supervisor retains processes")
    step_ref=v7.file_ref(phase/"steps.jsonl",2<<20)
    with Path(step_ref["path"]).open("rb") as stream:
        rows=[]
        for raw in stream:
            require(len(raw)<=65536 and raw.endswith(b"\n") and len(rows)<22,"Bounded full22 saved steps required")
            rows.append(reader.strict_json(raw))
    expected=project_steps(rows,config,summary,position,role)
    require(summary==report["raw_members"][position-1],"Archived raw point differs from actual588 ABBA report")
    run_dirs=list((phase/"wandb").glob("offline-run-*"));require(len(run_dirs)==1,"Exactly one standalone SDK required")
    run=run_dirs[0];run_id=run.name.rsplit("-",1)[1];require(run_id==summary["tracking_run_id"],"Standalone SDK identity differs")
    inventory=helper.source_manifest(run)
    attachments=[config_ref,summary_ref,status_ref,step_ref,supervisor_ref,v7.file_ref(PRODUCER)]
    all_sources=attachments+report_attachments+[ref for ref,_ in point_sources]
    require(sum(ref["bytes"] for ref in all_sources)+sum(row["bytes"] for row in inventory)<=128<<20,"Timing-case selected source budget exceeded")
    for ref in attachments:v7.copy_ref(ref,pending/"case_files"/Path(ref["path"]).name)
    for ref in report_attachments:v7.copy_ref(ref,pending/"all_four_point_report"/Path(ref["path"]).name)
    for ref,relative in point_sources:v7.copy_ref(ref,pending/"all_four_raw_points"/relative)
    raw_root=pending/"wandb"/run.name
    for row in inventory:v7.copy_ref({"path":row["read_path"],"bytes":row["bytes"],"sha256":row["sha256"]},raw_root/row["relative_path"])
    output=pending/"sdk_exports"/run_id;output.mkdir(parents=True)
    with (output/"expected.code_derived_savedsteps.jsonl").open("xb") as stream:
        for row in expected:stream.write(reader.encoded(row))
    from wandb.sdk.internal.datastore import DataStore
    from wandb.proto import wandb_internal_pb2 as pb
    data=DataStore()
    try:
        data.open_for_scan(str(raw_root/("run-"+run_id+".wandb")))
        capture=NativeConfigCapture(data,pb.Record,config)
        with (output/"history.normalized.jsonl").open("xb") as stream:
            details=reader.verify_stream(capture,pb.Record,stream,expected_run_id=run_id,expected_exit=0,expected_rows=22,
                mirror_factory=lambda native_config:iter({"step":row["step"],"row":reader.flatten(row["row"])} for row in expected))
        verified_fields=capture.verify(config,job)
    finally:data.close()
    details.update(comparison="code-derivedsavedsteps",original_fsync_mirror_exists=False,saved_steps_source=step_ref,
        producer_source_sha256=LOGGER_SHA,role=role,abba_position=position,warmup_explicit_steps=[1,2],measured_explicit_steps=list(range(3,23)),
        native_scientific_config_fields_verified=verified_fields,saved_configuration=config_ref,
        native_full_configuration_verified=True,stage="STANDALONE_NATIVE_TIMING_ONLY",numeric_acceptance=False,
        speed_or_recipe_adopted=False,ABBA_report=report_ref,speedup_candidate_over_reference=report["speedup_candidate_over_reference"])
    details["CSV_scalar_rows"]=v9.scalar_exports(output/"history.normalized.jsonl",output)
    helper.atomic_json(output/"verification.json",details)
    helper.atomic_bytes(output/"index.html",('<!doctype html><meta charset="utf-8"><h1>A03 ABBA '+str(position)+' '+role+'</h1><p>Timing-only; all22 rows including2warmup. Code-derived savedsteps, not an original fsync SDK mirror. Candidate/reference ratio '+str(report["speedup_candidate_over_reference"])+': no actual speedup, head-off not adopted, recipe not frozen.</p><a href="history.scalars.csv">all native scalars</a> | <a href="history.normalized.jsonl">all22 rows</a> | <a href="verification.json">role/config/step/EOF/exit certificate</a>').encode())
    require(helper.source_manifest(run)==inventory and all(v7.file_ref(ref["path"])==ref for ref in all_sources),"Original timing/report source changed")
    manifest={"schema":"model_v3_A03_standalone_ABBA_archive_v10","job_id":job,"slurm_state":"COMPLETED","exit_code":"0:0",
        "source_attachments":all_sources,"SDK_runs":[{"run_id":run_id,"source_run":str(run),"source_files":inventory,"verification":details}],
        "role":role,"abba_position":position,"stage":"STANDALONE_NATIVE_TIMING_ONLY","comparison":"code-derivedsavedsteps",
        "ABBA_report":report_ref,"pooled_base_records_per_second":report["base_records_per_second"],
        "speedup_candidate_over_reference":report["speedup_candidate_over_reference"],"head_off_adopted":False,"recipe_frozen":False,
        "actual_numeric_match_is_separate549":True,"original_files_preserved":True,"online_sync_performed":False}
    return manifest,[{"job_id":job,"run_id":run_id,"name":"A03 ABBA position"+str(position)+" "+role+" timing-only; no speedup/adoption",
        "slurm_state":"COMPLETED","exit_code":"0:0","offline_unsynced":True}]


def verify_pins(path,sha):
    value,reference=v7.read_json(path)
    require(reference["sha256"]==sha and value["schema"]=="model_v3_archive_closed_sources_v10","v10 frozen source inventory differs")
    for ref in value["files"]:require(v7.file_ref(ref["path"])==ref,"Frozen v10/readonly source bytes differ")
    require(v7.file_ref(PRODUCER)["sha256"]==LOGGER_SHA,"Fixed standalone producer source differs")
    logger_contract(PRODUCER.read_text())
    return reference


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pins",type=Path,required=True);parser.add_argument("--source-pins-sha256",required=True)
    parser.add_argument("--quota-closed-receipt",type=Path,required=True);parser.add_argument("--quota-closed-sha256",required=True)
    parser.add_argument("--expected-node",required=True);parser.add_argument("--expected-partition",default="cpu")
    parser.add_argument("--jobs",nargs="+",choices=tuple(MEMBERS),default=list(MEMBERS))
    args=parser.parse_args()
    require(os.getuid()==1278 and os.environ.get("SLURM_JOB_ID") and int(os.environ.get("SLURM_CPUS_PER_TASK","0"))>=16
        and socket.gethostname().split(".")[0]==args.expected_node and os.environ.get("SLURM_JOB_PARTITION")==args.expected_partition=="cpu"
        and os.environ.get("CUDA_VISIBLE_DEVICES")=="" and args.expected_node not in {"compute-0-20","compute-0-21","compute-0-22"},"Expected owned>=16CPU CPU-node binding required")
    source_ref=verify_pins(args.source_pins,args.source_pins_sha256)
    jobs=[(job,"COMPLETED","0:0") for job in (*MEMBERS,"4520588","4520549")]
    v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs)
    helper=load_source(v7.HELPER,v7.HELPER_SHA,"fixed_archive_helper_v10")
    descriptor=os.open(v7.DEST/".archive.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    info=helper.owned(v7.DEST/".archive.lock")
    require((os.fstat(descriptor).st_dev,os.fstat(descriptor).st_ino)==(info.st_dev,info.st_ino),"Task lock identity changed")
    with os.fdopen(descriptor,"a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=v7.read_json(v7.DEST/"index.json")[0]
        report,report_ref,report_attachments,point_sources=verify_report(helper)
        root=v7.DEST/"closed_v10";root.mkdir(mode=0o700,exist_ok=True);helper.owned(root,True)
        for job in dict.fromkeys(args.jobs):
            receipt,receipt_ref=v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs)
            target=root/("job"+job)
            if target.exists():
                helper.owned(target,True);manifest=v7.read_json(target/"manifest.json")[0]
                require(manifest["job_id"]==job and manifest["archive_source_pins"]==source_ref,"Existing v10 identity differs")
                v7.recheck_manifest(helper,manifest,target)
                entries=manifest["task_index_entries"]
            else:
                pending=root/(".job"+job+".archive_job"+os.environ["SLURM_JOB_ID"]+".pending");pending.mkdir(mode=0o700)
                manifest,entries=make_member(helper,pending,job,report,report_ref,report_attachments,point_sources)
                for entry in entries:entry["path"]=str(target.relative_to(v7.ARCHIVE))
                manifest.update(archive_source_pins=source_ref,archive_helper_sha256=v7.HELPER_SHA,quota_closed_receipt=receipt_ref,
                    actual_closed_job_lines={j:receipt["closed_jobs"][j] for j,_,_ in jobs},task_index_entries=entries)
                links=''.join('<li><a href="sdk_exports/'+html.escape(entry["run_id"])+'/index.html">'+html.escape(entry["name"])+'</a></li>' for entry in entries)
                helper.atomic_bytes(pending/"index.html",('<!doctype html><meta charset="utf-8"><h1>'+job+'</h1><p>Standalone native timing only; all22 steps retained. A03 pooled candidate/reference throughput ratio0.8660889573595555: no actual speedup, no adoption, recipe not frozen. Originals preserved and offline unsynced.</p><ul>'+links+'</ul><a href="all_four_point_report/ABBA_report.json">four-point ABBA</a> | <a href="manifest.json">full sources</a>').encode())
                files=list(pending.rglob("*"));require(len(files)<=10000,"v10 entry cap exceeded")
                for path in files:helper.owned(path,path.is_dir())
                manifest["archived_files"]=[{"relative_path":str(path.relative_to(pending)),**{k:v for k,v in v7.file_ref(path).items() if k!="path"}} for path in files if path.is_file()]
                helper.atomic_json(pending/"manifest.json",manifest)
                require(sum(path.stat().st_size for path in pending.rglob("*") if path.is_file())<=256<<20,"v10 per-case256MiB cap exceeded")
                v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs);verify_pins(args.source_pins,args.source_pins_sha256)
                os.rename(pending,target)
            old={**old,"entries":v7.merge_entries(old["entries"],entries),"offline_unsynced":True,"updated_Asia_Shanghai":helper.stamp()}
            helper.atomic_json(v7.DEST/"index.json",old)
            links=''.join('<li><a href="../'+html.escape(entry["path"])+'/index.html">'+html.escape(entry["name"]+' / '+entry["job_id"]+' / '+entry["run_id"])+'</a></li>' for entry in old["entries"])
            helper.atomic_bytes(v7.DEST/"index.html",('<!doctype html><meta charset="utf-8"><h1>Model v3 offline archive</h1><p>Originals and prior entries preserved. Offline unsynced; numeric, diagnostic and speed/adoption scopes remain distinct.</p><ul>'+links+'</ul>').encode())
        print(json.dumps({"status":"ARCHIVED","processed_jobs":args.jobs,"index_entries":len(old["entries"]),"online_sync_performed":False}))


if __name__=="__main__":main()
