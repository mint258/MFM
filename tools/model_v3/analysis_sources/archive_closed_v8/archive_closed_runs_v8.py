"""Minimal CPU archive additions: failed546 and verified short500 primary512."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import fcntl
import hashlib
import html
import importlib.util
import importlib.metadata
import inspect
import io
import json
import os
from pathlib import Path
import socket
import sys
import time

BASE = Path("/share/home/zixiao/descriptor_analysis")
TASK = BASE / "runs/model_v3_20261025"
V7_ROOT = TASK / "archive_closed_v7_source"
PRIMARY_ROOT = TASK / "sa3_primary512_verification_v1"
V7_SHA = "df35afad7a538f556d9108e957e563ebb9ca31342d2942b546201d0aa0ac6c3c"
PRIMARY_SHA = "2a50c1d3143f95df29b44bd99e431e4445548662ec1b3bd9b487d9a134ad035c"
SCOPE_SHA = "00fd8bbce80eae6a8a1abe2283abe9b2a8926d4e945228d2bcfd071fdd6021ee"
CERT_SHA = "7b2dfeb176351b0a3076519f3afcfa2c0a3b716f7be9daf352950274541677eb"


def load_source(path, sha, name):
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise ValueError("Frozen readonly implementation differs: " + str(path))
    if name in sys.modules:
        if Path(sys.modules[name].__file__).absolute() != path.absolute():
            raise ValueError("Imported module identity differs")
        return sys.modules[name]
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


v7 = load_source(V7_ROOT / "archive_closed_runs_v7.py", V7_SHA, "archive_closed_readonly_v7")
reader = sys.modules["bounded_history_v7"]
if Path(reader.__file__).absolute() != (V7_ROOT/"bounded_history_v7.py").absolute() or hashlib.sha256(Path(reader.__file__).read_bytes()).hexdigest() != "6aee76e16c182be97b7f88e635b43948510d0fc335e0ccfbf9ba107a1c29ab95":
    raise ValueError("Frozen v7 reader module identity differs")
require = reader.require


class CompleteScalarSink:
    """Every normalized row and every scalar; never a sampled report."""
    def __init__(self, normalized, scalar_csv, *, max_bytes=96 << 20):
        self.normalized, self.scalar_csv, self.maximum = normalized, scalar_csv, max_bytes
        self.rows, self.scalars, self.bytes, self.last_step = 0, 0, 0, -1
        self.digest = hashlib.sha256()
        self.writer = csv.writer(self)
        self.writer.writerow(("step", "key", "value_json"))

    def write(self, raw):
        if type(raw) is str:  # csv.writer calls this for every complete CSV line
            data = raw.encode("utf-8")
            require(self.bytes + len(data) <= self.maximum, "Complete scalar export byte budget exhausted")
            self.scalar_csv.write(data); self.bytes += len(data)
            return len(raw)
        row = reader.strict_json(raw)
        step = row["step"]
        require(type(step) is int and step == self.last_step + 1 and self.rows < 100000, "Complete scalar step/grid budget differs")
        require(self.bytes + len(raw) <= self.maximum, "Complete scalar export byte budget exhausted")
        self.normalized.write(raw); self.digest.update(raw); self.bytes += len(raw)
        for key, value in row.items():
            if key == "step":
                continue
            require(type(value) in (int, float), "Normalized panel scalar type differs")
            self.writer.writerow((step, key, json.dumps(value, ensure_ascii=False, allow_nan=False)))
            self.scalars += 1
        self.rows += 1; self.last_step = step
        return len(raw)


def compare_certificate(details, certificate):
    for key in ("native_records", "record_types", "history_rows", "normalized_history_bytes", "normalized_history_sha256",
                "series", "sdk_run_id", "sdk_exit_code", "clean_eof"):
        require(details[key] == certificate[key], "Full native history/summary certificate differs: " + key)


class ProvenanceBindings:
    def __init__(self):
        self.cache = {}

    @staticmethod
    def identity(path):
        value = Path(path).lstat()
        return value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns

    def __call__(self,path,limit=128<<20):
        path = str(Path(path).absolute()); identity = self.identity(path)
        if path not in self.cache or self.cache[path][0] != identity:
            reference = v7.file_ref(path,limit)
            require(identity == self.identity(path),"Source changed during provenance hash")
            self.cache[path] = identity,reference
        reference = self.cache[path][1]
        require(reference["bytes"] <= limit,"Source exceeds this explicit reference bound")
        return reference

    def unchanged(self):
        require(all(self.identity(path) == identity for path,(identity,_) in self.cache.items()),"Hashed provenance source identity/size/mtime changed")


def observe_failed_stream(records, record_class, destination, *, expected_run_id, max_packets=500000,
                          max_history=100000, deadline=None):
    """Count actual history; do not predeclare zero or claim mirror verification."""
    from google.protobuf.message import DecodeError
    deadline = time.monotonic()+180 if deadline is None else deadline
    packets, histories, output_bytes, clean, decode, partial = 0, 0, 0, False, None, 0
    ids, exits, kinds = [], [], Counter()
    try:
        while True:
            if time.monotonic() > deadline:
                raise reader.BudgetError("Failed SDK wall budget exhausted")
            raw = records.scan_data()
            if raw is None:
                clean = True; break
            if packets >= max_packets or len(raw) > 4 << 20:
                raise reader.BudgetError("Failed SDK packet/record budget exhausted")
            packets += 1
            record = record_class(); record.ParseFromString(raw)
            kind = record.WhichOneof("record_type"); kinds[kind or "none"] += 1
            if kind == "run":
                ids.append(record.run.run_id)
            elif kind == "exit":
                exits.append(int(record.exit.exit_code))
            elif kind == "request" and "partial_history" in record.request.DESCRIPTOR.fields_by_name and record.request.HasField("partial_history"):
                partial += 1
            elif kind == "history":
                if histories >= max_history:
                    raise reader.BudgetError("Failed SDK history budget exhausted")
                values = reader.native_items(record.history.item)
                require(type(values.get("_step")) is int, "Observed history lacks explicit integer step")
                encoded = reader.encoded({"native_step": values.pop("_step"), "observed_payload": values})
                output_bytes += len(encoded)
                if output_bytes > 64 << 20:
                    raise reader.BudgetError("Failed observed history byte budget exhausted")
                destination.write(encoded); histories += 1
    except (EOFError, OSError, AssertionError, DecodeError) as exc:
        decode = type(exc).__name__ + ": " + str(exc)[:200]
    require(len(ids) <= 1 and all(run_id == expected_run_id for run_id in ids) and len(exits) <= 1, "Failed SDK identity/exit duplication differs")
    return {"native_packets": packets, "history_rows_observed": histories, "run_ids": ids, "native_exit_codes": exits,
            "clean_eof": clean, "decode_error": decode, "uncommitted_native_requests":partial,
            "native_closed": clean and ids == [expected_run_id] and len(exits) == 1 and partial == 0,
            "independent_mirror_verification": False, "slurm_state": "FAILED", "numeric_gate_pass": False, "timing_gate_pass": False}


def make_546(helper, pending):
    phase = TASK / "A_a01_backbone_off_4520546"
    status, status_ref = v7.read_json(phase / "run_status.json")
    supervisor, supervisor_ref = v7.read_json(TASK / "A_candidate_supervisor_4520546.json")
    require(status["status"] == "FAILED" and status["failure"]["type"] == "MemoryError"
            and status["failure"]["message"] == "A diagnostic exceeded85% of physical GPU capacity",
            "Actual546 soft capacity failure differs")
    require(supervisor["status"] == "FAILED" and supervisor["exit_code"] == 1
            and str(supervisor["job_id"]) == "4520546"
            and supervisor["first_failure"] == {"phase": "child_exit", "exit_code": 1}, "Actual546 supervisor child exit differs")
    attachments = [v7.file_ref(phase / name) for name in v7.PHASE_FILES if (phase / name).exists()]
    attachments.extend((supervisor_ref, v7.file_ref(TASK / "A_candidate_4520546.log")))
    runs = sorted((phase / "wandb").glob("offline-run-*")); require(len(runs) == 2, "Actual546 two SDKs required")
    inventories = [(run, helper.source_manifest(run)) for run in runs]
    require(sum(ref["bytes"] for ref in attachments) + sum(row["bytes"] for _, inv in inventories for row in inv) <= 128 << 20,
            "Selected546 source cap exceeded")
    for ref in attachments:
        v7.copy_ref(ref, pending / "case_files" / Path(ref["path"]).name)
    from wandb.sdk.internal.datastore import DataStore
    from wandb.proto import wandb_internal_pb2 as pb
    SDKs, entries = [], []
    for run, inventory in inventories:
        run_id = run.name.rsplit("-", 1)[1]
        raw_root = pending / "wandb" / run.name
        for row in inventory:
            v7.copy_ref({"path":row["read_path"],"bytes":row["bytes"],"sha256":row["sha256"]}, raw_root / row["relative_path"])
        output = pending / "sdk_exports" / run_id; output.mkdir(parents=True)
        data = DataStore()
        try:
            data.open_for_scan(str(raw_root / ("run-"+run_id+".wandb")))
            with (output / "observed_history.jsonl").open("xb") as stream:
                observation = observe_failed_stream(data, pb.Record, stream, expected_run_id=run_id)
        finally:
            data.close()
        helper.atomic_json(output / "verification.json", observation)
        helper.atomic_bytes(output / "index.html", b'<!doctype html><meta charset="utf-8"><p>FAILED546: soft85% capacity refusal, no numeric/timing acceptance. Actual committed-history observations: <a href="verification.json">certificate</a>; <a href="observed_history.jsonl">complete observed stream</a>.</p>')
        require(helper.source_manifest(run) == inventory, "Original546 SDK changed")
        SDKs.append({"run_id":run_id,"source_run":str(run),"source_files":inventory,"verification":observation})
        entries.append({"job_id":"4520546","run_id":run_id,"name":"A01 backbone-off soft85% refusal", "slurm_state":"FAILED","exit_code":"1:0","offline_unsynced":True})
    return {"schema":"model_v3_failed546_archive_v8","job_id":"4520546","slurm_state":"FAILED","exit_code":"1:0",
        "source_attachments":attachments,"SDK_runs":SDKs,"primary_cause":{"run_status":status_ref,"supervisor":supervisor_ref,
        "failure":status["failure"],"CUDA_OOM_stdout_required":False},"original_files_preserved":True,
        "numeric_gate_pass":False,"timing_gate_pass":False,"scientific_acceptance":False,"online_sync_performed":False}, entries


def make_primary(helper, pending):
    scope = load_source(PRIMARY_ROOT / "primary512_scope.py", SCOPE_SHA, "primary512_scope")
    primary = load_source(PRIMARY_ROOT / "verify_native_history.py", PRIMARY_SHA, "archive_readonly_primary_verifier")
    execution = PRIMARY_ROOT / "execution_4520566"
    certificate, cert_ref = v7.read_json(execution / "native_sdk/verification.json")
    require(cert_ref["sha256"] == CERT_SHA and certificate["status"] == "VERIFIED"
            and certificate["reference_kind"] == "primary" and (certificate["H0_dimension"],certificate["layers"]) == (512,6)
            and certificate["architecture_selection_claimed"] is False and certificate["formal_pretraining_complete"] is False,
            "Exact verified primary512 short500 certificate required")
    verifier_supervisor, verifier_supervisor_ref = v7.read_json(TASK / "primary512_verification_supervisor_4520566.json")
    scope.successful_supervisor(verifier_supervisor, "4520566")
    closure, closure_ref = v7.read_json(execution / "closure.json")
    require(closure["status"] == "VERIFIED_AND_REPORTED_PENDING_OUTER_TERMINAL" and closure["job_id"] == "4520566"
            and closure["certificate"] == cert_ref, "Original566 closure binding differs")
    refs = certificate["inputs"]
    bindings = ProvenanceBindings()
    values = {}
    for name, ref in refs.items():
        limit = 512 << 20 if name == "export_checkpoint" else 128 << 20
        require(bindings(ref["path"], limit) == ref, "Original primary certificate source differs: " + name)
        if Path(ref["path"]).suffix == ".json":
            values[name] = v7.read_json(ref["path"], ref)[0]
    require(v7.file_ref(primary.__file__) == certificate["verifier_implementation"], "Verified primary parser source differs")
    primary.check_result_guard(values["result"],values["guard"],values["request"],refs["result"],refs["request"])
    # Read-only tested source chain: hashes the unique bounded checkpoint but
    # never deserializes it or accesses a target. Frozen helper is not patched.
    checked_refs = {name:dict(ref) for name,ref in refs.items()}
    def source_json(path,expected_sha,limit=8<<20):
        value,ref = v7.read_json(path)
        require(ref["bytes"] <= limit and ref["sha256"] == expected_sha,"Bound source JSON differs")
        return value,ref
    source_scope = scope.read_source_chain(values["result"],values["guard"],values["request"],values["launch_spec"],values["admission"],checked_refs,
        binding=bindings,bound_json=source_json)
    require(source_scope == certificate["source_scope"], "Actual source chain differs from primary certificate")
    result, request = values["result"], values["request"]
    run = Path(refs["sdk"]["path"]).parent
    inventory = helper.source_manifest(run)
    report, report_ref = v7.read_json(execution / "report/report_manifest.json")
    require(report["verification"]["certificate"] == cert_ref and report["verification"]["independently_verified"] is True,
            "Primary compact report does not bind verified566 certificate")
    for ref in (*report["inputs"].values(),*report["outputs"]):
        require(bindings(ref["path"],512<<20 if ref["path"] == refs["export_checkpoint"]["path"] else 128<<20) == ref,
                "Primary report source/output bytes differ")
    selected = {ref["path"]:ref for name,ref in refs.items() if name != "export_checkpoint"}
    selected.update({ref["path"]:ref for name,ref in report["inputs"].items() if name != "export_checkpoint"})
    selected.update({ref["path"]:ref for ref in (cert_ref,closure_ref,verifier_supervisor_ref,report_ref,*report["outputs"])})
    for row in inventory:
        selected[row["read_path"]] = {"path":row["read_path"],"bytes":row["bytes"],"sha256":row["sha256"]}
    require(sum(ref["bytes"] for ref in selected.values()) <= 128<<20, "Selected primary archive source cap exceeded")
    for row in inventory:
        v7.copy_ref({"path":row["read_path"],"bytes":row["bytes"],"sha256":row["sha256"]},pending/"wandb"/run.name/row["relative_path"])
    for name,ref in refs.items():
        if name not in ("sdk","export_checkpoint"):
            v7.copy_ref(ref,pending/"source_metadata"/(name+Path(ref["path"]).suffix))
    for name,ref in report["inputs"].items():
        if name not in refs and name != "export_checkpoint":
            v7.copy_ref(ref,pending/"source_metadata"/("report_"+name+Path(ref["path"]).suffix))
    for ref in (cert_ref,closure_ref,verifier_supervisor_ref,report_ref,*report["outputs"]):
        relative = Path(ref["path"]).relative_to(execution) if Path(ref["path"]).is_relative_to(execution) else Path("source_metadata")/Path(ref["path"]).name
        v7.copy_ref(ref,pending/"certified_primary"/relative)
    output = pending/"sdk_exports"/certificate["sdk_run_id"]; output.mkdir(parents=True)
    expected_config = {key:request[key] for key in ("code_sha","preregistration_sha","data_version","architecture_sha256","pretraining_seed")}
    expected_config.update(request_sha256=refs["request"]["sha256"],job_id=result["job_id"],gpu_uuid=result["gpu_uuid"],panel_sha256=result["panel_sha256"],
        random_reference_initialization_seed=result["random_reference_initialization_seed"],readout_seed=result["readout_seed"])
    expected_summary = {"evaluation_status":"COMPLETED","dev_primary_score":result["summaries"]["primary_18_cells"]["mean_normalized_improvement"]}
    from wandb.sdk.internal.datastore import DataStore
    from wandb.proto import wandb_internal_pb2 as pb
    require(v7.file_ref(inspect.getsourcefile(DataStore)) == certificate["sdk_reader"]["DataStore"]
            and importlib.metadata.version("wandb") == certificate["sdk_reader"]["version"]
            and importlib.metadata.version("protobuf") == certificate["sdk_reader"]["protobuf_version"]
            and hashlib.sha256(pb.Record.DESCRIPTOR.file.serialized_pb).hexdigest() == certificate["sdk_reader"]["Record_schema_sha256"],
            "Actual primary SDK reader/schema/version differs from566")
    data = DataStore()
    try:
        data.open_for_scan(str(pending/"wandb"/run.name/Path(refs["sdk"]["path"]).name))
        with Path(refs["journal"]["path"]).open("rb") as journal, (output/"history.normalized.jsonl").open("xb") as normalized, (output/"history.scalars.csv").open("xb") as scalar_csv:
            sink = CompleteScalarSink(normalized,scalar_csv)
            details = primary.compare_records(primary.scan_records(data,pb.Record,deadline=time.monotonic()+180),primary.journal_rows(journal),sink,
                expected_run_id=certificate["sdk_run_id"],expected_config=expected_config,expected_summary=expected_summary,
                expected_rows=certificate["history_rows"],expected_display_name=request["run_id"],budget_bytes=64<<20)
            normalized.flush(); scalar_csv.flush(); os.fsync(normalized.fileno()); os.fsync(scalar_csv.fileno())
    finally:
        data.close()
    compare_certificate(details,certificate)
    require(sink.rows == certificate["history_rows"] and sink.digest.hexdigest() == certificate["normalized_history_sha256"], "Complete export stream differs")
    require(sink.scalars == sum(item["count"] for item in certificate["series"].values()),"Full CSV scientific scalar population differs")
    details.update(complete_scalar_CSV_rows=sink.scalars,complete_history_exported=True,expected_summary=expected_summary,
                   reference_kind="primary",H0_dimension=512,layers=6,formal_pretraining_complete=False,architecture_selection_claimed=False)
    helper.atomic_json(output/"verification.json",details)
    helper.atomic_bytes(output/"index.html",b'<!doctype html><meta charset="utf-8"><h1>Primary512 short500 diagnostic</h1><p>All56738 native history rows and every scalar, not a sample. Not formal pretraining or architecture selection.</p><ul><li><a href="history.scalars.csv">complete long scalar CSV</a></li><li><a href="history.normalized.jsonl">complete normalized history</a></li><li><a href="verification.json">native/config/summary/step/EOF/exit verification</a></li></ul>')
    for ref in selected.values():
        require(v7.file_ref(ref["path"]) == ref,"Primary original selected source changed")
    require(helper.source_manifest(run)==inventory,"Original primary SDK changed")
    bindings.unchanged()
    manifest = {"schema":"model_v3_primary512_closed_archive_v8","job_id":"4520544","verification_job_id":"4520566",
        "slurm_state":"COMPLETED","exit_code":"0:0","source_attachments":list(selected.values()),
        "SDK_runs":[{"run_id":certificate["sdk_run_id"],"source_run":str(run),"source_files":inventory,"verification":details}],
        "hash_only_checkpoint_reference":refs["export_checkpoint"],"checkpoint_max_bytes":512<<20,"checkpoint_copied_or_deserialized":False,
        "reference_kind":"primary","H0_dimension":512,"layers":6,"optimizer_updates_before_panel":500,
        "source_kind":"short_A00_native20_500_diagnostic_only","formal_pretraining_complete":False,"architecture_selection_claimed":False,
        "original_files_preserved":True,"online_sync_performed":False,"scientific_acceptance":False}
    return manifest,[{"job_id":"4520544","run_id":certificate["sdk_run_id"],"name":"Primary512 six-layer short500 complete18cell development panel",
                     "slurm_state":"COMPLETED","exit_code":"0:0","offline_unsynced":True}]


def verify_pins(path,sha):
    value,reference = v7.read_json(path)
    require(reference["sha256"] == sha and value["schema"] == "model_v3_archive_closed_sources_v8","v8 source manifest differs")
    for item in value["files"]:
        require(v7.file_ref(item["path"]) == item,"Frozen v8/dependency source differs")
    return reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quota-closed-receipt",type=Path,required=True)
    parser.add_argument("--quota-closed-sha256",required=True)
    parser.add_argument("--source-pins",type=Path,required=True)
    parser.add_argument("--source-pins-sha256",required=True)
    parser.add_argument("--expected-node",required=True)
    parser.add_argument("--expected-partition",default="cpu")
    parser.add_argument("--jobs",nargs="+",choices=("4520546","4520544"),default=["4520546","4520544"])
    args = parser.parse_args()
    require(os.getuid()==1278 and os.environ.get("SLURM_JOB_ID") and int(os.environ.get("SLURM_CPUS_PER_TASK","0"))>=16,
            "Owned>=16CPU Slurm allocation required")
    require(socket.gethostname().split(".")[0] == args.expected_node and os.environ.get("SLURM_JOB_PARTITION") == args.expected_partition == "cpu"
            and args.expected_node not in {"compute-0-20","compute-0-21","compute-0-22"} and os.environ.get("CUDA_VISIBLE_DEVICES")=="",
            "Exact CPU-only partition/node/hidden-GPU binding required")
    source_ref = verify_pins(args.source_pins,args.source_pins_sha256)
    jobs = [(job,"FAILED","1:0") if job=="4520546" else (job,"COMPLETED","0:0") for job in dict.fromkeys(args.jobs)]
    if "4520544" in args.jobs:
        jobs.append(("4520566","COMPLETED","0:0"))
    v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs)
    helper = load_source(v7.HELPER,v7.HELPER_SHA,"fixed_archive_helper_v8")
    descriptor = os.open(v7.DEST/".archive.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    info = helper.owned(v7.DEST/".archive.lock")
    require((os.fstat(descriptor).st_dev,os.fstat(descriptor).st_ino)==(info.st_dev,info.st_ino),"Task lock identity differs")
    with os.fdopen(descriptor,"a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old = v7.read_json(v7.DEST/"index.json")[0]
        root = v7.DEST/"closed_v8"; root.mkdir(mode=0o700,exist_ok=True); helper.owned(root,True)
        for job in dict.fromkeys(args.jobs):
            receipt,receipt_ref = v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs)
            target = root/("job"+job)
            if target.exists():
                helper.owned(target,True)
                manifest = v7.read_json(target/"manifest.json")[0]
                require(manifest["archive_source_pins"]==source_ref and manifest["job_id"]==job,"Existing v8 archive identity differs")
                v7.recheck_manifest(helper,manifest,target)
                if "hash_only_checkpoint_reference" in manifest:
                    ref = manifest["hash_only_checkpoint_reference"]
                    require(v7.file_ref(ref["path"],512<<20)==ref,"Existing hash-only checkpoint provenance differs")
                entries = manifest["task_index_entries"]
            else:
                pending = root/(".job"+job+".archive_job"+os.environ["SLURM_JOB_ID"]+".pending"); pending.mkdir(mode=0o700)
                manifest,entries = make_546(helper,pending) if job=="4520546" else make_primary(helper,pending)
                for row in entries:
                    row["path"] = str(target.relative_to(v7.ARCHIVE))
                manifest.update(archive_source_pins=source_ref,archive_helper_sha256=v7.HELPER_SHA,quota_closed_receipt=receipt_ref,
                    actual_closed_job_lines={j:receipt["closed_jobs"][j] for j,_,_ in jobs},task_index_entries=entries)
                links = ''.join('<li><a href="sdk_exports/'+html.escape(row["run_id"])+'/index.html">'+html.escape(row["name"])+'</a></li>' for row in entries)
                helper.atomic_bytes(pending/"index.html",('<!doctype html><meta charset="utf-8"><h1>'+job+'</h1><p>Originals preserved; offline unsynced. Actual '+manifest["slurm_state"]+' '+manifest["exit_code"]+'. No architecture-selection/formal-pretraining claim.</p><ul>'+links+'</ul><a href="manifest.json">Complete archive manifest</a>').encode())
                files = list(pending.rglob("*")); require(len(files)<=10000,"Archive entry bound exceeded")
                for path in files:
                    helper.owned(path,path.is_dir())
                manifest["archived_files"] = [{"relative_path":str(path.relative_to(pending)),**{k:v for k,v in v7.file_ref(path).items() if k!="path"}} for path in files if path.is_file()]
                helper.atomic_json(pending/"manifest.json",manifest)
                require(sum(path.stat().st_size for path in pending.rglob("*") if path.is_file())<=256<<20,"Per-case256MiB archive bound exceeded")
                v7.check_receipt(args.quota_closed_receipt,args.quota_closed_sha256,jobs)
                verify_pins(args.source_pins,args.source_pins_sha256)
                os.rename(pending,target)
            old = {**old,"entries":v7.merge_entries(old["entries"],entries),"offline_unsynced":True,"updated_Asia_Shanghai":helper.stamp()}
            helper.atomic_json(v7.DEST/"index.json",old)
            links = ''.join('<li><a href="../'+html.escape(row["path"])+'/index.html">'+html.escape(row["name"]+' / '+row["job_id"]+' / '+row["run_id"])+'</a></li>' for row in old["entries"])
            helper.atomic_bytes(v7.DEST/"index.html",('<!doctype html><meta charset="utf-8"><h1>模型v3离线归档</h1><p>Failed jobs, synthetic diagnostics, historical384 and primary512 short500 scopes remain explicit. Offline unsynced.</p><ul>'+links+'</ul>').encode())
        print(json.dumps({"status":"ARCHIVED","processed_jobs":args.jobs,"index_entries":len(old["entries"]),"online_sync_performed":False}))


if __name__=="__main__":
    main()
