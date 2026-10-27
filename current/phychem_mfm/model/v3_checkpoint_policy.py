"""Opt-in checkpoint policy consuming bounded CLOSED capacity observations.

No marketing-name table, fabricated capacity, OOM fallback or adoption gate.
Manual mode needs no profile and is how a first genuine observation is made.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import torch
from .v3_logical_batch import LogicalBatchPadding

ROOT = Path(__file__).resolve().parents[3]
FLAGS = ("backbone_checkpointing", "distance_checkpointing", "head_checkpointing")


def require(ok, reason):
    if not ok:raise ValueError(reason)


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()

def workload_identity(model, *, seed, input_kind, snapshot, binding):
    return canonical({"model":model,"seed":seed,"input":input_kind,"snapshot":snapshot,
        "reference_configuration_sha256":binding["reference_configuration"]["sha256"],
        "a4_configuration_sha256":binding["a4_configuration"]["sha256"],
        "loss_policy":binding["loss_policy"],"loss_weights":binding["loss_weights"],
        "supervision":binding["supervision"]})

def file_reference(path, limit=16 * 1024**2):
    path=Path(path).absolute();require(path.resolve()==path,"Capacity source ancestry must not alias another path");before=path.lstat()
    require(path.is_file() and not path.is_symlink() and before.st_uid==os.getuid()
            and before.st_nlink==1 and before.st_size<=limit,"Ordinary owned bounded capacity source required")
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024**2),b""):h.update(block)
    after=path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),"Capacity source changed while hashing")
    return {"path":str(path),"bytes":before.st_size,"sha256":h.hexdigest()}


def read_bound(reference, limit=2 * 1024**2):
    require(isinstance(reference,dict) and set(reference)=={"path","bytes","sha256"},"Exact capacity rawref required")
    require(file_reference(reference["path"],limit)==reference,"Capacity source raw SHA differs")
    return json.loads(Path(reference["path"]).read_bytes())


def implementation_sources():
    """Mandatory complete model/S-source projection, independent of import order.

    All package sources include routes, typed outputs, normalization, registry,
    decoding, supervision and the actual numeric acceptance implementation.
    All original S script sources include local imports which may be loaded
    after load_references. Optional dynamically imported extras stay separate.
    """
    paths=set()
    for relative in ("current/phychem_mfm","workflows/sprime_s/scripts"):
        directory=ROOT/relative
        require(directory.is_dir() and directory.resolve()==directory,
                "Ordinary complete mandatory source directory required")
        paths.update(directory.rglob("*.py"))
    for name in ("tools/model_v3/profile_s_baseline.py","tools/model_v3/profile_sampling.py",
                 "tools/model_v3/analyze_trace_v3.py","tools/model_v3/native_runtime_bindings.py",
                 "tools/model_v3/private_runtime_storage.py","tools/model_v3/run_supervised.py",
                 "tools/model_v3/runtime_monitor.py","tools/model_v3/a_execution_runtime.py",
                 "tools/model_v3/paired_a_acceptance.py","tools/model_v3/single_a_benchmark.py",
                 "tools/model_v3/a_speed_report.py","tools/model_v3/a_checkpoint_export.py",
                 "tools/model_v3/s_input_stream.py"):
        paths.add(ROOT/name)
    require(0<len(paths)<=2048,"Bounded complete mandatory execution source graph required")
    result,total={},0
    for path in sorted(paths):
        reference=file_reference(path,2*1024**2);total+=reference["bytes"]
        require(total<=32*1024**2,"Mandatory execution source graph exceeds explicit32MiB bound")
        result[path.relative_to(ROOT).as_posix()]=reference["sha256"]
    return result


def verify_observed_sources(observed,mandatory):
    """Check the saved actual graph, without demanding equal dynamic extra sets."""
    require(isinstance(observed,dict) and 0<len(observed)<=2048,
            "Actual run config.source_sha256 execution graph required")
    require(set(mandatory)<=set(observed) and all(observed[name]==sha for name,sha in mandatory.items()),
            "Actual run source graph lacks or changes a mandatory execution dependency")
    total=0
    for name,sha in observed.items():
        relative=Path(name)
        require(isinstance(name,str) and not relative.is_absolute() and ".." not in relative.parts
                and relative.suffix==".py" and isinstance(sha,str) and re.fullmatch("[0-9a-f]{64}",sha),
                "Ordinary repository-relative actual Python source binding required")
        reference=file_reference(ROOT/relative,2*1024**2);total+=reference["bytes"]
        require(total<=32*1024**2 and reference["sha256"]==sha,
                "Saved actual execution dependency differs from current source bytes")


def bind_execution_sources(binding):
    """Executed by both opt-in A runners before model allocation/config save."""
    mandatory=implementation_sources()
    require(isinstance(binding.get("source_sha256"),dict),"Actual runner source binding required")
    source=dict(binding["source_sha256"])
    for name,sha in mandatory.items():
        require(name not in source or source[name]==sha,"Execution source changed after initial runner binding")
        source[name]=sha
    verify_observed_sources(source,mandatory)
    binding["source_sha256"]=dict(sorted(source.items()))
    return mandatory

@dataclass(frozen=True)
class PerformanceExecution:
    schema: str = "model_v3_performance_execution_v1"
    checkpoint_policy: str = "manual"
    padding: dict | None = None
    capacity_profile: dict | None = None
    batch_padded_cost: int = 8000000
    resident_models: int = 1
    workload_sha256: str | None = None

    def __post_init__(self):
        require(self.schema=="model_v3_performance_execution_v1" and self.checkpoint_policy in
                {"manual","auto_closed_profile_v1"},"Unknown execution schema/checkpoint policy")
        require(type(self.batch_padded_cost) is int and self.batch_padded_cost>0
                and type(self.resident_models) is int and self.resident_models in (1,2),"Actual batch/residency limits required")
        if self.padding is not None:LogicalBatchPadding(**self.padding)
        require(self.workload_sha256 is None or isinstance(self.workload_sha256,str)
                and re.fullmatch("[0-9a-f]{64}",self.workload_sha256),"Explicit workload SHA required")
        if self.checkpoint_policy=="auto_closed_profile_v1":
            require(self.capacity_profile is not None and self.workload_sha256 is not None,
                    "Auto checkpoint policy needs a bound actual profile and workload; unknown capacity is refused")
        else:require(self.capacity_profile is None,"Manual mode cannot silently consume an automatic profile")

    def semantic(self):
        result=asdict(self)
        if self.padding is not None:result["padding"]=asdict(LogicalBatchPadding(**self.padding))
        return result


def runtime_controls():
    return {"deterministic_algorithms":torch.are_deterministic_algorithms_enabled(),
            "deterministic_warn_only":torch.is_deterministic_algorithms_warn_only_enabled(),
            "cudnn_deterministic":bool(torch.backends.cudnn.deterministic),
            "cudnn_benchmark":bool(torch.backends.cudnn.benchmark),
            "matmul_tf32_before_role_context":bool(torch.backends.cuda.matmul.allow_tf32),
            "cudnn_tf32_before_role_context":bool(torch.backends.cudnn.allow_tf32),
            "float32_matmul_precision_before_role_context":torch.get_float32_matmul_precision(),
            "cublas_workspace_config":os.environ.get("CUBLAS_WORKSPACE_CONFIG")}

def current_cuda_capacity():
    require(torch.cuda.is_available() and torch.cuda.device_count()==1,"Auto profile requires an actual single visible CUDA device")
    uuid=os.environ.get("CUDA_VISIBLE_DEVICES","")
    require(re.fullmatch("GPU-[0-9a-fA-F-]+",uuid),"Physical CUDA UUID must be explicit")
    prop=torch.cuda.get_device_properties(0)
    actual=str(getattr(prop,"uuid",""))
    require(actual.removeprefix("GPU-").lower()==uuid.removeprefix("GPU-").lower(),"Torch and actual physical UUID differ")
    argv=["nvidia-smi","--id="+uuid,"--query-gpu=uuid,name,driver_version,memory.total,memory.free","--format=csv,noheader,nounits"]
    observation=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10)
    row=[part.strip() for part in observation.stdout.strip().split(",")]
    require(observation.returncode==0 and len(row)==5 and row[0]==uuid,"Actual GPU capacity/driver observation failed")
    app_argv=["nvidia-smi","--query-compute-apps=gpu_uuid,pid,used_memory","--format=csv,noheader,nounits"]
    apps=subprocess.run(app_argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10)
    require(apps.returncode==0,"Current physical GPU process observation failed")
    for line in apps.stdout.splitlines():
        cells=[value.strip() for value in line.split(",")]
        require(len(cells)>=3,"Malformed current GPU process observation")
        if cells[0]==uuid:require(int(cells[1])==os.getpid(),"Current GPU contains a foreign compute process")
    return {"uuid":uuid,"name":row[1],"driver_version":row[2],"total_bytes":int(float(row[3])*1024**2),
            "free_bytes":int(float(row[4])*1024**2),"torch_total_bytes":int(prop.total_memory),"torch_version":str(torch.__version__),
            "cuda_version":torch.version.cuda,"cudnn_version":torch.backends.cudnn.version(),"runtime_controls":runtime_controls(),"raw_argv":argv,"raw_stdout":observation.stdout,
            "raw_returncode":observation.returncode,"raw_stderr":observation.stderr,
            "process_argv":app_argv,"process_stdout":apps.stdout,"process_returncode":apps.returncode,"process_stderr":apps.stderr}


def _parent_c0(raw,job):
    require(raw["returncode"]==0 and raw["argv"][0]=="sacct" and "-j" in raw["argv"]
            and raw["argv"][raw["argv"].index("-j")+1]==job,"Actual parent sacct observation required")
    formats=[part.split("=",1)[1].split(",") for part in raw["argv"] if part.startswith("--format=")]
    require(len(formats)==1,"Explicit actual sacct columns required")
    rows=[dict(zip(formats[0],line.split("|"))) for line in raw["stdout"].splitlines() if line.strip()]
    rows=[row for row in rows if row.get("JobIDRaw",row.get("JobID"))==job]
    require(len(rows)==1 and rows[0]["State"]=="COMPLETED" and rows[0]["ExitCode"]=="0:0","Actual capacity parent must be C0")


def _one_cli_value(arguments,name,*,default=None,required=False):
    require(not any(arg.startswith(name+"=") for arg in arguments),
            "Use the existing explicit separate-value A CLI form: "+name)
    places=[i for i,arg in enumerate(arguments) if arg==name]
    require(len(places)<=1 and (not required or len(places)==1),"Missing/duplicate actual A CLI option: "+name)
    if not places:return default
    require(places[0]+1<len(arguments),"Missing actual A CLI value: "+name)
    return arguments[places[0]+1]


def qualify_a_invocation(config,summary,sup,output,sources,*,paired):
    """Join the original guard's actual argv/kernel frame to the fixed A tool.

    Retired PIDs are never probed. Relative scripts are resolved using the
    actual opt-in runner cwd, cross-checked against argv and source bytes.
    """
    frame=config.get("performance_execution_invocation")
    require(isinstance(frame,dict) and set(frame)=={"source_root","cwd","logical_python","argv"},
            "Actual opt-in A runner invocation frame required")
    command=sup["command"]
    require(isinstance(command,list) and len(command)>=2 and all(isinstance(arg,str) for arg in command),
            "Actual A child command required")
    require(command[0]==config["logical_python"]==frame["logical_python"] and Path(command[0]).is_absolute(),
            "Actual A interpreter differs from the saved logical interpreter")
    offset=1;flags=[]
    while offset<len(command) and command[offset] in ("-u","-B"):
        flags.append(command[offset]);offset+=1
    require(len(flags)==len(set(flags)) and offset<len(command) and not command[offset].startswith("-"),
            "Only the existing -u/-B Python prefix flags are admitted")
    require(frame["argv"]==command[offset:],"Actual sys.argv and supervisor Python command differ")
    cwd,source_root=Path(frame["cwd"]),Path(frame["source_root"])
    require(all(path.is_absolute() and path.is_dir() and path.resolve()==path for path in (cwd,source_root)),
            "Actual ordinary source-root/cwd evidence required")
    def actual_path(value):
        path=Path(value)
        return (path if path.is_absolute() else cwd/path).resolve(strict=True)
    relative="tools/model_v3/paired_a_acceptance.py" if paired else "tools/model_v3/single_a_benchmark.py"
    entry=actual_path(command[offset])
    require(entry==source_root/relative and file_reference(entry,2*1024**2)["sha256"]==sources[relative]
            ==config["source_sha256"][relative],"Actual A entrypoint/source is not the qualified original tool")
    guard="tools/model_v3/run_supervised.py"
    require(sup["supervisor_source_sha256"]==sources[guard]==config["source_sha256"][guard],
            "Actual supervisor guard source differs from the pinned original guard")
    identity=sup["launch_identity"]
    argv_sha=hashlib.sha256(b"\0".join(arg.encode("utf-8","surrogateescape") for arg in command)+b"\0").hexdigest()
    require(identity["status"]=="ACTIVE" and identity["argv"]==command and identity["argv_sha256"]==argv_sha
            and type(identity["pid"]) is int and identity["pid"]>0
            and identity["pid"]==sup["child_pid"]==identity["pgid"]==identity["sid"]
            and type(identity["start_ticks"]) is int and identity["start_ticks"]>0
            and re.fullmatch(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}",identity["boot_id"])
            and str(identity["slurm_job_id"])==str(config["job_id"])
            and isinstance(identity["cgroup"],str) and identity["cgroup"]==sup["supervisor_slurm_cgroup"] and identity["cgroup"]
            and sup["gpu_uuid"]==config["gpu_uuid"],"Original guard launch argv/kernel/job/GPU identity differs")
    arguments=command[offset+1:]
    require(not any(flag in arguments for flag in ("--smoke","--resume","--atom-bucket-width","--exact-atom-sort")),
            "Smoke/resume or changed logical-batch sampler cannot qualify a capacity profile")
    require(actual_path(_one_cli_value(arguments,"--output",required=True))==output.resolve()
            and _one_cli_value(arguments,"--code-sha",required=True)==config["code_sha"]
            and _one_cli_value(arguments,"--input",default="native_s")==config["input"]=="native_s"
            and int(_one_cli_value(arguments,"--seed",default="0"))==config["seed"],
            "Actual A command does not bind its saved output/code/input/seed")
    request=config["performance_execution_request"]
    require(actual_path(_one_cli_value(arguments,"--performance-execution",required=True))==Path(request["path"])
            and _one_cli_value(arguments,"--performance-execution-sha256",required=True)==request["sha256"],
            "Actual A invocation did not request this bound performance execution")
    read_bound(request)
    candidate=actual_path(_one_cli_value(arguments,"--candidate-options",required=True))
    require(file_reference(candidate,2*1024**2)["sha256"]==config["candidate_options_sha256"],
            "Actual A candidate-options source differs")
    if paired:
        require(config["fixed_batches"]==20 and config["trajectory_updates"]==500
                and not any(flag in arguments for flag in ("--role","--abba-position","--series-id")),
                "Only the actual original20batch/500update paired tool qualifies")
    else:
        require(_one_cli_value(arguments,"--role",required=True)==config["role"]==summary["role"]=="candidate"
                and int(_one_cli_value(arguments,"--abba-position",required=True))==config["abba_position"]
                ==summary["abba_position"] and config["abba_position"] in (2,3)
                and _one_cli_value(arguments,"--series-id",required=True)==config["series_id"]==summary["series_id"]
                and isinstance(config["series_id"],str) and 0<len(config["series_id"])<=128
                and config["warmup_updates"]==2 and config["measured_updates"]==20
                and config["padding_exploration"] is False and summary["padding_exploration"] is False,
                "Only the matching standalone candidate2+20 A/B/B/A role qualifies")

def load_closed_observation(item, requested, configuration, options, sources):
    """Recognize only the existing A runner's actual metadata, not arbitrary bools.

    New execution-enabled runs write per-step logical graph counts. Older runs
    without that observation are not silently upgraded to this capacity schema.
    """
    require(set(item)=={"configuration","summary","run_status","supervisor","parent_sacct","steps"},
            "Unknown closed capacity observation members")
    config=read_bound(item["configuration"]);summary=read_bound(item["summary"])
    status=read_bound(item["run_status"]);sup=read_bound(item["supervisor"])
    job=str(config["job_id"]);_parent_c0(read_bound(item["parent_sacct"]),job)
    require(str(sup["job_id"])==job and sup["status"]=="COMPLETED" and sup["exit_code"]==0
            and sup["first_failure"] is None and sup["remaining_recorded_processes_before_retirement"]==[]
            and sup["private_storage_cleanup_errors"]==[] and sup["launch_identity"]["uid"]==os.getuid(),
            "Capacity observation supervisor/private/process closure failed")
    require(status["failure"] is None and status["cleanup_errors"]==[]
            and status["stream_cleanup"]["input_descriptors_closed"] is True and config["input"]=="native_s"
            and config["smoke"] is False and config["model"]==dict(configuration),"Closed native capacity model/scope differs")
    paired=summary["status"]=="PAIRED_GATES_PASS"
    if paired:
        require(summary["full_A_numeric_acceptance"] is True and summary["fixed_batch_pass"] is True
                and summary["trajectory_pass"] is True,"Paired capacity source needs its full original gates")
        expected_updates=500;observed_residency=2
    else:
        require(summary["status"]=="STANDALONE_TIMING_COMPLETED" and summary["smoke"] is False
                and summary["warmup_updates"]==2 and summary["measured_updates"]==20
                and summary["foreign_gpu_risk_observed"] is False,"Full standalone capacity observation required")
        expected_updates=22;observed_residency=1
    require(summary["configuration_sha256"]==config["configuration_sha256"]
            and summary["gpu_uuid"]==config["gpu_uuid"] and status["status"]==summary["status"],"Capacity summary/config/terminal identity differs")
    require(canonical({k:v for k,v in config.items() if k!="configuration_sha256"})==config["configuration_sha256"]
            and summary["code_sha"]==config["code_sha"],"Actual capacity configuration/source binding differs")
    require("performance_execution" in config,"Older run has no explicit execution/source observation; do not retrofit it")
    output=Path(item["configuration"]["path"]).parent
    require(all(Path(item[key]["path"]).parent==output for key in ("summary","run_status","steps")),
            "Capacity records must come from one actual run output")

    require("source_sha256" in config,"Closed capacity config lacks its actual complete execution source graph")
    verify_observed_sources(config["source_sha256"],sources)
    qualify_a_invocation(config,summary,sup,output,sources,paired=paired)
    execution=config["performance_execution"]
    observed=execution["requested"]
    require(observed["workload_sha256"]==workload_identity(config["model"],seed=config["seed"],
            input_kind=config["input"],snapshot=config["original_shard_snapshot_prejob_sha256"],binding=config),
            "Capacity workload declaration does not bind its actual saved input/seed/loss configuration")
    require(execution["implementation_sha256"]==sources and observed["padding"]==requested.padding
            and observed["workload_sha256"]==requested.workload_sha256
            and observed["resident_models"]==requested.resident_models==observed_residency
            and requested.batch_padded_cost<=observed["batch_padded_cost"],"Capacity source/workload/layout/residency/budget differs")
    physical=execution["resolved_options"]
    for name,value in asdict(options).items():
        if name not in FLAGS:require(physical[name]==value,"Capacity measurement changed another execution option: "+name)
    flags={key:physical[key] for key in FLAGS}
    require(all(type(value) is bool for value in flags.values()),"Three measured checkpoint booleans required")
    rawref=item["steps"];require(file_reference(rawref["path"],16*1024**2)==rawref,"Capacity step journal SHA differs")
    physical_total=config["gpu"]["total_bytes"]
    require(type(physical_total) is int and physical_total>0 and type(config["gpu_total_bytes"]) is int
            and config["gpu_total_bytes"]>0,"Actual NVML and Torch positive memory observations required")
    shapes,updates,peak=set(),[],0
    limits={"graphs":0,"atoms":0,"max_nodes":0,"padded_cost":0}
    with Path(rawref["path"]).open() as stream:
        for line in stream:
            require(len(line)<=1024**2,"Bounded capacity observation line required")
            row=json.loads(line)
            if paired and row["phase"]!="trajectory":continue
            updates.append(row["optimizer_updates"])
            resource=row if paired else row["resources"]
            require(resource["foreign_gpu_risk_observed"] is False,"Foreign process in observed capacity source")
            gpu=resource["gpu_observation"]
            require(gpu["uuid"]==config["gpu_uuid"] and gpu["total_bytes"]==physical_total,"Physical GPU identity drifted during capacity measurement")
            require(all(type(process["used_memory_bytes"]) is int and process["used_memory_bytes"]>=0
                        for process in gpu["compute_processes"]),"Unknown actual GPU process memory is not zero")
            own=sum(process["used_memory_bytes"] for process in gpu["compute_processes"] if process["own"])
            require(all(type(resource[name]) is int and resource[name]>=0 for name in
                        ("peak_allocated_bytes","peak_reserved_bytes")),"Actual allocator byte counts required")
            peak=max(peak,own,resource["peak_allocated_bytes"],resource["peak_reserved_bytes"])
            counts=row["performance_execution"]["graph_atom_counts"]
            require(counts and all(type(n) is int and n>0 for n in counts),"Actual packed graph observation required")
            shapes.add((len(counts),max(counts)))
            for key,value in (("graphs",len(counts)),("atoms",sum(counts)),("max_nodes",max(counts)),
                              ("padded_cost",len(counts)*max(counts)**2)):
                limits[key]=max(limits[key],value)
    require(updates==list(range(1,expected_updates+1)) and 0<peak<=.85*physical_total,
            "Incomplete/out-of-budget actual optimizer-state capacity observation")
    return {"gpu_uuid":config["gpu_uuid"],"gpu_name":config["gpu_name"],"total_bytes":physical_total,"torch_total_bytes":config["gpu_total_bytes"],
            "torch_version":config["torch_version"],"cuda_version":config["cuda_version"],
            "driver_version":config["gpu"]["driver_version"],"cudnn_version":config["cudnn_version"],
            "runtime_controls":{key:config["deterministic_controls"]["actual"][key] for key in runtime_controls()},"flags":flags,"peak_bytes":peak,
            "observed_dense_shapes":tuple(sorted(shapes)),"observed_size_limits":limits,"source":item,
            "compile_backbone":physical["compile_backbone"],"sampled_capacity_not_universal_bound":True}


class ClosedCapacityGuard:
    def __init__(self, observation, configured_budget):
        self.observation,self.configured_budget=observation,configured_budget
    def check(self,data,counts):
        require(data.x.device.type=="cuda","Actual profiled CUDA execution required")
        actual={"graphs":len(counts),"atoms":sum(counts),"max_nodes":max(counts),
                "padded_cost":len(counts)*max(counts)**2}
        require(all(actual[key]<=self.observation["observed_size_limits"][key] for key in actual),
                "Actual logical batch exceeds measured size envelope; no implicit OOM retry, dropping or fallback")
        if self.observation["compile_backbone"]:
            require((len(counts),max(counts)) in self.observation["observed_dense_shapes"],
                    "Unmeasured compiled dense shape has no workspace-capacity admission")


def select_capacity(records,environment):
    """Pure metadata predicate. CPU fixtures do not constitute a CUDA admission."""
    for row in records:
        compatible=(row["gpu_uuid"]==environment["uuid"] and row["gpu_name"]==environment["name"]
            and row["total_bytes"]==environment["total_bytes"] and row["torch_total_bytes"]==environment["torch_total_bytes"]
            and row["torch_version"]==environment["torch_version"]
            and row["cuda_version"]==environment["cuda_version"] and row["driver_version"]==environment["driver_version"]
            and row["cudnn_version"]==environment["cudnn_version"] and row["runtime_controls"]==environment["runtime_controls"]
            and environment["free_bytes"]>=row["peak_bytes"]+.1*environment["total_bytes"]
            and environment["total_bytes"]-environment["free_bytes"]+row["peak_bytes"]<=.85*environment["total_bytes"])
        if compatible:return row
    return None

def prepare_execution(configuration, options, execution):
    spec=execution if isinstance(execution,PerformanceExecution) else PerformanceExecution(**execution)
    # Canonicalize optional padding defaults before matching measured observations.
    spec=PerformanceExecution(**spec.semantic())
    require(not (spec.checkpoint_policy=="auto_closed_profile_v1" and options.compile_backbone and spec.padding is not None),
            "Auto checkpoint with compiled logical-batch chunks lacks actual compiled chunk-shape capacity evidence")
    if spec.padding is not None:
        require(options.precision=="fp32","Logical-batch A padding is currently fp32 only")
        require(float(configuration["backbone"].get("dropout",0.))==0.,"Logical-batch padding requires zero dropout before construction")
    require("v3_architecture" not in configuration["backbone"],"Execution integration requires the declared original backbone, not unreviewed C1 mathematics")
    sources=implementation_sources();resolved=options;guard=None;selection=None
    if spec.checkpoint_policy=="auto_closed_profile_v1":
        require(options.backbone_checkpointing is None and options.distance_checkpointing and options.head_checkpointing,
                "Auto checkpoint policy cannot silently override manual checkpoint flags")
        profile=read_bound(spec.capacity_profile)
        require(set(profile)=={"schema","observations"} and profile["schema"]=="model_v3_closed_checkpoint_capacity_profiles_v1"
                and isinstance(profile["observations"],list) and 0<len(profile["observations"])<=32,"Unknown, empty or oversized actual capacity profile")
        records=[load_closed_observation(item,spec,configuration,options,sources) for item in profile["observations"]]
        environment=current_cuda_capacity()
        row=select_capacity(records,environment)
        if row is not None:
            resolved=replace(options,**row["flags"]);guard=ClosedCapacityGuard(row,spec.batch_padded_cost)
            selection={"environment":environment,"measured":row,"reason":"MATCHED_CLOSED_PROFILE_BEFORE_EXECUTION"}
        require(selection is not None,"No applicable measured GPU/workload/budget capacity profile; execution refused")
    physical=asdict(resolved)
    if physical["backbone_checkpointing"] is None:
        physical["backbone_checkpointing"]=bool(configuration["backbone"].get("activation_checkpointing",False))
    receipt={"schema":"model_v3_performance_execution_receipt_v1","requested":spec.semantic(),
             "resolved_options":physical,"implementation_sha256":sources,"selection":selection,
             "OOM_fallback_or_unmeasured_capacity_claimed":False,"scientific_acceptance":False}
    return resolved,spec,guard,receipt
