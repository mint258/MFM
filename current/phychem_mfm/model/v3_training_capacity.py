"""Training-owned bounded observations, distinct from A-only capacity proofs.

No monitor, scheduler, data authority or claimed parent C0 is implemented here.
The existing GPU supervisor/UUID lock and outer resource budgets remain final.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import os
import re
from pathlib import Path
import sys

import torch

from .v3_checkpoint_policy import (ROOT, FLAGS, canonical, require, file_reference, read_bound,
    verify_observed_sources, current_cuda_capacity, select_capacity, _parent_c0, _one_cli_value)

ROLES = ("TRAIN", "VAL", "TRAIN_UNSEEN_CONFORMATION")
RESOURCE_KEYS = {"gpu_observation", "peak_allocated_bytes", "peak_reserved_bytes", "process_rss_sum_bytes",
                 "foreign_gpu_risk_observed", "output_bytes"}
PROFILE_SCHEMA = "model_v3_closed_training_capacity_profiles_v1"
CONFIG_SCHEMA = "model_v3_training_capacity_configuration_v1"
SUMMARY_SCHEMA = "model_v3_training_capacity_summary_v1"


def _json(value):
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def training_implementation_sources():
    # Use the SAME mandatory graph actually saved/checked by the training CLI,
    # not the old A invocation's outside-package inventory or import-order set.
    from ..phase1.v3_proxy_run import collect_sources
    for name, relative in (("phychem_mfm.phase1.v3_proxy_run", "current/phychem_mfm/phase1/v3_proxy_run.py"),
            ("phychem_mfm.phase1.v3_training_execution", "current/phychem_mfm/phase1/v3_training_execution.py"),
            ("phychem_mfm.model.v3_training_capacity", "current/phychem_mfm/model/v3_training_capacity.py"),
            ("phychem_mfm.model.v3_performance", "current/phychem_mfm/model/v3_performance.py"),
            ("phychem_mfm.model.v3_architecture", "current/phychem_mfm/model/v3_architecture.py")):
        module = sys.modules.get(name)
        if module is not None:
            actual = module.__dict__.get("__file__")
            require(type(actual) is str and Path(actual).is_absolute()
                    and Path(actual).resolve() == ROOT / relative, "Mixed training runtime module origin: " + name)
    result = collect_sources(ROOT)
    require("current/phychem_mfm/phase1/v3_training_execution.py" in result
            and "current/phychem_mfm/model/v3_training_capacity.py" in result
            and "tools/model_v3/run_proxy_experiment.py" in result, "Complete training source graph required")
    verify_observed_sources(result, result)
    return result


def optimizer_storage_inventory(optimizer):
    require(type(optimizer) is torch.optim.AdamW, "Only declared AdamW state has a bounded implementation here")
    parameters, count, parameter_bytes, missing, unknown = set(), 0, 0, 0, []
    materialized = 0
    for group_index, group in enumerate(optimizer.param_groups):
        for index, parameter in enumerate(group["params"]):
            require(id(parameter) not in parameters, "Duplicate optimizer parameter")
            parameters.add(id(parameter)); count += 1
            size = parameter.numel() * parameter.element_size(); parameter_bytes += size
            state = optimizer.state.get(parameter, {})
            expected = {"step", "exp_avg", "exp_avg_sq"} | ({"max_exp_avg_sq"} if group.get("amsgrad", False) else set())
            if not state:
                # Tensor storage bound only. It is NOT a universal workspace,
                # throughput or future allocator-peak certificate.
                missing += (3 if group.get("amsgrad", False) else 2) * size + 16
            elif set(state) != expected:
                unknown.append("group%d/parameter%d:unexpected_state_keys" % (group_index, index))
            else:
                valid = True
                for key in expected - {"step"}:
                    slot = state[key]
                    valid &= isinstance(slot, torch.Tensor) and slot.shape == parameter.shape and slot.dtype == parameter.dtype
                step = state["step"]
                valid &= isinstance(step, torch.Tensor) and step.numel() == 1
                if valid:materialized += 1
                else:unknown.append("group%d/parameter%d:unknown_state_layout" % (group_index, index))
    return {"optimizer_class": "torch.optim.AdamW", "parameter_count": count, "parameter_bytes": parameter_bytes,
        "materialized_parameter_count": materialized, "unmaterialized_state_storage_upper_bound_bytes": missing,
        "unknown_state": unknown, "bound_scope": "AdamW_tensor_storage_not_universal_workspace_or_peak"}


class TrainingCapacityObserver:
    """Snapshot the MAIN forward before a probe overwrites its last receipt.

    Rows go immediately to an explicit sink; only finite aggregate metadata is
    retained. CPU engineering observations never qualify CUDA selection.
    """
    def __init__(self, workload, requested, resolved_options, sources):
        self.workload, self.requested = _json(workload), _json(requested)
        self.options, self.sources = _json(resolved_options), dict(sources)
        self.contract = None
        self.capacity_selection = None
        self._sink = None
        self._captures = self._completed = self._bytes = 0
        self._device = None
        self._environment = None
        self._roles = {role: {"batches": 0, "graphs": 0, "atoms": 0, "max_nodes": 0, "padded_cost": 0,
                              "executed_dense_shapes": set()} for role in ROLES}
        self._validation = {}
        self._active_validation = {}
        self._peak = self._future_storage = 0
        self._all_cuda = True
        self._foreign = False
        self._inventory = None
        self._last_train_update = None

    def _check_runtime_model(self, full_model):
        require(self.contract is not None and full_model.training_execution_contract == self.contract,
                "Observed model execution contract changed")
        require(all(parameter.dtype == torch.float32 for parameter in full_model.parameters()),
                "Live execution changed fp32 master parameter dtype")
        expected = self.contract["execution_state"]
        for path, options in expected["performance_options"].items():
            require(full_model.get_submodule(path).v3_performance_options == options,
                    "Live performance options changed")
        for path, flags in expected["resolved_checkpoint_flags"].items():
            module = full_model.get_submodule(path)
            require(all(type(getattr(module, key, None)) is bool and getattr(module, key) == value
                        for key, value in flags.items()), "Live checkpoint flags changed")
        for path, semantic in expected.get("performance_integration", {}).items():
            require(full_model.get_submodule(path).performance_execution_contract == semantic,
                    "Live packing execution changed")
        require(torch.get_float32_matmul_precision() == expected["float32_matmul_precision"]
                and bool(torch.backends.cuda.matmul.allow_tf32) == expected["matmul_tf32"]
                and bool(torch.backends.cudnn.allow_tf32) == expected["cudnn_tf32"]
                and torch.are_deterministic_algorithms_enabled() == expected["deterministic_algorithms"],
                "Live numeric runtime controls changed")

    @contextmanager
    def forward_context(self, full_model, *, role):
        require(role in ROLES, "Unknown actual forward role")
        self._check_runtime_model(full_model)
        guard = getattr(full_model.encoder.backbone, "capacity_guard", None)
        if guard is None:
            yield
            return
        previous = guard.active_role
        guard.active_role = role
        try:
            yield
        finally:
            guard.active_role = previous

    def bind_contract(self, contract):
        require(self.contract is None, "Observer contract is bound once")
        self.contract = _json(contract)

    def set_sink(self, sink):
        require(self._sink is None and callable(sink), "One explicit streaming capacity sink required")
        self._sink = sink

    def capture_forward(self, full_model, *, role):
        require(role in ROLES and self.contract is not None, "Bound completed-forward role required")
        self._check_runtime_model(full_model)
        value = getattr(full_model.encoder.backbone, "last_logical_batch_execution", None)
        require(type(value) is dict, "The actual encoder did not produce its logical batch observation")
        value = _json(value)
        counts = value["graph_atom_counts"]
        require(counts and all(type(n) is int and n > 0 for n in counts)
                and value["logical_graph_count"] == len(counts) and value["logical_atom_count"] == sum(counts)
                and value["original_atom_and_graph_order_restored"] is True
                and value["views_noise_masks_targets_regenerated"] is False
                and value["loss_or_group_reduction_per_chunk"] is False, "Actual logical forward identity differs")
        groups = value.get("chunk_graphs", [list(range(len(counts)))])
        require(sorted(g for group in groups for g in group) == list(range(len(counts))), "Actual chunk graph membership differs")
        shapes = [[len(group), max(counts[g] for g in group)] for group in groups]
        if "executed_dense_shapes" in value:
            require(shapes == value["executed_dense_shapes"], "Declared chunk shapes differ from actual plan")
        self._captures += 1
        device = next(full_model.parameters()).device.type
        require(self._device is None or self._device == device, "Observed model device changed")
        if self._device is None and device == "cuda":
            self._environment = current_cuda_capacity()
        self._device = device
        return {"schema": "model_v3_training_capacity_step_v1", "capture_id": self._captures,
            "role": role, "device_type": device, "logical_batch": value, "executed_dense_shapes": shapes}

    def begin_validation(self, role, *, batch_count, population_binding):
        require(role in ROLES[1:] and role not in self._active_validation and type(batch_count) is int
                and batch_count > 0, "Explicit provider validation population/count required")
        expected = self.workload["data"].get("validation_population_bindings", {})
        require(role in expected and _json(population_binding) == expected[role],
                "Validation population differs from the validated input binding")
        self._active_validation[role] = (self._roles[role]["batches"], batch_count, canonical(population_binding))

    def complete_validation(self, role):
        require(role in self._active_validation, "Validation was not registered")
        start, count, digest = self._active_validation[role]
        require(self._roles[role]["batches"] - start == count, "Capacity validation did not complete its exact population")
        self._active_validation.pop(role)
        self._validation[role] = {"batches": count, "population_sha256": digest}

    def record_completed(self, snapshot, *, optimizer, optimizer_updates, samples_consumed, resources):
        row = _json(snapshot)
        require(row["capture_id"] == self._completed + 1 and row["capture_id"] <= self._captures,
                "Capacity snapshots must commit once in capture order")
        require(type(optimizer_updates) is int and optimizer_updates >= 0 and type(samples_consumed) is int
                and samples_consumed >= 0 and type(resources) is dict and RESOURCE_KEYS <= set(resources),
                "Actual committed clock and complete resource observation required")
        for key in RESOURCE_KEYS - {"gpu_observation", "foreign_gpu_risk_observed"}:
            require(type(resources[key]) is int and resources[key] >= 0, "Unknown observed resource is not zero: " + key)
        require(type(resources["foreign_gpu_risk_observed"]) is bool, "Actual foreign-process result required")
        inventory = optimizer_storage_inventory(optimizer)
        row.update(optimizer_updates=optimizer_updates, samples_consumed=samples_consumed,
                   resources=_json(resources), optimizer_inventory=inventory)
        if row["role"] == "TRAIN":
            require(self._last_train_update is None or optimizer_updates in
                    (self._last_train_update, self._last_train_update + 1), "Training capacity optimizer clock skipped")
            self._last_train_update = optimizer_updates
        gpu = resources["gpu_observation"]
        self._all_cuda &= row["device_type"] == "cuda" and gpu is not None
        self._foreign |= resources["foreign_gpu_risk_observed"]
        if gpu is not None:
            processes = gpu["compute_processes"]
            require(all(type(p["used_memory_bytes"]) is int and p["used_memory_bytes"] >= 0 for p in processes),
                    "Unknown GPU process memory is not zero")
            self._peak = max(self._peak, sum(p["used_memory_bytes"] for p in processes if p["own"]),
                             resources["peak_allocated_bytes"], resources["peak_reserved_bytes"])
        self._future_storage = max(self._future_storage, inventory["unmaterialized_state_storage_upper_bound_bytes"])
        self._inventory = inventory
        counts = row["logical_batch"]["graph_atom_counts"]
        aggregate = self._roles[row["role"]]
        for key, value in (("graphs", len(counts)), ("atoms", sum(counts)), ("max_nodes", max(counts)),
                           ("padded_cost", len(counts) * max(counts) ** 2)):
            aggregate[key] = max(aggregate[key], value)
        aggregate["batches"] += 1
        aggregate["executed_dense_shapes"].update(tuple(s) for s in row["executed_dense_shapes"])
        require(len(aggregate["executed_dense_shapes"]) <= 8192, "Finite observed shape inventory exceeded")
        encoded = json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        require(len(encoded) <= 1 << 20 and self._bytes + len(encoded) + 1 <= 16 << 20,
                "Capacity journal exceeded original bounded metadata allowance")
        if self._sink is not None:self._sink(deepcopy(row))
        self._bytes += len(encoded) + 1
        self._completed += 1
        return deepcopy(row)

    def summary(self):
        require(self.contract is not None and self._completed == self._captures and not self._active_validation,
                "Incomplete forward/validation observations cannot be finalized")
        roles = deepcopy(self._roles)
        for value in roles.values():value["executed_dense_shapes"] = [list(s) for s in sorted(value["executed_dense_shapes"])]
        return {"schema": SUMMARY_SCHEMA, "status": "OBSERVED_TRAINING_CAPACITY_PENDING_ACTUAL_OUTER_C0",
            "execution_contract_sha256": canonical(self.contract), "workload_sha256": canonical(self.workload),
            "rows": self._completed, "roles": roles, "completed_validation": deepcopy(self._validation),
            "all_observations_cuda": self._all_cuda and self._completed > 0,
            "foreign_gpu_risk_observed": self._foreign, "observed_peak_bytes": self._peak,
            "future_state_storage_allowance_bytes": self._future_storage, "optimizer_inventory": deepcopy(self._inventory),
            "sampled_capacity_not_universal_workspace_or_future_bound": True, "scientific_acceptance": False}

    def configuration(self, *, request_reference):
        require(self.contract is not None and os.environ.get("SLURM_JOB_ID"), "Real job/contract required for observation producer")
        request = read_bound(request_reference)
        require(request["sources"]["runtime_files"] == self.sources, "Actual training request source graph differs")
        declared = read_bound(request["configuration"])
        from ..phase1.v3_training_execution import TrainingExecutionSpec
        require(declared["model"] == self.workload["model_configuration"] and declared["seed"] == self.workload["seed"]
                and TrainingExecutionSpec(**declared["training_execution"]).semantic() == self.requested,
                "Actual request/model/policy differs from observation")
        from ..phase1.v3_proxy_run import validate_training_workload_request
        validate_training_workload_request(self.workload, request, declared)
        environment = deepcopy(self._environment)
        require(self._device != "cuda" or environment is not None, "Missing actual first-forward GPU frame")
        return {"schema": CONFIG_SCHEMA, "job_id": os.environ["SLURM_JOB_ID"], "request": request_reference,
            "workload": deepcopy(self.workload), "requested_execution": deepcopy(self.requested),
            "training_contract": deepcopy(self.contract), "source_sha256": dict(self.sources), "gpu_environment": environment,
            "capacity_selection": deepcopy(self.capacity_selection),
            "invocation": {"source_root": str(ROOT), "cwd": str(Path.cwd().resolve()),
                           "logical_python": str(Path(sys.executable).absolute()), "argv": list(sys.argv)}}


def _qualify_invocation(config, supervisor, output, sources, request):
    frame = config["invocation"]
    require(frame["source_root"] == str(ROOT) and Path(frame["cwd"]).resolve() == ROOT,
            "Training capacity must come from the actual single runtime root")
    command = supervisor["command"]
    require(command and command[0] == frame["logical_python"], "Actual interpreter differs")
    index, seen = 1, set()
    while index < len(command) and command[index] in ("-u", "-B"):
        require(command[index] not in seen, "Repeated Python flag")
        seen.add(command[index]); index += 1
    require(command[index:] == frame["argv"] and index < len(command), "Supervisor argv differs from actual training invocation")
    script = Path(command[index])
    script = script if script.is_absolute() else Path(frame["cwd"]) / script
    relative = "tools/model_v3/run_wsd_fork.py" if "fork" in request else "tools/model_v3/run_proxy_experiment.py"
    entry = ROOT / relative
    require(script.resolve() == entry and file_reference(entry, 2 << 20)["sha256"] == sources[entry.relative_to(ROOT).as_posix()],
            "Capacity observation did not execute the original training entry")
    arguments = command[index + 1:]
    require(arguments and arguments[0] == "run", "Actual training run subcommand required")
    request = config["request"]
    def actual_path(value):
        path = Path(value)
        return (path if path.is_absolute() else Path(frame["cwd"]) / path).resolve()
    require(actual_path(_one_cli_value(arguments, "--request", required=True)) == Path(request["path"])
            and _one_cli_value(arguments, "--request-sha256", required=True) == request["sha256"]
            and actual_path(_one_cli_value(arguments, "--output", required=True)) == output,
            "Actual training request/output invocation differs")
    launch = supervisor["launch_identity"]
    require(launch["status"] == "ACTIVE" and launch["argv"] == command and launch["argv_sha256"] == hashlib.sha256(
            b"\0".join(arg.encode("utf-8", "surrogateescape") for arg in command) + b"\0").hexdigest()
            and launch["uid"] == os.getuid() and type(launch["pid"]) is int and launch["pid"] > 0
            and launch["pid"] == supervisor["child_pid"] == launch["pgid"] == launch["sid"]
            and type(launch["start_ticks"]) is int and launch["start_ticks"] > 0
            and re.fullmatch(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", launch["boot_id"])
            and str(launch["slurm_job_id"]) == str(config["job_id"])
            and launch["cgroup"] == supervisor["supervisor_slurm_cgroup"] and bool(launch["cgroup"])
            and supervisor["gpu_uuid"] == config["gpu_environment"]["uuid"],
            "Recorded kernel training launch identity differs")
    require(supervisor["supervisor_source_sha256"] == sources["tools/model_v3/run_supervised.py"],
            "Actual supervisor source differs from the tested runtime guard")


def load_closed_training_observation(item, requested, workload, options, sources):
    require(set(item) == {"configuration", "summary", "run_status", "supervisor", "parent_sacct", "steps"},
            "Unknown training capacity profile rawref members")
    config, summary = read_bound(item["configuration"]), read_bound(item["summary"])
    status, sup = read_bound(item["run_status"]), read_bound(item["supervisor"])
    require(config["schema"] == CONFIG_SCHEMA and summary["schema"] == SUMMARY_SCHEMA,
            "A-only/unknown capacity evidence cannot qualify training")
    job = str(config["job_id"])
    _parent_c0(read_bound(item["parent_sacct"]), job)
    require(str(sup["job_id"]) == job and sup["status"] == "COMPLETED" and sup["exit_code"] == 0
            and sup["first_failure"] is None and sup["remaining_recorded_processes_before_retirement"] == []
            and sup["private_storage_cleanup_errors"] == [], "Actual GPU supervisor/private/process closure failed")
    actual_request = read_bound(config["request"])
    expected_status_schema = "model_v3_wsd_child_receipt_v1" if "fork" in actual_request else "model_v3_proxy_child_receipt_v1"
    require(status["schema"] == expected_status_schema and str(status["job_id"]) == job
            and status["status"] == "CHILD_FINISHED_PENDING_ROOT_CLOSURE" and status["first_failure"] is None
            and status["cleanup_errors"] == [] and status["committed_cursors"]["pending_log"] is False,
            "Actual training child/SDK/provider closure failed")
    require(config["source_sha256"] == sources, "Training implementation graph changed")
    verify_observed_sources(config["source_sha256"], sources)
    require(actual_request["sources"]["runtime_files"] == sources, "Saved actual request did not bind this runtime")
    declared = read_bound(actual_request["configuration"])
    from ..phase1.v3_training_execution import TrainingExecutionSpec
    require(config["workload"] == workload and declared["model"] == workload["model_configuration"]
            and declared["seed"] == workload["seed"] and TrainingExecutionSpec(**declared["training_execution"]).semantic() == config["requested_execution"],
            "Training model/seed/input/heads/views/workload or actual policy changed")
    from ..phase1.v3_proxy_run import validate_training_workload_request
    validate_training_workload_request(workload, actual_request, declared)
    from ..phase1.v3_training_execution import validate_training_execution_contract
    contract = validate_training_execution_contract(config["training_contract"])
    require(contract["workload_sha256"] == canonical(workload)
            and summary["execution_contract_sha256"] == canonical(contract)
            and summary["workload_sha256"] == canonical(workload), "Training capacity execution contract differs")
    observed = config["requested_execution"]
    require(observed["resident_models"] == requested.resident_models == 1
            and observed["padding"] == requested.padding and observed["geometry_scope"] == requested.geometry_scope
            and observed["batch_padded_cost"] >= requested.batch_padded_cost, "R1 training scope/packing/budget differs")
    physical = contract["resolved_options"]
    require(all(physical[key] == value for key, value in asdict(options).items() if key not in FLAGS),
            "Training capacity changed a non-checkpoint execution option")
    require(all(type(physical[key]) is bool for key in FLAGS), "Three actual checkpoint booleans required")
    output = Path(item["configuration"]["path"]).parent
    require(all(Path(item[key]["path"]).parent == output for key in ("summary", "run_status", "steps")),
            "Training profile child files must share one actual output")
    require(("fork" in actual_request) == ("wsd_fork" in declared), "WSD request/config/entry role differs")
    artifacts = status["training_execution_capacity_artifacts"]
    require(set(artifacts) == {"configuration", "summary", "steps"} and all(artifacts[key] == item[key]
            for key in artifacts), "Actual child did not bind these exact capacity artifacts")
    _qualify_invocation(config, sup, output, sources, actual_request)
    require(summary["status"] == "OBSERVED_TRAINING_CAPACITY_PENDING_ACTUAL_OUTER_C0"
            and summary["all_observations_cuda"] is True and summary["foreign_gpu_risk_observed"] is False,
            "CPU engineering/foreign/incomplete observations cannot qualify CUDA capacity")
    environment = config["gpu_environment"]
    require(type(environment) is dict and environment["total_bytes"] > 0, "Actual training CUDA environment required")
    journal = item["steps"]
    require(file_reference(journal["path"], 16 << 20) == journal, "Training capacity journal changed")
    roles = {role: {"batches": 0, "graphs": 0, "atoms": 0, "max_nodes": 0, "padded_cost": 0,
                    "executed_dense_shapes": set()} for role in ROLES}
    rows, peak, future, last_train, inventory = 0, 0, 0, None, None
    with Path(journal["path"]).open() as stream:
        for line in stream:
            require(len(line) <= 1 << 20, "Oversized capacity journal row")
            row = json.loads(line); rows += 1
            require(row["schema"] == "model_v3_training_capacity_step_v1" and row["capture_id"] == rows
                    and row["role"] in ROLES and row["device_type"] == "cuda", "Incomplete/unknown training journal row")
            resource = row["resources"]
            require(RESOURCE_KEYS <= set(resource) and resource["foreign_gpu_risk_observed"] is False,
                    "Missing resource or foreign process in capacity observation")
            gpu = resource["gpu_observation"]
            require(gpu["uuid"] == environment["uuid"] and gpu["total_bytes"] == environment["total_bytes"],
                    "Physical GPU changed during training measurement")
            require(all(type(p["used_memory_bytes"]) is int and p["used_memory_bytes"] >= 0
                        for p in gpu["compute_processes"]), "Unknown GPU memory is not zero")
            require(all(type(resource[key]) is int and resource[key] >= 0
                        for key in RESOURCE_KEYS - {"gpu_observation", "foreign_gpu_risk_observed"}), "Unknown actual resource count")
            peak = max(peak, sum(p["used_memory_bytes"] for p in gpu["compute_processes"] if p["own"]),
                       resource["peak_allocated_bytes"], resource["peak_reserved_bytes"])
            logical = row["logical_batch"]; counts = logical["graph_atom_counts"]
            require(counts and all(type(n) is int and n > 0 for n in counts)
                    and logical["logical_graph_count"] == len(counts) and logical["logical_atom_count"] == sum(counts)
                    and logical["original_atom_and_graph_order_restored"] is True
                    and logical["views_noise_masks_targets_regenerated"] is False
                    and logical["loss_or_group_reduction_per_chunk"] is False, "Training logical population changed")
            groups = logical.get("chunk_graphs", [list(range(len(counts)))])
            require(sorted(g for group in groups for g in group) == list(range(len(counts)))
                    and row["executed_dense_shapes"] == [[len(g), max(counts[i] for i in g)] for g in groups],
                    "Actual compiled/chunk shape inventory differs")
            target = roles[row["role"]]; target["batches"] += 1
            for key, value in (("graphs", len(counts)), ("atoms", sum(counts)), ("max_nodes", max(counts)),
                               ("padded_cost", len(counts) * max(counts) ** 2)):
                target[key] = max(target[key], value)
            target["executed_dense_shapes"].update(tuple(s) for s in row["executed_dense_shapes"])
            if row["role"] == "TRAIN":
                require(type(row["optimizer_updates"]) is int and row["optimizer_updates"] >= 0
                        and (last_train is None or row["optimizer_updates"] in (last_train, last_train + 1)),
                        "Observed training optimizer clock skipped")
                last_train = row["optimizer_updates"]
            inventory = row["optimizer_inventory"]
            require(inventory["optimizer_class"] == "torch.optim.AdamW" and inventory["unknown_state"] == []
                    and type(inventory["unmaterialized_state_storage_upper_bound_bytes"]) is int
                    and inventory["unmaterialized_state_storage_upper_bound_bytes"] >= 0,
                    "Unknown future optimizer state cannot become zero")
            future = max(future, inventory["unmaterialized_state_storage_upper_bound_bytes"])
    for value in roles.values():value["executed_dense_shapes"] = [list(s) for s in sorted(value["executed_dense_shapes"])]
    require(rows > 0 and rows == summary["rows"] and roles == summary["roles"]
            and peak == summary["observed_peak_bytes"] and future == summary["future_state_storage_allowance_bytes"]
            and inventory == summary["optimizer_inventory"], "Training summary does not match the full bounded journal")
    require(last_train == status["committed_cursors"]["optimizer_updates"], "Final capacity clock differs from child committed cursor")
    require(roles["TRAIN"]["batches"] > 0 and last_train is not None and last_train > 0
            and inventory["materialized_parameter_count"] > 0, "Real completed AdamW training update required")
    populations = workload["data"].get("validation_population_bindings", {})
    for role in ROLES[1:]:
        value = summary["completed_validation"][role]
        require(value["batches"] > 0 and value["batches"] <= roles[role]["batches"]
                and value["population_sha256"] == canonical(populations[role]),
                "Both actual bound validation populations must complete")
    require(0 < peak + future <= .85 * environment["total_bytes"], "Measured training plus known state storage exceeds85%")
    limits = {key: max(roles[r][key] for r in ROLES) for key in ("graphs", "atoms", "max_nodes", "padded_cost")}
    shapes = sorted({tuple(s) for value in roles.values() for s in value["executed_dense_shapes"]})
    return {"gpu_uuid": environment["uuid"], "gpu_name": environment["name"], "total_bytes": environment["total_bytes"],
        "torch_total_bytes": environment["torch_total_bytes"], "torch_version": environment["torch_version"],
        "cuda_version": environment["cuda_version"], "driver_version": environment["driver_version"],
        "cudnn_version": environment["cudnn_version"], "runtime_controls": environment["runtime_controls"],
        "flags": {key: physical[key] for key in FLAGS}, "peak_bytes": peak + future,
        "observed_size_limits": limits, "role_size_limits": roles, "observed_dense_shapes": shapes,
        "compile_backbone": physical["compile_backbone"], "source": item,
        "sampled_capacity_not_universal_bound": True}


class TrainingCapacityGuard:
    def __init__(self, observation):
        self.observation = observation
        self.active_role = None

    def check(self, data, counts):
        require(data.x.device.type == "cuda", "Actual CUDA training capacity required")
        actual = {"graphs": len(counts), "atoms": sum(counts), "max_nodes": max(counts),
                  "padded_cost": len(counts) * max(counts) ** 2}
        require(self.active_role in ROLES, "Actual role context required before profiled training forward")
        limits = self.observation["role_size_limits"][self.active_role]
        require(all(actual[key] <= limits[key] for key in actual),
                "Training batch exceeds measured capacity; no re-batching/OOM fallback")
        if self.observation["compile_backbone"]:
            require((len(counts), max(counts)) in {tuple(s) for s in limits["executed_dense_shapes"]},
                    "Unobserved compiled training shape refused")


def resolve_training_capacity(spec, configuration, workload, options, sources, admission, *, existing_model=False):
    if spec.checkpoint_policy == "manual":
        require(admission is None, "Manual training must not silently use an automatic capacity profile")
        return options, None, None
    adopted = spec.checkpoint_policy == "auto_adopted_A_v1"
    if adopted:
        from .v3_adopted_checkpoint_policy import (CONSERVATIVE_FLAGS, adopted_capacity_records,
            conservative_selection)
        require(options.backbone_checkpointing is None and options.distance_checkpointing and options.head_checkpointing,
                "Automatic training policy cannot override explicit checkpoint flags")
        conservative = replace(options, **CONSERVATIVE_FLAGS)
        if admission is None:
            return conservative, None, conservative_selection("NO_MATCHED_CAPACITY_KEEP_OLD_CHECKPOINTS")
    require(type(admission) is dict and set(admission) == {"schema", "capacity_profile"}
            and admission["schema"] == "model_v3_training_execution_admission_v1",
            "Actual operational training capacity admission required")
    require(options.backbone_checkpointing is None and options.distance_checkpointing and options.head_checkpointing,
            "Automatic training policy cannot override explicit checkpoint flags")
    try:
        profile = read_bound(admission["capacity_profile"])
        require(set(profile) == {"schema", "observations"} and profile["schema"] == PROFILE_SCHEMA
                and type(profile["observations"]) is list and 0 < len(profile["observations"]) <= 32,
                "Unknown/empty/oversized closed training capacity profile")
        records = [load_closed_training_observation(item, spec, workload, options, sources) for item in profile["observations"]]
    except (ValueError, KeyError, TypeError, OSError):
        if not adopted:
            raise
        return conservative, None, conservative_selection("CAPACITY_EVIDENCE_UNAVAILABLE_KEEP_OLD_CHECKPOINTS", admission=_json(admission))
    # Actual physical GPU/foreign-process checks are deliberately outside the
    # metadata fallback handler. They remain hard resource protections.
    environment = current_cuda_capacity()
    if adopted:
        records = adopted_capacity_records(records, environment["name"])
    if existing_model:
        # WSD rebind allocates NO second model or optimizer. Remove the actual
        # already-resident owned process from the hypothetical preallocation
        # free-space frame, then separately enforce its actual live85%/reserve.
        # This never changes the observed R1 residency or borrows a parent scope.
        own = 0
        for line in environment["process_stdout"].splitlines():
            cells = [part.strip() for part in line.split(",")]
            require(len(cells) >= 3, "Actual owned GPU process memory required for no-allocation rebind")
            if cells[0] == environment["uuid"]:
                require(int(cells[1]) == os.getpid(), "Foreign process in no-allocation rebind")
                memory = float(cells[2])
                require(memory >= 0 and memory < float("inf"), "Unknown owned GPU memory is not zero")
                own += int(memory * 1024 ** 2)
        require(0 < own <= environment["total_bytes"] and environment["free_bytes"] >= .1 * environment["total_bytes"]
                and environment["total_bytes"] - environment["free_bytes"] <= .85 * environment["total_bytes"],
                "Existing owned model/context is outside the original live85%/reserve")
        virtual = dict(environment, free_bytes=min(environment["total_bytes"], environment["free_bytes"] + own))
        selected = select_capacity(records, virtual)
    else:
        selected = select_capacity(records, environment)
    if adopted and selected is None:
        return conservative, None, conservative_selection("NO_SAFE_MATCHED_ADOPTED_A_PROFILE_KEEP_OLD_CHECKPOINTS", admission=_json(admission))
    require(selected is not None, "No closed same-seed/source/GPU/training-workload capacity observation")
    guard = TrainingCapacityGuard(selected)
    guard.capacity_selection = {"admission": _json(admission), "environment": _json(environment),
        "observed_source": deepcopy(selected["source"]), "existing_model_no_allocation": existing_model}
    return replace(options, **selected["flags"]), guard, _json(admission)
