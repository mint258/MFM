"""Immutable model-owned checkpoint outbox and aggregate curve receipts.

No job submission, model construction, source-store access or data authority is
provided here. Only complete wrapper checkpoints may publish panel events.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import stat
import uuid

MAX_JSON_BYTES = 2 * 1024**2
TASKS = frozenset(("cyp.3A4", "cyp.2D6", "exp.LogD", "exp.LogS", "exp.Log_HLM_CLint",
                   "qm9.U0", "qm9.homo", "qm9.lumo", "qm9.alpha"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()


def canonical(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def physical(path):
    path = Path(path).absolute()
    require(".." not in path.parts, "Physical paths without parent traversal required")
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), "Symlink ancestry is not permitted")
    return path


def binding(path):
    path = physical(path)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid(),
        "Owned ordinary single-link file required")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            digest.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "Bound source changed while hashing")
    return {"path": str(path), "bytes": before.st_size, "sha256": digest.hexdigest()}


def read_bound(ref):
    require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}
        and type(ref["bytes"]) is int and 0 <= ref["bytes"] <= MAX_JSON_BYTES, "Bounded metadata reference required")
    require(binding(ref["path"]) == ref, "Metadata binding/size differs")
    raw = Path(ref["path"]).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "Metadata changed before parsing")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate metadata key")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("Nonfinite metadata")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def fsync_directory(path):
    descriptor = os.open(str(physical(path)), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_once(path, value):
    path, raw = physical(path), encoded(value)
    require(len(raw) <= MAX_JSON_BYTES, "Bounded metadata file required")
    if path.exists():
        require(binding(path)["bytes"] == len(raw) and path.read_bytes() == raw,
            "Existing/partial metadata differs; preserve it and use explicit recovery")
    else:
        with path.open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        fsync_directory(path.parent)
    return binding(path)


def owned_bytes(root):
    root = physical(root)
    total = 0
    for path in root.rglob("*"):
        require(not path.is_symlink(), "This checkpoint/metadata root cannot contain SDK or arbitrary links")
        info = path.stat()
        require(info.st_uid == os.getuid(), "Foreign output ownership")
        if stat.S_ISREG(info.st_mode):
            require(info.st_nlink == 1, "Hard-linked output is not counted as owned storage")
            total += info.st_size
        else:
            require(stat.S_ISDIR(info.st_mode), "Unexpected output object")
    return total


def verify_checkpoint_record(ref):
    record = read_bound(ref)
    require(record["schema"] == "model_v3_sample_experiment_checkpoint_v1", "Wrapper completion schema differs")
    state, trainer_marker = read_bound(record["state"]), read_bound(record["trainer_marker"])
    intent = read_bound(record["intent"])
    require(intent["state"] == {key: value for key, value in state.items() if key != "event"}
        and trainer_marker["schema"] == "model_v3_training_checkpoint_v1"
        and trainer_marker["bindings"] == state["contract"]["trainer_bindings"], "Checkpoint source/intent contract differs")
    require(record["trainer_marker"]["path"] == str(Path(record["trainer_payload"]["path"]).parent / "COMPLETE.json")
        and binding(record["trainer_payload"]["path"]) == record["trainer_payload"]
        and trainer_marker["payload_sha256"] == record["trainer_payload"]["sha256"]
        and trainer_marker["payload_bytes"] == record["trainer_payload"]["bytes"], "Incomplete/changed trainer checkpoint")
    require((trainer_marker["samples_consumed"], trainer_marker["optimizer_updates"]) ==
        (state["samples_consumed"], state["optimizer_updates"]), "Wrapper/trainer consumed clocks differ")
    for validation in state["validation"]:
        read_bound(validation)
    event = state["event"]
    require(event["checkpoint"] == record["trainer_payload"] and event["training_completion"] == record["trainer_marker"]
        and event["event_id"] == canonical({key: value for key, value in event.items() if key != "event_id"}),
        "Event does not bind this exact immutable checkpoint")
    return record, state


class PanelEventController:
    """One explicit immutable experiment ledger; ACK state never rolls back with training."""
    def __init__(self, root, *, contract, max_records):
        self.root = physical(root)
        require(type(max_records) is int and max_records > 0, "Explicit bounded ledger size required")
        self.maximum, self.contract = max_records, contract
        self.root.mkdir(parents=True, exist_ok=True)
        fsync_directory(self.root.parent)
        require(self.root.stat().st_uid == os.getuid(), "Owned ledger required")
        write_once(self.root / "EXPERIMENT.json", {"schema": "model_v3_sample_experiment_ledger_v1", "contract": contract})
        for name in ("events", "acks"):
            physical(self.root / name).mkdir(exist_ok=True)
        fsync_directory(self.root)

    def publish(self, completion_ref):
        _, state = verify_checkpoint_record(completion_ref)
        require(state["contract"] == self.contract, "Cannot publish another experiment's checkpoint")
        body = state["event"]
        require(body["event_id"] == canonical({key: value for key, value in body.items() if key != "event_id"}),
            "Event semantic identity differs")
        files = list((self.root / "events").glob("*.json"))
        require(len(files) < self.maximum or (self.root / "events" / (body["event_id"]+".json")).exists(),
            "Ledger event cap reached")
        for path in files:
            existing = read_bound(binding(path))["body"]
            require(existing["samples_consumed"] != body["samples_consumed"] or existing["event_id"] == body["event_id"],
                "A different checkpoint already owns this sample point; no implicit lineage fork or ACK replay")
        return write_once(self.root / "events" / (body["event_id"]+".json"),
            {"schema": "model_v3_checkpoint_panel_event_v1", "body": body, "checkpoint_completion": completion_ref})

    def events(self):
        paths = sorted((self.root / "events").glob("*.json"))
        require(len(paths) <= self.maximum, "Ledger event cap exceeded")
        result = []
        for path in paths:
            ref = binding(path); value = read_bound(ref)
            _, state = verify_checkpoint_record(value["checkpoint_completion"])
            require(value["schema"] == "model_v3_checkpoint_panel_event_v1" and value["body"] == state["event"]
                and state["contract"] == self.contract and path.stem == value["body"]["event_id"], "Outbox source differs")
            result.append((ref, value["body"]))
        return result

    def acknowledgements(self):
        directories = list((self.root / "acks").iterdir())
        require(len(directories) <= self.maximum*4, "ACK attempt cap reached; partials require Root review")
        result = {}
        for directory in directories:
            physical(directory)
            require(directory.is_dir() and directory.stat().st_uid == os.getuid(), "Owned ordinary ACK attempt directory required")
            marker = directory / "ACK_COMPLETE.json"
            if not marker.exists():
                continue  # Preserve partial attempts; never accept their receipt.
            ack = read_bound(binding(marker))
            event = read_bound(ack["event"])
            require(event["body"]["event_id"] == ack["event_id"], "ACK event identity differs")
            result_value, evidence_value = read_bound(ack["result"]), read_bound(ack["evidence"])
            validate_panel_evidence(event["body"], ack["result"], result_value, evidence_value)
            require(ack["event_id"] not in result or result[ack["event_id"]] == ack, "Conflicting completed ACKs")
            result[ack["event_id"]] = ack
        return result

    def pending(self):
        ack = self.acknowledgements()
        return [(ref, body) for ref, body in self.events() if body["event_id"] not in ack]

    def acknowledge(self, event_ref, result_ref, evidence_ref):
        event = read_bound(event_ref)
        known = {ref["sha256"]: body for ref, body in self.events()}
        require(event_ref["sha256"] in known and event["body"] == known[event_ref["sha256"]], "Unknown event")
        body = event["body"]
        previous = self.acknowledgements().get(body["event_id"])
        if previous is not None:
            require(previous["result"] == result_ref and previous["evidence"] == evidence_ref, "ACK replay changes evidence")
            return previous
        result, evidence = read_bound(result_ref), read_bound(evidence_ref)
        validate_panel_evidence(body, result_ref, result, evidence)
        require(len(list((self.root / "acks").iterdir())) < self.maximum*4, "ACK attempt cap reached")
        directory = self.root / "acks" / (body["event_id"]+"_"+uuid.uuid4().hex)
        directory.mkdir()
        fsync_directory(directory.parent)
        receipt = {"schema": "model_v3_sample_panel_ack_v1", "event_id": body["event_id"],
            "event": event_ref, "result": result_ref, "evidence": evidence_ref}
        write_once(directory / "receipt.json", receipt)
        write_once(directory / "ACK_COMPLETE.json", receipt)
        return receipt

    def curve(self):
        ack = self.acknowledgements()
        rows = []
        for event_ref, event in self.events():
            receipt = ack.get(event["event_id"])
            envelope = read_bound(event_ref)
            _, state = verify_checkpoint_record(envelope["checkpoint_completion"])
            validation = []
            for ref in state["validation"]:
                point = read_bound(ref)
                validation.append({"role": point["role"], "samples_consumed": point["samples_consumed"],
                    "optimizer_updates": point["optimizer_updates"], "fields": {name: {key: value for key, value in field.items()
                        if key in {"loss", "MAE", "R2", "accuracy", "valid_labels", "enabled", "metric_status", "unit",
                                   "RMSE", "vector_RMSE", "eps_component_RMSE", "sigma", "component_denominator", "target_width"}}
                        for name, field in point["result"]["fields"].items()}})
            row = {"event_id": event["event_id"], "samples_consumed": event["samples_consumed"],
                "optimizer_updates": event["optimizer_updates"], "checkpoint": event["checkpoint"],
                "status": event["status"] if receipt is None else "ACKNOWLEDGED", "summaries": None,
                "validation": validation, "segment_runtime_before_this_save": state["segment_runtime"],
                "GPU_counter_scope": "process allocator high-water since last reset; not device-global"}
            if receipt:
                result, evidence = read_bound(receipt["result"]), read_bound(receipt["evidence"])
                validate_panel_evidence(event, receipt["result"], result, evidence)
                row["summaries"] = {name: {"mean_normalized_improvement": item["mean_normalized_improvement"],
                    "bootstrap_ci": item["bootstrap_ci"], "tasks": {task: {key: values[key] for key in
                        ("error", "reference_error", "normalized_improvement", "bootstrap_ci", "observed_labels", "observed_molecules")}
                        for task, values in item["tasks"].items()}} for name, item in result["summaries"].items()}
            rows.append(row)
        return {"schema": "model_v3_sample_budget_curve_v1", "scientific_acceptance": False,
            "platform_or_architecture_decision": None, "data_authority_asserted": False,
            "points": sorted(rows, key=lambda row: (row["samples_consumed"], row["event_id"]))}


def validate_panel_evidence(event, result_ref, result, evidence):
    require(event["status"] == "READY", "BLOCKED_UNSUPPORTED_ENCODER cannot be ACKed as an evaluated panel")
    require(result["status"] == "COMPLETED" and result["reference_kind"] == "primary", "Incomplete panel result")
    pair, panel = result["encoder_pair"], event["panel_binding"]
    require(pair["checkpoint"]["sha256"] == event["checkpoint"]["sha256"]
        and pair["original_configuration"]["sha256"] == event["model_configuration"]["sha256"]
        and pair["H0_dimension"] == 512 and pair["pretraining_seed"] == event["pretraining_seed"]
        and pair["checkpoint_schema"] == "model_v3_immutable_sample_checkpoint"
        and pair["training_completion"] == event["training_completion"]
        and result["architecture_sha256"] == event["architecture_sha256"], "Panel candidate/configuration/seed differs")
    for key in ("panel_sha256", "training_store_sha256", "membership_sha256", "preregistration_sha", "code_sha"):
        require(result[key] == panel[key], "Panel source binding differs: "+key)
    require(pair["random_reference_seed"] == result["random_reference_initialization_seed"] == 20261025
        and result["readout_seed"] == 0, "Matched readout/random seeds differ")
    require(pair["checkpoint_encoder_state_sha256"] != pair["random_encoder_state_sha256"], "Candidate/random states must differ")
    datasets = ("cyp_isoform", "expansionrx", "qm9")
    require(set(result["h0_caches"]) == {label+"/"+dataset for label in ("candidate", "reference") for dataset in datasets},
        "Both matched H0 inventories are required")
    for dataset in datasets:
        candidate, reference = (result["h0_caches"][label+"/"+dataset] for label in ("candidate", "reference"))
        left, right = candidate["binding"], reference["binding"]
        for key in ("architecture_sha256", "membership_sha256", "geometry_sha256", "dimension",
                    "packing_plan_sha256", "packing_budget_sha256", "effective_runtime_sha256"):
            require(left[key] == right[key], "Candidate/random H0 bindings differ")
        require(left["dimension"] == 512 and left["architecture_sha256"] == event["architecture_sha256"]
            and left["membership_sha256"] == panel["membership_sha256"][dataset]
            and left["encoder_sha256"] == pair["checkpoint_encoder_state_sha256"]
            and right["encoder_sha256"] == pair["random_encoder_state_sha256"]
            and candidate["targets_cached"] is False and reference["targets_cached"] is False,
            "Paired target-free H0 source differs")
    for name, methods in (("primary_18_cells", ("ridge", "linear64_relu")), ("ridge", ("ridge",)),
                          ("linear64_relu", ("linear64_relu",))):
        item = result["summaries"][name]
        require(item["complete"] is True and set(item["tasks"]) == {t+"@"+m for t in TASKS for m in methods}
            and item["bootstrap_samples"] == item["bootstrap_defined"] == 1000
            and math.isfinite(item["mean_normalized_improvement"]), "Incomplete18cell/1000-draw panel")
        scores = []
        for cell, row in item["tasks"].items():
            require(all(type(row[key]) in (int, float) and math.isfinite(row[key])
                for key in ("error", "reference_error", "normalized_improvement"))
                and row["error"] >= 0 and row["reference_error"] > 0, "Invalid panel task errors")
            score = (row["reference_error"]-row["error"])/row["reference_error"]
            require(math.isclose(score, row["normalized_improvement"], abs_tol=1e-12), "Panel relative improvement differs")
            require(row == result["summaries"][cell.split("@")[1]]["tasks"][cell], "Readout and primary task cells differ")
            scores.append(score)
            for key in ("observed_labels", "observed_molecules"):
                require(type(row[key]) is int and row[key] > 0, "Observed molecular/label counts required")
            require(len(row["bootstrap_ci"]) == 2 and all(math.isfinite(v) for v in row["bootstrap_ci"])
                and row["bootstrap_ci"][0] <= row["bootstrap_ci"][1], "Invalid task bootstrap interval")
        require(math.isclose(sum(scores)/len(scores), item["mean_normalized_improvement"], abs_tol=1e-12)
            and len(item["bootstrap_ci"]) == 2 and all(math.isfinite(v) for v in item["bootstrap_ci"])
            and item["bootstrap_ci"][0] <= item["bootstrap_ci"][1], "Invalid mean/interval")
    require(evidence["schema"] == "model_v3_sample_panel_evidence_v1" and evidence["result"] == result_ref,
        "Root panel evidence must bind these exact result bytes")
    outer, sdk = read_bound(evidence["outer_terminal"]), read_bound(evidence["sdk_verification"])
    require(outer["status"] == "COMPLETED" and outer["exit_code"] == 0 and str(outer["job_id"]) == str(result["job_id"]),
        "Actual successful outer terminal receipt required")
    require(sdk["status"] == "VERIFIED" and sdk["wandb_history_independently_verified"] is True
        and sdk["inputs"]["result"] == result_ref and sdk["sdk_run_id"] == result["wandb_run_id"]
        and sdk["clean_eof"] is True and sdk["sdk_exit_code"] == 0
        and sdk["history_rows"] == result["journal_records"] > 0,
        "Independent SDK certificate for these actual bytes required")
