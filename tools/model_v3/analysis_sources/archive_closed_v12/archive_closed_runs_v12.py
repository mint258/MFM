"""Archive C2 actual603 by reusing the independently verified606 certificate."""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import html
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import stat
import sys

BASE=Path("/share/home/zixiao/descriptor_analysis")
TASK=BASE/"runs/model_v3_20261025"
REPORT_ROOT=TASK/"C2_actual_SDK_report_4520606"
REPORT_INPUTS=TASK/"C2_artifact_v3_report_inputs_v1.json"
REPORT_SOURCES=TASK/"c2_artifact_v3_report_source"
SCHEMA_SHA="c9e84294a5a9b176e2fdb35d40a4194ca198d75c9f91e5fb9ff7e3d979233542"
REPORTER_SHA="cac85ec7a9f4d8763eac7a3705bc6f8b27fdf1328282ebbe1bff62831686445f"
VERIFIER_SHA="4bb2b4a6455ebbfa0c754ab9c47f9a5173ab88a4682b89a6bffd48e0876e85c2"
CERT_SHA="9cdbce56eeb9c0df9ff58737e83e0570f24281fb833ff9e6b7121f1fc0d35f02"
REPORT_SHA="ee7156f72bfdb4b7bdd52e1ff361386c11ae49572d4d01773aa83e6dd7a9f332"
REPORT_FILES={"native_verification.json","report.json","report.md","summary.csv","metrics.png","metrics.pdf"}
BINDING_NAMES={"artifact_inputs","completion","fit_receipt","input_binding","prior_diagnostic_input_binding","prior_diagnostic_inputs",
    "protocol","report_inputs","result","root_closure","selection_plan","source_request","supervisor"}
REPORT_KEYS=set("KKT_origin actual_job_id core_metric_metadata current_job_PRETRAIN_VAL_geometry_reads current_job_TRAIN_geometry_reads "
    "current_job_elapsed_seconds current_job_parameter_estimation_performed current_job_resources derived_zero_baseline diagnostic_mapping_observation "
    "diagnostic_registration_mapping fit_origin identities_weights_native_geometries_predictions_exported independent_native_SDK lookup_or_NPZ_opened "
    "metric_units_and_denominators metrics model_owned_identity_metadata_read model_selection_gate online_sync_claimed original_v1_job_4520482_remains_FAILED "
    "original_v1_stop_inferred parameter_estimation_job_id prior_TRAIN_atoms prior_TRAIN_job_elapsed_seconds prior_TRAIN_records prior_original_coordinate_diagnostics "
    "prior_solver_statistics producer_path producer_sources_sha256 protocol_registration reporting_sources run_id schema solver source_bindings status".split())


def load_source(path,sha,name):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError("Frozen readonly source differs")
    sys.path.insert(0,str(path.parent))
    if name in sys.modules:
        if Path(sys.modules[name].__file__).absolute()!=path.absolute():raise ValueError("Readonly module path differs")
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


v7=load_source(TASK/"archive_closed_v7_source/archive_closed_runs_v7.py","df35afad7a538f556d9108e957e563ebb9ca31342d2942b546201d0aa0ac6c3c","archive_closed_readonly_v7")
reader=sys.modules["bounded_history_v7"];require=reader.require
schema=load_source(REPORT_SOURCES/"c2_artifact_schema.py",SCHEMA_SHA,"archive_readonly_c2_aggregate_schema")


def successful_supervisor(value,job):
    require(value["job_id"]==job and value["status"]=="COMPLETED" and value["exit_code"]==0 and value["first_failure"] is None
        and value["remaining"]==[] and value["private_storage"]["first_sampling_failure"] is None,"Actual closed successful CPU supervisor required")


def safe_report(value):
    require(set(value)==REPORT_KEYS,"Only the fixed safe aggregate report fields may be exported")
    forbidden={"molecule_id","molecule_ids","record_keys","member_ids","members","TRAIN_member_ids","weights","coefficients","coordinates","predictions"}
    def visit(item,path=()):
        if type(item) is dict:
            require(not (set(item)&forbidden),"Identity/weight/coordinate payload cannot enter aggregate archive")
            for key,child in item.items():visit(child,(*path,key))
        elif type(item) is list:require(path==("independent_native_SDK","steps") and item==[0,1],"Member arrays or unallowlisted lists cannot enter aggregate archive")
        else:
            require(type(item) in (str,int,float,bool,type(None)) and (type(item) is not str or len(item)<=512),"Only bounded aggregate scalar values allowed")
            if type(item) is float:require(item==item and abs(item)!=float("inf"),"Finite aggregate scalar required")
    visit(value)


def bound_refs(refs,binder=None):
    binder=v7.file_ref if binder is None else binder
    require(set(refs)==BINDING_NAMES,"Exact independent certificate metadata bindings required")
    for name,ref in refs.items():
        path=Path(ref["path"])
        require(set(ref)=={"path","bytes","sha256"} and path.is_absolute() and path.suffix==".json"
            and "LOOKUP" not in path.name.upper() and path.is_relative_to(BASE)
            and type(ref["bytes"]) is int and 0<=ref["bytes"]<=32<<20,"Only bounded model-owned JSON hash references are admitted; no LOOKUP/NPZ")
        require(binder(path,32<<20)==ref,"Independent certificate metadata raw SHA differs: "+name)
    return list(refs.values())


def decoder_ref(name,ref):
    # Read-only provenance only; package manager hard links are legitimate.
    relative={"DataStore":"sdk/internal/datastore.py","Record_module":"proto/wandb_internal_pb2.py"}
    path=Path(ref["path"])
    expected=Path("/share/home/zixiao/.conda/envs/chemprop/lib/python3.11/site-packages/wandb")/relative[name]
    require(path==expected and path.resolve(strict=True)==path,"Only the two recorded installed decoder Python sources are admitted")
    before=path.stat();require(stat.S_ISREG(before.st_mode) and before.st_size<=32<<20,"Bounded ordinary decoder source required")
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1<<20),b""):digest.update(block)
    after=path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),"Installed decoder source changed")
    require({"path":str(path),"bytes":before.st_size,"sha256":digest.hexdigest()}==ref,"Recorded606 decoder source raw SHA differs")
    return ref


def verified_payload(report):
    return [{"step":0,"row":{"prior_TRAIN_fit/records":report["prior_TRAIN_records"],"prior_TRAIN_fit/atoms":report["prior_TRAIN_atoms"],
        "prior_TRAIN_fit/parameter_estimation_job_id":report["parameter_estimation_job_id"],"current_job/TRAIN_geometry_reads":report["current_job_TRAIN_geometry_reads"]}},
        {"step":1,"row":{"validation/"+key:value for key,value in report["metrics"].items() if type(value) in (int,float)}}]


def validate_bundle(complete,certificate,report,inputs,supervisor603,supervisor606):
    safe_report(report);successful_supervisor(supervisor603,"4520603");successful_supervisor(supervisor606,"4520606")
    require(complete["schema"]=="model_v3_C2_artifact_v3_report_complete_v1" and complete["status"]==report["status"]=="VERIFIED_ANALYSIS_ONLY_NOT_MODEL_SELECTION"
        and complete["model_selection_gate"] is False and complete["identities_weights_coordinates_predictions_exported"] is False,"Actual606 analysis-only report closure required")
    require(certificate["schema"]=="model_v3_C2_artifact_v3_native_verification_v1" and certificate["status"]=="VERIFIED"
        and certificate["job_id"]==report["actual_job_id"]==inputs["expected_job_id"]=="4520603"
        and certificate["run_id"]==report["run_id"]=="10oej1zg" and certificate["verified_steps"]==[0,1]
        and certificate["all_public_metrics_config_summary_exact"] is True and certificate["SDK_original_modified"] is False
        and certificate["scientific_acceptance"] is False and certificate["online_sync_performed"] is False,"Exact independent603 SDK certificate required")
    require(certificate["expectation_origin"]=="code-derived saved outputs; no independent mirrored history file exists",
        "Certificate cannot become an original history mirror")
    native=certificate["native"]
    require(native["history_rows"]==2 and native["first_explicit_step"]==0 and native["last_explicit_step"]==1
        and native["sdk_run_ids"]==[certificate["run_id"]] and native["sdk_exit_codes"]==[0] and native["native_closed"] is True
        and native["clean_eof"] is True and native["decode_error"] is None and native["uncommitted_native_requests"]==0,
        "Two actual scientific history rows with full run/exit0/EOF closure required")
    require(complete["input_bindings"]==certificate["metadata_bindings"] and complete["SDK_file"]==certificate["SDK_file"]==inputs["SDK_file"]
        and complete["reader_source"]==certificate["reader_source"] and complete["reporting_sources"]==report["reporting_sources"],"Independent certificate/complete/input/report references differ")
    require(certificate["reader_source"]["sha256"]==schema.READER_SHA and certificate["verifier_source"]==complete["reporting_sources"]["c2_native_sdk.py"]
        and certificate["verifier_source"]["sha256"]==VERIFIER_SHA
        and {name:ref["sha256"] for name,ref in complete["reporting_sources"].items()}=={
            "c2_artifact_report.py":REPORTER_SHA,"c2_artifact_schema.py":SCHEMA_SHA,"c2_native_sdk.py":VERIFIER_SHA},"Frozen606 reporter/reader/verifier source differs")
    require(certificate["fixed_runtime_sources_sha256"]==report["producer_sources_sha256"]==schema.RUNTIME_SOURCES
        and certificate["fixed_producer_path"]==report["producer_path"]==str(schema.PRODUCER)
        and certificate["fixed_logger_source_sha256"]==schema.RUNTIME_SOURCES[schema.PRODUCER.name],"Original fixed603 producer/logger provenance differs")
    for name,ref in certificate["metadata_bindings"].items():
        if name in inputs:require(inputs[name]==ref,"Report input/certificate binding differs")
    require(all(certificate["metadata_bindings"][name]==ref for name,ref in report["source_bindings"].items()),"Safe report source bindings differ")
    require(report["parameter_estimation_job_id"]=="4520559" and report["prior_TRAIN_records"]==8192 and report["prior_TRAIN_atoms"]==436120
        and report["current_job_TRAIN_geometry_reads"]==0 and report["current_job_PRETRAIN_VAL_geometry_reads"]==1024
        and report["current_job_parameter_estimation_performed"] is False and report["fit_origin"]=="prior_TRAIN_diagnostic_artifact",
        "Prior TRAIN artifact reuse and fixed first VAL population must remain distinct")
    require(report["model_selection_gate"] is False and report["online_sync_claimed"] is False
        and report["identities_weights_native_geometries_predictions_exported"] is False and report["lookup_or_NPZ_opened"] is False
        and report["original_v1_job_4520482_remains_FAILED"] is True and report["original_v1_stop_inferred"] is False
        and report["prior_original_coordinate_diagnostics"]["acceptance_threshold_applied"] is False,
        "Analysis cannot grant model selection/export or reinterpret original failures")
    schema.metrics_checked({**report["metrics"],**report["core_metric_metadata"]})
    require(report["metrics"]["records"]==1024 and report["metrics"]["atoms"]==55650
        and report["metric_units_and_denominators"]=={key:{"unit":unit,"denominator":denominator} for key,(unit,denominator) in schema.DEFINITIONS.items()},
        "Actual1024/55650 populations, vector/component/sigma units and denominators required")
    require(report["independent_native_SDK"]=={"status":"VERIFIED","history_rows":2,"native_records":native["native_packets"],
        "steps":[0,1],"expectation_origin":certificate["expectation_origin"],"SDK_file":certificate["SDK_file"]},"Report native summary differs from606 certificate")
    payload=verified_payload(report);encoded=b"".join(schema.encoded(row) for row in payload)
    require(hashlib.sha256(encoded).hexdigest()==certificate["expected_two_rows_sha256"]==native["normalized_history_sha256"]
        and len(encoded)==native["normalized_history_bytes"],"Safe aggregate projection does not match independently verified two-row digest")
    root=str(Path(certificate["SDK_file"]["path"]).parents[2])
    expected_config={"method":schema.SOLVER,"fit_origin":schema.ORIGIN,"parameter_estimation_job_id":"4520559","current_job_TRAIN_geometry_reads":0,
        "source_request_sha256":inputs["source_request"]["sha256"],"selection_plan_sha256":inputs["selection_plan"]["sha256"],
        "public_artifact_protocol_commit":report["protocol_registration"]["commit"],"tracking_layout":{"WANDB_DIR":root,"WANDB_CACHE_DIR":root+"/cache",
            "WANDB_DATA_DIR":root+"/wandb_data","WANDB_CONFIG_DIR":root+"/wandb_config","WANDB_MODE":"offline"}}
    require(schema.canonical(expected_config)==certificate["expected_config_sha256"],"Certificate fixed config digest differs from safe aggregate metadata")
    return payload


def check_csv(text,report,inputs):
    rows=list(csv.DictReader(io.StringIO(text)));require(len(rows)==1,"Exactly one safe aggregate training-compatible CSV row required")
    row=rows[0]
    expected={"metric__current_TRAIN_geometry_reads":0,"metric__current_VAL_records":1024,
        **{"metric__"+key:value for key,value in report["metrics"].items()}}
    require({key for key in row if key.startswith("metric__")}==set(expected),"CSV scientific metric whitelist differs")
    for key,value in expected.items():reader.typed_like(reader.strict_json(row[key]),value)
    require(row["run_id"]=="C2_artifact_4520603" and row["stage"]=="5" and row["status"]=="COMPLETED"
        and row["config_sha256"]==inputs["source_request"]["sha256"]
        and row["code_sha"]==row["preregistration_sha"]==report["protocol_registration"]["commit"]
        and row["gpu_model"]=="CPU" and row["allocated_gpu_seconds"]=="0","CSV provenance/current CPU stage differs")
    reader.typed_like(reader.strict_json(row["denoise_rmse"]),report["metrics"]["coordinate_component_RMSE_A"])
    require(int(row["elapsed_seconds"])==report["current_job_elapsed_seconds"]==127 and int(row["allocated_cpu_seconds"])==16*127,
        "Actual603 resource ledger differs")


def payload_csv(rows):
    stream=io.StringIO(newline="");writer=csv.writer(stream,lineterminator="\n");writer.writerow(("verified_native_step","key","value_json"))
    for row in rows:
        for key,value in row["row"].items():writer.writerow((row["step"],key,json.dumps(value,ensure_ascii=False,allow_nan=False)))
    return stream.getvalue().encode()


def copy_selected_metadata(helper,ref,target):
    allowed=REPORT_FILES|{"REPORT_COMPLETE.json","C2_artifact_v3_report_inputs_v1.json",
        "C2_first_VAL_supervisor_4520603.json","C2_actual_SDK_report_supervisor_4520606.json"}
    require(Path(ref["path"]).name in allowed,"Raw fit/result/selection/member metadata is hash-only and cannot be copied")
    v7.copy_ref(ref,target)


def make_case(helper,pending):
    complete,complete_ref=v7.read_json(REPORT_ROOT/"REPORT_COMPLETE.json")
    cert,cert_ref=v7.read_json(REPORT_ROOT/"native_verification.json");report,report_ref=v7.read_json(REPORT_ROOT/"report.json")
    inputs,inputs_ref=v7.read_json(REPORT_INPUTS)
    require(cert_ref["sha256"]==CERT_SHA and report_ref["sha256"]==REPORT_SHA,"Exact actual606 certificate/report bytes required")
    supervisor603,sup603_ref=v7.read_json(TASK/"C2_first_VAL_supervisor_4520603.json")
    supervisor606,sup606_ref=v7.read_json(TASK/"C2_actual_SDK_report_supervisor_4520606.json")
    rows=validate_bundle(complete,cert,report,inputs,supervisor603,supervisor606)
    require(cert["metadata_bindings"]["report_inputs"]==inputs_ref and cert["metadata_bindings"]["supervisor"]==sup603_ref,"Actual603/606 input/supervisor binding differs")
    originals=bound_refs(cert["metadata_bindings"])
    for ref in complete["reporting_sources"].values():require(v7.file_ref(ref["path"])==ref,"Actual606 reporting implementation changed")
    for name,sha in schema.RUNTIME_SOURCES.items():require(v7.file_ref(schema.PRODUCER.with_name(name))["sha256"]==sha,"Original603 runtime implementation changed")
    require(set(cert["SDK_decoder_sources"])=={"DataStore","Record_module"},"Exactly the original606 decoder provenance sources required")
    for name,ref in cert["SDK_decoder_sources"].items():decoder_ref(name,ref)
    for supervisor in (supervisor603,supervisor606):
        for path,sha in supervisor["sources_sha256"].items():require(v7.file_ref(path)["sha256"]==sha,"Actual supervisor source changed")
    report_refs=complete["files"]
    require(len(report_refs)==len(REPORT_FILES) and {Path(ref["path"]).name for ref in report_refs}==REPORT_FILES
        and all(Path(ref["path"]).parent==REPORT_ROOT and v7.file_ref(ref["path"])==ref for ref in report_refs),"Actual606 full report file SHA closure differs")
    check_csv((REPORT_ROOT/"summary.csv").read_text(),report,inputs)
    sdk=cert["SDK_file"];require(v7.file_ref(sdk["path"])==sdk,"Original independently verified SDK raw SHA differs")
    run=Path(sdk["path"]).parent;require(run.parent==TASK/"C2_prior_TRAIN_first_VAL_4520603/wandb" and run.name.endswith("-10oej1zg"),"Exact original603 SDK layout required")
    inventory=helper.source_manifest(run)
    attachments=[complete_ref,inputs_ref,sup603_ref,sup606_ref]
    legacy=v7.file_ref(TASK/"C2_first_VAL_supervisor_4520595.json")
    require(sum(ref["bytes"] for ref in originals+attachments+report_refs)+sum(row["bytes"] for row in inventory)<=128<<20,"C2 selected source exceeds128MiB")
    for ref in attachments:copy_selected_metadata(helper,ref,pending/"case_files"/Path(ref["path"]).name)
    for ref in report_refs:copy_selected_metadata(helper,ref,pending/"independent_606_report"/Path(ref["path"]).name)
    raw=pending/"wandb"/run.name
    for item in inventory:v7.copy_ref({"path":item["read_path"],"bytes":item["bytes"],"sha256":item["sha256"]},raw/item["relative_path"])
    output=pending/"sdk_exports"/cert["run_id"];output.mkdir(parents=True)
    reuse={"schema":"model_v3_C2_certificate_reuse_archive_v12","status":"EXISTING606_INDEPENDENT_CERTIFICATE_REUSED",
        "actual_source_job":"4520603","independent_verification_job":"4520606","certificate":cert_ref,"source_SDK":sdk,
        "independent_scans_performed_by_this_archive":0,"decoder_reexecuted":False,"original_fsync_mirror_exists":False,
        "verified_scientific_history_rows":2,"verified_steps":[0,1],"verified_native_packets":cert["native"]["native_packets"],
        "verified_native_exit_codes":[0],"verified_clean_eof":True,"config_metrics_summary_exact_from606_certificate":True,
        "metrics_CSV_origin":"safe aggregate projection equals606 expected and normalized payload digest; not a new scan/mirror",
        "hash_only_metadata_bindings":cert["metadata_bindings"],"fit_receipt_result_parsed_or_copied":False,
        "selection_plan_parsed_or_copied":False,"LOOKUP_NPZ_opened":False,"online_sync_performed":False,"model_selection_gate":False,
        "original_failed482_and595_reinterpreted":False,"prior_failed595_supervisor_hash_only":legacy}
    helper.atomic_json(output/"verification.json",reuse);helper.atomic_bytes(output/"certificate_bound_metrics.csv",payload_csv(rows))
    helper.atomic_bytes(output/"index.html",b'<!doctype html><meta charset="utf-8"><h1>C2 actual603 / independently verified606</h1><p>Fixed1024 PRETRAIN_VAL records /55650 atoms. Prior TRAIN fit559 is reused; current TRAIN geometry reads0. Two actual scientific history rows at steps0/1, exit0 and full EOF are established by the original606 certificate. This archive performs no repeat scan and creates no history mirror. Analysis only; no model-selection acceptance.</p><a href="verification.json">reuse/source certificate</a> | <a href="certificate_bound_metrics.csv">all certificate-bound scientific metrics</a> | <a href="../../independent_606_report/report.md">original report</a> | <a href="../../independent_606_report/summary.csv">original aggregate CSV</a> | <a href="../../independent_606_report/metrics.png">figure</a>')
    require(helper.source_manifest(run)==inventory and all(v7.file_ref(ref["path"])==ref for ref in attachments+report_refs+originals)
        and v7.file_ref(legacy["path"])==legacy,"Original603/606 source changed during archive")
    entry={"job_id":"4520603","run_id":cert["run_id"],"name":"C2 prior TRAIN559 artifact / actual1024 first VAL; independently verified606",
        "slurm_state":"COMPLETED","exit_code":"0:0","offline_unsynced":True}
    manifest={"schema":"model_v3_C2_actual603_archive_v12","job_id":"4520603","slurm_state":"COMPLETED","exit_code":"0:0",
        "source_attachments":attachments+report_refs,"additional_bound_inputs":originals+[legacy],"installed_decoder_provenance":cert["SDK_decoder_sources"],
        "SDK_runs":[{"run_id":cert["run_id"],"source_run":str(run),"source_files":inventory,"verification":reuse}],
        "model_selection_gate":False,"prior_failed482_and595_unchanged":True,"original_files_preserved":True,"online_sync_performed":False}
    return manifest,[entry]


def verify_pins(path,sha):
    value,ref=v7.read_json(path)
    require(ref["sha256"]==sha and value["schema"]=="model_v3_archive_closed_sources_v12","Exact frozen v12 sources required")
    for item in (*value["files"],*value["hash_only"]):require(v7.file_ref(item["path"])==item,"Frozen source/hash-only metadata changed")
    return ref


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pins",type=Path,required=True);parser.add_argument("--source-pins-sha256",required=True)
    parser.add_argument("--quota-closed-receipt",type=Path,required=True);parser.add_argument("--quota-closed-sha256",required=True)
    parser.add_argument("--expected-node",required=True);parser.add_argument("--expected-partition",default="cpu");args=parser.parse_args()
    require(os.getuid()==1278 and os.environ.get("SLURM_JOB_ID") and int(os.environ.get("SLURM_CPUS_PER_TASK","0"))>=16
        and socket.gethostname().split(".")[0]==args.expected_node and os.environ.get("SLURM_JOB_PARTITION")==args.expected_partition=="cpu"
        and os.environ.get("CUDA_VISIBLE_DEVICES")=="" and args.expected_node not in {"compute-0-20","compute-0-21","compute-0-22"},"Owned>=16CPU CPU-node binding required")
    source_ref=verify_pins(args.source_pins,args.source_pins_sha256);jobs=[("4520603","COMPLETED","0:0"),("4520606","COMPLETED","0:0")]
    v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs)
    helper=load_source(v7.HELPER,v7.HELPER_SHA,"fixed_archive_helper_v12")
    descriptor=os.open(v7.DEST/".archive.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);info=helper.owned(v7.DEST/".archive.lock")
    require((os.fstat(descriptor).st_dev,os.fstat(descriptor).st_ino)==(info.st_dev,info.st_ino),"Task lock identity changed")
    with os.fdopen(descriptor,"a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);old=v7.read_json(v7.DEST/"index.json")[0]
        failed=[entry for entry in old["entries"] if entry["job_id"]=="4520482"]
        require(failed and all(entry["slurm_state"]=="FAILED" and entry["exit_code"]=="1:0" for entry in failed),"Original482 failed entry must remain")
        root=v7.DEST/"closed_v12";root.mkdir(mode=0o700,exist_ok=True);helper.owned(root,True);target=root/"job4520603"
        receipt,receipt_ref=v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs)
        if target.exists():
            helper.owned(target,True);manifest=v7.read_json(target/"manifest.json")[0]
            require(manifest["job_id"]=="4520603" and manifest["archive_source_pins"]==source_ref,"Existing v12 identity differs")
            v7.recheck_manifest(helper,manifest,target)
            for name,ref in manifest["installed_decoder_provenance"].items():decoder_ref(name,ref)
            entries=manifest["task_index_entries"]
        else:
            pending=root/(".job4520603.archive_job"+os.environ["SLURM_JOB_ID"]+".pending");pending.mkdir(mode=0o700)
            manifest,entries=make_case(helper,pending)
            for entry in entries:entry["path"]=str(target.relative_to(v7.ARCHIVE))
            manifest.update(archive_source_pins=source_ref,archive_helper_sha256=v7.HELPER_SHA,quota_closed_receipt=receipt_ref,
                actual_closed_job_lines={job:receipt["closed_jobs"][job] for job,_,_ in jobs},task_index_entries=entries)
            helper.atomic_bytes(pending/"index.html",b'<!doctype html><meta charset="utf-8"><h1>C2 actual603</h1><p>Original606 independent SDK certificate reused, no repeated decoder/target computation. Fixed1024VAL/55650atoms; analysis only, offline unsynced.</p><a href="sdk_exports/10oej1zg/index.html">SDK evidence and scalar metrics</a> | <a href="independent_606_report/report.md">original report</a> | <a href="manifest.json">full provenance</a>')
            files=list(pending.rglob("*"));require(len(files)<=10000,"v12 entry cap exceeded")
            for path in files:helper.owned(path,path.is_dir())
            manifest["archived_files"]=[{"relative_path":str(path.relative_to(pending)),**{key:value for key,value in v7.file_ref(path).items() if key!="path"}} for path in files if path.is_file()]
            helper.atomic_json(pending/"manifest.json",manifest)
            require(sum(path.stat().st_size for path in pending.rglob("*") if path.is_file())<=256<<20,"v12 per-case256MiB cap exceeded")
            v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs);verify_pins(args.source_pins,args.source_pins_sha256);os.rename(pending,target)
        old={**old,"entries":v7.merge_entries(old["entries"],entries),"offline_unsynced":True,"updated_Asia_Shanghai":helper.stamp()}
        helper.atomic_json(v7.DEST/"index.json",old)
        links=''.join('<li><a href="../'+html.escape(entry["path"])+'/index.html">'+html.escape(entry["name"]+' / '+entry["job_id"]+' / '+entry["run_id"])+'</a></li>' for entry in old["entries"])
        helper.atomic_bytes(v7.DEST/"index.html",('<!doctype html><meta charset="utf-8"><h1>Model v3 offline archive</h1><p>Originals/prior entries preserved; failed evidence and analysis/model-selection scopes remain distinct.</p><ul>'+links+'</ul>').encode())
        print(json.dumps({"status":"ARCHIVED","processed_jobs":["4520603"],"index_entries":len(old["entries"]),"online_sync_performed":False}))


if __name__=="__main__":main()
