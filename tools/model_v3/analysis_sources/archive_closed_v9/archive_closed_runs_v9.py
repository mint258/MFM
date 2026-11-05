"""Append559 code-derived SDK diagnosis and549 numeric A03, offline CPU only."""
from __future__ import annotations

import argparse
import ast
from contextlib import ExitStack
import csv
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

BASE=Path("/share/home/zixiao/descriptor_analysis")
TASK=BASE/"runs/model_v3_20261025"
SOURCE=TASK/"c2_solver_diagnostic_v1_source"
SCRIPT_SHA="7c78234b333dddd87ff5efd0927cf9f25642f455e6c31ca73c9abb936ed1e781"
LOCAL_PROTOCOL="c65db8b647eb4d39360e31478c4c63368cd84a43"
PUBLIC_PROTOCOL="cd0c434bb39824cd75c24d7c6de0531946da1de5"
PUBLIC_TREE="eecadc77e71a4d290f7a6b00c7d0906e14e58f3f"
STATUS="DIAGNOSTIC_ONLY_COMPLETED_NO_BASELINE_ACCEPTANCE"
A549={"job_id":"4520549","phase":"A_a03_head_off_4520549","state":"COMPLETED","exit_code":"0:0","SDKs":2,"history_rows":500,"kind":"A_plain"}


def load_source(path,sha,name):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
        raise ValueError("Frozen dependency source differs")
    sys.path.insert(0,str(path.parent))
    if name in sys.modules:
        if Path(sys.modules[name].__file__).absolute()!=path.absolute():
            raise ValueError("Dependency module identity differs")
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


v7=load_source(TASK/"archive_closed_v7_source/archive_closed_runs_v7.py","df35afad7a538f556d9108e957e563ebb9ca31342d2942b546201d0aa0ac6c3c","archive_closed_readonly_v7")
reader=sys.modules["bounded_history_v7"]
require=reader.require


def logger_contract(text):
    tree=ast.parse(text)
    calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
           and isinstance(node.func.value,ast.Name) and node.func.value.id=="run" and node.func.attr=="log"]
    require(len(calls)==2,"Fixed source logger call count differs")
    indexed={next((kw.value.value for kw in call.keywords if kw.arg=="step" and isinstance(kw.value,ast.Constant)),None):call for call in calls}
    require(set(indexed)=={0,1} and all(any(kw.arg=="commit" and isinstance(kw.value,ast.Constant) and kw.value.value is True for kw in call.keywords) for call in calls),
            "Fixed source explicit step/commit contract differs")
    first=indexed[0].args[0]
    require(isinstance(first,ast.Dict) and {key.value for key in first.keys}=={"source/stop_code","source/iterations","source/solver_wall_seconds"},"Fixed source scientific logger fields differ")
    require(isinstance(indexed[1].args[0],ast.Name) and indexed[1].args[0].id=="numeric","Fixed second logger input differs")
    dictionaries=[node.value for node in ast.walk(tree) if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="numeric" for t in node.targets)]
    require(len(dictionaries)==1 and isinstance(dictionaries[0],ast.Dict)
            and {key.value for key in dictionaries[0].keys}=={"diagnostic/completed_requested_work","diagnostic/native_PRETRAIN_VAL_records_decoded"},"Fixed diagnostic scientific fields differ")
    updates=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
             and isinstance(node.func.value,ast.Name) and node.func.value.id=="numeric" and node.func.attr=="update"]
    require(len(updates)==1 and isinstance(updates[0].args[0],ast.Dict)
            and {key.value for key in updates[0].args[0].keys}=={"candidate/iterations","candidate/solver_wall_seconds"},"Fixed candidate scientific fields differ")


def derive_expected(source,candidate,result,done,binding,inputs):
    """Cross-check saved outputs, then derive exactly what pinned code logged."""
    require(result["status"]==done["status"]==STATUS,"559 must remain diagnostic-only completion")
    require(source["schema"]=="model_v3_C2_controlled_source_solver_return_v1"
            and source["status"]==candidate["status"]=="DIAGNOSTIC_ONLY_NOT_BASELINE_ACCEPTANCE","Saved diagnostic scope differs")
    zeros=(source["native_PRETRAIN_VAL_records_read"],candidate["native_PRETRAIN_VAL_records_decoded"],
        result["native_PRETRAIN_VAL_records_decoded"],result["source"]["native_PRETRAIN_VAL_records_decoded"],
        result["candidate"]["native_PRETRAIN_VAL_records_decoded"],done["native_PRETRAIN_VAL_records_decoded"],binding["native_PRETRAIN_VAL_records_decoded"])
    require(all(type(value) is int and value==0 for value in zeros) and inputs["validation_geometry_access_authorized"] is False,"PRETRAIN_VAL access/count must remain exactly zero")
    require(done["baseline_accepted"] is False and result["model_selection_gate"] is False
            and result["candidate"]["KKT_acceptance_threshold_applied"] is False
            and candidate["KKT_acceptance_threshold_applied"] is False,"Diagnostic cannot claim baseline/model/KKT acceptance")
    for node in (source,candidate,result,done,binding):
        for key in ("baseline_accepted","baseline_acceptance","model_selection_gate"):
            require(key not in node or node[key] is False,"Unexpected baseline acceptance claim")
    require(result["original_v1_job_4520482_remains_FAILED"] is True
            and result["original_v1_stop_or_iteration_count_inferred"] is False
            and source["old_job_4520482_stop_inferred"] is False,"559 cannot infer the unknown original482 stop")
    for key in ("stop_code","iterations","solver_wall_seconds"):
        require(result["source"]["baseline"][key]==source[key],"Saved controlled-source scientific field drift")
    require(result["candidate"]["solver"]==candidate["solver"]
            and result["candidate"]["solver_wall_seconds"]==candidate["solver_wall_seconds"],"Saved candidate scientific field drift")
    for value in (source["stop_code"],source["iterations"],candidate["solver"]["iterations"]):
        require(type(value) is int and value>=0,"Source solver counters must be integers")
    for value in (source["solver_wall_seconds"],candidate["solver_wall_seconds"]):
        require(type(value) is float and math.isfinite(value) and value>=0,"Source solver wall values must be finite floats")
    require(source["iterations"]<=500 and source["configured_iteration_limit"]==500
            and candidate["solver"]["iterations"]<=2000 and result["array_artifact"]["saved"] is True,
            "Completed requested work/source iteration caps differ")
    return [{"step":0,"row":{"source/stop_code":source["stop_code"],"source/iterations":source["iterations"],"source/solver_wall_seconds":source["solver_wall_seconds"]}},
            {"step":1,"row":{"diagnostic/completed_requested_work":True,"diagnostic/native_PRETRAIN_VAL_records_decoded":0,
             "candidate/iterations":candidate["solver"]["iterations"],"candidate/solver_wall_seconds":candidate["solver_wall_seconds"]}}]


def scalar_exports(path,output):
    count=0
    with (output/"history.scalars.csv").open("x",newline="",encoding="utf-8") as target,path.open("rb") as source:
        writer=csv.writer(target);writer.writerow(("step","key","value_json"))
        for line in source:
            row=reader.strict_json(line)
            for key,value in row["row"].items():
                writer.writerow((row["step"],key,json.dumps(value,ensure_ascii=False,allow_nan=False)));count+=1
        target.flush();os.fsync(target.fileno())
    return count


def make_559(helper,pending):
    phase=TASK/"C2_train_diagnostic_4520559"
    require(not (phase/"history.jsonl").exists(),"This exact case has no original fsync mirror; review changed inputs")
    script_ref=v7.file_ref(SOURCE/"diagnose_coordinate_lookup.py")
    require(script_ref["sha256"]==SCRIPT_SHA,"Fixed diagnostic logger source differs")
    logger_contract(Path(script_ref["path"]).read_text())
    names=("controlled_source_solver_return.json","active_jacobi_candidate_return.json","DIAGNOSTIC_RESULT.json","DIAGNOSTIC_DONE.json","input_binding.json")
    items={name:v7.read_json(phase/name) for name in names}
    source,candidate,result,done,binding=(items[name][0] for name in names)
    require(done["result"]==items["DIAGNOSTIC_RESULT.json"][1] and done["inputs"]==binding["inputs"],"DONE/result/inputs byte binding differs")
    inputs,input_ref=v7.read_json(binding["inputs"]["path"],binding["inputs"])
    registration=binding["protocol_registration"]
    require(registration==inputs["protocol_registration"] and registration["commit"]==LOCAL_PROTOCOL
            and inputs["public_registration"]=={"commit":PUBLIC_PROTOCOL,"tree":PUBLIC_TREE},"Fixed local/public diagnostic protocol differs")
    protocol_path=Path(registration["repository"])/registration["path"]
    protocol,protocol_ref=v7.read_json(protocol_path)
    require(protocol_ref["sha256"]==registration["sha256"] and protocol["scope"]=="TRAIN_ONLY_DIAGNOSTIC_NOT_BASELINE_ACCEPTANCE"
            and protocol["executed_source_sha256"]==binding["executed_sources"],"Fixed protocol/source inventory differs")
    inventory_sha=hashlib.sha256(json.dumps(binding["executed_sources"],sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    require(protocol["source_inventory_sha256"]==inventory_sha,"Diagnostic source inventory seal differs")
    source_refs=[v7.file_ref(SOURCE/name) for name in binding["executed_sources"]]
    require(all(ref["sha256"]==binding["executed_sources"][Path(ref["path"]).name] for ref in source_refs),"Executed diagnostic source bytes differ")
    evidence_refs=[]
    for name in ("source_request","selection_plan","original_failure"):
        ref=binding[name]
        require(inputs[name]==ref and v7.file_ref(ref["path"])==ref,"Original readonly input binding differs")
        evidence_refs.append(ref)
    monitor=v7.file_ref(inputs["runtime_monitor"]["path"])
    require(monitor["sha256"]==inputs["runtime_monitor"]["sha256"]=="dbe875ab7ceec7e5002c5b70bff0608e3506f7451bdacd38e5f5bfc0700663fe",
            "Diagnostic's actual runtime census source differs")
    evidence_refs.append(monitor)
    original_failure=v7.read_json(binding["original_failure"]["path"],binding["original_failure"])[0]
    require(not any(key in original_failure for key in ("stop_code","iterations","solver_return")),"Original482 stop metadata changed; do not infer unknown state")
    artifact=result["array_artifact"]["binding"]
    require(Path(artifact["path"]).parent==phase and Path(artifact["path"]).suffix==".npz"
            and v7.file_ref(artifact["path"],32<<20)==artifact,"Bounded hash-only optional array artifact differs")
    expected=derive_expected(source,candidate,result,done,binding,inputs)
    supervisor,supervisor_ref=v7.read_json(TASK/"C2_train_diagnostic_supervisor_4520559.json")
    require(supervisor["status"]=="COMPLETED" and supervisor["exit_code"]==0 and str(supervisor["job_id"])=="4520559"
            and supervisor["first_failure"] is None and supervisor.get("remaining",supervisor.get("remaining_recorded_processes_before_retirement"))==[],"Actual559 outer supervisor is not complete")
    require(supervisor["gpu_initialization_permitted"] is False
            and supervisor["private_storage"]["first_sampling_failure"] is None
            and supervisor["private_storage"]["budget_bytes"]==128<<20,"Actual559 CPU-only128MiB private storage receipt differs")
    supervisor_sources=[v7.file_ref(path) for path in supervisor["sources_sha256"]]
    require(all(ref["sha256"]==supervisor["sources_sha256"][ref["path"]] for ref in supervisor_sources),"Actual CPU supervisor dependency source bytes differ")
    command=supervisor["command"]
    require(script_ref["path"] in command and command[command.index("--inputs")+1]==input_ref["path"]
            and command[command.index("--inputs-sha256")+1]==input_ref["sha256"],"Actual559 command/input binding differs")
    runs=list((phase/"wandb").glob("offline-run-*"));require(len(runs)==1 and runs[0].name.endswith("-vnfjg196")
        and result["wandb_run_id"]=="vnfjg196","Exact559 SDK identity differs")
    run=runs[0];inventory=helper.source_manifest(run)
    attachments=[v7.file_ref(path) for path in phase.glob("*.json")]
    attachments.extend((input_ref,protocol_ref,*source_refs,*supervisor_sources,supervisor_ref,v7.file_ref(TASK/"C2_train_diagnostic_4520559.log")))
    require(sum(ref["bytes"] for ref in attachments+evidence_refs+[artifact])+sum(row["bytes"] for row in inventory)<=128<<20,"Case559 source/evidence budget exceeds128MiB")
    for ref in attachments:
        destination=pending/"case_files"/Path(ref["path"]).name
        v7.copy_ref(ref,destination)
    raw_root=pending/"wandb"/run.name
    for row in inventory:
        v7.copy_ref({"path":row["read_path"],"bytes":row["bytes"],"sha256":row["sha256"]},raw_root/row["relative_path"])
    output=pending/"sdk_exports/vnfjg196";output.mkdir(parents=True)
    with (output/"expected.code_derived.jsonl").open("xb") as stream:
        for row in expected:stream.write(reader.encoded(row))
    with (output/"history.normalized.jsonl").open("xb") as stream:
        details=reader.verify_file(raw_root/"run-vnfjg196.wandb",stream,expected_run_id="vnfjg196",expected_exit=0,expected_rows=2,
            mirror_factory=lambda config: iter({"step":row["step"],"row":reader.flatten(row["row"])} for row in expected))
    details.update(comparison="code-derived_saved_outputs",original_fsync_mirror_exists=False,source_script=script_ref,
        source_saved_outputs=[ref for _,ref in items.values()],local_protocol_commit=LOCAL_PROTOCOL,public_protocol_commit=PUBLIC_PROTOCOL,
        diagnostic_status=STATUS,native_PRETRAIN_VAL_records_decoded=0,baseline_accepted=False,original482_remains_FAILED=True,
        original482_stop_code="UNKNOWN_NOT_SAVED_NOT_INFERRED",array_artifact_hash_only=artifact)
    details["CSV_scalar_rows"]=scalar_exports(output/"history.normalized.jsonl",output)
    require(details["CSV_scalar_rows"]==7,"All seven code-derived scientific values must be exported")
    helper.atomic_json(output/"verification.json",details)
    helper.atomic_bytes(output/"index.html",b'<!doctype html><meta charset="utf-8"><h1>C2 TRAIN diagnostic559</h1><p>DIAGNOSTIC_ONLY_COMPLETED_NO_BASELINE_ACCEPTANCE; native PRETRAIN_VAL0. Original482 remains FAILED; stop unknown. Comparison is code-derived saved outputs, not an original fsync mirror.</p><a href="history.scalars.csv">all7 scalar values</a> | <a href="history.normalized.jsonl">complete native comparison</a> | <a href="verification.json">source/SDK certificate</a>')
    require(helper.source_manifest(run)==inventory,"Original559 SDK changed")
    require(all(v7.file_ref(ref["path"])==ref for ref in attachments+evidence_refs)
            and v7.file_ref(artifact["path"],32<<20)==artifact,"Original559 metadata/hash-only artifact changed")
    manifest={"schema":"model_v3_C2_diagnostic559_archive_v9","job_id":"4520559","slurm_state":"COMPLETED","exit_code":"0:0",
        "source_attachments":attachments,"additional_bound_inputs":evidence_refs,"artifact_hash_only":artifact,"NPZ_copied_or_deserialized":False,
        "SDK_runs":[{"run_id":"vnfjg196","source_run":str(run),"source_files":inventory,"verification":details}],
        "diagnostic_status":STATUS,"comparison":"code-derived_saved_outputs","original_fsync_mirror_exists":False,
        "native_PRETRAIN_VAL_records_decoded":0,"baseline_accepted":False,"original482_remains_FAILED":True,
        "original482_stop_code":"UNKNOWN_NOT_SAVED_NOT_INFERRED","local_protocol_commit":LOCAL_PROTOCOL,"public_protocol_commit":PUBLIC_PROTOCOL,
        "actual_CPU_supervisor_sources":supervisor_sources,"actual_CPU_private_storage":supervisor["private_storage"],
        "original_files_preserved":True,"online_sync_performed":False,"scientific_acceptance":False}
    return manifest,[{"job_id":"4520559","run_id":"vnfjg196","name":"C2 TRAIN-only solver diagnostic; no baseline acceptance;482 unknown stop",
        "slurm_state":"COMPLETED","exit_code":"0:0","offline_unsynced":True}]


def make_A_plain(helper,pending,spec):
    """Explicit new spec; never change or impersonate frozen v7.CASES."""
    require(spec==A549,"Only the explicitly admitted549 case is supported")
    phase=TASK/spec["phase"]
    summary,summary_ref=v7.read_json(phase/"summary.json")
    status,status_ref=v7.read_json(phase/"run_status.json")
    config,config_ref=v7.read_json(phase/"configuration.json")
    require(summary["full_A_numeric_acceptance"] is True and summary["fixed_batch_pass"] is True and summary["trajectory_pass"] is True
            and summary["consumed_trajectory_base_records"]==201216 and status["failure"] is None and status["cleanup_errors"]==[],
            "Actual549 complete native20/500 pass evidence differs")
    require(config["code_sha"]=="8ece64c685fe287d6863fbbe2f6f52006632a5cc"
            and config["prereg_sha"]=="61658a4c1f472de035601dbedc17809315774784"
            and config["candidate"]["head_checkpointing"] is False and config["candidate"]["precision"]=="fp32",
            "Actual A03 source/prereg/head-off configuration differs")
    supervisor,supervisor_ref=v7.read_json(TASK/"A_candidate_supervisor_4520549.json")
    require(supervisor["status"]=="COMPLETED" and supervisor["exit_code"]==0 and supervisor["first_failure"] is None
            and supervisor.get("remaining",supervisor.get("remaining_recorded_processes_before_retirement"))==[],"A03 supervisor not closed")
    attachments=[v7.file_ref(phase/name) for name in v7.PHASE_FILES if (phase/name).exists()]+[supervisor_ref]
    runs=sorted((phase/"wandb").glob("offline-run-*"));require(len(runs)==spec["SDKs"],"A03 exact two SDKs required")
    inventories=[(run,helper.source_manifest(run)) for run in runs]
    require(sum(ref["bytes"] for ref in attachments)+sum(row["bytes"] for _,inventory in inventories for row in inventory)<=128<<20,"A03 source budget exceeded")
    for ref in attachments:v7.copy_ref(ref,pending/"case_files"/Path(ref["path"]).name)
    SDKs,entries=[],[]
    for run,inventory in inventories:
        run_id=run.name.rsplit("-",1)[1];raw_root=pending/"wandb"/run.name
        for row in inventory:v7.copy_ref({"path":row["read_path"],"bytes":row["bytes"],"sha256":row["sha256"]},raw_root/row["relative_path"])
        output=pending/"sdk_exports"/run_id;output.mkdir(parents=True)
        with ExitStack() as stack:
            chosen={}
            def expected(config):
                role=config.get("paired_role");require(role in ("reference","candidate"),"A03 native role missing")
                path=phase/(role+"_history.jsonl");chosen.update(role=role,source=v7.file_ref(path))
                return reader.mirror_rows(stack.enter_context(path.open("rb")),"A_plain")
            with (output/"history.normalized.jsonl").open("xb") as stream:
                details=reader.verify_file(raw_root/("run-"+run_id+".wandb"),stream,expected_run_id=run_id,expected_exit=0,
                    expected_rows=spec["history_rows"],mirror_factory=expected)
        details.update(original_history=chosen,actual_numeric_A_pass=True,speed_or_recipe_adopted=False)
        details["CSV_scalar_rows"]=scalar_exports(output/"history.normalized.jsonl",output)
        helper.atomic_json(output/"verification.json",details)
        helper.atomic_bytes(output/"index.html",b'<!doctype html><meta charset="utf-8"><h1>A03 head checkpoint off549</h1><p>Actual native20batch/500update numeric PASS. Speed/recipe adoption pending separate ABBA.</p><a href="history.scalars.csv">complete scalar CSV</a> | <a href="history.normalized.jsonl">all500 rows</a> | <a href="verification.json">native certificate</a>')
        require(helper.source_manifest(run)==inventory,"A03 original SDK changed")
        SDKs.append({"run_id":run_id,"source_run":str(run),"source_files":inventory,"verification":details})
        entries.append({"job_id":spec["job_id"],"run_id":run_id,"name":"A03 head-off native20/500 numeric PASS / "+chosen["role"],
            "slurm_state":spec["state"],"exit_code":spec["exit_code"],"offline_unsynced":True})
    require({sdk["verification"]["paired_role"] for sdk in SDKs}=={"reference","candidate"},"Two distinct A03 SDK roles required")
    require(all(v7.file_ref(ref["path"])==ref for ref in attachments),"Original A03 metadata/history changed")
    return {"schema":"model_v3_A03_numeric549_archive_v9","job_id":spec["job_id"],"case_spec":spec,
        "slurm_state":spec["state"],"exit_code":spec["exit_code"],"source_attachments":attachments,"SDK_runs":SDKs,
        "actual_A_numeric_pass":True,"speed_or_recipe_adopted":False,"ABBA_pending":True,
        "original_files_preserved":True,"online_sync_performed":False},entries


def verify_pins(path,sha):
    value,reference=v7.read_json(path)
    require(reference["sha256"]==sha and value["schema"]=="model_v3_archive_closed_sources_v9","v9 frozen source inventory differs")
    for ref in value["files"]:require(v7.file_ref(ref["path"])==ref,"Frozen v9/readonly source bytes differ")
    return reference


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pins",type=Path,required=True);parser.add_argument("--source-pins-sha256",required=True)
    parser.add_argument("--quota-closed-receipt",type=Path,required=True);parser.add_argument("--quota-closed-sha256",required=True)
    parser.add_argument("--expected-node",required=True);parser.add_argument("--expected-partition",default="cpu")
    parser.add_argument("--jobs",nargs="+",choices=("4520559","4520549"),default=["4520559","4520549"])
    args=parser.parse_args()
    require(os.getuid()==1278 and os.environ.get("SLURM_JOB_ID") and int(os.environ.get("SLURM_CPUS_PER_TASK","0"))>=16
        and socket.gethostname().split(".")[0]==args.expected_node and os.environ.get("SLURM_JOB_PARTITION")==args.expected_partition=="cpu"
        and os.environ.get("CUDA_VISIBLE_DEVICES")=="" and args.expected_node not in {"compute-0-20","compute-0-21","compute-0-22"},"Expected owned>=16CPU CPU-node binding required")
    source_ref=verify_pins(args.source_pins,args.source_pins_sha256)
    jobs=[(job,"COMPLETED","0:0") for job in dict.fromkeys(args.jobs)]
    v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs)
    helper=load_source(v7.HELPER,v7.HELPER_SHA,"fixed_archive_helper_v9")
    descriptor=os.open(v7.DEST/".archive.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    info=helper.owned(v7.DEST/".archive.lock")
    require((os.fstat(descriptor).st_dev,os.fstat(descriptor).st_ino)==(info.st_dev,info.st_ino),"Task lock identity changed")
    with os.fdopen(descriptor,"a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=v7.read_json(v7.DEST/"index.json")[0]
        if "4520559" in args.jobs:
            original=[entry for entry in old["entries"] if entry["job_id"]=="4520482"]
            require(original and all(entry["slurm_state"]=="FAILED" and entry["exit_code"]=="1:0" for entry in original),"Original482 failed archive identity must be retained")
        root=v7.DEST/"closed_v9";root.mkdir(mode=0o700,exist_ok=True);helper.owned(root,True)
        for job in dict.fromkeys(args.jobs):
            receipt,receipt_ref=v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs)
            target=root/("job"+job)
            if target.exists():
                helper.owned(target,True);manifest=v7.read_json(target/"manifest.json")[0]
                require(manifest["job_id"]==job and manifest["archive_source_pins"]==source_ref,"Existing v9 identity differs")
                v7.recheck_manifest(helper,manifest,target)
                if "artifact_hash_only" in manifest:
                    ref=manifest["artifact_hash_only"];require(v7.file_ref(ref["path"],32<<20)==ref,"Hash-only optional artifact changed")
                entries=manifest["task_index_entries"]
            else:
                pending=root/(".job"+job+".archive_job"+os.environ["SLURM_JOB_ID"]+".pending");pending.mkdir(mode=0o700)
                manifest,entries=make_559(helper,pending) if job=="4520559" else make_A_plain(helper,pending,dict(A549))
                for entry in entries:entry["path"]=str(target.relative_to(v7.ARCHIVE))
                manifest.update(archive_source_pins=source_ref,archive_helper_sha256=v7.HELPER_SHA,quota_closed_receipt=receipt_ref,
                    actual_closed_job_lines={j:receipt["closed_jobs"][j] for j,_,_ in jobs},task_index_entries=entries)
                links=''.join('<li><a href="sdk_exports/'+html.escape(entry["run_id"])+'/index.html">'+html.escape(entry["name"])+'</a></li>' for entry in entries)
                helper.atomic_bytes(pending/"index.html",('<!doctype html><meta charset="utf-8"><h1>'+job+'</h1><p>Originals preserved; offline unsynced. Diagnostic-only C2 and A03 numeric/speed scopes remain separate.</p><ul>'+links+'</ul><a href="manifest.json">Full source manifest</a>').encode())
                files=list(pending.rglob("*"));require(len(files)<=10000,"v9 entry cap exceeded")
                for path in files:helper.owned(path,path.is_dir())
                manifest["archived_files"]=[{"relative_path":str(path.relative_to(pending)),**{k:v for k,v in v7.file_ref(path).items() if k!="path"}} for path in files if path.is_file()]
                helper.atomic_json(pending/"manifest.json",manifest)
                require(sum(path.stat().st_size for path in pending.rglob("*") if path.is_file())<=256<<20,"v9 per-case256MiB cap exceeded")
                v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs);verify_pins(args.source_pins,args.source_pins_sha256)
                os.rename(pending,target)
            old={**old,"entries":v7.merge_entries(old["entries"],entries),"offline_unsynced":True,"updated_Asia_Shanghai":helper.stamp()}
            helper.atomic_json(v7.DEST/"index.json",old)
            links=''.join('<li><a href="../'+html.escape(entry["path"])+'/index.html">'+html.escape(entry["name"]+' / '+entry["job_id"]+' / '+entry["run_id"])+'</a></li>' for entry in old["entries"])
            helper.atomic_bytes(v7.DEST/"index.html",('<!doctype html><meta charset="utf-8"><h1>模型v3离线归档</h1><p>Originals and prior entries preserved. Offline unsynced; numeric control, optimizer/solver diagnostics and speed/adoption scopes are distinct.</p><ul>'+links+'</ul>').encode())
        print(json.dumps({"status":"ARCHIVED","processed_jobs":args.jobs,"index_entries":len(old["entries"]),"online_sync_performed":False}))


if __name__=="__main__":main()
