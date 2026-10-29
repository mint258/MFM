"""Typed CPU protocol checks, never fabricated CUDA/Slurm acceptance.

No selection function queries hardware in these tests. The positive observer
uses genuine CPU forward/backward/Adam state and must remain CUDA-ineligible.
"""
from copy import deepcopy
import json

import pytest
import torch

from test_model_v3_training_execution import assembled, packed, configuration, workload, policy, cpu_runtime
from phychem_mfm.model.v3_checkpoint_policy import canonical
from phychem_mfm.model.v3_training_capacity import (TrainingCapacityObserver, TrainingCapacityGuard,
    optimizer_storage_inventory, load_closed_training_observation)


def cpu_resources():
    return {"gpu_observation": None, "peak_allocated_bytes": 0, "peak_reserved_bytes": 0,
        "process_rss_sum_bytes": 1, "foreign_gpu_risk_observed": False, "output_bytes": 0}


def observed(tmp_path):
    model, optimizer, execution, contract = assembled("C1-b", packing=True)
    observer = execution.observer
    journal = tmp_path / "capacity.jsonl"
    journal.touch(exist_ok=False)
    def sink(row):
        with journal.open("a") as stream:stream.write(json.dumps(row, allow_nan=False) + "\n")
    observer.set_sink(sink)
    batches = packed(); rows = []
    for role in ("TRAIN", "VAL", "TRAIN_UNSEEN_CONFORMATION"):
        if role != "TRAIN":
            observer.begin_validation(role, batch_count=1,
                population_binding=observer.workload["data"]["validation_population_bindings"][role])
        with observer.forward_context(model, role=role):
            if role == "TRAIN":
                output, pd = model(batches)
                snapshot = observer.capture_forward(model, role=role)
                # The real probe is a different batch, after MAIN capture.
                model(packed().to_data_list()[0])
                (output.atom_repr.square().mean() + pd.square().mean()).backward(); optimizer.step()
            else:
                with torch.no_grad():model(batches)
                snapshot = observer.capture_forward(model, role=role)
        row = observer.record_completed(snapshot, optimizer=optimizer, optimizer_updates=1,
            samples_consumed=3, resources=cpu_resources()); rows.append(row)
        if role != "TRAIN":observer.complete_validation(role)
    return model, optimizer, execution, observer.summary(), rows, journal


def test_actual_cpu_observation_streams_main_shapes_not_probe_and_both_populations(tmp_path):
    model, optimizer, execution, summary, rows, journal = observed(tmp_path)
    assert summary["status"] == "OBSERVED_TRAINING_CAPACITY_PENDING_ACTUAL_OUTER_C0"
    assert summary["all_observations_cuda"] is False and summary["observed_peak_bytes"] == 0
    assert summary["rows"] == 3 and summary["scientific_acceptance"] is False
    assert set(summary["completed_validation"]) == {"VAL", "TRAIN_UNSEEN_CONFORMATION"}
    assert all(row["logical_batch"]["graph_atom_counts"] == [1, 3, 7] for row in rows)
    assert summary["roles"]["TRAIN"]["graphs"] == 3
    assert summary["roles"]["TRAIN"]["executed_dense_shapes"] == [[1, 1], [1, 3], [1, 7]]
    assert [json.loads(line) for line in journal.read_text().splitlines()] == rows
    inventory = optimizer_storage_inventory(optimizer)
    assert inventory["materialized_parameter_count"] > 0 and inventory["unknown_state"] == []
    assert inventory["unmaterialized_state_storage_upper_bound_bytes"] >= 0
    assert not hasattr(execution.observer, "rows")  # No activation/journal list in memory.


def test_adam_future_state_inventory_is_real_shape_storage_and_unknown_stays_unknown():
    parameter = torch.nn.Parameter(torch.ones(5, dtype=torch.float32))
    optimizer = torch.optim.AdamW([parameter], lr=.001, amsgrad=True)
    initial = optimizer_storage_inventory(optimizer)
    assert initial["unmaterialized_state_storage_upper_bound_bytes"] == 3 * 5 * 4 + 16
    parameter.sum().backward(); optimizer.step()
    ready = optimizer_storage_inventory(optimizer)
    assert ready["materialized_parameter_count"] == 1 and ready["unmaterialized_state_storage_upper_bound_bytes"] == 0
    optimizer.state[parameter]["unexpected"] = torch.ones(1)
    assert optimizer_storage_inventory(optimizer)["unknown_state"]


@pytest.mark.parametrize("change", ["missing_resource", "unknown_memory", "duplicate_commit", "wrong_population"])
def test_observer_typed_failures_do_not_gain_cuda_qualification(change):
    model, optimizer, execution, _ = assembled("C1-a")
    observer = execution.observer
    model(packed()); snapshot = observer.capture_forward(model, role="TRAIN")
    resource = cpu_resources()
    if change == "missing_resource":resource.pop("output_bytes")
    elif change == "unknown_memory":resource["peak_reserved_bytes"] = None
    elif change == "wrong_population":
        with pytest.raises(ValueError, match="population"):
            observer.begin_validation("VAL", batch_count=1, population_binding={"fixture": "other"})
        return
    if change == "duplicate_commit":
        observer.record_completed(snapshot, optimizer=optimizer, optimizer_updates=0,
            samples_consumed=3, resources=resource)
    with pytest.raises(ValueError):
        observer.record_completed(snapshot, optimizer=optimizer, optimizer_updates=0,
            samples_consumed=3, resources=resource)


def test_incomplete_validation_keeps_profile_unfinalized():
    model, _, execution, _ = assembled("C1-a")
    observer = execution.observer
    observer.begin_validation("VAL", batch_count=2,
        population_binding=observer.workload["data"]["validation_population_bindings"]["VAL"])
    with pytest.raises(ValueError, match="exact population"):observer.complete_validation("VAL")
    # Failed/incomplete population stays active and cannot be finalized.
    with pytest.raises(ValueError, match="Incomplete"):
        observer.summary()


def test_A_only_capacity_schema_rejected_before_gpu_or_model_qualification(tmp_path):
    from phychem_mfm.model.v3_checkpoint_policy import file_reference
    files = {}
    for key in ("configuration", "summary", "run_status", "supervisor", "parent_sacct", "steps"):
        path = tmp_path / (key + ".json")
        path.write_text(json.dumps({"schema": "A_ONLY_EXISTING_SCHEMA"}))
        files[key] = file_reference(path)
    from phychem_mfm.phase1.v3_training_execution import TrainingExecutionSpec
    from phychem_mfm.model.v3_performance import PerformanceOptions
    initialized = torch.cuda.is_initialized()
    with pytest.raises(ValueError, match="A-only"):
        load_closed_training_observation(files, TrainingExecutionSpec(), workload(configuration()), PerformanceOptions(), {})
    assert torch.cuda.is_initialized() == initialized


def test_auto_missing_training_profile_refuses_before_actual_hardware_selection():
    from phychem_mfm.phase1.v3_training_execution import build_training_encoder
    request = policy(); request["checkpoint_policy"] = "auto_closed_training_profile_v1"
    request["options"]["backbone_checkpointing"] = None
    initialized = torch.cuda.is_initialized()
    with pytest.raises(ValueError, match="operational"):
        build_training_encoder(configuration(), execution=request, workload_binding=workload(configuration()))
    assert torch.cuda.is_initialized() == initialized
