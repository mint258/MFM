"""Complete standalone SDK projection/config/step closure, not timing remeasurement."""
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parent))
import archive_closed_runs_v10 as archive


def fixture():
    config={"role":"reference","abba_position":1,"warmup_updates":2,"measured_updates":20,
        "code_sha":"unit-source-only","seed":0,"data_version":{"snapshot":{"sha256":"unit-snapshot"}},
        "source_sha256":{"tools/model_v3/single_a_benchmark.py":archive.LOGGER_SHA},
        "model":{"layers":6,"hidden":512,"empty":{}},"optimizer":{"betas":[.9,.999],"weight_decay":.01},
        "deterministic_controls":{"requested":True,"actual":True},"smoke":False,"optional":None}
    config["configuration_sha256"]=archive.canonical(config)
    rows=[]
    for step in range(1,23):
        receipt={"base_records":2,"native_atoms":7,"logical_indices":[2*step-2,2*step-1],"label":"unit"}
        receipt["receipt_sha256"]=archive.canonical(receipt)
        rows.append({"optimizer_updates":step,"measured":step>2,"loss":.25+step,"compute_seconds":.5,
            "loader_seconds":.125,"gradient_norm":1.25,"valid_label_counts":{"denoising":21,"distance":0},
            "input":receipt,"consumed_base_records":2*step,"committed_stream":{"committed_base_samples":2*step},
            "resources":{"foreign_gpu_risk_observed":False}})
    summary={"role":"reference","abba_position":1,"warmup_updates":2,"measured_updates":20,
        "configuration_sha256":config["configuration_sha256"],"measured_base_records":40,"measured_native_atoms":140,
        "input_receipts_sha256":archive.canonical([row["input"]["receipt_sha256"] for row in rows[2:]]),
        "numeric_acceptance":False,"adoption_eligible":False}
    return rows,config,summary


def project(values):return archive.project_steps(*values,1,"reference")


def test_fixed_original_logger_projection_is_bound_and_scientific_field_drift_rejected():
    text=archive.PRODUCER.read_text()
    archive.logger_contract(text)
    with pytest.raises(ValueError,match="scalar projection"):
        archive.logger_contract(text.replace('"native_atoms": receipt["native_atoms"]','"wrong_atoms": receipt["native_atoms"]'))


def test_all22_steps_include_warmup_and_exact_logged_projection_only():
    expected=project(fixture())
    assert [row["step"] for row in expected]==list(range(1,23))
    assert expected[0]["row"]["consumed_base_records"]==2
    assert expected[-1]["row"]["consumed_base_records"]==44
    assert expected[0]["row"]["valid_label_count/denoising"]==21
    assert all(type(row["row"]["optimizer_updates"]) is int and type(row["row"]["loss"]) is float for row in expected)
    assert not ({"gradient_norm","measured","resources","input"}&set(expected[0]["row"]))
    assert "commit" not in expected[0]  # no invented original SDK fsync-mirror envelope


@pytest.mark.parametrize("drift",("missing_warmup","explicit_step","warmup_flag","consumed","stream_cursor","receipt",
    "count_bool","loss_nan","foreign_gpu","configuration_seal","population","adoption"))
def test_saved_source_step_clock_population_or_scope_drift_rejected(drift):
    rows,config,summary=fixture()
    if drift=="missing_warmup":rows.pop(0)
    elif drift=="explicit_step":rows[0]["optimizer_updates"]=0
    elif drift=="warmup_flag":rows[0]["measured"]=True
    elif drift=="consumed":rows[1]["consumed_base_records"]=2
    elif drift=="stream_cursor":rows[1]["committed_stream"]["committed_base_samples"]=2
    elif drift=="receipt":rows[0]["input"]["native_atoms"]=8
    elif drift=="count_bool":rows[0]["valid_label_counts"]["distance"]=False
    elif drift=="loss_nan":rows[0]["loss"]=float("nan")
    elif drift=="foreign_gpu":rows[0]["resources"]["foreign_gpu_risk_observed"]=True
    elif drift=="configuration_seal":config["seed"]=1
    elif drift=="population":summary["measured_base_records"]=44
    else:summary["adoption_eligible"]=True
    with pytest.raises(ValueError):project((rows,config,summary))


def sdk_rows():
    from wandb.proto import wandb_internal_pb2 as pb
    expected=project(fixture());config=fixture()[1]
    first=pb.Record();first.run.run_id="unit10";first.run.display_name="A_speed_reference_unitjob"
    for key,value in config.items():
        item=first.run.config.update.add();item.key=key;item.value_json=json.dumps(value,allow_nan=False)
    records=[first]
    for row in expected:
        record=pb.Record()
        for key,value in {"_step":row["step"],**row["row"]}.items():
            item=record.history.item.add()
            if "/" in key:item.nested_key.extend(key.split("/"))
            else:item.key=key
            item.value_json=json.dumps(value,allow_nan=False)
        records.append(record)
    last=pb.Record();last.exit.exit_code=0;records.append(last)
    return records,expected,config


class Stream:
    def __init__(self,records):self.items=iter(records)
    def scan_data(self):
        record=next(self.items,None)
        return None if record is None else record.SerializeToString()


def compare(records,expected,config):
    from wandb.proto import wandb_internal_pb2 as pb
    capture=archive.NativeConfigCapture(Stream(records),pb.Record,config)
    destination=io.BytesIO()
    result=archive.reader.verify_stream(capture,pb.Record,destination,expected_run_id="unit10",expected_exit=0,expected_rows=22,
        mirror_factory=lambda native:iter({"step":row["step"],"row":archive.reader.flatten(row["row"])} for row in expected))
    fields=capture.verify(config,"unitjob")
    return result,destination.getvalue(),fields


def test_all_native_scalar_nested_keys_config_role_steps_exit_and_EOF_verified(tmp_path):
    result,raw,fields=compare(*sdk_rows())
    assert result["history_rows"]==22 and result["first_explicit_step"]==1 and result["last_explicit_step"]==22
    assert result["native_closed"] and result["clean_eof"] and result["sdk_exit_codes"]==[0]
    assert result["native_packets"]==24  # synthetic protobuf records, not real SDK packet-count assertion
    assert set(fields)==set(fixture()[1])
    path=tmp_path/"history.normalized.jsonl";path.write_bytes(raw)
    assert archive.v9.scalar_exports(path,tmp_path)==22*9
    with (tmp_path/"history.scalars.csv").open() as stream:rows=list(csv.DictReader(stream))
    assert {int(row["step"]) for row in rows}==set(range(1,23))
    assert next(row for row in rows if row["step"]=="1" and row["key"]=="valid_label_count/distance")["value_json"]=="0"


@pytest.mark.parametrize("drift",("missing_metric","extra_metric","step","duplicate_step","run_id","exit","missing_exit","nan","int_as_bool","uncommitted"))
def test_native_metric_step_type_run_exit_or_uncommitted_drift_rejected(drift):
    from wandb.proto import wandb_internal_pb2 as pb
    records,expected,config=sdk_rows()
    if drift=="missing_metric":del records[1].history.item[-1]
    elif drift=="extra_metric":
        item=records[1].history.item.add();item.key="numeric_acceptance";item.value_json="true"
    elif drift=="step":records[1].history.item[0].value_json="0"
    elif drift=="duplicate_step":records[2].history.item[0].value_json="1"
    elif drift=="run_id":records[0].run.run_id="other"
    elif drift=="exit":records[-1].exit.exit_code=1
    elif drift=="missing_exit":records.pop()
    elif drift=="nan":records[1].history.item[2].value_json="NaN"
    elif drift=="int_as_bool":records[1].history.item[-1].value_json="false"
    else:
        partial=pb.Record();partial.request.partial_history.SetInParent();records.insert(2,partial)
    with pytest.raises(ValueError):compare(records,expected,config)


@pytest.mark.parametrize("drift",("role","position","source","missing","extra","name","remove","transient"))
def test_native_full_configuration_or_role_drift_rejected(drift):
    from wandb.proto import wandb_internal_pb2 as pb
    records,expected,config=sdk_rows()
    if drift=="name":records[0].run.display_name="A_speed_candidate_unitjob"
    elif drift in {"role","position","source"}:
        key={"role":"role","position":"abba_position","source":"source_sha256"}[drift]
        item=next(item for item in records[0].run.config.update if item.key==key)
        item.value_json=json.dumps({"role":"candidate","position":2,"source":{"modified":True}}[drift])
    elif drift=="missing":del records[0].run.config.update[-1]
    elif drift=="extra":
        item=records[0].run.config.update.add();item.key="unbound_scientific_control";item.value_json="true"
    elif drift=="remove":
        update=pb.Record();item=update.config.remove.add();item.key="role";records.insert(2,update)
    else:
        bad=pb.Record();item=bad.config.update.add();item.key="role";item.value_json='"candidate"'
        good=pb.Record();item=good.config.update.add();item.key="role";item.value_json='"reference"'
        records[2:2]=[bad,good]
    with pytest.raises(ValueError):compare(records,expected,config)


def test_native_capture_packet_and_config_budgets_reject_before_unbounded_accumulation():
    from wandb.proto import wandb_internal_pb2 as pb
    records,_,config=sdk_rows();capture=archive.NativeConfigCapture(Stream(records),pb.Record,config)
    capture.packets=500000
    with pytest.raises(archive.reader.BudgetError):capture.scan_data()
    capture=archive.NativeConfigCapture(Stream([]),pb.Record)
    record=pb.ConfigRecord();item=record.update.add()
    item.key="test";item.value_json=json.dumps({str(k):0 for k in range(10001)})
    with pytest.raises(ValueError,match="configuration budget"):capture.apply(record)


@pytest.mark.parametrize("drift",("numeric","inputs","foreign","matched","speed"))
def test_timing_scope_cannot_grant_numeric_acceptance_or_rewrite_actual_no_speedup(drift):
    report={"scientific_speed_comparison":True,"same_measured_inputs":True,"foreign_gpu_risk_observed":False,
        "has_matched_A_numeric_acceptance":True,"numeric_acceptance_granted_by_this_report":False,"speedup_candidate_over_reference":.8660889573595555}
    archive.validate_report_scope(report)
    key={"numeric":"numeric_acceptance_granted_by_this_report","inputs":"same_measured_inputs","foreign":"foreign_gpu_risk_observed",
         "matched":"has_matched_A_numeric_acceptance","speed":"speedup_candidate_over_reference"}[drift]
    report[key]=1.1 if drift=="speed" else not report[key]
    with pytest.raises(ValueError,match="slower/no-adoption"):archive.validate_report_scope(report)


def test_pending_paired_cases_require_actual_terminal_but_never_infer500_or_PASS():
    before=deepcopy(archive.v7.CASES)
    for job in ("4520589","4520590"):
        with pytest.raises(ValueError,match="pending actual closed"):archive.paired_case_adapter(job)
        with pytest.raises(ValueError,match="terminal state"):archive.paired_case_adapter(job,job+"|RUNNING|0:0")
        for state,exit_code in (("COMPLETED","0:0"),("FAILED","1:0")):
            value=archive.paired_case_adapter(job,job+"|"+state+"|"+exit_code)
            assert value["history_rows"] is None and value["numeric_pass"] is None and value["archive_enabled_in_this_batch"] is False
    assert archive.v7.CASES==before


def test_real_offline_SDK_roundtrip_all22_rows_config_and_clean_exit(tmp_path,monkeypatch):
    import wandb
    from wandb.proto import wandb_internal_pb2 as pb
    from wandb.sdk.internal.datastore import DataStore
    root=tmp_path/"offline_roundtrip";root.mkdir()
    for key,value in {"WANDB_MODE":"offline","WANDB_CACHE_DIR":str(root/"cache"),"WANDB_DATA_DIR":str(root/"wandb_data"),"WANDB_SILENT":"true"}.items():monkeypatch.setenv(key,value)
    rows,config,summary=fixture();expected=archive.project_steps(rows,config,summary,1,"reference")
    run=wandb.init(project="model_v3_archive_v10_unit",mode="offline",dir=str(root),
        name="A_speed_reference_unitjob",config=config,settings=wandb.Settings(quiet=True))
    run_id=run.id
    try:
        for row in expected:run.log(row["row"],step=row["step"],commit=True)
    finally:run.finish(exit_code=0)
    sdk=list((root/"wandb").glob("offline-run-*/run-*.wandb"));assert len(sdk)==1
    data=DataStore()
    try:
        data.open_for_scan(str(sdk[0]));capture=archive.NativeConfigCapture(data,pb.Record,config)
        result=archive.reader.verify_stream(capture,pb.Record,io.BytesIO(),expected_run_id=run_id,expected_exit=0,expected_rows=22,
            mirror_factory=lambda native:iter({"step":row["step"],"row":archive.reader.flatten(row["row"])} for row in expected))
        assert set(capture.verify(config,"unitjob"))==set(config)
    finally:data.close()
    assert result["history_rows"]==22 and result["native_closed"] and result["clean_eof"]
    assert result["first_explicit_step"]==1 and result["last_explicit_step"]==22
