"""Certificate reuse, exact aggregate projection, privacy and unit preservation."""
from copy import deepcopy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).parent))
import archive_closed_runs_v12 as archive


@pytest.fixture(scope="module")
def original():
    # Only these safe public aggregate/ref/supervisor metadata files are parsed.
    return tuple(archive.v7.read_json(path)[0] for path in (
        archive.REPORT_ROOT/"REPORT_COMPLETE.json",archive.REPORT_ROOT/"native_verification.json",archive.REPORT_ROOT/"report.json",
        archive.REPORT_INPUTS,archive.TASK/"C2_first_VAL_supervisor_4520603.json",archive.TASK/"C2_actual_SDK_report_supervisor_4520606.json"))


def test_actual606_certificate_safe_aggregate_two_steps_digest_and_config_match_without_decoder(original,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError("Sensitive metadata parser must not execute")
    monkeypatch.setattr(archive.schema,"prepare",forbidden);monkeypatch.setattr(archive.schema,"read",forbidden)
    rows=archive.validate_bundle(*original)
    assert [row["step"] for row in rows]==[0,1]
    assert rows[0]["row"]["prior_TRAIN_fit/records"]==8192
    assert rows[0]["row"]["current_job/TRAIN_geometry_reads"]==0
    assert rows[1]["row"]["validation/records"]==1024 and rows[1]["row"]["validation/atoms"]==55650
    raw=b"".join(archive.schema.encoded(row) for row in rows)
    assert hashlib.sha256(raw).hexdigest()==original[1]["native"]["normalized_history_sha256"]
    assert len(raw)==908 and original[1]["native"]["native_packets"]==31
    assert "commit" not in rows[0]  # not a fabricated original fsync mirror


@pytest.mark.parametrize("drift",("history_count","steps","native_records","exit","EOF","uncommitted","config_digest","payload_digest",
    "SDK_ref","all_fields_exact","verifier_source","producer_source","report_bindings","report_complete"))
def test_certificate_complete_report_or_source_drift_cannot_be_reused(original,drift):
    values=deepcopy(original);complete,cert,report,inputs,_,_=values
    if drift=="history_count":cert["native"]["history_rows"]=500
    elif drift=="steps":cert["verified_steps"]=[1,2]
    elif drift=="native_records":report["independent_native_SDK"]["native_records"]=2
    elif drift=="exit":cert["native"]["sdk_exit_codes"]=[1]
    elif drift=="EOF":cert["native"]["clean_eof"]=False
    elif drift=="uncommitted":cert["native"]["uncommitted_native_requests"]=1
    elif drift=="config_digest":cert["expected_config_sha256"]="0"*64
    elif drift=="payload_digest":cert["expected_two_rows_sha256"]="0"*64
    elif drift=="SDK_ref":inputs["SDK_file"]["sha256"]="0"*64
    elif drift=="all_fields_exact":cert["all_public_metrics_config_summary_exact"]=False
    elif drift=="verifier_source":cert["verifier_source"]["sha256"]="0"*64
    elif drift=="producer_source":cert["fixed_logger_source_sha256"]="0"*64
    elif drift=="report_bindings":report["source_bindings"]["result"]["sha256"]="0"*64
    else:complete["status"]="PENDING"
    with pytest.raises(ValueError):archive.validate_bundle(*values)


@pytest.mark.parametrize("drift",("VAL_population","atoms","TRAIN_reads","new_fit","parameter_job","component_vector_swap","sigma",
    "denominator","unknown_excluded","model_selection","identity_export","old_failed_reinterpreted","old_stop_inferred","online","supervisor"))
def test_population_units_analysis_scope_and_old_failures_are_preserved(original,drift):
    values=deepcopy(original);report=values[2]
    if drift=="VAL_population":report["current_job_PRETRAIN_VAL_geometry_reads"]=1023
    elif drift=="atoms":report["metrics"]["atoms"]=55649
    elif drift=="TRAIN_reads":report["current_job_TRAIN_geometry_reads"]=8192
    elif drift=="new_fit":report["current_job_parameter_estimation_performed"]=True
    elif drift=="parameter_job":report["parameter_estimation_job_id"]="4520603"
    elif drift=="component_vector_swap":report["metrics"]["coordinate_component_RMSE_A"]=report["metrics"]["coordinate_vector_RMSE_A"]
    elif drift=="sigma":report["metrics"]["explicit_sigma_normalized_component_MSE"]=report["metrics"]["displacement_vector_MSE_A2"]
    elif drift=="denominator":report["metric_units_and_denominators"]["coordinate_vector_RMSE_A"]["denominator"]="sqrt(SSE/(3N))"
    elif drift=="unknown_excluded":report["core_metric_metadata"]["unknown_bins_use_zero_correction_without_exclusion"]=False
    elif drift=="model_selection":report["model_selection_gate"]=True
    elif drift=="identity_export":report["identities_weights_native_geometries_predictions_exported"]=True
    elif drift=="old_failed_reinterpreted":report["original_v1_job_4520482_remains_FAILED"]=False
    elif drift=="old_stop_inferred":report["original_v1_stop_inferred"]=True
    elif drift=="online":report["online_sync_claimed"]=True
    else:values[5]["first_failure"]={"type":"failure"}
    with pytest.raises(ValueError):archive.validate_bundle(*values)


@pytest.mark.parametrize("drift",("root_member_ids","nested_member_ids","scalar_identity","unallowlisted_array","weight_payload"))
def test_safe_report_rejects_identity_arrays_weights_or_extra_payload(original,drift):
    report=deepcopy(original[2])
    if drift=="root_member_ids":report["TRAIN_member_ids"]=["sensitive"]
    elif drift=="nested_member_ids":report["metrics"]["members"]=["sensitive"]
    elif drift=="scalar_identity":report["metrics"]["molecule_id"]="sensitive"
    elif drift=="unallowlisted_array":report["prior_solver_statistics"]["unexpected"]=[1,2]
    else:report["prior_solver_statistics"]["weights"]={"test":1.}
    with pytest.raises(ValueError):archive.safe_report(report)


def test_hash_only_metadata_binding_never_parses_or_copies_fit_result_or_plan(original):
    refs=deepcopy(original[1]["metadata_bindings"]);seen=[]
    def binder(path,maximum):
        seen.append((str(path),maximum));return next(ref for ref in refs.values() if ref["path"]==str(path))
    actual=archive.bound_refs(refs,binder)
    assert actual==list(refs.values()) and len(seen)==len(refs)
    assert all(maximum==32<<20 for _,maximum in seen)
    assert {refs[name]["path"] for name in ("fit_receipt","result","selection_plan")}<=set(path for path,_ in seen)
    # The callback sees raw file references only; no JSON/result loader is used.


@pytest.mark.parametrize("name",("LOOKUP.json","weights.npz"))
def test_LOOKUP_or_NPZ_ref_is_rejected_before_its_reader_is_called(original,name):
    refs=deepcopy(original[1]["metadata_bindings"]);forbidden=str(archive.TASK/name);refs["result"]["path"]=forbidden;seen=[]
    def binder(path,maximum):
        seen.append(str(path));return next(ref for ref in refs.values() if ref["path"]==str(path))
    with pytest.raises(ValueError,match="no LOOKUP/NPZ"):archive.bound_refs(refs,binder)
    assert forbidden not in seen


def test_hash_only_source_drift_or_oversized_reference_is_rejected(original):
    refs=deepcopy(original[1]["metadata_bindings"])
    with pytest.raises(ValueError,match="raw SHA"):
        archive.bound_refs(refs,lambda path,maximum:{**next(ref for ref in refs.values() if ref["path"]==str(path)),"sha256":"0"*64})
    refs["result"]["bytes"]=(32<<20)+1
    with pytest.raises(ValueError):archive.bound_refs(refs,lambda path,maximum:None)


@pytest.mark.parametrize("name",("fit_receipt","result","selection_plan"))
def test_full_member_metadata_cannot_cross_copy_boundary(original,name,tmp_path,monkeypatch):
    copied=[]
    monkeypatch.setattr(archive.v7,"copy_ref",lambda *args:copied.append(args))
    with pytest.raises(ValueError,match="hash-only and cannot be copied"):
        archive.copy_selected_metadata(None,original[1]["metadata_bindings"][name],tmp_path/"forbidden")
    assert copied==[] and not (tmp_path/"forbidden").exists()


def test_actual_safe_aggregate_csv_and_all_two_step_scalar_exports_match(original):
    text=(archive.REPORT_ROOT/"summary.csv").read_text()
    archive.check_csv(text,original[2],original[3])
    rows=list(csv.DictReader(io.StringIO(archive.payload_csv(archive.verified_payload(original[2])).decode())))
    assert len(rows)==19 and {row["verified_native_step"] for row in rows}=={"0","1"}
    assert next(row for row in rows if row["key"]=="validation/coordinate_component_RMSE_A")["value_json"]=="0.06549941338751054"


@pytest.mark.parametrize("drift",("missing_metric","extra_metric","component_vector_swap","wrong_stage","wrong_fit_provenance"))
def test_csv_cannot_drop_fields_change_RMSE_units_or_provenance(original,drift):
    source=(archive.REPORT_ROOT/"summary.csv").read_text();row=list(csv.DictReader(io.StringIO(source)))[0]
    if drift=="missing_metric":row.pop("metric__atoms")
    elif drift=="extra_metric":row["metric__member_ids"]="1"
    elif drift=="component_vector_swap":row["denoise_rmse"]=row["metric__coordinate_vector_RMSE_A"]
    elif drift=="wrong_stage":row["stage"]="6"
    else:row["code_sha"]="0"*40
    stream=io.StringIO(newline="");writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerow(row)
    with pytest.raises(ValueError):archive.check_csv(stream.getvalue(),original[2],original[3])


def test_archive_module_has_no_native_decoder_or_sensitive_prepare_invocation():
    import ast
    tree=ast.parse(Path(archive.__file__).read_text())
    names={node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
    assert not (names&{"prepare","load_context","open_for_scan","scan_data","verify_stream","verify_file"})
    imports=[node for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom))]
    assert not any("wandb" in ast.unparse(node) for node in imports)
