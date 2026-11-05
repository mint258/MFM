"""Reject fabricated successful exits, trajectory, numeric and capacity claims."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0,str(Path(__file__).parent))
import archive_closed_runs_v11 as archive


def fixture(job="4520589"):
    config={"job_id":job,"code_sha":"8ece64c685fe287d6863fbbe2f6f52006632a5cc",
        "prereg_sha":"61658a4c1f472de035601dbedc17809315774784","input":"native_s","smoke":False,
        "fixed_batches":20,"trajectory_updates":500,"checkpoint_export":{"requested":True},
        "candidate":{"precision":"fp32","tf32":job=="4520589","distance_checkpointing":job!="4520590"}}
    config["configuration_sha256"]=archive.v10.canonical(config)
    status={"job_id":job,"checkpoint_export":None,"status":"FIXED_BATCH_GATE_FAILED","failure":None,"cleanup_errors":[],
        "stream_cleanup":{"input_descriptors_closed":True,"errors":[]}}
    supervisor={"job_id":job,"status":"FAILED","exit_code":2,"first_failure":{"phase":"child_exit","exit_code":2},
        "remaining_recorded_processes_before_retirement":[],"foreign_gpu_processes_signalled":False}
    consumption=[]
    for batch in range(20 if job=="4520589" else 2):
        receipt={"base_records":3,"native_atoms":17,"batch_identity":batch}
        receipt["receipt_sha256"]=archive.v10.canonical(receipt)
        consumption.append({"phase":"fixed_batch","batch":batch,"input":receipt,"committed_stream":{"committed_base_samples":3*(batch+1)}})
    resources=[{"phase":"fixed_batch","batch":batch} for batch in range(20 if job=="4520589" else 1)]
    gate={"gate":"A_fixed_batch_equivalence","batches":20,"pass":False,
        "results":[{"batch":i,"input_receipt":row["input"],"forward":{"pass":True},"gradient":{"pass":False},"pass":False}
                   for i,row in enumerate(consumption)]}
    if job=="4520590":
        gate=None;status.update(status="FAILED",failure={"type":"MemoryError","message":"A diagnostic exceeded85% of physical GPU capacity"},
            cleanup_errors=[{"component":key,"type":"ConnectionResetError"} for key in ("stream","reference","candidate")],
            stream_cleanup={"input_descriptors_closed":False,"errors":[{"component":"iterator","type":"RuntimeError"}]})
        supervisor.update(exit_code=-6,first_failure={"type":"MemoryError","message":"Owned GPU process memory exceeded 85% of physical capacity"},
            retirement={"remaining":[]})
    return config,status,supervisor,gate,consumption,resources


def test_frozen_paired_logger_is_after_fixed_rejection_and_inside_trajectory_loop():
    text=archive.PRODUCER.read_text();archive.producer_contract(text)
    with pytest.raises(ValueError,match="rejection must precede"):
        archive.producer_contract(text.replace("return 2","return 0",1))


def test_589_fixed_gate_rejection_has_outer1_child2_and_no_trajectory_export():
    result=archive.validate_failure("4520589",*fixture())
    assert result["outer_slurm"]=={"state":"FAILED","exit_code":"1:0"} and result["child_exit_code"]==2
    assert result["failure"] is None and result["saved_fixed_batch_results"]==20
    assert result["primary_cause"]=="SAVED_FIXED_BATCH_NUMERIC_GATE_REJECTED"
    assert result["actual_trajectory_updates"]==0 and result["requested_trajectory_updates"]==500
    assert not result["actual_numeric_acceptance"] and not result["checkpoint_exported"]


def test_590_retains_soft_cap_abort_and_all_cleanup_failures_without_numeric_inference():
    result=archive.validate_failure("4520590",*fixture("4520590"))
    assert result["child_exit_code"]==-6 and result["outer_slurm"]["exit_code"]=="1:0"
    assert result["saved_fixed_batch_results"] is None and result["saved_failed_batch_count"] is None
    assert result["stream_cleanup"]["input_descriptors_closed"] is False and len(result["cleanup_errors"])==3
    assert result["actual_numeric_acceptance"] is False and result["actual_trajectory_updates"]==0


@pytest.mark.parametrize("drift",("outer_child_exit_confused","outer_success","child_exit","gate_pass","gate_count","gate_input",
    "trajectory_phase","receipt","cursor","export","configuration","cleanup_erased"))
def test_589_failed_gate_source_or_exit_drift_rejected(drift):
    values=fixture();kwargs={}
    if drift=="outer_child_exit_confused":kwargs["slurm_exit"]="2:0"
    elif drift=="outer_success":kwargs["slurm_state"]="COMPLETED";kwargs["slurm_exit"]="0:0"
    elif drift=="child_exit":values[2]["exit_code"]=1
    elif drift=="gate_pass":values[3]["pass"]=True
    elif drift=="gate_count":values[3]["results"].pop()
    elif drift=="gate_input":values[3]["results"][0]["input_receipt"]=dict(values[4][0]["input"],base_records=4)
    elif drift=="trajectory_phase":values[4][0]["phase"]="trajectory"
    elif drift=="receipt":values[4][0]["input"]["native_atoms"]=18
    elif drift=="cursor":values[4][1]["committed_stream"]["committed_base_samples"]=3
    elif drift=="export":values[1]["checkpoint_export"]={"saved":True}
    elif drift=="configuration":values[0]["candidate"]["tf32"]=False
    else:values[1]["stream_cleanup"]["input_descriptors_closed"]=False
    with pytest.raises(ValueError):archive.validate_failure("4520589",*values,**kwargs)


@pytest.mark.parametrize("drift",("CUDA_OOM_inferred","exception_erased","cap_cause_erased","abort_erased","cleanup_erased","input_closed_claim",
    "invented_gate","all20_inferred","owned_process_left"))
def test_590_capacity_abort_cannot_become_OOM_or_closed_numeric_run(drift):
    values=list(fixture("4520590"))
    if drift=="CUDA_OOM_inferred":values[1]["failure"]["type"]="OutOfMemoryError"
    elif drift=="exception_erased":values[1]["failure"]["message"]="unknown"
    elif drift=="cap_cause_erased":values[2]["first_failure"]["message"]="unknown"
    elif drift=="abort_erased":values[2]["exit_code"]=1
    elif drift=="cleanup_erased":values[1]["cleanup_errors"]=[]
    elif drift=="input_closed_claim":values[1]["stream_cleanup"]["input_descriptors_closed"]=True
    elif drift=="invented_gate":values[3]={"pass":True}
    elif drift=="all20_inferred":values[4]=fixture()[4];values[5]=fixture()[5]
    else:values[2]["retirement"]["remaining"]=[123]
    with pytest.raises(ValueError):archive.validate_failure("4520590",*values)


class Stream:
    def __init__(self,records,broken=False):self.rows=iter(records);self.broken=broken
    def scan_data(self):
        record=next(self.rows,None)
        if record is None and self.broken:raise EOFError("unit incomplete native block")
        return None if record is None else record.SerializeToString()
    def close(self):pass


def native_fixture(exit_code=1):
    from wandb.proto import wandb_internal_pb2 as pb
    config=fixture()[0];first=pb.Record();first.run.run_id="unit11";first.run.display_name="A_reference_4520589"
    for key,value in {**config,"paired_role":"reference"}.items():
        item=first.run.config.update.add();item.key=key;item.value_json=json.dumps(value)
    records=[first]
    if exit_code is not None:
        last=pb.Record();last.exit.exit_code=exit_code;records.append(last)
    return records,config


def compare(records,config,*,broken=False,factory=None):
    from wandb.proto import wandb_internal_pb2 as pb
    return archive.verify_scans(factory or (lambda:Stream(records,broken)),pb.Record,io.BytesIO(),run_id="unit11",config=config,job="4520589")


def test_failed_native_exit1_is_verified_without_claiming_success():
    result=compare(*native_fixture())
    assert result["status"]=="FAILED_SOURCE_SDK_CLOSED_WITH_EXIT1"
    assert result["sdk_exit_codes"]==[1] and result["history_rows"]==0 and result["clean_eof"] is True
    assert result["native_closed"] is True and result["successful_run_or_exit_claimed"] is False
    assert result["paired_role"]=="reference" and result["native_full_configuration_verified"] is True
    assert result["comparison"]=="code-derivedsavedoutputs_pretrajectory_empty"
    assert result["actual_A_numeric_acceptance"] is False


def test_header_only_or_absent_exit_preserves_no_native_identity_or_role():
    result=compare([],fixture()[0])
    assert result["history_rows"]==0 and result["native_packets"]==0 and result["clean_eof"] is True
    assert result["sdk_run_ids"]==result["sdk_exit_codes"]==[] and result["paired_role"] is None
    assert result["native_closed"] is False and result["native_full_configuration_verified"] is False
    assert result["status"]=="FAILED_SOURCE_SDK_INCOMPLETE_RAW_PRESERVED"


@pytest.mark.parametrize("broken",(False,True))
def test_missing_native_exit_or_broken_EOF_never_invents_clean_finish(broken):
    result=compare(*native_fixture(None),broken=broken)
    assert result["native_closed"] is False and result["sdk_exit_codes"]==[]
    assert result["clean_eof"] is (not broken)
    assert bool(result["decode_error"]) is broken
    assert result["status"]=="FAILED_SOURCE_SDK_INCOMPLETE_RAW_PRESERVED"


@pytest.mark.parametrize("drift",("success_exit","wrong_run","duplicate_run","duplicate_exit","source","role","name","missing_config","unexpected_science"))
def test_failed_SDK_cannot_accept_wrong_identity_config_or_unsourced_history(drift):
    from wandb.proto import wandb_internal_pb2 as pb
    records,config=native_fixture()
    if drift=="success_exit":records[-1].exit.exit_code=0
    elif drift=="wrong_run":records[0].run.run_id="other"
    elif drift=="duplicate_run":records.insert(1,deepcopy(records[0]))
    elif drift=="duplicate_exit":records.append(deepcopy(records[-1]))
    elif drift in {"source","role"}:
        key="code_sha" if drift=="source" else "paired_role"
        next(item for item in records[0].run.config.update if item.key==key).value_json='"wrong"'
    elif drift=="name":records[0].run.display_name="A_candidate_4520589"
    elif drift=="missing_config":del records[0].run.config.update[0]
    else:
        record=pb.Record()
        for key,value in {"_step":1,"loss":.2}.items():
            item=record.history.item.add();item.key=key;item.value_json=json.dumps(value)
        records.insert(1,record)
    with pytest.raises(ValueError):compare(records,config)


def test_native_preflight_budget_and_two_pass_source_change_are_rejected():
    from wandb.proto import wandb_internal_pb2 as pb
    records,config=native_fixture()
    with pytest.raises(ValueError,match="packet budget"):
        archive.scan_native(Stream(records),pb.Record,run_id="unit11",config=config,job="4520589",max_packets=0)
    with pytest.raises(archive.reader.BudgetError,match="wall budget"):
        archive.scan_native(Stream(records),pb.Record,run_id="unit11",config=config,job="4520589",deadline=time.monotonic()-1)
    series=iter([Stream(records),Stream([])])
    with pytest.raises(ValueError):compare(records,config,factory=lambda:next(series))


def test_source_journal_is_bounded_complete_and_new_cases_do_not_mutate_old_globals(tmp_path):
    before=deepcopy(archive.v7.CASES)
    path=tmp_path/"source.jsonl";path.write_bytes(b'{"phase":"fixed_batch","batch":0}\n')
    rows,ref=archive.bounded_rows(path,1);assert len(rows)==1 and ref["bytes"]==len(path.read_bytes())
    with pytest.raises(ValueError):archive.bounded_rows(path,0)
    path.write_bytes(b'{"phase":"fixed_batch","batch":0}')
    with pytest.raises(ValueError):archive.bounded_rows(path,1)
    assert archive.v7.CASES==before and not (set(archive.CASES)&set(before))


def test_real_offline_failed_SDK_roundtrip_keeps_exit1_and_no_science(tmp_path,monkeypatch):
    import wandb
    root=tmp_path/"failed_offline";root.mkdir()
    for key,value in {"WANDB_MODE":"offline","WANDB_CACHE_DIR":str(root/"cache"),"WANDB_DATA_DIR":str(root/"wandb_data"),"WANDB_SILENT":"true"}.items():monkeypatch.setenv(key,value)
    config=fixture()[0]
    run=wandb.init(project="model_v3_archive_v11_unit",mode="offline",dir=str(root),name="A_reference_4520589",
        config={**config,"paired_role":"reference"},settings=wandb.Settings(quiet=True))
    run_id=run.id;run.finish(exit_code=1)
    files=list((root/"wandb").glob("offline-run-*/run-*.wandb"));assert len(files)==1
    result=archive.verify_sdk(files[0],io.BytesIO(),run_id=run_id,config=config,job="4520589")
    assert result["history_rows"]==0 and result["sdk_exit_codes"]==[1] and result["native_closed"] is True
    assert result["status"]=="FAILED_SOURCE_SDK_CLOSED_WITH_EXIT1" and result["actual_A_numeric_acceptance"] is False
