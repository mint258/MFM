"""Actual native-aligned H0 SoM ranking; NOT_FROZEN preparation only.

Candidate masks, enzyme/task names, supervision and source/role declarations
come from the caller. This consumer neither extracts annotations nor proves
chemical negatives, final-test membership or checkpoint-file provenance.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import time

import torch
from torch import Tensor
from torch_geometric.data import Data

from ..model.shared import SharedBackboneMFM
from .downstream_readout import SourceAlignedH0Readout
from .downstream_training import validate_downstream_batch, validate_training_config
from .downstream_evaluation import (
    _backbone_hash, _check_grads, _restore, _snapshot, _state_hash, _stream_tensor,
)
from .identity import canonical_hash


SOM_EVALUATION_SCHEMA = "phase1_som_ranking_evaluation_v1"
LABEL_SEMANTICS = "source_native_binary_0_1_supervision_subset_candidates_v1"
RANKING_RECIPE = "molecule_task_candidate_scores_desc_native_id_asc_hit_at_clamped_k_v1"


class SomEvaluationError(RuntimeError):
    """Actual forward, ranking, state preservation or cooperative budget failed."""


def _require(condition, message):
    if not condition:
        raise SomEvaluationError(message)


def _positive(value, name, *, integer=False):
    _require(type(value) is int if integer else type(value) in (int, float), name + " has an invalid type")
    _require(value > 0 and math.isfinite(value), name + " must be positive finite")


def _sha(value, name):
    _require(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
             name + " must be a lowercase SHA256")


def _text(value, name):
    _require(type(value) is str and 0 < len(value) <= 256 and value.strip() == value,
             name + " must be an explicit bounded string")


def _contract(value, config):
    names = {"schema_version", "role", "ks", "score_space", "tie_policy", "k_over_candidates",
             "incomplete_supervision", "no_positive_policy", "label_semantics", "units", "task_metadata",
             "primary_metric_per_task", "primary_contract_sha256", "dataset_sha256", "split_manifest_sha256", "caps"}
    _require(type(value) is dict and set(value) == names, "SoM evaluation requires its exact contract fields")
    try:
        result = json.loads(json.dumps(value, allow_nan=False))
    except (ValueError, TypeError, RecursionError) as exc:
        raise SomEvaluationError("Evaluation contract must be finite JSON") from exc
    _require(result["schema_version"] == SOM_EVALUATION_SCHEMA
             and result["role"] == "train_inner_validation", "Only preparation inner validation is supported")
    ks = result["ks"]
    _require(type(ks) is list and 0 < len(ks) <= 32
             and all(type(k) is int and 0 < k <= 4096 for k in ks)
             and len(set(ks)) == len(ks), "ks must be explicit unique bounded positive integers")
    _require(result["score_space"] in ("raw_logits", "sigmoid_fp32"), "Explicit score space is required")
    _require(result["tie_policy"] == "score_desc_native_source_id_asc", "Unsupported or implicit tie policy")
    _require(result["k_over_candidates"] == "clamp_to_candidate_count", "Explicit candidate-count clamp is required")
    _require(result["incomplete_supervision"] in ("skip_instance", "reject"), "Explicit incomplete supervision policy is required")
    _require(result["no_positive_policy"] == "exclude_and_report", "Explicit no-positive exclusion/reporting is required")
    _require(result["label_semantics"] == LABEL_SEMANTICS, "Explicit source-native binary semantics are required")
    tasks = set(config["tasks"])
    for name in ("units", "task_metadata", "primary_metric_per_task"):
        _require(type(result[name]) is dict and set(result[name]) == tasks, name + " must cover exact task IDs")
    _require(all(unit == "binary" for unit in result["units"].values()), "Every task must explicitly declare binary units")
    for task in config["tasks"]:
        metadata = result["task_metadata"][task]
        _require(type(metadata) is dict and set(metadata) == {"dataset_id", "enzyme_id", "positive_definition"},
                 "Task metadata requires explicit dataset, enzyme and positive definition")
        _text(metadata["dataset_id"], "dataset_id")
        _text(metadata["positive_definition"], "positive_definition")
        if metadata["enzyme_id"] is not None:
            _text(metadata["enzyme_id"], "enzyme_id")
        primary = result["primary_metric_per_task"][task]
        _require(type(primary) is dict and set(primary) == {"metric", "k"}
                 and primary["metric"] == "molecule_hit_at_k" and type(primary["k"]) is int
                 and primary["k"] in ks, "Each task requires an explicit supported primary metric and k")
    for name in ("primary_contract_sha256", "dataset_sha256", "split_manifest_sha256"):
        _sha(result[name], name)
    _require(result["primary_contract_sha256"] == canonical_hash(result["primary_metric_per_task"]),
             "Primary metric contract hash differs")
    _require(result["split_manifest_sha256"] == config["bindings"]["split_manifest_sha256"],
             "Evaluation must use the declared training/inner split plan")
    caps = result["caps"]
    _require(type(caps) is dict and set(caps) == {"wall_seconds", "max_sequence_batches", "max_unique_samples",
             "max_graphs_per_batch", "max_atoms_per_batch"}, "Evaluation requires exact cooperative caps")
    _positive(caps["wall_seconds"], "wall cap")
    for name in set(caps) - {"wall_seconds"}:
        _positive(caps[name], name, integer=True)
    return result


def _rank_frame(digest, *, sample, task, status, native_ids):
    frame = json.dumps({"sample_id": sample, "task": task, "status": status,
                        "ranked_native_source_ids": native_ids}, sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    digest.update(len(frame).to_bytes(8, "big"))
    digest.update(frame)


def evaluate_som_ranking(model, readout, config, batches, *, evaluation_contract):
    """Run actual H0/atom readout and macro molecule-by-task hit@k.

    ``batches`` contains existing DownstreamTrainBatch objects. Their separate
    candidate_mask and supervision_mask are packed in full native source order.
    Ranking never shrinks candidates to the observed subset. Fully known
    candidate sets with a positive site alone enter the hit-rate denominator.
    All other instances have explicit counters; rejection/skip is contractual.
    Full temporary state/gradient copies stay on their original device. The
    caller must bound full process RSS and blocking calls in addition to these
    cooperative wall/shape caps. No file I/O or tracker mutation occurs here.
    """
    started = time.monotonic()
    try:
        configuration = validate_training_config(config)
        devices = [0] if configuration["device"] == "cuda:0" else []
        with torch.random.fork_rng(devices=devices):
            return _evaluate(model, readout, configuration, batches,
                             evaluation_contract=evaluation_contract, started=started)
    except SomEvaluationError:
        raise
    except Exception as exc:
        raise SomEvaluationError("SoM ranking evaluation failed") from exc


def _evaluate(model, readout, configuration, batches, *, evaluation_contract, started):
    contract = _contract(evaluation_contract, configuration)
    _require(isinstance(model, SharedBackboneMFM) and isinstance(readout, SourceAlignedH0Readout)
             and readout.output_level == "atom", "Actual shared H0 and the allowed atom readout are required")
    _require(configuration["loss"] == "bce_logits" and configuration["normalization"]["kind"] == "identity",
             "SoM ranking requires an explicitly binary BCE/identity-trained readout")
    _require(readout.config_dict() == configuration["readout_config"]
             and readout.input_dim == model.latent_dim and readout.output_dim == len(configuration["tasks"]),
             "Readout architecture/task dimensions differ")
    device, modules = torch.device(configuration["device"]), (model, readout)
    for module in modules:
        for tensor in list(module.parameters()) + list(module.buffers()):
            _require(tensor.device == device and (not tensor.is_floating_point() or tensor.dtype == torch.float32),
                     "Current model/readout must be FP32 on the single declared device")
            _require(not tensor.is_floating_point() or bool(torch.isfinite(tensor).all()), "Current state is nonfinite")
    caps = contract["caps"]

    def wall_check():
        _require(time.monotonic() - started < caps["wall_seconds"], "SoM cooperative wall budget exhausted")

    wall_check()
    _require(type(batches) in (tuple, list) and 0 < len(batches) <= caps["max_sequence_batches"],
             "A bounded fixed evaluation batch sequence is required")
    specs, seen = [], set()
    samples = atoms = 0
    mask_digest = hashlib.sha256(b"phase1_som_candidate_and_supervision_masks_v1\0")
    logit_digest = hashlib.sha256(b"phase1_som_actual_logits_fp32_v1\0")
    score_digest = hashlib.sha256(b"phase1_som_actual_ranking_scores_fp32_v1\0")
    rank_digest = hashlib.sha256(b"phase1_som_ranked_native_source_ids_v1\0")
    for index, item in enumerate(batches):
        wall_check()
        spec = validate_downstream_batch(item, configuration, model,
                                        expected_role="train_inner_validation", require_observed=False)
        _require(spec["samples"] <= caps["max_graphs_per_batch"] and spec["atoms"] <= caps["max_atoms_per_batch"],
                 "Evaluation graph/atom cap exceeded")
        _require(not seen.intersection(item.sample_ids), "Evaluation sample IDs must be globally unique")
        seen.update(item.sample_ids)
        _require(len(seen) <= caps["max_unique_samples"], "Evaluation unique sample cap exceeded")
        specs.append(spec)
        samples += spec["samples"]
        atoms += spec["atoms"]
        for field in ("candidate_mask", "supervision_mask"):
            _stream_tensor(mask_digest, getattr(item, field), batch_index=index, sample_ids=item.sample_ids, field=field)
    before = {"model_state_sha256": _state_hash(model), "encoder_state_sha256": _backbone_hash(model),
              "readout_state_sha256": _state_hash(readout)}
    snapshot = _snapshot(modules)
    snapshot_bytes = sum(value.numel() * value.element_size() for state in snapshot[0]
                         for value in state.values() if isinstance(value, Tensor))
    snapshot_bytes += sum(gradient.numel() * gradient.element_size()
                          for _, _, _, gradient in snapshot[2] if gradient is not None)
    counters = {task: {name: 0 for name in ("instances", "evaluable", "no_candidate", "unknown",
                                         "partial_supervision", "no_positive")} for task in configuration["tasks"]}
    hits = {task: {str(k): 0 for k in contract["ks"]} for task in configuration["tasks"]}
    completed = False
    try:
        model.eval()
        readout.eval()
        with torch.no_grad(), torch.autocast(device_type=device.type, enabled=False):
            for index, item in enumerate(batches):
                wall_check()
                _require(validate_downstream_batch(item, configuration, model,
                         expected_role="train_inner_validation", require_observed=False) == specs[index],
                         "Evaluation batch changed after sequence binding")
                data = item.encoder_batch
                safe = Data(x=data.x.detach().clone(), pos=data.pos.detach().clone(),
                            batch=data.batch.detach().clone(), ptr=data.ptr.detach().clone())
                h0 = model.encode_atoms(safe)
                output = readout(h0, source_atom_ids=item.source_atom_ids, batch=safe.batch, ptr=safe.ptr)
                logits = output.predictions
                _require(output.output_level == "atom" and logits.dtype == torch.float32
                         and logits.device == device and logits.shape == (specs[index]["atoms"], len(hits))
                         and output.graph_ids.dtype == torch.long and output.graph_ids.device == device
                         and output.ptr.dtype == torch.long and output.ptr.device == device
                         and torch.equal(output.graph_ids, safe.batch) and torch.equal(output.ptr, safe.ptr)
                         and isinstance(output.source_atom_ids, Tensor)
                         and output.source_atom_ids.dtype == torch.long and output.source_atom_ids.device == device
                         and torch.equal(output.source_atom_ids, item.source_atom_ids),
                         "Readout returned a different atom/source contract")
                _require(bool(torch.isfinite(logits).all()), "Actual logits are nonfinite")
                scores = logits if contract["score_space"] == "raw_logits" else torch.sigmoid(logits)
                _require(scores.dtype == torch.float32 and bool(torch.isfinite(scores).all()), "Actual ranking scores are invalid")
                _stream_tensor(logit_digest, logits, batch_index=index, sample_ids=item.sample_ids, field="raw_logits")
                _stream_tensor(score_digest, scores, batch_index=index, sample_ids=item.sample_ids, field=contract["score_space"])
                native_index = output.ptr[output.graph_ids] + output.source_atom_ids
                candidates = item.candidate_mask[native_index].detach().cpu()
                observed = item.supervision_mask[native_index].detach().cpu()
                targets = item.targets[native_index].detach().cpu()
                score_rows, native_ids = scores.detach().cpu(), output.source_atom_ids.detach().cpu().tolist()
                boundaries = output.ptr.detach().cpu().tolist()
                for graph, sample in enumerate(item.sample_ids):
                    start, end = boundaries[graph:graph + 2]
                    for task_index, task in enumerate(configuration["tasks"]):
                        count = counters[task]
                        count["instances"] += 1
                        eligible = torch.nonzero(candidates[start:end, task_index], as_tuple=False).flatten().tolist()
                        known = int(observed[start:end, task_index].sum())
                        state = ("no_candidate" if not eligible else "unknown" if not known
                                 else "partial_supervision" if known < len(eligible) else "evaluable")
                        if state in ("unknown", "partial_supervision"):
                            _require(contract["incomplete_supervision"] != "reject", "Incomplete candidate supervision is rejected")
                        positive_ids = {native_ids[start + offset] for offset in eligible
                                        if state == "evaluable" and targets[start + offset, task_index].item() == 1}
                        if state == "evaluable" and not positive_ids:
                            state = "no_positive"
                        count[state] += 1
                        ordered = []
                        if state == "evaluable":
                            ordered = sorted(eligible, key=lambda offset: (-score_rows[start + offset, task_index].item(),
                                                                          native_ids[start + offset]))
                            ordered = [native_ids[start + offset] for offset in ordered]
                            for k in contract["ks"]:
                                hits[task][str(k)] += int(bool(positive_ids.intersection(ordered[:min(k, len(ordered))])))
                        _rank_frame(rank_digest, sample=sample, task=task, status=state, native_ids=ordered)
                    wall_check()
                del output, h0, logits, scores, safe, native_index, candidates, observed, targets, score_rows
                wall_check()
        # Source/target tensors are owned by the caller. Recheck the complete
        # sequence after the final forward, including earlier batches that a
        # later callback might have altered, before accepting any metrics.
        for index, item in enumerate(batches):
            wall_check()
            _require(validate_downstream_batch(item, configuration, model,
                     expected_role="train_inner_validation", require_observed=False) == specs[index],
                     "Evaluation input mutated during actual forward")
        _require(_state_hash(model) == before["model_state_sha256"]
                 and _state_hash(readout) == before["readout_state_sha256"], "Evaluation mutated current model/readout state")
        _check_grads(snapshot)
        wall_check()
        completed = True
    finally:
        _restore(modules, snapshot)
    after = {"model_state_sha256": _state_hash(model), "encoder_state_sha256": _backbone_hash(model),
             "readout_state_sha256": _state_hash(readout)}
    _require(completed and before == after, "Evaluation did not complete with preserved current state")
    _check_grads(snapshot)
    wall_check()
    metrics = {}
    for task in configuration["tasks"]:
        count = counters[task]
        _require(count["instances"] == samples and sum(count[name] for name in count if name != "instances") == samples,
                 "Instance coverage counters differ")
        denominator = count["evaluable"]
        by_k = {str(k): {"hits": hits[task][str(k)], "denominator": denominator,
                        "hit_rate": hits[task][str(k)] / denominator if denominator else None} for k in contract["ks"]}
        primary = contract["primary_metric_per_task"][task]
        metrics[task] = {"unit": "binary", "task_metadata": deepcopy(contract["task_metadata"][task]),
                         "counters": count, "by_k": by_k, "primary_metric": primary["metric"],
                         "primary_k": primary["k"], "primary_value": by_k[str(primary["k"])]["hit_rate"],
                         "status": "OK" if denominator else "NO_EVALUABLE_INSTANCES"}
    valid = [counters[task]["evaluable"] for task in configuration["tasks"]]
    receipt = {
        "schema_version": SOM_EVALUATION_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
        "status": "COMPLETE" if all(valid) else "PARTIAL_NO_EVALUABLE_INSTANCES" if any(valid) else "NO_EVALUABLE_INSTANCES",
        "role": contract["role"], "metrics": metrics, "batches": len(batches), "samples": samples, "atoms": atoms,
        "evaluation_contract": contract, "evaluation_contract_sha256": canonical_hash(contract),
        "primary_contract_sha256": contract["primary_contract_sha256"], "training_config_sha256": canonical_hash(configuration),
        "model_config_sha256": canonical_hash(model.config_dict()), "readout_config_sha256": canonical_hash(readout.config_dict()),
        "actual_state_before": before, "actual_state_after": after,
        "evaluation_sequence_sha256": canonical_hash([spec["hash"] for spec in specs]),
        "sample_membership_sha256": canonical_hash({"schema_version": "phase1_evaluation_sample_membership_v1",
                                                   "sample_ids": sorted(seen)}),
        "label_masks_sha256": mask_digest.hexdigest(), "raw_logit_score_sha256": logit_digest.hexdigest(),
        "ranking_score_sha256": score_digest.hexdigest(), "ranked_native_source_ids_sha256": rank_digest.hexdigest(),
        "ranking_recipe": RANKING_RECIPE,
        "caller_declarations": {"evaluation_dataset_sha256": contract["dataset_sha256"],
                                "split_manifest_sha256": contract["split_manifest_sha256"], **deepcopy(configuration["bindings"])},
        "source_dataset_role_truth_independently_verified": False, "annotation_and_candidate_truth_independently_verified": False,
        "checkpoint_file_sha256_independently_verified": False,
        "resource_limits": {"wall_enforcement": "cooperative", "rss_enforcement": "caller_supervisor_required",
                            "temporary_snapshot_tensor_bytes": snapshot_bytes,
                            "temporary_copies": "full model/readout state and existing gradients on their declared device",
                            "score_retention": "one bounded batch; stream hashes and task counters only"},
    }
    wall_check()
    receipt["wall_seconds"] = time.monotonic() - started
    receipt["receipt_sha256"] = canonical_hash(receipt)
    wall_check()
    return receipt
