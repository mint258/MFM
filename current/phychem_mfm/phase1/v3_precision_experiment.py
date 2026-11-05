"""Opt-in four-member precision protocol; no physical D5 format is inferred.

The original trainer remains unchanged. Synthetic members test the execution
and recovery protocol only. Scientific acceptance also needs externally
verified D5 authority and terminal Slurm/SDK evidence for every segment.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import random

import numpy as np
import torch

from .v3_contract import canonical_hash, require
from .v3_trainer import V3StepTrainer
from .v3_training import ValidationAccumulator, _check_output_path, _file_sha
from ..model.v3_performance import PerformanceOptions, execution_context
from ..training.v3_performance_acceptance import bf16_curve_report

ROLES = ("VAL", "TRAIN_UNSEEN_CONFORMATION")
B_VALIDATION_AUTHORITY = "proxy_TRAIN_only_molecular_inner_split_frozen_before_first_run"
B_POPULATION_AUTHORITY = "data_line_D5_nested_240000_TRAIN_molecules_all_allowed_conformations_PM7"
PREREGISTERED_PLAN = Path(__file__).absolute().parents[2] / "configs/model_v3/performance/b_proxy_plan_v1.json"


def production_protocol():
    protocol = json.loads(PREREGISTERED_PLAN.read_text())
    validation = protocol["validation"]
    require(protocol["population"]["authority"] == B_POPULATION_AUTHORITY
            and validation["authority"] == B_VALIDATION_AUTHORITY
            and protocol["pretraining_seeds"] == [0, 1] and protocol["updates_per_run"] == 20000
            and protocol["same_gpu_environment_for_all_four_runs"] is True
            and protocol["precision_only_difference"] is True and validation["outer_final_population_read"] is False
            and (validation["update_start"], validation["update_interval"], validation["update_end_inclusive"],
                 validation["noise_seed"], validation["epoch"]) == (0, 500, 20000, 0, 0),
            "Published B protocol differs; review a new protocol explicitly")
    return protocol


def validate_role_sources(sources, populations, *, production):
    require(set(sources) == set(populations) == set(ROLES), "Explicit source and purpose required for each validation role")
    gate_roles = []
    for role, source in sources.items():
        require(source.get("population_binding_sha256") == populations[role] and bool(source.get("authority")),
                "Validation role source binding differs")
        purpose = source.get("purpose")
        require(purpose in (("B_NUMERIC_GATE", "DIAGNOSTIC_ONLY") if production
                            else ("SYNTHETIC_HARNESS_GATE", "DIAGNOSTIC_ONLY")), "Explicit admitted validation purpose required")
        if purpose != "DIAGNOSTIC_ONLY":
            if production:
                require(source["authority"] == B_VALIDATION_AUTHORITY,
                        "B gate requires the preregistered proxy TRAIN-only molecular inner authority")
            gate_roles.append(role)
    require(gate_roles, "No validation role is admitted to the B numeric gate")
    return tuple(sorted(gate_roles))


def write_new_json(path, value):
    import os
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())


def file_binding(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), "Ordinary pinned protocol file required")
    return {"path": str(path), "sha256": _file_sha(path), "bytes": path.stat().st_size}


def read_bound(reference):
    require(file_binding(reference["path"]) == reference, "Precision protocol bytes differ")
    raw = Path(reference["path"]).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == reference["sha256"] and len(raw) == reference["bytes"],
            "Precision protocol bytes changed during read")
    return json.loads(raw)


@dataclass(frozen=True)
class PrecisionPlan:
    input_kind: str
    updates: int = 20000
    validation_updates: tuple = tuple(range(0, 20001, 500))
    checkpoint_updates: tuple = (10000, 20000)
    max_batch_samples: int = 512
    sample_budget: int = 10240000
    validation_seed: int = 0

    def __post_init__(self):
        require(self.input_kind in ("authoritative_proxy", "synthetic"), "Explicit precision input kind required")
        require(type(self.updates) is int and self.updates > 0
                and (self.input_kind == "synthetic" or self.updates == 20000),
                "Real B members require exactly20000 optimizer updates")
        for name in ("validation_updates", "checkpoint_updates"):
            values = getattr(self, name)
            require(type(values) is tuple and values == tuple(sorted(set(values))) and values
                    and all(type(v) is int and 0 <= v <= self.updates for v in values)
                    and values[-1] == self.updates, "Fixed ordered grid including endpoint required: " + name)
        require(self.validation_updates[0] == 0, "Precision validation includes the untrained update0 point")
        require(type(self.max_batch_samples) is int and 0 < self.max_batch_samples <= 512
                and type(self.sample_budget) is int and self.sample_budget >= self.updates
                and type(self.validation_seed) is int and self.validation_seed >= 0, "Bounded precision sample plan required")
        if self.input_kind == "authoritative_proxy":
            protocol = production_protocol()
            validation = protocol["validation"]
            require(self.validation_updates == tuple(range(validation["update_start"], validation["update_end_inclusive"] + 1,
                                                           validation["update_interval"]))
                    and self.validation_seed == validation["noise_seed"], "Production validation must match the published B grid/noise seed")

    @property
    def sha256(self):
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class PrecisionInputs:
    """Model-side objects supplied by a separately pinned authority adapter.

    authority_receipt is opaque data-line evidence, not a replacement D5 schema.
    The adapter verifies the actual D5 and TRAIN-only/two-validation contracts.
    """
    index: object
    provider: object
    registry: object
    structural_binding: object
    normalizations: dict
    model_configuration: dict
    authority_receipt: dict
    validation_population_bindings: dict
    validation_role_sources: dict
    verified_request_sha256: str = ""


def bind_authoritative_inputs(adapter, request):
    hook = getattr(adapter, "verify_and_bind_model_v3_precision_inputs", None)
    require(callable(hook), "Awaiting authoritative D5 adapter and TRAIN/two-validation interfaces; old S prefixes are not a proxy")
    production_protocol()
    request = {**deepcopy(request), "required_population": {"authority": B_POPULATION_AUTHORITY,
        "molecule_count": 240000, "index_unit": "molecule", "role": "TRAIN", "geometry_source": "PM7",
        "allowed_conformations": "all_authoritatively_allowed", "sampling": "uniform_molecule_then_uniform_allowed_conformation",
        "old_record_prefix_substitute_allowed": False},
        "required_B_validation": {"authority": B_VALIDATION_AUTHORITY, "noise_seed": 0, "epoch": 0,
            "updates": list(range(0, 20001, 500)), "outer_final_population_read": False},
        "required_verification": {"same_gpu_environment_for_all_four_runs": True, "source_binding_required": True,
                                  "receipt_proves_actual_D5_PM7_all_allowed_and_validation_origins": True}}
    bound = hook(deepcopy(request))
    require(isinstance(bound, PrecisionInputs), "Authority adapter must return explicit model-side PrecisionInputs")
    require(getattr(bound.index, "authority", None) == "data_line"
            and getattr(bound.index, "role", None) == "TRAIN",
            "Data-line-authoritative TRAIN molecule/conformer index required")
    require(len(bound.index) == 240000, "D5 proxy requires exactly240000 TRAIN molecules, not conformer/record rows")
    require(bound.authority_receipt and set(bound.validation_population_bindings) == set(ROLES),
            "Verified D5 authority and both complete validation population bindings required")
    json.dumps(bound.authority_receipt, allow_nan=False)
    require(all(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
                for value in bound.validation_population_bindings.values()), "Pinned validation population hashes required")
    validate_role_sources(bound.validation_role_sources, bound.validation_population_bindings, production=True)
    require(bound.verified_request_sha256 == canonical_hash(request),
            "Pinned authority hook must bind its opaque verification receipt to this exact model-owned request")
    return bound


class PrecisionValidationAccumulator(ValidationAccumulator):
    """Accumulate SSE directly; never derive RMSE from field-mean losses."""
    def result(self):
        result = super().result()
        for field in self.fields:
            row, item = self.rows[field.name], result["fields"][field.name]
            count, width = row["count"], field.target_width
            item.update(unit=field.unit, target_width=width, RMSE=None, vector_RMSE=None,
                        squared_error_sum=None, component_denominator=None)
            if field.kind not in ("binary", "classification") and count and row.get("prediction_available", True):
                item.update(squared_error_sum=row["squared"], component_denominator=count * width,
                            RMSE=math.sqrt(row["squared"] / (count * width)),
                            vector_RMSE=math.sqrt(row["squared"] / count))
                if field.kind == "denoise_eps_mse":
                    item.update(sigma=field.denoise_sigma,
                                eps_component_RMSE=item["RMSE"] / field.denoise_sigma,
                                loss_denominator="3*valid_atoms*sigma^2",
                                RMSE_definition="sqrt(raw_coordinate_SSE/(3*valid_atoms))")
        return result


def _hash_tensor(digest, name, value):
    if value is None:
        digest.update((name + ":None\n").encode()); return
    value = value.detach().cpu().contiguous()
    digest.update(canonical_hash({"name": name, "shape": list(value.shape), "dtype": str(value.dtype)}).encode())
    digest.update(value.numpy().tobytes())


class PrecisionStepTrainer(V3StepTrainer):
    """Original update path plus fixed-RNG, raw-unit S validation metrics."""
    def __init__(self, *args, validation_seed=0, **kwargs):
        super().__init__(*args, **kwargs)
        require(self.groups == ("S",), "B precision comparison currently admits S-only training")
        self.validation_seed = validation_seed

    def _validate_population(self, role, batches):
        # Called inside original validate's RNG/provider preservation scopes.
        from dataclasses import replace
        previous_config, previous_mode = self.view_config, self.model.training
        self.view_config = replace(self.view_config, seed=self.validation_seed, epoch=0)
        torch.manual_seed(self.validation_seed)
        np.random.seed(self.validation_seed % 2**32); random.seed(self.validation_seed)
        digest = hashlib.sha256()
        metric = PrecisionValidationAccumulator(self.model.registry, role=role, enabled_groups=self.groups,
                                                enabled_fields=self.fields)
        actual = 0
        try:
            if batches is None:
                count, iterator = self.provider.validation_batches(role=role, view_config=self.view_config,
                    enabled_groups=self.groups, enabled_fields=self.fields)
            else:
                require(type(batches) in (list, tuple), "Bounded explicit validation batches required")
                count, iterator = len(batches), iter(batches)
            require(type(count) is int and 0 < count <= self.validation_batch_cap, "Bounded full validation population required")
            with torch.no_grad():
                self.model.eval()
                for value in iterator:
                    require(actual < count, "Validation exceeded its declared population")
                    batch = self._prepared(value, role=role)
                    prediction, loss = self._forward_loss(batch)
                    predictions, targets = self._tables(prediction, batch)
                    metric.add(predictions, targets, loss)
                    digest.update(canonical_hash({"role": role, "choices": [asdict(c) for c in batch.choices]}).encode())
                    for name in ("x", "pos", "target_x", "target_pos", "sample_type_id", "element_corrupt_mask"):
                        _hash_tensor(digest, name, getattr(batch.views.batch, name, None))
                    for name in sorted(targets):
                        _hash_tensor(digest, name + ":target", targets[name].values)
                        _hash_tensor(digest, name + ":valid", targets[name].valid)
                        _hash_tensor(digest, name + ":pair_index", targets[name].pair_index)
                    bond = prediction.source_outputs.bond
                    for name in ("pair_index", "pair_graph_index", "existence_target", "order_target"):
                        _hash_tensor(digest, "bond:" + name, getattr(bond, name))
                    actual += 1
            require(actual == count, "Validation ended before its declared population")
            result = metric.result()
            result.update(input_population_sha256=digest.hexdigest(), batches=actual,
                          validation_seed=self.validation_seed, validation_epoch=0, precision_validation_schema="S_raw_metrics_v1",
                          optimizer_updates=self.clock.optimizer_updates)
            self.validation_state[role] = {"completed_runs": self.validation_state[role]["completed_runs"] + 1,
                                          "last_result": deepcopy(result)}
            self._log({"event": "VALIDATION", "samples_consumed": self.clock.samples_consumed,
                       "optimizer_updates": self.clock.optimizer_updates, **result})
            return result
        finally:
            self.view_config = previous_config
            self.model.train(previous_mode)


def curve_point(result, noise_field):
    numeric, population = {}, {}
    for name, row in result["fields"].items():
        require(row["valid_labels"] > 0, "Every S validation field needs observed labels")
        population[name] = {key: row.get(key) for key in ("valid_labels", "unit", "target_width", "sigma",
            "component_denominator", "RMSE_definition", "loss_denominator")}
        for metric in ("loss", "accuracy", "MAE", "R2", "RMSE", "vector_RMSE", "eps_component_RMSE"):
            value = row.get(metric)
            if value is not None:
                require(type(value) in (float, int) and math.isfinite(value), "Nonfinite S validation field")
                numeric[name + "/" + metric] = value
    require(noise_field + "/RMSE" in numeric, "Raw-coordinate denoising component RMSE required")
    return {"metrics": numeric, "population": population,
            "input_population_sha256": result["input_population_sha256"],
            "validation_noise_seed": result["validation_seed"], "validation_epoch": result["validation_epoch"]}


class PrecisionExperiment:
    """One precision/seed member, fixed update endpoint, fresh segment outputs."""
    def __init__(self, trainer, plan, *, seed, precision, comparison_binding):
        require(isinstance(trainer, PrecisionStepTrainer) and isinstance(plan, PrecisionPlan), "Bound precision trainer/plan required")
        require(seed in (0, 1) and type(seed) is int and precision in ("fp32", "bf16"), "The four preregistered members are fp32/bf16 x seed0/1")
        options = PerformanceOptions(**trainer.model.encoder.v3_performance_options)
        require(options.precision == precision and trainer.view_config.seed == seed
                and trainer.validation_seed == plan.validation_seed, "Precision/member/view seed differs")
        require(trainer.clock.sample_budget == plan.sample_budget and not trainer.clock.milestones,
                "B endpoint is optimizer updates; sample milestones must not silently split it")
        require(bool(comparison_binding) and type(comparison_binding) is dict, "Complete common comparison binding required")
        require(comparison_binding.get("plan_sha256") == plan.sha256, "Comparison plan binding differs")
        if plan.input_kind == "authoritative_proxy":
            require(getattr(trainer.sampler.index, "authority", None) == "data_line"
                    and comparison_binding.get("authority_receipt_sha256")
                    and set(comparison_binding.get("validation_population_bindings", {})) == set(ROLES),
                    "Authoritative D5 TRAIN/two-validation bindings required before real precision training")
            require(len(trainer.sampler.index) == 240000 and comparison_binding.get("verified_authority_request_sha256"),
                    "Verified240000-molecule proxy request required")
            backbone = trainer.model.encoder.config_dict()["backbone_config"]
            require((backbone["dim"], backbone["layers"]) == (512, 6), "Real B primary architecture must be512x6")
        validate_role_sources(comparison_binding["validation_role_sources"], comparison_binding["validation_population_bindings"],
                              production=plan.input_kind == "authoritative_proxy")
        self.trainer, self.plan, self.seed, self.precision, self.options = trainer, plan, seed, precision, options
        self.comparison_binding = deepcopy(comparison_binding)
        self.contract = {"plan": asdict(plan), "plan_sha256": plan.sha256, "seed": seed, "precision": precision,
            "comparison_binding": self.comparison_binding, "trainer_bindings": trainer.bindings,
            "validation_seed": plan.validation_seed, "controller_source_sha256": _file_sha(Path(__file__))}
        self.points, self.saved_updates, self.parent_checkpoint = {}, [], None

    def state_dict(self):
        return {"contract": deepcopy(self.contract), "points": deepcopy(self.points), "saved_updates": list(self.saved_updates),
                "optimizer_updates": self.trainer.clock.optimizer_updates,
                "samples_consumed": self.trainer.clock.samples_consumed,
                "log_cursor": self.trainer.log_cursor, "parent_checkpoint": self.parent_checkpoint}

    def save(self, directory, *, output_root):
        directory = _check_output_path(directory, output_root)
        directory.mkdir(mode=0o700, exist_ok=False)
        trainer_marker = self.trainer.save(directory / "trainer", output_root=directory)
        state = self.state_dict()
        state["saved_updates"] = sorted(set([*self.saved_updates, self.trainer.clock.optimizer_updates]))
        write_new_json(directory / "precision_state.json", state)
        complete = {"schema": "model_v3_precision_member_resume_v1", "state": file_binding(directory / "precision_state.json"),
                    "trainer_marker": file_binding(directory / "trainer/COMPLETE.json"),
                    "trainer_payload_sha256": trainer_marker["payload_sha256"], "contract_sha256": canonical_hash(self.contract)}
        write_new_json(directory / "PRECISION_COMPLETE.json", complete)
        self.saved_updates = state["saved_updates"]
        return complete

    def load(self, directory, *, output_root):
        directory = _check_output_path(directory, output_root)
        marker = json.loads((directory / "PRECISION_COMPLETE.json").read_text())
        require(marker["schema"] == "model_v3_precision_member_resume_v1"
                and marker["contract_sha256"] == canonical_hash(self.contract), "Precision member/config/source contract differs")
        require(Path(marker["state"]["path"]) == directory / "precision_state.json"
                and Path(marker["trainer_marker"]["path"]) == directory / "trainer/COMPLETE.json", "Precision checkpoint source path differs")
        state, trainer_marker = read_bound(marker["state"]), read_bound(marker["trainer_marker"])
        require(state["contract"] == json.loads(json.dumps(self.contract))
                and marker["trainer_payload_sha256"] == trainer_marker["payload_sha256"], "Precision checkpoint state binding differs")
        require(state["optimizer_updates"] <= self.plan.updates and state["saved_updates"] == sorted(set(state["saved_updates"]))
                and all(int(step) in self.plan.validation_updates and int(step) <= state["optimizer_updates"] for step in state["points"]),
                "Invalid precision checkpoint validation cursor")
        self.trainer.load(directory / "trainer", output_root=directory)
        require((state["optimizer_updates"], state["samples_consumed"], state["log_cursor"])
                == (self.trainer.clock.optimizer_updates, self.trainer.clock.samples_consumed, self.trainer.log_cursor),
                "Precision checkpoint optimizer/sample/history cursors differ")
        self.points, self.saved_updates = state["points"], state["saved_updates"]
        self.parent_checkpoint = file_binding(directory / "PRECISION_COMPLETE.json")

    def run(self, output_root, *, until_update=None, resource_guard=None):
        root = Path(output_root)
        target = self.plan.updates if until_update is None else until_update
        require(type(target) is int and self.trainer.clock.optimizer_updates <= target <= self.plan.updates,
                "Invalid explicit optimizer-update segment endpoint")
        require(root.is_dir() and not root.is_symlink(), "Owned fresh precision segment root required")
        def complete_events(update):
            key = str(update)
            if update in self.plan.validation_updates:
                points = self.points.setdefault(key, {})
                for role in ROLES:
                    if role not in points:
                        previous = self.trainer.validation_state[role]["last_result"]
                        result = (previous if previous is not None and previous.get("optimizer_updates") == update
                                  else self.trainer.validate(role))
                        points[role] = {**curve_point(result, self.trainer.model.structural_binding.noise),
                                        "source": deepcopy(self.comparison_binding["validation_role_sources"][role])}
            if update in self.plan.checkpoint_updates and update not in self.saved_updates:
                self.save(root / f"checkpoint_u{update}_log{self.trainer.log_cursor}", output_root=root)

        self.trainer.flush_pending_log()
        with execution_context(self.options):
            complete_events(self.trainer.clock.optimizer_updates)
            while self.trainer.clock.optimizer_updates < target:
                self.trainer.next_step(self.plan.max_batch_samples)
                update = self.trainer.clock.optimizer_updates
                complete_events(update)
                if resource_guard is not None:
                    resource_guard()
            if target not in self.saved_updates:
                self.save(root / f"checkpoint_u{target}_log{self.trainer.log_cursor}", output_root=root)
        result = {"schema": "model_v3_precision_member_result_v1", "status": "UPDATES_COMPLETE_PENDING_OUTER_TERMINAL" if target == self.plan.updates else "SEGMENT_PAUSED",
            "scientific_acceptance": False, "input_kind": self.plan.input_kind, "seed": self.seed, "precision": self.precision,
            "optimizer_updates": self.trainer.clock.optimizer_updates, "samples_consumed": self.trainer.clock.samples_consumed,
            "contract": deepcopy(self.contract), "validation": deepcopy(self.points), "tracker": self.trainer.tracker_identity,
            "resume_parent_tracker": self.trainer.resume_parent, "parent_checkpoint": self.parent_checkpoint,
            "outer_terminal_evidence_required": True}
        write_new_json(root / "member_result.json", result)
        return result


def compare_precision_members(members):
    """Numeric audit only; caller still authenticates SDK/Slurm segment closure."""
    require(len(members) == 4 and {(m["precision"], m["seed"]) for m in members}
            == {(p, s) for p in ("fp32", "bf16") for s in (0, 1)}, "All four distinct precision members required")
    first = members[0]
    common = first["contract"]["comparison_binding"]
    plan = PrecisionPlan(**{**first["contract"]["plan"], "validation_updates": tuple(first["contract"]["plan"]["validation_updates"]),
                           "checkpoint_updates": tuple(first["contract"]["plan"]["checkpoint_updates"])})
    for member in members:
        require(member["contract"]["comparison_binding"] == common and member["contract"]["plan_sha256"] == plan.sha256
                and member["status"] == "UPDATES_COMPLETE_PENDING_OUTER_TERMINAL" and member["optimizer_updates"] == plan.updates,
                "Precision member source/data/plan/endpoint differs or segment is incomplete")
        require(set(member["validation"]) == {str(step) for step in plan.validation_updates}, "Complete identical validation grid required")
        require(member["contract"]["seed"] == member["seed"] and member["contract"]["precision"] == member["precision"],
                "Member identity differs from its training contract")
        require(all(set(point) == set(ROLES) for point in member["validation"].values()), "Both complete validation roles required")
    for seed in (0, 1):
        pair = [member for member in members if member["seed"] == seed]
        require(pair[0]["samples_consumed"] == pair[1]["samples_consumed"], "Paired seed consumed-sample clocks differ")
    reports = {}
    gate_roles = validate_role_sources(common["validation_role_sources"], common["validation_population_bindings"],
                                       production=plan.input_kind == "authoritative_proxy")
    for role in ROLES:
        for step in plan.validation_updates:
            rows = [member["validation"][str(step)][role] for member in members]
            require(all(row["population"] == rows[0]["population"] and row["input_population_sha256"] == rows[0]["input_population_sha256"] for row in rows),
                    "Validation units/sigma/effective population/input bytes differ")
            require(all(row["source"] == common["validation_role_sources"][role] for row in rows), "Validation point source/purpose differs")
            require(all(row["validation_noise_seed"] == plan.validation_seed and row["validation_epoch"] == 0 for row in rows),
                    "Validation noise seed/epoch differs from the fixed protocol")
        runs = [{"seed": member["seed"], "optimizer_updates": member["optimizer_updates"],
                 "validation": {step: member["validation"][str(step)][role]["metrics"] for step in plan.validation_updates}}
                for member in members]
        noise_metric = common["noise_field"] + "/RMSE"
        reports[role] = bf16_curve_report([run for run, member in zip(runs, members) if member["precision"] == "fp32"],
            [run for run, member in zip(runs, members) if member["precision"] == "bf16"],
            validation_updates=plan.validation_updates, denoise_metric=noise_metric, required_updates=plan.updates)
        reports[role].update(source=common["validation_role_sources"][role], admitted_to_B_gate=role in gate_roles)
    passed = all(reports[role]["pass"] for role in gate_roles)
    return {"schema": "model_v3_B_precision_curve_audit_v1", "numeric_pass": passed,
            "scientific_acceptance": False, "status": "SYNTHETIC_HARNESS_ONLY" if plan.input_kind == "synthetic" else "NUMERIC_AUDIT_REQUIRES_AUTHENTICATED_D5_AND_ALL_SEGMENT_TERMINALS",
            "plan_sha256": plan.sha256, "roles": reports, "gate_roles": list(gate_roles), "required_updates": plan.updates,
            "RMSE_gate": "per-seed paired relative<=0.02; every metric also inside two-fp32-seed envelope"}
