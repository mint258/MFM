"""Typed code-derived559 source rows, scope rejection and exact SDK checks."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parent))
import archive_closed_runs_v9 as archive


def fixture():
    source={"schema":"model_v3_C2_controlled_source_solver_return_v1","status":"DIAGNOSTIC_ONLY_NOT_BASELINE_ACCEPTANCE",
        "native_PRETRAIN_VAL_records_read":0,"old_job_4520482_stop_inferred":False,"stop_code":7,"iterations":500,
        "configured_iteration_limit":500,"solver_wall_seconds":34.550494480878115}
    candidate={"status":"DIAGNOSTIC_ONLY_NOT_BASELINE_ACCEPTANCE","native_PRETRAIN_VAL_records_decoded":0,
        "KKT_acceptance_threshold_applied":False,"solver":{"iterations":74,"stop_code":2},"solver_wall_seconds":4.711929500102997}
    result={"status":archive.STATUS,"native_PRETRAIN_VAL_records_decoded":0,"source":{"native_PRETRAIN_VAL_records_decoded":0,"baseline":deepcopy(source)},
        "candidate":deepcopy(candidate),"model_selection_gate":False,"original_v1_job_4520482_remains_FAILED":True,
        "original_v1_stop_or_iteration_count_inferred":False,"array_artifact":{"saved":True}}
    done={"status":archive.STATUS,"native_PRETRAIN_VAL_records_decoded":0,"baseline_accepted":False}
    binding={"native_PRETRAIN_VAL_records_decoded":0}
    inputs={"validation_geometry_access_authorized":False}
    return source,candidate,result,done,binding,inputs


def test_actual_fixed_logger_contract_and_changed_scientific_field_rejected():
    text=(archive.SOURCE/"diagnose_coordinate_lookup.py").read_text()
    archive.logger_contract(text)
    with pytest.raises(ValueError,match="scientific logger fields"):
        archive.logger_contract(text.replace('"source/iterations"','"source/changed_iterations"'))


def test_code_derived_rows_preserve_explicit_steps_and_source_native_types():
    rows=archive.derive_expected(*fixture())
    assert [row["step"] for row in rows]==[0,1]
    assert type(rows[0]["row"]["source/stop_code"]) is int
    assert type(rows[0]["row"]["source/iterations"]) is int
    assert type(rows[0]["row"]["source/solver_wall_seconds"]) is float
    assert rows[1]["row"]["diagnostic/completed_requested_work"] is True
    assert type(rows[1]["row"]["diagnostic/native_PRETRAIN_VAL_records_decoded"]) is int
    assert "commit" not in rows[0]  # not an invented original fsync-mirror envelope


@pytest.mark.parametrize("field",("source_iterations","candidate_iterations","source_wall","candidate_wall"))
def test_independent_saved_outputs_reject_scientific_field_drift(field):
    values=fixture()
    if field=="source_iterations":values[0]["iterations"]=499
    elif field=="candidate_iterations":values[1]["solver"]["iterations"]=75
    elif field=="source_wall":values[0]["solver_wall_seconds"]=34.5
    else:values[1]["solver_wall_seconds"]=4.8
    with pytest.raises(ValueError,match="scientific field drift"):
        archive.derive_expected(*values)


@pytest.mark.parametrize("field",("source","candidate","result","binding","authorization","boolean_zero"))
def test_validation_access_or_nonzero_or_untyped_VAL_count_is_rejected(field):
    values=fixture()
    if field=="source":values[0]["native_PRETRAIN_VAL_records_read"]=1
    elif field=="candidate":values[1]["native_PRETRAIN_VAL_records_decoded"]=1
    elif field=="result":values[2]["native_PRETRAIN_VAL_records_decoded"]=1
    elif field=="binding":values[4]["native_PRETRAIN_VAL_records_decoded"]=1
    elif field=="authorization":values[5]["validation_geometry_access_authorized"]=True
    else:values[3]["native_PRETRAIN_VAL_records_decoded"]=False
    with pytest.raises(ValueError,match="PRETRAIN_VAL"):
        archive.derive_expected(*values)


@pytest.mark.parametrize("claim",("baseline","selection","KKT","old_stop_inferred","old_failure_erased"))
def test_diagnostic_cannot_become_baseline_or_infer_original482_stop(claim):
    values=fixture()
    if claim=="baseline":values[3]["baseline_accepted"]=True
    elif claim=="selection":values[2]["model_selection_gate"]=True
    elif claim=="KKT":values[1]["KKT_acceptance_threshold_applied"]=True
    elif claim=="old_stop_inferred":values[2]["original_v1_stop_or_iteration_count_inferred"]=True
    else:values[2]["original_v1_job_4520482_remains_FAILED"]=False
    with pytest.raises(ValueError):archive.derive_expected(*values)


def sdk_rows():
    from wandb.proto import wandb_internal_pb2 as pb
    expected=archive.derive_expected(*fixture())
    first=pb.Record();first.run.run_id="unit559"
    records=[first]
    for row in expected:
        record=pb.Record()
        for key,value in {"_step":row["step"],**row["row"]}.items():
            item=record.history.item.add();item.key=key;item.value_json=json.dumps(value)
        records.append(record)
    final=pb.Record();final.exit.exit_code=0;records.append(final)
    return records,expected


def compare(records,expected):
    from wandb.proto import wandb_internal_pb2 as pb
    class Stream:
        def __init__(self):self.items=iter(records)
        def scan_data(self):
            record=next(self.items,None)
            return None if record is None else record.SerializeToString()
    return archive.reader.verify_stream(Stream(),pb.Record,io.BytesIO(),expected_run_id="unit559",expected_exit=0,expected_rows=2,
        mirror_factory=lambda config:iter({"step":row["step"],"row":archive.reader.flatten(row["row"])} for row in expected))


def test_native_full_fields_steps_identity_exit_and_EOF_match_code_derived_rows():
    result=compare(*sdk_rows())
    assert result["history_rows"]==2 and result["clean_eof"] and result["native_closed"]
    assert result["sdk_run_ids"]==["unit559"] and result["sdk_exit_codes"]==[0]


@pytest.mark.parametrize("drift",("boolean_as_int","extra_metric","missing_metric","step","exit"))
def test_native_scientific_or_step_drift_cannot_pass(drift):
    records,expected=sdk_rows()
    if drift=="boolean_as_int":records[2].history.item[1].value_json="1"
    elif drift=="extra_metric":
        item=records[2].history.item.add();item.key="baseline/accepted";item.value_json="true"
    elif drift=="missing_metric":del records[1].history.item[-1]
    elif drift=="step":records[2].history.item[0].value_json="2"
    else:records[-1].exit.exit_code=1
    with pytest.raises(ValueError):compare(records,expected)


def test_new_A_case_spec_is_explicit_and_frozen_v7_globals_are_unchanged(tmp_path):
    before=deepcopy(archive.v7.CASES)
    assert "4520549" not in before
    with pytest.raises(ValueError,match="explicitly admitted549"):
        archive.make_A_plain(None,tmp_path,{**archive.A549,"history_rows":499})
    assert archive.v7.CASES==before
