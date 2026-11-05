"""CPU-only evidence predicates; synthetic receipts are NOT GPU/C0 admission."""
from copy import deepcopy
from dataclasses import asdict
import json
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
import torch
from phychem_mfm.model.v3_checkpoint_policy import (
    PerformanceExecution, canonical, file_reference, load_closed_observation,
    read_bound, runtime_controls, select_capacity,workload_identity)
from phychem_mfm.model.v3_performance import PerformanceOptions,build_performance_model

ROOT=Path(__file__).resolve().parents[2]


def write(path,value):
    path.write_text(json.dumps(value,allow_nan=False),encoding="utf-8")
    return file_reference(path)


def fixture_invocation(values,sources,source_root,output,*,paired=False,prefix=("-u","-B"),absolute=False):
    """Typed CPU-only command/kernel receipts; no subprocess/CUDA/C0 claim."""
    cfg,summary,sup=values["configuration"],values["summary"],values["supervisor"]
    cfg["logical_python"]="/explicit/unit/python"
    cfg["performance_execution_request"]=write(output/"execution.json",{
        "schema":"model_v3_performance_execution_v1","checkpoint_policy":"manual"})
    cfg["candidate_options_sha256"]=write(output/"options.json",asdict(PerformanceOptions()))["sha256"]
    relative="tools/model_v3/paired_a_acceptance.py" if paired else "tools/model_v3/single_a_benchmark.py"
    script=str(source_root/relative) if absolute else relative
    arguments=["--candidate-options",str(output/"options.json"),"--input","native_s",
        "--code-sha",cfg["code_sha"],"--performance-execution",cfg["performance_execution_request"]["path"],
        "--performance-execution-sha256",cfg["performance_execution_request"]["sha256"],"--output",str(output)]
    if paired:
        cfg.update(fixed_batches=20,trajectory_updates=500)
        for key in ("role","abba_position","series_id","warmup_updates","measured_updates","padding_exploration"):
            cfg.pop(key,None);summary.pop(key,None)
    else:
        cfg.update(role="candidate",abba_position=2,series_id="CPU_FIXTURE_ONLY",warmup_updates=2,
                   measured_updates=20,padding_exploration=False)
        summary.update(role="candidate",abba_position=2,series_id="CPU_FIXTURE_ONLY",padding_exploration=False)
        arguments += ["--role","candidate","--abba-position","2","--series-id","CPU_FIXTURE_ONLY"]
    cfg["performance_execution_invocation"]={"source_root":str(source_root),"cwd":str(source_root),
        "logical_python":cfg["logical_python"],"argv":[script,*arguments]}
    command=[cfg["logical_python"],*prefix,script,*arguments]
    cgroup="0::/synthetic_fixture/job_"+str(cfg["job_id"])+"\n"
    identity={"status":"ACTIVE","pid":101,"uid":os.getuid(),"boot_id":"00000000-0000-0000-0000-000000000000",
        "start_ticks":123,"pgid":101,"sid":101,"argv":deepcopy(command),
        "argv_sha256":hashlib.sha256(b"\0".join(arg.encode() for arg in command)+b"\0").hexdigest(),
        "cgroup":cgroup,"slurm_job_id":str(cfg["job_id"])}
    sup.update(command=command,child_pid=101,launch_identity=identity,supervisor_slurm_cgroup=cgroup,
        gpu_uuid=cfg["gpu_uuid"],supervisor_source_sha256=sources["tools/model_v3/run_supervised.py"])
    cfg["configuration_sha256"]=canonical({k:v for k,v in cfg.items() if k!="configuration_sha256"})
    summary["configuration_sha256"]=cfg["configuration_sha256"]

def fixture_observation(tmp_path,monkeypatch):
    """Explicit fake parent identity exercises parsing only; never queries CUDA."""
    options=PerformanceOptions();physical=asdict(options);physical["backbone_checkpointing"]=True
    model={"backbone":{"dim":16,"layers":1,"heads":4,"activation_checkpointing":True}}
    import phychem_mfm.model.v3_checkpoint_policy as policy
    source_root=tmp_path/"synthetic_source_tree";source_root.mkdir()
    (source_root/"source.py").write_text("# synthetic model source fixture\n")
    (source_root/"acceptance.py").write_text("# synthetic numeric gate source fixture\n")
    monkeypatch.setattr(policy,"ROOT",source_root)
    (source_root/"tools/model_v3").mkdir(parents=True)
    names=("source.py","acceptance.py","tools/model_v3/paired_a_acceptance.py",
           "tools/model_v3/single_a_benchmark.py","tools/model_v3/run_supervised.py")
    for name in names[2:]:(source_root/name).write_text("# synthetic original tool source fixture: "+name+"\n")
    sources={name:file_reference(source_root/name)["sha256"] for name in names}
    job="1234567"
    binding={"reference_configuration":{"sha256":"d"*64},"a4_configuration":{"sha256":"e"*64},
             "loss_policy":{},"loss_weights":{},"supervision":{}}
    work=workload_identity(model,seed=0,input_kind="native_s",snapshot="f"*64,binding=binding)
    spec=PerformanceExecution(workload_sha256=work)
    configuration={**binding,"seed":0,"original_shard_snapshot_prejob_sha256":"f"*64,"job_id":job,"input":"native_s","smoke":False,"model":model,"code_sha":"c"*40,
        "gpu_uuid":"GPU-unit-only","gpu_name":"UNIT NOT CUDA","gpu_total_bytes":10000,
        "torch_version":"unit","cuda_version":"unit","cudnn_version":0,"gpu":{"driver_version":"unit","total_bytes":10000},
        "deterministic_controls":{"actual":runtime_controls()},"source_sha256":deepcopy(sources),
        "performance_execution":{"requested":spec.semantic(),"resolved_options":physical,"implementation_sha256":sources}}
    configuration["configuration_sha256"]=canonical(configuration)
    summary={"status":"STANDALONE_TIMING_COMPLETED","configuration_sha256":configuration["configuration_sha256"],
             "gpu_uuid":configuration["gpu_uuid"],"code_sha":configuration["code_sha"],"smoke":False,
             "warmup_updates":2,"measured_updates":20,"foreign_gpu_risk_observed":False}
    status={"status":summary["status"],"failure":None,"cleanup_errors":[],"stream_cleanup":{"input_descriptors_closed":True}}
    sup={"job_id":job,"status":"COMPLETED","exit_code":0,"first_failure":None,
         "remaining_recorded_processes_before_retirement":[],"private_storage_cleanup_errors":[],
         "launch_identity":{"uid":os.getuid()},
         "command":["/explicit/unit/python","--output",str(tmp_path),"--code-sha",configuration["code_sha"]]}
    parent={"argv":["sacct","-j",job,"--format=JobIDRaw,State,ExitCode","--parsable2","--noheader"],
            "returncode":0,"stdout":job+"|COMPLETED|0:0\n","stderr":""}
    resources={"foreign_gpu_risk_observed":False,"peak_allocated_bytes":1000,"peak_reserved_bytes":1200,
        "gpu_observation":{"uuid":configuration["gpu_uuid"],"total_bytes":10000,
                           "compute_processes":[{"own":True,"used_memory_bytes":1500}]}}
    rows=[{"optimizer_updates":i,"resources":deepcopy(resources),
           "performance_execution":{"graph_atom_counts":[2,3,2]}} for i in range(1,23)]
    values={"configuration":configuration,"summary":summary,"run_status":status,"supervisor":sup,"parent_sacct":parent}
    fixture_invocation(values,sources,source_root,tmp_path)
    item={key:write(tmp_path/(key+".json"),value) for key,value in values.items()}
    journal=tmp_path/"steps.jsonl";journal.write_text("".join(json.dumps(row)+"\n" for row in rows))
    item["steps"]=file_reference(journal)
    return item,spec,model,options,sources,values,rows


def rebind(item,key,value):
    item[key]=write(Path(item[key]["path"]),value)


def test_explicit_closed_run_metadata_is_parsed_and_size_envelope_is_observed(tmp_path,monkeypatch):
    item,spec,model,options,sources,_,_=fixture_observation(tmp_path,monkeypatch)
    row=load_closed_observation(item,spec,model,options,sources)
    assert row["observed_dense_shapes"]==((3,3),)
    assert row["observed_size_limits"]=={"graphs":3,"atoms":7,"max_nodes":3,"padded_cost":27}
    assert row["flags"]=={"backbone_checkpointing":True,"distance_checkpointing":True,"head_checkpointing":True}
    assert row["peak_bytes"]==1500 and row["sampled_capacity_not_universal_bound"]


@pytest.mark.parametrize("fault",["source","workload","residency","budget","parent","supervisor","foreign","missing_update","null_memory","old_run","wrong_actual_seed","missing_actual_sources","declared_source_drift","changed_actual_gate"])
def test_unknown_or_mismatched_actual_capacity_is_rejected(tmp_path,monkeypatch,fault):
    item,spec,model,options,sources,values,rows=fixture_observation(tmp_path,monkeypatch)
    if fault=="source":sources={"changed":"e"*64}
    elif fault=="workload":spec=PerformanceExecution(workload_sha256="f"*64)
    elif fault=="residency":spec=PerformanceExecution(resident_models=2,workload_sha256=spec.workload_sha256)
    elif fault=="budget":spec=PerformanceExecution(batch_padded_cost=8000001,workload_sha256=spec.workload_sha256)
    elif fault=="parent":values["parent_sacct"]["stdout"]="1234567|FAILED|1:0\n"
    elif fault=="supervisor":values["supervisor"]["remaining_recorded_processes_before_retirement"]=[123]
    elif fault=="foreign":rows[1]["resources"]["foreign_gpu_risk_observed"]=True
    elif fault=="missing_update":rows.pop(3)
    elif fault=="null_memory":rows[1]["resources"]["gpu_observation"]["compute_processes"][0]["used_memory_bytes"]=None
    elif fault=="old_run":
        del values["configuration"]["performance_execution"]
        values["configuration"]["configuration_sha256"]=canonical({k:v for k,v in values["configuration"].items() if k!="configuration_sha256"})
        values["summary"]["configuration_sha256"]=values["configuration"]["configuration_sha256"]
    if fault=="missing_actual_sources":del values["configuration"]["source_sha256"]
    if fault=="declared_source_drift":values["configuration"]["source_sha256"]["source.py"]="0"*64
    if fault=="changed_actual_gate":
        import phychem_mfm.model.v3_checkpoint_policy as policy
        (policy.ROOT/"acceptance.py").write_text("# changed numeric gate must invalidate old capacity qualification\n")
    if fault in ("missing_actual_sources","declared_source_drift","changed_actual_gate"):
        values["configuration"]["configuration_sha256"]=canonical({k:v for k,v in values["configuration"].items() if k!="configuration_sha256"})
        values["summary"]["configuration_sha256"]=values["configuration"]["configuration_sha256"]
    if fault=="wrong_actual_seed":
        values["configuration"]["seed"]=1
        values["configuration"]["configuration_sha256"]=canonical({k:v for k,v in values["configuration"].items() if k!="configuration_sha256"})
        values["summary"]["configuration_sha256"]=values["configuration"]["configuration_sha256"]
    for key,value in values.items():rebind(item,key,value)
    Path(item["steps"]["path"]).write_text("".join(json.dumps(row)+"\n" for row in rows))
    item["steps"]=file_reference(item["steps"]["path"])
    with pytest.raises((ValueError,TypeError)):
        load_closed_observation(item,spec,model,options,sources)


def test_capacity_selection_is_physical_environment_and_free_memory_specific(tmp_path,monkeypatch):
    item,spec,model,options,sources,_,_=fixture_observation(tmp_path,monkeypatch)
    row=load_closed_observation(item,spec,model,options,sources)
    environment={"uuid":row["gpu_uuid"],"name":row["gpu_name"],"total_bytes":10000,"torch_total_bytes":10000,"free_bytes":9000,
                 **{k:row[k] for k in ("torch_version","cuda_version","driver_version","cudnn_version","runtime_controls")}}
    assert select_capacity([row],environment) is row
    for key,value in (("uuid","GPU-other"),("free_bytes",2000),("driver_version","other"),("torch_version","other"),("torch_total_bytes",9000)):
        assert select_capacity([row],{**environment,key:value}) is None
    changed=deepcopy(environment);changed["runtime_controls"]["deterministic_algorithms"]=not changed["runtime_controls"]["deterministic_algorithms"]
    assert select_capacity([row],changed) is None


def test_auto_rejects_unknown_profile_before_model_construction_and_rng(tmp_path):
    rng=torch.get_rng_state().clone()
    configuration={"backbone":{"dim":16,"layers":1,"heads":4}}
    with pytest.raises(ValueError,match="unknown capacity"):
        build_performance_model(configuration,execution={"checkpoint_policy":"auto_closed_profile_v1"})
    ref=write(tmp_path/"unknown.json",{"schema":"not_a_closed_profile","observations":[]})
    with pytest.raises(ValueError,match="Unknown, empty"):
        build_performance_model(configuration,execution={"checkpoint_policy":"auto_closed_profile_v1",
                                "capacity_profile":ref,"workload_sha256":"a"*64})
    assert torch.equal(rng,torch.get_rng_state())
    Path(ref["path"]).write_text("{}")
    with pytest.raises(ValueError,match="raw SHA"):
        read_bound(ref)


def test_runner_opt_in_is_source_bound_and_old_rebatching_stays_rejected(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/"tools/model_v3"))
    from a_execution_runtime import load_performance_execution,validate_arguments
    ref=write(tmp_path/"execution.json",{"padding":{"max_graphs_per_chunk":2}})
    args=SimpleNamespace(performance_execution=Path(ref["path"]),performance_execution_sha256=ref["sha256"],
        seed=0,input="native_s",shard_snapshot_sha256="d"*64,max_padded_cost=8000000,
        resume=None,workers=0,atom_bucket_width=None,exact_atom_sort=False,code_sha="c"*40,prereg_sha="d"*40)
    bindings={"reference_configuration":{"sha256":"e"*64},"a4_configuration":{"sha256":"f"*64},
              "loss_policy":{},"loss_weights":{},"supervision":{},"source_sha256":{}}
    result=load_performance_execution(args,{},bindings,resident_models=2)
    assert result["resident_models"]==2 and result["batch_padded_cost"]==8000000
    assert bindings["performance_execution_invocation"]["argv"]==__import__("sys").argv
    assert "current/phychem_mfm/model/routes.py" in bindings["source_sha256"]
    assert "current/phychem_mfm/training/v3_performance_acceptance.py" in bindings["source_sha256"]
    assert result["padding"]["max_graphs_per_chunk"]==2 and len(result["workload_sha256"])==64
    args.performance_execution_sha256="0"*64
    with pytest.raises(ValueError,match="source changed"):load_performance_execution(args,{},bindings,resident_models=2)
    args.performance_execution_sha256=ref["sha256"];args.atom_bucket_width=8
    monkeypatch.setenv("SLURM_JOB_ID","1234567");monkeypatch.setenv("SLURM_CPUS_PER_TASK","16")
    with pytest.raises(ValueError,match="regroup optimizer batches"):validate_arguments(args,paired=True)


def test_two_resident_paired_journal_uses_all_500_actual_step_resources(tmp_path,monkeypatch):
    item,spec,model,options,sources,values,rows=fixture_observation(tmp_path,monkeypatch)
    spec=PerformanceExecution(resident_models=2,workload_sha256=spec.workload_sha256)
    values["configuration"]["performance_execution"]["requested"]=spec.semantic()
    values["configuration"]["configuration_sha256"]=canonical({k:v for k,v in values["configuration"].items() if k!="configuration_sha256"})
    values["summary"].update(status="PAIRED_GATES_PASS",full_A_numeric_acceptance=True,
        fixed_batch_pass=True,trajectory_pass=True,configuration_sha256=values["configuration"]["configuration_sha256"])
    values["run_status"]["status"]="PAIRED_GATES_PASS"
    import phychem_mfm.model.v3_checkpoint_policy as policy
    fixture_invocation(values,sources,policy.ROOT,tmp_path,paired=True)
    for key,value in values.items():rebind(item,key,value)
    original=rows[0]
    paired=[{"phase":"fixed_batch","batch":i} for i in range(20)]+[
        {"phase":"trajectory","optimizer_updates":i,**original["resources"],
         "performance_execution":original["performance_execution"]} for i in range(1,501)]
    journal=tmp_path/"resources.jsonl";journal.write_text("".join(json.dumps(row)+"\n" for row in paired))
    item["steps"]=file_reference(journal)
    result=load_closed_observation(item,spec,model,options,sources)
    assert result["peak_bytes"]==1500 and result["observed_size_limits"]["graphs"]==3


@pytest.mark.parametrize("fault",[None,"layout","mixed"])
def test_abba_requires_explicit_matching_integrated_candidate_layout(monkeypatch,fault):
    from test_model_v3_a_execution import module,members_fixture
    report=module(monkeypatch,"a_speed_report");runtime=module(monkeypatch,"a_execution_runtime")
    members=members_fixture(runtime)
    receipt={"requested":{"padding":{"mode":"logical_batch_chunks_v1"},"workload_sha256":"a"*64},
             "resolved_options":asdict(PerformanceOptions()),"implementation_sha256":{"unit_source":"b"*64}}
    for i,item in enumerate(members):
        item["configuration"]["performance_execution_request"]={"path":"/unit/source","sha256":"c"*64}
        item["configuration"]["performance_execution"]=(deepcopy(receipt) if i in (1,2) else {"applied":False})
    if fault=="layout":members[2]["configuration"]["performance_execution"]["requested"]["padding"]["mode"]="different"
    if fault=="mixed":del members[0]["configuration"]["performance_execution_request"]
    for item in members:
        cfg=item["configuration"]
        cfg["configuration_sha256"]=runtime.canonical_sha({k:v for k,v in cfg.items() if k!="configuration_sha256"})
        item["summary"]["configuration_sha256"]=cfg["configuration_sha256"]
    if fault is not None:
        with pytest.raises(ValueError,match="Mixed declared|execution layout"):report.summarize_abba(members)
    else:
        result=report.summarize_abba(members)
        assert result["same_measured_inputs"] and not result["has_matched_A_numeric_acceptance"]


def test_auto_compiled_logical_chunks_reject_before_unproved_workspace_or_rng():
    from phychem_mfm.model.v3_checkpoint_policy import prepare_execution
    rng=torch.get_rng_state().clone()
    with pytest.raises(ValueError,match="compiled chunk-shape capacity evidence"):
        prepare_execution({"backbone":{"dim":16}},PerformanceOptions(compile_backbone=True),{
            "checkpoint_policy":"auto_closed_profile_v1","padding":{"max_graphs_per_chunk":2},
            "capacity_profile":{"path":"/synthetic/not/read","bytes":1,"sha256":"a"*64},
            "workload_sha256":"b"*64})
    assert torch.equal(rng,torch.get_rng_state())


def test_saved_dynamic_extra_source_is_checked_without_requiring_identical_import_sets(tmp_path,monkeypatch):
    import phychem_mfm.model.v3_checkpoint_policy as policy
    item,spec,model,options,sources,values,_=fixture_observation(tmp_path,monkeypatch)
    extra=policy.ROOT/"observed_optional_extra.py";extra.write_text("# real source bytes for this CPU fixture\n")
    values["configuration"]["source_sha256"]["observed_optional_extra.py"]=file_reference(extra)["sha256"]
    cfg=values["configuration"];cfg["configuration_sha256"]=canonical({k:v for k,v in cfg.items() if k!="configuration_sha256"})
    values["summary"]["configuration_sha256"]=cfg["configuration_sha256"]
    for key,value in values.items():rebind(item,key,value)
    assert "observed_optional_extra.py" not in sources
    assert load_closed_observation(item,spec,model,options,sources)["peak_bytes"]==1500
    extra.write_text("# the observed optional dependency changed\n")
    with pytest.raises(ValueError,match="dependency differs"):
        load_closed_observation(item,spec,model,options,sources)


@pytest.mark.parametrize("absolute,prefix",[(False,("-u","-B")),(True,())])
def test_exact_original_tool_qualification_accepts_actual_python_prefix_and_recorded_cwd(tmp_path,monkeypatch,absolute,prefix):
    import phychem_mfm.model.v3_checkpoint_policy as policy
    item,spec,model,options,sources,values,_=fixture_observation(tmp_path,monkeypatch)
    fixture_invocation(values,sources,policy.ROOT,tmp_path,prefix=prefix,absolute=absolute)
    for key,value in values.items():rebind(item,key,value)
    command=values["supervisor"]["command"]
    frame=values["configuration"]["performance_execution_invocation"]
    assert frame["argv"]==command[1+len(prefix):]
    assert load_closed_observation(item,spec,model,options,sources)["peak_bytes"]==1500


@pytest.mark.parametrize("fault",["wrong_entry","missing_entry","wrong_role","wrong_series","guard_source",
                                  "argv_mismatch","sysargv_mismatch","optin_sha","python_code_prefix","paired_wrong_tool"])
def test_capacity_requires_actual_original_A_tool_optin_role_and_guard_identity(tmp_path,monkeypatch,fault):
    from phychem_mfm.model.v3_checkpoint_policy import qualify_a_invocation
    import phychem_mfm.model.v3_checkpoint_policy as policy
    _,_,_,_,sources,values,_=fixture_observation(tmp_path,monkeypatch)
    paired=fault=="paired_wrong_tool"
    if paired:fixture_invocation(values,sources,policy.ROOT,tmp_path,paired=True)
    cfg,summary,sup=values["configuration"],values["summary"],values["supervisor"]
    command=sup["command"]
    if fault=="wrong_entry":
        wrong=policy.ROOT/"unqualified_other_tool.py"
        wrong.write_bytes((policy.ROOT/"tools/model_v3/single_a_benchmark.py").read_bytes())
        command[3]=str(wrong)
    elif fault=="missing_entry":del command[3]
    elif fault=="wrong_role":command[command.index("--role")+1]="reference"
    elif fault=="wrong_series":command[command.index("--series-id")+1]="different"
    elif fault=="guard_source":sup["supervisor_source_sha256"]="0"*64
    elif fault=="optin_sha":command[command.index("--performance-execution-sha256")+1]="0"*64
    elif fault=="python_code_prefix":command[1]="-c"
    elif fault=="paired_wrong_tool":command[3]="tools/model_v3/single_a_benchmark.py"
    if fault not in ("argv_mismatch","sysargv_mismatch"):
        cfg["performance_execution_invocation"]["argv"]=deepcopy(command[3:])
        sup["launch_identity"]["argv"]=deepcopy(command)
        sup["launch_identity"]["argv_sha256"]=hashlib.sha256(b"\0".join(arg.encode() for arg in command)+b"\0").hexdigest()
    if fault=="argv_mismatch":sup["launch_identity"]["argv"][-1]="different"
    if fault=="sysargv_mismatch":cfg["performance_execution_invocation"]["argv"]=["-u",*cfg["performance_execution_invocation"]["argv"]]
    with pytest.raises(ValueError):qualify_a_invocation(cfg,summary,sup,tmp_path,sources,paired=paired)
