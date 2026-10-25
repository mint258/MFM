"""Opt-in consumed-draw controller over the unchanged v3 trainer/save/load APIs.

This model-side API supplies no D schema/authority, scheduler fork, model choice,
plateau rule or job launcher. A Root supervisor still enforces whole-job limits.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import resource
import time
import uuid

from .v3_sample_budget_events import (PanelEventController, binding, canonical, encoded,
    fsync_directory, owned_bytes, physical, read_bound, require, verify_checkpoint_record, write_once)
from .v3_trainer import V3StepTrainer
from .v3_training import runtime_metrics


class SegmentPause(RuntimeError):
    """A preflight hook requests an orderly checkpoint boundary and pause."""


@dataclass(frozen=True)
class SampleBudgetPlan:
    sample_budget: int
    panel_samples: tuple
    validation_samples: tuple
    validation_roles: tuple
    recovery_interval_samples: int
    max_batch_samples: int
    max_checkpoints_per_segment: int
    max_total_checkpoints: int
    max_segment_seconds: int
    checkpoint_reserve_seconds: int
    checkpoint_reserve_bytes: int
    max_segment_bytes: int

    def __post_init__(self):
        for key in ("sample_budget", "recovery_interval_samples", "max_batch_samples",
                    "max_checkpoints_per_segment", "max_total_checkpoints", "max_segment_seconds",
                    "checkpoint_reserve_seconds", "checkpoint_reserve_bytes", "max_segment_bytes"):
            require(type(getattr(self, key)) is int and getattr(self, key) > 0, "Explicit positive budget/count/frequency required: "+key)
        require(self.max_segment_seconds <= 7200 and self.max_segment_bytes <= 2*1024**3
            and self.checkpoint_reserve_seconds < self.max_segment_seconds
            and 2*1024**2 <= self.checkpoint_reserve_bytes < self.max_segment_bytes
            and self.max_checkpoints_per_segment <= self.max_total_checkpoints, "Invalid bounded segment/reserve configuration")
        for key in ("panel_samples", "validation_samples"):
            values = getattr(self, key)
            require(type(values) is tuple and values == tuple(sorted(set(values)))
                and all(type(n) is int and 0 < n <= self.sample_budget for n in values), "Explicit sorted sample points required")
        require(self.sample_budget in self.panel_samples, "Final budget must have a checkpoint/panel event")
        require(type(self.validation_roles) is tuple and len(set(self.validation_roles)) == len(self.validation_roles)
            and set(self.validation_roles) <= {"VAL", "TRAIN_UNSEEN_CONFORMATION"}
            and bool(self.validation_roles) == bool(self.validation_samples), "Explicit original validation roles/points required")


def implementation_sources():
    directory = Path(__file__).parent
    return {name: binding(directory / name)["sha256"] for name in
        ("v3_sample_budget_experiment.py", "v3_sample_budget_events.py")}


class SampleBudgetExperiment:
    def __init__(self, trainer, plan, *, output_root, lineage, input_scope,
                 model_configuration=None, panel_binding=None, panel_required=False):
        require(isinstance(trainer, V3StepTrainer) and isinstance(plan, SampleBudgetPlan), "Existing v3 trainer and explicit plan required")
        require(input_scope in ("synthetic_fixture", "externally_supplied_adapter"), "Explicit model-side input scope required")
        require(type(lineage) is str and lineage and len(lineage) <= 128, "Explicit immutable experiment lineage required")
        require(trainer.clock.sample_budget == trainer.sampler.sample_budget == trainer.scheduler.contract["sample_budget"] == plan.sample_budget,
            "Do not change the existing trainer/sampler/scheduler budget")
        milestones = {n for n in trainer.clock.milestones if n <= plan.sample_budget}
        require(milestones <= set(plan.panel_samples), "Every original milestone needs a checkpoint/panel outbox point")
        if input_scope != "synthetic_fixture":
            require(set(plan.validation_roles) == {"VAL", "TRAIN_UNSEEN_CONFORMATION"}, "Production keeps both original validation populations")
        self.trainer, self.plan, self.input_scope = trainer, plan, input_scope
        self.configuration = model_configuration
        self.panel_binding = json.loads(encoded(panel_binding)) if panel_binding is not None else None
        self.encoder_status, self.architecture_sha, self.seed = self._encoder_capability()
        require(not panel_required or self.encoder_status == "READY", "BLOCKED_UNSUPPORTED_ENCODER: original bridge contract/configuration required")
        self.contract = json.loads(encoded({"schema": "model_v3_sample_budget_experiment_v1", "lineage": lineage,
            "plan": asdict(plan), "trainer_bindings": trainer.bindings, "trainer_contract": trainer.contract,
            "model_configuration": self.configuration, "panel_binding": self.panel_binding,
            "input_scope": input_scope, "data_authority_asserted": False, "scientific_acceptance": False,
            "implementation_sources": implementation_sources()}))
        self.root = physical(output_root)
        repository = Path(__file__).absolute().parents[3]
        require(not self.root.is_relative_to(repository), "Checkpoints/metadata stay outside Git")
        self.root.mkdir(parents=True, exist_ok=True)
        fsync_directory(self.root.parent)
        physical(self.root / "segments")
        self.controller = PanelEventController(self.root / "ledger", contract=self.contract, max_records=plan.max_total_checkpoints)
        (self.root / "segments").mkdir(exist_ok=True)
        self.completed, self.points = [], {}
        self.last_checkpoint = None
        self.segment = self.preflight = None
        self.segment_checkpoints = 0

    def _encoder_capability(self):
        from .v3_architecture_training import ArchitectureStepTrainer, architecture_training_sources
        from .v3_encoder_bridge import source_model_configuration
        from .v3_dev_panel import canonical as architecture_hash
        if not isinstance(self.trainer, ArchitectureStepTrainer) or self.configuration is None or self.panel_binding is None:
            return "BLOCKED_UNSUPPORTED_ENCODER", None, None
        configuration = read_bound(self.configuration)
        require(self.configuration["sha256"] == self.trainer.bindings["configuration_sha256"], "Full source configuration raw SHA differs")
        extension = self.trainer.contract["architecture_extension"]
        model = source_model_configuration(configuration)
        supported = (extension["schema"] == "model_v3_architecture_trainer_v1"
            and extension["encoder_state_prefix"] == "encoder."
            and extension["implementation_sources"] == architecture_training_sources()
            and extension["encoder_configuration"] == self.trainer.model.encoder.config_dict()
            and (model["backbone"]["dim"], model["backbone"]["layers"]) == (512, 6)
            and type(configuration.get("seed")) is int)
        required = {"panel_sha256", "training_store_sha256", "membership_sha256", "preregistration_sha", "code_sha"}
        require(required <= set(self.panel_binding), "Full downstream panel source bindings required")
        return ("READY" if supported else "BLOCKED_UNSUPPORTED_ENCODER", architecture_hash(model), configuration.get("seed"))

    def _all_checkpoint_directories(self):
        return list((self.root / "segments").glob("*/checkpoint_*"))

    def _preflight(self, action, *, allow_pause=True):
        size = owned_bytes(self.segment)
        elapsed = time.monotonic()-self.started
        require(size <= self.plan.max_segment_bytes, "Segment checkpoint/metadata byte cap exhausted")
        if action != "CHECKPOINT" and elapsed >= self.plan.max_segment_seconds-self.plan.checkpoint_reserve_seconds:
            raise SegmentPause("checkpoint wall reserve reached")
        require(elapsed < self.plan.max_segment_seconds, "Segment wall budget exhausted; outer supervisor remains required")
        context = {"action": action, "samples_consumed": self.trainer.clock.samples_consumed,
            "optimizer_updates": self.trainer.clock.optimizer_updates, "segment_bytes": size,
            "max_segment_bytes": self.plan.max_segment_bytes, "elapsed_seconds": elapsed,
            "segment_checkpoint_count": self.segment_checkpoints,
            "total_checkpoint_count_including_partials": len(self._all_checkpoint_directories()),
            "payload_capacity_proven": False}
        if self.preflight is not None:
            try:
                self.preflight(action, context)
            except SegmentPause:
                if not allow_pause:
                    raise RuntimeError("Checkpoint preflight denied; retain last complete checkpoint")
                raise
        return context

    def _state_before(self, reason):
        return {"contract": self.contract, "samples_consumed": self.trainer.clock.samples_consumed,
            "optimizer_updates": self.trainer.clock.optimizer_updates, "log_cursor": self.trainer.log_cursor,
            "pending_log": self.trainer.pending_log is not None, "reason": reason,
            "previous_checkpoints": list(self.completed), "points": dict(self.points),
            "validation": list(self.points.get(str(self.trainer.clock.samples_consumed), [])),
            "segment_runtime": runtime_metrics(samples=self.trainer.clock.samples_consumed-self.segment_initial_samples,
                started=self.metric_started)}

    def _finish_checkpoint(self, directory, intent):
        state = intent["state"]
        fsync_directory(directory / "trainer")
        marker_ref = binding(directory / "trainer/COMPLETE.json")
        marker = read_bound(marker_ref)
        require(marker["bindings"] == self.trainer.bindings and
            (marker["samples_consumed"], marker["optimizer_updates"]) == (state["samples_consumed"], state["optimizer_updates"]),
            "Intent and original committed checkpoint differ")
        payload_ref = binding(directory / "trainer/payload.pt")
        require(marker["payload_sha256"] == payload_ref["sha256"] and marker["payload_bytes"] == payload_ref["bytes"], "Incomplete checkpoint payload")
        status = ("BLOCKED_PENDING_LOG" if state["pending_log"] else self.encoder_status)
        if state["samples_consumed"] not in self.plan.panel_samples and status == "READY":
            status = "RECOVERY_ONLY"
        body = {"schema": "model_v3_sample_checkpoint_panel_body_v1", "contract_sha256": canonical(self.contract),
            "lineage": self.contract["lineage"], "samples_consumed": state["samples_consumed"],
            "optimizer_updates": state["optimizer_updates"], "reason": state["reason"], "status": status,
            "checkpoint": payload_ref, "training_completion": marker_ref,
            "model_configuration": self.configuration, "architecture_sha256": self.architecture_sha,
            "pretraining_seed": self.seed, "panel_binding": self.panel_binding,
            "bridge_load_executed_by_publisher": False, "data_authority_asserted": False, "scientific_acceptance": False}
        body["event_id"] = canonical(body)
        state = {**state, "event": body}
        state_ref = write_once(directory / "experiment_state.json", state)
        completion = {"schema": "model_v3_sample_experiment_checkpoint_v1", "state": state_ref,
            "intent": binding(directory / "INTENT.json"), "trainer_marker": marker_ref, "trainer_payload": payload_ref}
        ref = write_once(directory / "EXPERIMENT_COMPLETE.json", completion)
        fsync_directory(directory)
        self.completed = [*state["previous_checkpoints"], ref]
        self.last_checkpoint = ref
        if not state["pending_log"]:
            self.controller.publish(ref)
        return ref

    def _checkpoint(self, reason):
        self._preflight("CHECKPOINT", allow_pause=False)
        if self.last_checkpoint is not None:
            _, previous = verify_checkpoint_record(self.last_checkpoint)
            if ((previous["samples_consumed"], previous["optimizer_updates"], previous["log_cursor"], previous["pending_log"]) ==
                (self.trainer.clock.samples_consumed, self.trainer.clock.optimizer_updates, self.trainer.log_cursor, self.trainer.pending_log is not None)):
                if not previous["pending_log"]:
                    self.controller.publish(self.last_checkpoint)
                return self.last_checkpoint
        require(self.segment_checkpoints < self.plan.max_checkpoints_per_segment
            and len(self._all_checkpoint_directories()) < self.plan.max_total_checkpoints, "Explicit checkpoint count cap reached")
        directory = self.segment / ("checkpoint_s"+str(self.trainer.clock.samples_consumed)+"_"+uuid.uuid4().hex)
        directory.mkdir(); fsync_directory(self.segment)
        self.segment_checkpoints += 1
        intent = {"schema": "model_v3_sample_checkpoint_intent_v1", "state": self._state_before(reason)}
        write_once(directory / "INTENT.json", intent)
        remaining = self.plan.max_segment_bytes-owned_bytes(self.segment)-self.plan.checkpoint_reserve_bytes
        require(remaining > 0, "No declared byte reserve for another checkpoint")
        old = resource.getrlimit(resource.RLIMIT_FSIZE)
        limit = min(remaining, old[0]) if old[0] != resource.RLIM_INFINITY else remaining
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (limit, old[1]))
            self.trainer.save(directory / "trainer", output_root=directory)
        finally:
            resource.setrlimit(resource.RLIMIT_FSIZE, old)
        require(time.monotonic()-self.started <= self.plan.max_segment_seconds,
            "Checkpoint exceeded cooperative wall bound; retain original COMPLETE for explicit recovery")
        ref = self._finish_checkpoint(directory, intent)
        require(owned_bytes(self.segment) <= self.plan.max_segment_bytes, "Actual checkpoint exceeded segment byte cap")
        return ref

    def resume(self, directory):
        directory = physical(directory)
        require(directory.is_relative_to(self.root / "segments"), "Resume belongs to this explicit experiment root")
        intent = read_bound(binding(directory / "INTENT.json"))
        require(intent["schema"] == "model_v3_sample_checkpoint_intent_v1" and intent["state"]["contract"] == self.contract,
            "Experiment/plan/source/recipe lineage changed; no implicit budget or WSD fork")
        completion = directory / "EXPERIMENT_COMPLETE.json"
        state = intent["state"]
        if completion.exists():
            _, state = verify_checkpoint_record(binding(completion))
            require(state["contract"] == self.contract, "Wrapper state source differs")
        for ref in state["validation"]:
            read_bound(ref)
        self.trainer.load(directory / "trainer", output_root=directory)
        require((self.trainer.clock.samples_consumed, self.trainer.clock.optimizer_updates, self.trainer.log_cursor) ==
            (state["samples_consumed"], state["optimizer_updates"], state["log_cursor"]), "Restored wrapper/trainer cursors differ")
        self.points = state["points"]
        # A complete inner checkpoint plus intact intent can finish a publication
        # interrupted before wrapper COMPLETE. Malformed partial files are kept
        # and rejected by write_once; they are never silently repaired/deleted.
        return self._finish_checkpoint(directory, intent)

    def _validation(self):
        n, key = self.trainer.clock.samples_consumed, str(self.trainer.clock.samples_consumed)
        if n not in self.plan.validation_samples or key in self.points:
            return
        refs = []
        for role in self.plan.validation_roles:
            self._preflight("VALIDATION")
            result = self.trainer.validate(role)
            refs.append(write_once(self.segment / ("validation_"+key+"_"+role+"_"+uuid.uuid4().hex+".json"),
                {"schema": "model_v3_sample_validation_point_v1", "samples_consumed": n,
                    "optimizer_updates": self.trainer.clock.optimizer_updates, "role": role, "result": result}))
        self.points[key] = refs

    def run(self, *, segment_id, until_samples, preflight=None):
        import re
        require(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", segment_id or ""), "Fresh explicit segment identity required")
        require(type(until_samples) is int and self.trainer.clock.samples_consumed < until_samples <= self.plan.sample_budget,
            "Explicit advancing segment endpoint required")
        require(self.input_scope == "synthetic_fixture" or callable(preflight), "External adapters require a whole-job cooperative preflight hook")
        require(preflight is None or callable(preflight), "Preflight must be callable")
        require(len(list((self.root / "segments").iterdir())) < self.plan.max_total_checkpoints, "Explicit total segment/attempt cap reached")
        self.segment = self.root / "segments" / segment_id
        self.segment.mkdir(); fsync_directory(self.segment.parent)
        self.preflight, self.started, self.segment_checkpoints = preflight, time.monotonic(), 0
        self.metric_started, self.segment_initial_samples = time.perf_counter(), self.trainer.clock.samples_consumed
        write_once(self.segment / "SEGMENT_REQUEST.json", {"contract_sha256": canonical(self.contract),
            "until_samples": until_samples, "initial_samples": self.trainer.clock.samples_consumed,
            "preflight_hook_supplied": preflight is not None, "payload_capacity_proven": False})
        reason = "explicit_segment_endpoint"
        try:
            self.trainer.flush_pending_log()
            while True:
                n = self.trainer.clock.samples_consumed
                self._validation()
                due = (n > 0 and (n in self.trainer.clock.milestones or n in self.plan.panel_samples
                    or n % self.plan.recovery_interval_samples == 0 or n == until_samples))
                if due:
                    self._checkpoint("final_budget" if n == self.plan.sample_budget else "sample_boundary")
                if n == until_samples:
                    break
                if self.segment_checkpoints >= self.plan.max_checkpoints_per_segment or len(self._all_checkpoint_directories()) >= self.plan.max_total_checkpoints:
                    reason = "checkpoint_count_cap"; break
                try:
                    self._preflight("STEP")
                except SegmentPause as pause:
                    self._checkpoint("cooperative_pause")
                    reason = str(pause); break
                next_recovery = (n // self.plan.recovery_interval_samples+1)*self.plan.recovery_interval_samples
                boundaries = [until_samples, next_recovery, *self.plan.panel_samples, *self.plan.validation_samples,
                              *(p for p in self.trainer.clock.milestones if p <= self.plan.sample_budget)]
                boundary = min(p for p in boundaries if p > n)
                self.trainer.next_step(min(self.plan.max_batch_samples, boundary-n))
            status = ("BUDGET_REACHED_PENDING_EVALUATION" if self.trainer.clock.samples_consumed == self.plan.sample_budget
                else "SEGMENT_PAUSED")
            require(time.monotonic()-self.started <= self.plan.max_segment_seconds
                and owned_bytes(self.segment) <= self.plan.max_segment_bytes, "Final segment wall/byte cap exceeded")
            result = {"schema": "model_v3_sample_budget_segment_result_v1", "status": status, "reason": reason,
                "samples_consumed": self.trainer.clock.samples_consumed, "optimizer_updates": self.trainer.clock.optimizer_updates,
                "last_checkpoint": self.last_checkpoint, "new_checkpoint_count": self.segment_checkpoints,
                "input_scope": self.input_scope, "data_authority_asserted": False, "scientific_acceptance": False,
                "outer_terminal_evidence_required": True, "payload_capacity_proven": False,
                "elapsed_seconds": time.monotonic()-self.started}
            write_once(self.segment / "SEGMENT_RESULT.json", result)
            return result
        except BaseException as exc:
            recovery_error = None
            # Only the original trainer's explicit post-commit tracking record
            # proves this failure happened after a complete numerical commit.
            # Do not checkpoint arbitrary partially failed optimizer/forward work.
            pending = self.trainer.pending_log
            if pending is not None and pending.get("event") in ("TRAIN_STEP", "VALIDATION") and (
                self.trainer.clock.samples_consumed == self.trainer.sampler.samples_consumed == self.trainer.scheduler.samples_consumed):
                try:
                    self._checkpoint("tracking_failure_recovery_only")
                except BaseException as error:
                    recovery_error = type(error).__name__+": "+str(error)[:300]
            write_once(self.segment / "FAILURE.json", {"schema": "model_v3_sample_budget_failure_v1",
                "exception": type(exc).__name__, "message": str(exc)[:500], "last_checkpoint": self.last_checkpoint,
                "in_memory_samples": self.trainer.clock.samples_consumed, "recovery_error": recovery_error,
                "scientific_acceptance": False, "unpublished_and_partial_files_preserved": True})
            raise
