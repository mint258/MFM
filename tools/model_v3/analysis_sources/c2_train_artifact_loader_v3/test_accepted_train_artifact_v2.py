"""Synthetic TRAIN fit/artifact and fake QA receipts; never real data or jobs."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

import numpy as np
import pytest

from phychem_mfm.phase1 import v3_coordinate_lookup as core
import coordinate_baseline_v2 as base
import accepted_train_artifact_v2 as loader


def records(role="TRAIN"):
    x = np.array([[0., 0., 0.], [.4, .1, 0.], [.1, .7, .2], [.2, .2, .8]])
    epsilon = np.array([[.01, -.03, .02], [-.02, .01, .03], [.04, -.01, -.02], [-.01, .02, .01]])
    for index in range(2 if role == "TRAIN" else 1):
        yield core.LookupRecord("synthetic_"+role+"_record_"+str(index), "synthetic_"+role+"_molecule_"+str(index), role,
            np.array([0, 1, 2, 3]), x+(index+1)*epsilon, x.copy(), "a"*64)


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False)+"\n")
    return base.support_runtime.binding(path)


def make_diagnostic_registration(root):
    """Two real, different commits with the exact frozen protocol/tree/blob."""
    repository = root/"synthetic_diagnostic_git"; repository.mkdir()
    raw = Path(__file__).with_name("frozen_diagnostic_protocol.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == base.DIAGNOSTIC_PROTOCOL_RAW_SHA256
    (repository/"diagnostic_protocol.json").write_bytes(raw)
    def git(*args):
        return subprocess.run(["git", "-C", str(repository), *args], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
    identity = ("-c", "user.name=Synthetic Test", "-c", "user.email=fixture@example.invalid")
    git("init"); git("add", "diagnostic_protocol.json"); git(*identity, "commit", "-m", "synthetic local execution")
    local, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    public = git(*identity, "commit-tree", tree, "-p", local, "-m", "synthetic distinct public same-tree publication")
    assert local != public and git("rev-parse", public+"^{tree}") == tree
    return {"repository": str(repository), "commit": local, "path": "diagnostic_protocol.json",
            "sha256": base.DIAGNOSTIC_PROTOCOL_RAW_SHA256}, {"commit": public, "tree": tree}


def refresh(fixture):
    r, v, refs = fixture["root"], fixture["values"], fixture["inputs"]
    refs["source_request"] = write(r/"request.json", v["request"])
    v["plan"]["source_request_sha256"] = base.support_runtime.canonical(v["request"])
    refs["selection_plan"] = write(r/"plan.json", v["plan"])
    prior = {"schema": "model_v3_C2_train_solver_diagnostic_inputs_v1", "source_request": refs["source_request"],
        "selection_plan": refs["selection_plan"], "protocol_registration": fixture["local_registration"],
        "public_registration": fixture["public_registration"]}
    prior_ref = write(r/"synthetic_original_diagnostic_inputs.json", prior)
    v["binding"].update(inputs=prior_ref, source_request=refs["source_request"], selection_plan=refs["selection_plan"])
    v["binding"]["protocol_registration"] = deepcopy(fixture["local_registration"])
    refs["TRAIN_diagnostic_input_binding"] = write(r/"input_binding.json", v["binding"])
    with (r/"private_train_arrays.npz").open("wb") as stream: np.savez_compressed(stream, **fixture["arrays"])
    refs["TRAIN_artifact"] = base.support_runtime.binding(r/"private_train_arrays.npz")
    v["diagnostic"]["array_artifact"]["binding"] = refs["TRAIN_artifact"]
    refs["TRAIN_diagnostic_result"] = write(r/"DIAGNOSTIC_RESULT.json", v["diagnostic"])
    refs["TRAIN_diagnostic_done"] = write(r/"DIAGNOSTIC_DONE.json", {"status": v["diagnostic"]["status"],
        "result": refs["TRAIN_diagnostic_result"], "inputs": prior_ref, "native_PRETRAIN_VAL_records_decoded": 0})
    v["supervisor"]["command"] = ["/SYNTHETIC/python", "/SYNTHETIC/diagnose_coordinate_lookup.py",
        "--inputs", prior_ref["path"], "--inputs-sha256", prior_ref["sha256"]]
    v["closure"]["supervisor"] = write(r/"supervisor.json", v["supervisor"])
    refs["TRAIN_closure"] = write(r/"TRAIN_closure.json", v["closure"])
    p = fixture["protocol"]
    p.update(source_request_raw_sha256=refs["source_request"]["sha256"], selection_plan_raw_sha256=refs["selection_plan"]["sha256"],
        TRAIN_diagnostic_result_raw_sha256=refs["TRAIN_diagnostic_result"]["sha256"],
        TRAIN_diagnostic_done_raw_sha256=refs["TRAIN_diagnostic_done"]["sha256"],
        TRAIN_diagnostic_input_binding_raw_sha256=refs["TRAIN_diagnostic_input_binding"]["sha256"],
        TRAIN_closure_raw_sha256=refs["TRAIN_closure"]["sha256"],
        TRAIN_artifact_raw_sha256=refs["TRAIN_artifact"]["sha256"], TRAIN_artifact_bytes=refs["TRAIN_artifact"]["bytes"])


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    # A real small SciPy TRAIN fit supplies candidate c. Stop7/C0 metadata below
    # is a clearly fake QA scenario, never an observation about 559 or 482.
    cfg = core.CoordinateLookupConfig(radius_A=2., bin_width_A=2.)
    fitted = base.fit_v2(core, records(), config=cfg, expected_records=2,
                         source_request_sha256="b"*64, source_plan_sha256="c"*64)
    system = base.build_train_system(core, records(), cfg, expected_records=2)
    from solver_math import augmented_active_jacobi
    transformed = augmented_active_jacobi(system.matrix, system.rhs_normalized, system.support, n_atoms=system.atoms, ridge=cfg.ridge)
    active = transformed.active_columns; k = len(active)
    arrays = {"active_columns": active, "observed_support": fitted.train_edge_counts[active],
        "candidate_coefficient": fitted.coefficients[active], "controlled_source_coefficient": np.zeros(k),
        "jacobi_scale": transformed.scale}
    threads = fitted.fit_receipt["thread_control"]
    baseline = {"original_configuration": asdict(cfg), "configured_iteration_limit": 500, "stop_code": 7,
        "iterations": 500, "coefficients_finite": True, "TRAIN_atoms": system.atoms,
        "TRAIN_directed_edges": system.directed_edges, "observed_support_columns": k,
        **{key: threads[key] for key in ("threadpools_before", "threadpools_inside_before", "threadpools_inside_after", "threadpools_restored")}}
    candidate = {"solver": fitted.fit_receipt["augmented_operator_statistics"], "preprocessing": fitted.fit_receipt["preprocessing"],
        "original_coordinate_diagnostics": fitted.fit_receipt["original_coordinate_KKT_and_objective"],
        **{key: threads[key] for key in ("threadpools_before", "threadpools_inside_before", "threadpools_inside_after", "threadpools_restored")}}
    plan_records = {role: [{"record_id": x.record_id, "molecule_id": x.molecule_id, "payload_sha256": x.payload_sha256,
        "native_n_atoms": len(x.elements)} for x in records(role)] for role in ("TRAIN", "PRETRAIN_VAL")}
    request = {"schema": "model_v3_C2_existing_S_request_v1", "preregistration_sha": base.support_runtime.ORIGINAL_PREREGISTRATION,
        "method": asdict(cfg), "selection": {"train_records": 2, "validation_records": 1},
        "source_files": {"current/phychem_mfm/phase1/v3_coordinate_lookup.py": base.source_sha(core.__file__)}}
    plan = {"records": plan_records, "selection": request["selection"], "selection_uses_targets": False, "native_geometry_records_decoded": 0}
    diagnostic = {"status": "DIAGNOSTIC_ONLY_COMPLETED_NO_BASELINE_ACCEPTANCE", "native_PRETRAIN_VAL_records_decoded": 0,
        "source": {"baseline": baseline, "native_TRAIN_records_decoded": 2}, "candidate": candidate,
        "original_TRAIN_CSR": fitted.fit_receipt["original_matrix"], "array_artifact": {"saved": True, "CSR_saved": False,
            "contents": {name: {"dtype": str(value.dtype), "shape": [k]} for name, value in arrays.items()}}}
    job, stdout = "999999", "999999|COMPLETED|0:0|8|\n999999.batch|COMPLETED|0:0|8|\n"
    supervisor = {"job_id": job, "status": "COMPLETED", "exit_code": 0, "first_failure": None, "remaining": [],
        "gpu_initialization_permitted": False, "private_storage": {"first_sampling_failure": None},
        "sources_sha256": {"/SYNTHETIC/"+name: sha for name, sha in loader.TRAIN_SUPERVISOR_SOURCES.items()}}
    closure = {"schema": "model_v3_C2_TRAIN_artifact_closure_v1", "source_job": {"job_id": job,
        "state": "COMPLETED", "exit_code": "0:0", "elapsed_seconds": 8},
        "raw_sacct": {"argv": ["sacct", "-n", "-P", "-j", job, "--format=JobIDRaw,State,ExitCode,ElapsedRaw"],
            "stdout": stdout, "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest()}}
    protocol = {"schema": "model_v3_C2_coordinate_baseline_v2_protocol_v1", "adoption_status": "ADOPTED_AFTER_TRAIN_ONLY_DIAGNOSTIC",
        "fit_origin": loader.FIT_ORIGIN, "solver": base.SOLVER, "caps": base.CAPS,
        "source_inventory_sha256": base.support_runtime.canonical(base.executed_sources()),
        "artifact_runtime_source_inventory_sha256": base.support_runtime.canonical(loader.executed_sources()),
        "TRAIN_fit_job_id": job, "TRAIN_records": 2, "active_columns": k, "full_columns": cfg.columns,
        "TRAIN_supervisor_sources_sha256": loader.TRAIN_SUPERVISOR_SOURCES}
    local_registration, public_registration = make_diagnostic_registration(tmp_path)
    monkeypatch.setattr(base, "DIAGNOSTIC_PREREGISTRATION", public_registration["commit"])
    value = {"root": tmp_path, "inputs": {}, "protocol": protocol, "arrays": arrays, "fitted": fitted,
        "local_registration": local_registration, "public_registration": public_registration,
        "values": {"request": request, "plan": plan, "diagnostic": diagnostic, "supervisor": supervisor,
            "closure": closure, "binding": {"executed_sources": base.REUSED_SOURCE_SHA256, "native_PRETRAIN_VAL_records_decoded": 0}}}
    refresh(value)
    return value


def test_restore_equals_real_small_train_fit_and_never_divides_by_D_again(fixture):
    loaded = loader.load_accepted_TRAIN_artifact(core, fixture["inputs"], fixture["protocol"])
    assert np.array_equal(loaded.coefficients, fixture["fitted"].coefficients)
    active, c, d = (fixture["arrays"][key] for key in ("active_columns", "candidate_coefficient", "jacobi_scale"))
    assert np.array_equal(loaded.coefficients[active], c) and not np.allclose(c, c/d)
    assert np.equal(loaded.coefficients[loaded.train_edge_counts == 0], 0).all()
    assert loaded.fit_receipt["fit_origin"] == loader.FIT_ORIGIN
    assert loaded.fit_receipt["current_job_TRAIN_geometry_reads"] == 0
    assert not loaded.fit_receipt["current_job_parameter_estimation_performed"]
    mapping = loaded.fit_receipt["diagnostic_registration_mapping"]
    assert mapping["executed_local_protocol_registration"] == fixture["local_registration"]
    assert mapping["public_registration"] == fixture["public_registration"]
    assert mapping["verified_local_tree"] == fixture["public_registration"]["tree"]


def test_artifact_model_honest_restore_and_original_eval_only_reads_synthetic_val(fixture):
    loaded = loader.load_accepted_TRAIN_artifact(core, fixture["inputs"], fixture["protocol"])
    document = json.loads(json.dumps(loaded.document(), allow_nan=False))
    restored = loader.restore_accepted_TRAIN_model(core, document)
    with pytest.raises(ValueError): base.restore_v2(core, document)
    class Source:
        native_reads = 0
        roles = []
        def records(self, role, plan):
            assert role == "PRETRAIN_VAL"
            self.roles.append(role)
            for row in records(role): self.native_reads += 1; yield row
    source = Source()
    actual = loader.evaluate_only(core, restored, source, {}, expected_records=1)
    expected = core.evaluate_coordinate_lookup(fixture["fitted"], list(records("PRETRAIN_VAL")), expected_records=1)
    assert actual == expected and source.roles == ["PRETRAIN_VAL"] and source.native_reads == 1


@pytest.mark.parametrize("change", ["missing", "extra", "dtype", "shape", "unsorted", "duplicate", "range", "support", "D", "nan", "object"])
def test_exact_private_npz_schema_and_numeric_boundaries_are_enforced_after_rebinding(fixture, change):
    a = fixture["arrays"]; k = len(a["active_columns"])
    if change == "missing": a.pop("controlled_source_coefficient")
    elif change == "extra": a["coordinates"] = np.zeros(k)
    elif change == "dtype": a["active_columns"] = a["active_columns"].astype(np.int32)
    elif change == "shape": a["candidate_coefficient"] = a["candidate_coefficient"][:-1]
    elif change == "unsorted": a["active_columns"] = a["active_columns"][::-1]
    elif change == "duplicate": a["active_columns"][1] = a["active_columns"][0]
    elif change == "range": a["active_columns"][-1] = fixture["protocol"]["full_columns"]
    elif change == "support": a["observed_support"][0] = 0
    elif change == "D": a["jacobi_scale"][0] = 0.
    elif change == "nan": a["candidate_coefficient"][0] = np.nan
    else: a["candidate_coefficient"] = a["candidate_coefficient"].astype(object)
    refresh(fixture)
    with pytest.raises(ValueError): loader.load_accepted_TRAIN_artifact(core, fixture["inputs"], fixture["protocol"])


@pytest.mark.parametrize("change", ["failed_job", "raw_failed", "guard_2GiB", "source_pin", "remaining", "command", "old_succeeded", "candidate_failed", "thread", "matrix", "plan"])
def test_closed_source_job_and_train_method_chain_are_not_boolean_only(fixture, change):
    v = fixture["values"]
    if change == "failed_job": v["closure"]["source_job"]["state"] = "FAILED"
    elif change == "raw_failed":
        raw = v["closure"]["raw_sacct"]; raw["stdout"] = raw["stdout"].replace("COMPLETED", "FAILED")
        raw["stdout_sha256"] = hashlib.sha256(raw["stdout"].encode()).hexdigest()
    elif change == "guard_2GiB":
        pins = v["supervisor"]["sources_sha256"]; pins["/SYNTHETIC/run_cpu_supervised_v3.py"] = pins.pop("/SYNTHETIC/run_cpu_supervised_128m_v1.py")
    elif change == "source_pin": v["binding"]["executed_sources"] = {**base.REUSED_SOURCE_SHA256, "solver_math.py": "0"*64}
    elif change == "remaining": v["supervisor"]["remaining"] = [{"pid": 1}]
    elif change == "command":
        refresh(fixture)
        v["supervisor"]["command"][-1] = "0"*64
        v["closure"]["supervisor"] = write(fixture["root"]/"supervisor.json", v["supervisor"])
        fixture["inputs"]["TRAIN_closure"] = write(fixture["root"]/"TRAIN_closure.json", v["closure"])
    elif change == "old_succeeded": v["diagnostic"]["source"]["baseline"]["stop_code"] = 2
    elif change == "candidate_failed": v["diagnostic"]["candidate"]["solver"]["stop_code"] = 7
    elif change == "thread":
        v["diagnostic"]["candidate"]["threadpools_inside_after"] = [{"filepath": "synthetic_blas", "user_api": "blas", "num_threads": 2}]
    elif change == "matrix": v["diagnostic"]["original_TRAIN_CSR"]["shape"][0] += 3
    else: v["binding"]["selection_plan"] = {"sha256": "0"*64}  # set after refresh below
    if change not in ("command", "plan"): refresh(fixture)
    if change == "plan":
        ref = write(fixture["root"]/"input_binding.json", v["binding"])
        fixture["inputs"]["TRAIN_diagnostic_input_binding"] = ref
    with pytest.raises(ValueError): loader.load_accepted_TRAIN_artifact(core, fixture["inputs"], fixture["protocol"])


def test_raw_npz_or_completed_result_drift_is_refused_before_prediction(fixture):
    ref = fixture["inputs"]["TRAIN_artifact"]
    Path(ref["path"]).write_bytes(b"changed closed NPZ")
    with pytest.raises(ValueError): loader.load_accepted_TRAIN_artifact(core, fixture["inputs"], fixture["protocol"])
    refresh(fixture)
    Path(fixture["inputs"]["TRAIN_diagnostic_result"]["path"]).write_text("changed result")
    with pytest.raises(ValueError): loader.load_accepted_TRAIN_artifact(core, fixture["inputs"], fixture["protocol"])


@pytest.mark.parametrize("mode", ["compressed_bytes", "expanded_member"])
def test_npz_byte_and_expanded_header_budgets_are_checked_before_loading(fixture, monkeypatch, mode):
    ref = fixture["inputs"]["TRAIN_artifact"]
    declaration = fixture["values"]["diagnostic"]["array_artifact"]["contents"]
    k = fixture["protocol"]["active_columns"]
    if mode == "compressed_bytes":
        monkeypatch.setitem(base.CAPS, "maximum_array_bytes", 16)
    else:
        path = fixture["root"]/"oversized_header.npz"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, (name, array) in enumerate(fixture["arrays"].items()):
                buf = io.BytesIO(); np.save(buf, array, allow_pickle=False)
                archive.writestr(name+".npy", b"x"*(k*8+4097) if index == 0 else buf.getvalue())
        ref = base.support_runtime.binding(path)
    with pytest.raises(ValueError): loader.checked_npz(ref, declaration, active_count=k, full_columns=fixture["protocol"]["full_columns"])


@pytest.mark.parametrize("change", ["loader_source", "origin"])
def test_restored_model_cannot_hide_loader_drift_or_relabel_prior_training(fixture, change):
    model = loader.load_accepted_TRAIN_artifact(core, fixture["inputs"], fixture["protocol"])
    document = model.document()
    if change == "loader_source": document["artifact_runtime_source_sha256"] = {"accepted_train_artifact_v2.py": "0"*64}
    else: document["fit_receipt_v2"]["fit_origin"] = "new_current_job_fit"
    with pytest.raises(ValueError): loader.restore_accepted_TRAIN_model(core, document)


@pytest.mark.parametrize("prepared", [True, False])
def test_real_git_artifact_protocol_requires_explicit_new_adoption_and_all_five_sources(fixture, prepared):
    p = fixture["protocol"]
    if prepared: p["adoption_status"] = "PREPARED_CONDITIONAL_NOT_ADOPTED"
    protocol_ref = write(fixture["root"]/"protocol.json", p)
    def git(*args):
        return subprocess.run(["git", "-C", str(fixture["root"]), *args], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
    git("init"); git("add", "protocol.json")
    git("-c", "user.name=Synthetic Test", "-c", "user.email=fixture@example.invalid", "commit", "-m", "synthetic artifact protocol")
    fixture["inputs"]["protocol_registration"] = {"repository": str(fixture["root"]), "commit": git("rev-parse", "HEAD"),
        "path": "protocol.json", "sha256": protocol_ref["sha256"]}
    if prepared:
        with pytest.raises(ValueError, match="prepared"): loader.adopted_artifact_protocol(fixture["inputs"])
    else:
        assert loader.adopted_artifact_protocol(fixture["inputs"]) == p
