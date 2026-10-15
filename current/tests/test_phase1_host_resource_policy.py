"""Concrete CPU16/RAM64 resource revision; synthetic metadata, no model runs."""
from copy import deepcopy

import pytest

from phychem_mfm.phase1 import formal_gate as gate
from phychem_mfm.phase1 import pretraining_scientific_authority as authority
from test_phase1_pretraining_scope import prepared, seal, codes
from test_phase1_shared_gpu_policy import shared, live


def revision(state):
    state["case"]["protocol"]["compute"].update(
        gpu_isolation_policy=gate.SHARED_GPU_POLICY, resource_policy=authority.RESOURCE_POLICY,
        cpus_per_task=16, requested_cpu_memory_gib=64)
    seal(state)


def test_only_host_requests_change_without_rewriting_original_science(prepared):
    original = deepcopy(prepared["science"])
    digest = prepared["case"]["protocol"][authority.AUTHORITY_FIELD]
    revision(prepared)
    report = gate.check_formal_gate(**prepared["case"])
    assert not report.issues and report.status == "REVIEW_ONLY"
    assert not report.may_start_formal_training
    assert prepared["science"] == original
    assert prepared["case"]["protocol"][authority.AUTHORITY_FIELD] == digest
    receipt = authority.verify_pretraining_scientific_authority(
        prepared["case"]["protocol"], prepared["case"]["artifacts"], now=prepared["case"]["now"])
    assert receipt["host_resource_projection_override"] == {
        "policy": authority.RESOURCE_POLICY,
        "fields": {"compute.cpus_per_task": 16, "compute.requested_cpu_memory_gib": 64},
        "changes_scientific_model_or_data": False, "actual_allocation_verified": False}


def test_16cpu_64g_without_explicit_revision_still_mismatches_science(prepared):
    prepared["case"]["protocol"]["compute"].update(cpus_per_task=16, requested_cpu_memory_gib=64)
    seal(prepared)
    assert gate.check_formal_gate(**prepared["case"]).issues


@pytest.mark.parametrize("policy", ("ignore_resource_choices", True, {}, 16))
def test_unknown_or_nonstring_resource_policy_rejected(prepared, policy):
    revision(prepared)
    prepared["case"]["protocol"]["compute"]["resource_policy"] = policy
    seal(prepared)
    assert "protocol.execution_scope" in codes(gate.check_formal_gate(**prepared["case"]))


@pytest.mark.parametrize("field,value", (("cpus_per_task", 15), ("cpus_per_task", 17),
                                         ("cpus_per_task", 16.0), ("cpus_per_task", True),
                                         ("requested_cpu_memory_gib", 63), ("requested_cpu_memory_gib", 65),
                                         ("requested_cpu_memory_gib", 64.0), ("requested_cpu_memory_gib", True)))
def test_revision_cannot_silently_choose_different_counts(prepared, field, value):
    revision(prepared)
    prepared["case"]["protocol"]["compute"][field] = value
    seal(prepared)
    assert "protocol.execution_scope" in codes(gate.check_formal_gate(**prepared["case"]))


@pytest.mark.parametrize("scope,policy", (("full", gate.SHARED_GPU_POLICY),
                                         ("downstream", gate.SHARED_GPU_POLICY),
                                         ("pretraining_only", "protected_slurm_gpu")))
def test_revision_is_not_a_general_resource_relaxation(prepared, scope, policy):
    revision(prepared)
    protocol = prepared["case"]["protocol"]
    protocol["execution_scope"] = scope
    protocol["compute"]["gpu_isolation_policy"] = policy
    seal(prepared)
    assert "protocol.execution_scope" in codes(gate.check_formal_gate(**prepared["case"]))


@pytest.mark.parametrize("field", ("max_walltime_hours", "max_concurrent_jobs", "gpus_per_job",
                                  "min_free_gpu_memory_gib", "min_gpu_memory_gib"))
def test_other_frozen_resource_choices_still_match_original_authority(prepared, field):
    revision(prepared)
    prepared["case"]["protocol"]["compute"][field] += 1
    seal(prepared)
    assert gate.check_formal_gate(**prepared["case"]).issues


@pytest.mark.parametrize("field", ("optimizer_steps_per_condition", "structures_per_condition"))
def test_host_revision_does_not_allow_scientific_budget_drift(prepared, field):
    revision(prepared)
    prepared["case"]["protocol"]["pretraining"]["budget"][field] += 1
    seal(prepared)
    assert gate.check_formal_gate(**prepared["case"]).issues


@pytest.mark.parametrize("memory", ("64G", "65536M", "65536"))
def test_live_cpu16_ram64_uses_actual_site_request(shared, prepared, monkeypatch, memory):
    revision(prepared)
    shared[0]["slurm_job_text"] = shared[0]["slurm_job_text"].replace("cpu=4,mem=12G", "cpu=16") + " MinMemoryNode=" + memory
    report = live(shared, monkeypatch)
    assert not report.issues and report.status == gate.SHARED_GPU_STATUS
    assert report.may_start_formal_training
    assert report.runtime_observation["gpu_protection_verified"] is False


@pytest.mark.parametrize("actual,issue", (("cpu=2,mem=64G", "runtime.scientific_cpus"),
                                         ("cpu=16,mem=12G", "runtime.cpu_memory"),
                                         ("cpu=16,mem=invalid", "runtime.cpu_memory")))
def test_protocol_revision_does_not_invent_actual_allocation(shared, prepared, monkeypatch, actual, issue):
    revision(prepared)
    shared[0]["slurm_job_text"] = shared[0]["slurm_job_text"].replace("cpu=4,mem=12G", actual)
    report = live(shared, monkeypatch)
    assert issue in codes(report) and not report.may_start_formal_training
