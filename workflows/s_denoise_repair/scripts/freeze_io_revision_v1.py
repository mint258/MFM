"""Bind the tested runtime-only I/O revision without changing earlier evidence."""
import hashlib,json,os,socket,subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path("/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016")
SOURCE=ROOT/"source_v3"
OLD=ROOT/"source_v2"
def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):h.update(block)
    return h.hexdigest()
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".pending")
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n");temp.replace(path)
def actual(job):
    text=subprocess.check_output(["sacct","-j",str(job),"--format=JobIDRaw,State,ExitCode","-n","-P"],text=True)
    row=next(r.split("|") for r in text.splitlines() if r.split("|")[0]==str(job))
    assert row[1:]==["COMPLETED","0:0"],row
    return text
assert os.getuid()==1278 and socket.gethostname().split(".")[0]=="sonmi"
target=ROOT/"configs/D3_source_binding_v4.json"
assert not target.exists()
suite=ET.parse(ROOT/"reports/all_tests_v4.xml").getroot()
assert not list(suite.iter("failure")) and not list(suite.iter("error"))
assert len(list(suite.iter("testcase")))==2016
assert json.loads((ROOT/"reports/legacy_bitexact_v3/result.json").read_text())["status"]=="LEGACY_V2_BITEXACT_PASS"
worker=json.loads((ROOT/"reports/epoch_workers_v3.json").read_text())
assert worker["status"]=="REAL_SPAWN_EPOCH_NOISE_AND_RESUME_PASS" and worker["subset_map_close_uses_local_index"] is True
crossover=json.loads((ROOT/"reports/subset_handle_crossover_v1.json").read_text())
assert crossover["status"]=="SUBSET_HANDLE_CROSSOVER_PARITY_PASS" and crossover["scientific_data_or_seeds_modified"] is False
receipts={}
for name in ["all_suite_v4","epoch_workers_v3","gpu_smoke_v3","subset_handle_benchmark_v1","analysis_rules_v1"]:
    receipt=json.loads((ROOT/"submission"/(name+".json")).read_text())
    receipts[name]={"job_id":receipt["job_id"],"actual_sacct":actual(receipt["job_id"])}
smoke_job=receipts["gpu_smoke_v3"]["job_id"]
smoke_root=ROOT/"diagnostics/new_loss_gpu_smoke_v1"/("job_"+smoke_job)
assert json.loads((smoke_root/"result.json").read_text())["status"]=="REAL_S_MODEL_NEW_LOSS_GPU_SMOKE_PASS"
assert all((smoke_root/(name+"_safe_checkpoint.pt")).is_file() for name in ["A0","A1","A2"])
core=[]
for path in sorted((SOURCE/"current/phychem_mfm").rglob("*.py")):
    relative=path.relative_to(SOURCE)
    assert sha(path)==sha(OLD/relative),"CORE_SCIENTIFIC_CODE_CHANGED_DURING_IO_FIX"
    core.append(str(relative))
files=sorted((SOURCE/"current/phychem_mfm").rglob("*.py"))+sorted((SOURCE/"workflows/s_denoise").glob("*.py"))
refs=[{"path":str(path),"sha256":sha(path),"bytes":path.stat().st_size} for path in files]
value={"status":"D3_CODE_TESTED_AND_BOUND_BEFORE_SCIENTIFIC_TRAINING","runtime_revision":3,"source_root":str(SOURCE),
       "files":refs,"tests":2016,"C6_actual_job_closure":receipts,
       "core_identical_to_tested_v2":core,
       "new_option":{"subset_map_close_uses_local_index":True,"default":False,"source_global_noise_indices_unchanged":True},
       "guide_sha256":sha(ROOT/"user_repair_guide.md"),
       "old_input_manifest_sha256":sha(ROOT.parent/"sprime_s_convergence_20261013/training_inputs_v1/manifest.json"),
       "rules":{"path":str(SOURCE/"workflows/s_denoise/configs/decision_rules_v3.json"),
                "sha256":sha(SOURCE/"workflows/s_denoise/configs/decision_rules_v3.json")},
       "scientific_gate_passed":False}
save(target,value)
manifest_path=SOURCE/"docs/SOURCE_MANIFEST.json"
manifest=json.loads(manifest_path.read_text())
manifest["source_revisions"].append({"revision":"s_denoise_repair_v3_D3_IO_source_freeze","date":"2026-10-16",
    "status":"CODE_TESTS_PASSED_SCIENTIFIC_GATE_PENDING","source_root":str(SOURCE),
    "binding":{"path":str(target),"sha256":sha(target)},"files":refs})
save(manifest_path,manifest)
print(json.dumps({"status":value["status"],"files":len(refs),"tests":2016,"core_identical_files":len(core)}),flush=True)
