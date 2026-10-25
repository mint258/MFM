"""Targeted new v8 export/failed observation tests, no actual target access."""
from copy import deepcopy
import csv
import io
import json
import os
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0,str(Path(__file__).parent))
import archive_closed_runs_v8 as archive


def sample_rows():
    return [{"step":0,"candidate/qm9.U0@ridge/validation_error":.5},
            {"step":1,"candidate/qm9.U0@linear64_relu/readout/loss":.25,
             "candidate/qm9.U0@linear64_relu/readout/epoch":1,
             "candidate/qm9.U0@linear64_relu/readout/observed_labels":10,
             "candidate/qm9.U0@linear64_relu/readout/update":1}]


def records(rows=None,*,ancillary=0,summary_score=.125):
    from wandb.proto import wandb_internal_pb2 as pb
    first = pb.Record(); first.run.run_id="unit_primary"; first.run.display_name="unit_primary_display"
    item = first.run.config.update.add(); item.key="source"; item.value_json='"unit"'
    yield first
    for _ in range(ancillary):
        record=pb.Record(); record.metric.name="unit_metric"; yield record
    for row in (sample_rows() if rows is None else rows):
        record=pb.Record()
        for key,value in {"_step":row["step"],**{k:v for k,v in row.items() if k!="step"}}.items():
            item=record.history.item.add(); item.key=key; item.value_json=json.dumps(value)
        yield record
    summary=pb.Record(); item=summary.summary.update.add(); item.key="score"; item.value_json=json.dumps(summary_score); yield summary
    final=pb.Record(); final.exit.exit_code=0; yield final


def compare_primary(native=None,*,summary_score=.125,expected_summary=.125):
    scope=archive.load_source(archive.PRIMARY_ROOT/"primary512_scope.py",archive.SCOPE_SHA,"primary512_scope")
    parser=archive.load_source(archive.PRIMARY_ROOT/"verify_native_history.py",archive.PRIMARY_SHA,"archive_readonly_primary_verifier")
    normalized,scalar=io.BytesIO(),io.BytesIO()
    sink=archive.CompleteScalarSink(normalized,scalar)
    source=io.BytesIO(b"".join(parser.encoded(row) for row in sample_rows()))
    details=parser.compare_records(records(summary_score=summary_score) if native is None else native,
        parser.journal_rows(source),sink,expected_run_id="unit_primary",expected_display_name="unit_primary_display",
        expected_config={"source":"unit"},expected_summary={"score":expected_summary},expected_rows=2)
    return details,sink,normalized.getvalue(),scalar.getvalue()


def test_complete_scalar_csv_contains_every_field_and_matches_canonical_stream():
    details,sink,normalized,raw_csv=compare_primary()
    rows=list(csv.DictReader(io.StringIO(raw_csv.decode())))
    assert len(rows)==sink.scalars==5 and sink.rows==2
    assert {(int(row["step"]),row["key"]) for row in rows} == {(row["step"],key) for row in sample_rows() for key in row if key!="step"}
    assert details["normalized_history_sha256"]==sink.digest.hexdigest()
    assert details["normalized_history_bytes"]==len(normalized)
    assert {(int(row["step"]),row["key"]):json.loads(row["value_json"]) for row in rows} == {(row["step"],key):value for row in sample_rows() for key,value in row.items() if key!="step"}


@pytest.mark.parametrize("changed",("native_records","history_rows","normalized_history_sha256","series","sdk_exit_code","clean_eof"))
def test_exact_original_certificate_comparison_rejects_any_new_drift(changed):
    details,*_=compare_primary()
    certificate=deepcopy(details)
    if changed=="series":
        certificate[changed]={}
    elif changed=="normalized_history_sha256":
        certificate[changed]="0"*64
    elif changed=="clean_eof":
        certificate[changed]=False
    else:
        certificate[changed]+=1
    with pytest.raises(ValueError,match="certificate differs"):
        archive.compare_certificate(details,certificate)


def test_primary_ancillary_packets_over_50000_do_not_truncate_scalar_history():
    parser=archive.load_source(archive.PRIMARY_ROOT/"verify_native_history.py",archive.PRIMARY_SHA,"archive_readonly_primary_verifier")
    from wandb.proto import wandb_internal_pb2 as pb
    class Stream:
        def __init__(self):
            self.items=iter(records(ancillary=50001))
        def scan_data(self):
            record=next(self.items,None)
            return None if record is None else record.SerializeToString()
    details,sink,_,_=compare_primary(parser.scan_records(Stream(),pb.Record,deadline=time.monotonic()+20))
    assert details["native_records"]==50006 and details["history_rows"]==2 and sink.scalars==5 and details["clean_eof"]


def test_full_primary_comparison_checks_summary_and_all_metrics():
    with pytest.raises(ValueError,match="final summary"):
        compare_primary(summary_score=.25)
    bad=list(records()); bad[1].history.item[-1].value_json="0.501"
    with pytest.raises(ValueError,match="scientific payload/step"):
        compare_primary(bad)


@pytest.mark.parametrize("bad_step",(0,2))
def test_complete_sink_rejects_duplicate_or_missing_step(bad_step):
    sink=archive.CompleteScalarSink(io.BytesIO(),io.BytesIO())
    sink.write(archive.reader.encoded(sample_rows()[0]))
    row=deepcopy(sample_rows()[1]); row["step"]=bad_step
    with pytest.raises(ValueError,match="step/grid"):
        sink.write(archive.reader.encoded(row))


def test_complete_sink_checks_export_byte_budget():
    with pytest.raises(ValueError,match="byte budget"):
        archive.CompleteScalarSink(io.BytesIO(),io.BytesIO(),max_bytes=1)


@pytest.mark.parametrize("count",(0,1,3))
def test_failed546_counts_actual_history_without_preassuming_zero(count):
    from wandb.proto import wandb_internal_pb2 as pb
    native=list(records(rows=[{"step":i,"candidate/qm9.U0@ridge/validation_error":.5} for i in range(count)]))
    native[-1].exit.exit_code=1
    class Stream:
        items=iter(native)
        def scan_data(self):
            record=next(self.items,None)
            return None if record is None else record.SerializeToString()
    output=io.BytesIO()
    details=archive.observe_failed_stream(Stream(),pb.Record,output,expected_run_id="unit_primary")
    assert details["history_rows_observed"]==count and details["slurm_state"]=="FAILED"
    assert details["numeric_gate_pass"] is details["timing_gate_pass"] is False
    assert details["independent_mirror_verification"] is False and details["native_exit_codes"]==[1]


def test_failed_observer_preserves_missing_exit_and_keeps_packet_budget_strict():
    from wandb.proto import wandb_internal_pb2 as pb
    first=next(records())
    class NoExit:
        items=iter((first,))
        def scan_data(self):
            record=next(self.items,None)
            return None if record is None else record.SerializeToString()
    details=archive.observe_failed_stream(NoExit(),pb.Record,io.BytesIO(),expected_run_id="unit_primary")
    assert not details["native_closed"] and details["native_exit_codes"]==[]
    class Endless:
        def scan_data(self):
            record=pb.Record(); record.metric.name="unit"; return record.SerializeToString()
    with pytest.raises(archive.reader.BudgetError):
        archive.observe_failed_stream(Endless(),pb.Record,io.BytesIO(),expected_run_id="unit_primary",max_packets=2)


def test_hash_only_provenance_cache_rejects_changed_identity_and_bound(tmp_path):
    path=tmp_path/"unit_checkpoint_bytes"; path.write_bytes(b"old")
    cache=archive.ProvenanceBindings(); before=cache(path)
    assert cache(path)==before
    with pytest.raises(ValueError,match="explicit reference bound"):
        cache(path,2)
    path.write_bytes(b"new")
    current=path.stat(); os.utime(path,ns=(current.st_atime_ns,current.st_mtime_ns+1000000000))
    with pytest.raises(ValueError,match="identity/size/mtime"):
        cache.unchanged()
    assert cache(path)["sha256"]!=before["sha256"]
