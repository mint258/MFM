"""Actual native-H0/readout computation with explicit formal test membership.

This external implementation does not change the inner-only production APIs.
Only the physically verified FrozenDownstreamStore supplies labels and roles.
Authoring this module is not a formal execution or a verified source adapter.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import torch
from torch_geometric.data import Data

from phychem_mfm.factory import build_model
from phychem_mfm.model.shared import SharedBackboneMFM
from phychem_mfm.phase1.downstream_readout import SourceAlignedH0Readout, SourceAlignedLinearGraphReadout
from phychem_mfm.phase1.downstream_training import _tree_hash, _copy_cpu, checkpoint_content_sha256
from phychem_mfm.phase1.formal_runtime import backbone_state_hash

from formal_plan import MAIN, AUX, canonical, digest, require, sealed

CACHE_SCHEMA = "phase1_native_h0_disk_cache_v1"
FIT_SCHEMA = "phase1_formal_native_readout_checkpoint_v1"
REPORT_SCHEMA = "phase1_formal_outer_metric_file_v1"
ROLES = ("train", "train_inner_validation", "test")
INVENTORY_COUNTS = {"qm7": 7165, "qm9": 133885, "cyp_isoform": 2003,
                    "az_exactsom": 109, "expansionrx": 7608}


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_bound_json(ref, maximum=16 << 20):
    require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}, "Exact physical file reference required")
    path = Path(ref["path"])
    require(path.is_absolute() and path.is_file() and not path.is_symlink()
            and type(ref["bytes"]) is int and 0 < ref["bytes"] <= maximum
            and path.stat().st_size == ref["bytes"] and file_sha(path) == ref["sha256"], "Bound JSON bytes differ")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON field")
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def write_json(path, document):
    blob = canonical(document) + b"\n"
    with Path(path).open("xb") as stream:
        stream.write(blob)
        stream.flush()
        os.fsync(stream.fileno())


def native_input_sha(sample):
    return _tree_hash({"member_uid": sample.member_uid, "x": sample.x, "pos": sample.pos,
                       "source_atom_ids": sample.source_atom_ids})


def validate_sample(sample, fit, *, expected_uid=None):
    require(sample.dataset_id == fit["dataset_id"] and type(sample.member_index) is int
            and sample.member_index >= 0 and type(sample.member_uid) is str
            and (expected_uid is None or sample.member_uid == expected_uid), "Source member differs")
    require(type(sample.geometry_ready) is bool and type(sample.provenance) is dict, "Explicit source availability/provenance required")
    if not sample.geometry_ready:
        require(type(sample.unavailable_reason) is str and sample.unavailable_reason, "Unready source reason required")
        return
    x, pos, ids = sample.x, sample.pos, sample.source_atom_ids
    require(isinstance(x, torch.Tensor) and x.dtype == torch.long and x.device.type == "cpu"
            and x.ndim == 1 and x.numel() > 0 and bool(((x >= 0) & (x < 118)).all()), "Complete native Z1..118 CPU rows required")
    n, tasks = x.numel(), len(fit["tasks"])
    require(isinstance(pos, torch.Tensor) and pos.dtype == torch.float32 and pos.device.type == "cpu"
            and pos.shape == (n, 3) and not pos.requires_grad and bool(torch.isfinite(pos).all()), "Finite source FP32 angstrom coordinates required")
    require(isinstance(ids, torch.Tensor) and ids.dtype == torch.long and ids.device.type == "cpu"
            and torch.equal(ids, torch.arange(n)), "Native row IDs must retain original full source order")
    shape = (n if fit["output_level"] == "atom" else 1, tasks)
    require(isinstance(sample.targets, torch.Tensor) and sample.targets.dtype == torch.float32
            and sample.targets.device.type == "cpu" and sample.targets.shape == shape
            and not sample.targets.requires_grad, "Source target shape/dtype differs")
    for mask in (sample.candidate_mask, sample.supervision_mask):
        require(isinstance(mask, torch.Tensor) and mask.dtype == torch.bool
                and mask.device.type == "cpu" and mask.shape == shape, "Source mask shape/dtype differs")
    require(not bool((sample.supervision_mask & ~sample.candidate_mask).any()), "Supervision is outside source candidate set")
    observed = sample.targets[sample.supervision_mask]
    require(bool(torch.isfinite(observed).all()), "Observed targets are nonfinite")
    if fit["output_level"] == "atom":
        require(bool(((observed == 0) | (observed == 1)).all()), "Observed atom supervision must be exact binary")


def validate_store_group(store, fit, *, require_full_inventory=True):
    contract = store.contract(fit["dataset_id"], fit["fold_id"])
    require(contract["protocol_content_sha256"] == fit["protocol_content_sha256"]
            and type(contract["original_inventory_count"]) is int
            and contract["original_inventory_count"] == INVENTORY_COUNTS[fit["dataset_id"]],
            "Physical role contract is from a different protocol or original inventory")
    require(tuple(contract["tasks"]) == tuple(fit["tasks"])
            and tuple(contract["units"]) == tuple(fit["units"])
            and contract["output_level"] == fit["output_level"], "Physical data task/output contract differs")
    norm = contract["normalization"]
    require(norm["fit_scope"] == "train" and norm["kind"] in ("train_affine", "identity")
            and len(norm["means"]) == len(norm["scales"]) == len(norm["availability"]) == len(fit["tasks"])
            and all(type(value) is bool for value in norm["availability"]), "Actual train-only normalizer required")
    for mean, scale, available in zip(norm["means"], norm["scales"], norm["availability"], strict=True):
        if not available:
            require(mean is None and scale is None, "Unavailable affine must remain typed null, not a fitted dummy")
            continue
        require(type(mean) in (int, float) and math.isfinite(mean)
                and type(scale) in (int, float) and math.isfinite(scale) and scale > 0, "Available train-fitted affine invalid")
        checked = torch.tensor([mean, scale], dtype=torch.float32)
        require(bool(torch.isfinite(checked).all()) and checked[1].item() > 0, "Train-fitted affine must be finite positive in actual FP32")
    if fit["output_level"] == "atom":
        require(norm["kind"] == "identity" and all(not available or (mean == 0. and scale == 1.)
                for mean, scale, available in zip(norm["means"], norm["scales"], norm["availability"], strict=True)), "SoM normalization must remain identity")
    roles, seen = {}, set()
    for role in ROLES:
        indices = store.view(fit["dataset_id"], fit["fold_id"], role)
        require(type(indices) is tuple and all(type(index) is int and index >= 0 for index in indices)
                and len(set(indices)) == len(indices), "Actual ordered role view required")
        require(not seen.intersection(indices), "Frozen roles overlap")
        seen.update(indices)
        require(len(indices) == len(contract["ordered_members"][role]), "Role inventory cardinality differs")
        roles[role] = indices
    require(roles["train"] and roles["test"], "Formal train/test source inventories required")
    if require_full_inventory:
        require(len(seen) == INVENTORY_COUNTS[fit["dataset_id"]], "Formal roles do not cover the complete original dataset inventory")
    if fit["dataset_id"] == "expansionrx":
        require(fit["fold_id"] == "official" and not roles["train_inner_validation"], "Expansion official train/test has no new inner split")
    return deepcopy(contract), roles


def load_encoder(protocol, endpoint, *, device):
    """Physical safe-load of an actual FINAL, or exact fresh paired NONE."""
    factory = deepcopy(protocol["model"])
    normalization = read_bound_json(endpoint["normalization"])
    require(endpoint["normalization"]["sha256"] == protocol["artifacts"]["normalization"]["sha256"], "Endpoint factory fitted another training corpus")
    factory["head"]["regression_output_normalization"] = normalization
    seed = endpoint["pretraining_seed"]
    require(type(seed) is int and seed in protocol["seeds"] and endpoint["variant"] in protocol["variants"], "Declared encoder condition required")
    require(endpoint["strategy"] in protocol["strategies"]
            and endpoint["variant"] in protocol["strategies"][endpoint["strategy"]]["variants"], "Encoder strategy/variant differs")
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = build_model(factory)
    require(isinstance(model, SharedBackboneMFM) and model.latent_dim == 384 and model.pad_elem_index == 118, "Actual native119/shared384 model required")
    init = read_bound_json(endpoint["initialization"])
    require(endpoint["initialization"]["sha256"] == protocol["artifacts"]["initialization.seed_" + str(seed)]["sha256"]
            and init == {"schema_version": "phase1_full_corpus_paired_initialization_v1", "seed": seed,
                "model_config_sha256": digest(model.config_dict()), "backbone_state_sha256": backbone_state_hash(model)}, "Fresh paired initialization differs")
    initial_h0, initial_model = backbone_state_hash(model), checkpoint_content_sha256({"model": _copy_cpu(model.state_dict())})
    ref = endpoint["checkpoint"]
    require(Path(ref["path"]).is_file() and not Path(ref["path"]).is_symlink()
            and Path(ref["path"]).stat().st_size == ref["bytes"] and ref["bytes"] <= 256 << 20
            and file_sha(ref["path"]) == ref["sha256"], "Physical endpoint bytes differ")
    payload = torch.load(ref["path"], map_location="cpu", weights_only=True)
    require(type(payload) is dict and payload.get("checkpoint_content_sha256") == checkpoint_content_sha256(payload), "Actual typed endpoint seal differs")
    if endpoint["variant"] == "none":
        require(payload.get("schema_version") == "phase1_full_corpus_none_endpoint_v1"
                and payload["seed"] == seed and payload["protocol_sha256"] == protocol["content_sha256"]
                and all(payload["source"].get(key) == value for key, value in protocol["source"].items())
                and payload["model_config"] == model.config_dict()
                and payload["strategy"] == protocol["strategies"][endpoint["strategy"]]["config"]
                and payload["optimizer_updates"] == payload["consumed_base_exposures"] == payload["consumed_view_exposures"] == 0
                and payload["backbone_state_sha256"] == initial_h0
                and _tree_hash(payload["backbone_state"]) == _tree_hash(model.backbone.state_dict()), "NONE must be the real zero-update paired initialization")
        updates = 0
    else:
        cfg, counters = payload["config"], payload["counters"]
        n, epochs = protocol["data_coverage"]["actual_qualified_train_records"], protocol["training"]["epochs"]
        require(payload.get("schema_version") == "phase1_full_corpus_checkpoint_v1" and payload["status"] == "complete"
                and payload["config_sha256"] == digest(cfg) and cfg["variant"] == endpoint["variant"]
                and cfg["seed"] == seed and cfg["epochs"] == epochs == 3
                and cfg["strategy"] == protocol["strategies"][endpoint["strategy"]]["config"]
                and cfg["bindings"]["protocol_sha256"] == protocol["content_sha256"]
                and cfg["bindings"]["source_sha256"] == protocol["source"]["source_sha256"]
                and cfg["bindings"]["initial_encoder_sha256"] == initial_h0
                and payload["model_config"] == model.config_dict() and payload["initial_model_sha256"] == initial_model,
                "Trained encoder must be the physically bound fixed protocol FINAL")
        require(counters["consumed_base_exposures"] == epochs * n
                and counters["consumed_view_exposures"] == 3 * epochs * n
                and counters["optimizer_updates"] + counters["zero_label_batches"] == counters["consumed_batches"]
                and payload["sampler_state"]["epoch"] == epochs - 1
                and payload["sampler_state"]["samples_consumed"] == n
                and len(payload["completed_epoch_batches"]) == epochs - 1
                and payload["validation_state"] is None, "FINAL lacks complete three-epoch consumed coverage")
        report = payload["last_validation"]
        require(report["scope"] == "full" and report["base_exposure"] == epochs * n
                and report["optimizer_update"] == counters["optimizer_updates"]
                and report["manifest_sha256"] == cfg["bindings"]["full_validation_manifest_sha256"]
                and report["status"] in {"COMPLETE", "COMPLETE_WITH_UNAVAILABLE_TASKS"}, "FINAL full validation is not closed")
        model.load_state_dict(payload["model_state"], strict=True)
        updates = counters["optimizer_updates"]
    model.to(device).eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
        parameter.grad = None
    require(all(not tensor.is_floating_point() or bool(torch.isfinite(tensor).all())
                for tensor in model.state_dict().values() if isinstance(tensor, torch.Tensor)), "Loaded endpoint state is nonfinite")
    binding = {"strategy": endpoint["strategy"], "variant": endpoint["variant"], "pretraining_seed": seed,
        "checkpoint_file_sha256": ref["sha256"], "checkpoint_content_sha256": payload["checkpoint_content_sha256"],
        "shared_initialization_file_sha256": endpoint["initialization"]["sha256"],
        "initial_h0_sha256": initial_h0, "endpoint_h0_sha256": backbone_state_hash(model),
        "actual_pretraining_optimizer_updates": updates,
        "primary_control": "none_zero_update" if endpoint["variant"] == "none" else "fixed_three_full_epoch_base_exposure_FINAL"}
    return model, binding


class NativeH0Cache:
    """One encoder/dataset FP32 cache, shared by all folds and both readouts.

    No targets are serialized into the H0 cache. A cache is an input artifact,
    accounted under the whole-phase quota, not an extra free per-fit allowance.
    """
    def __init__(self, directory, *, expected_catalog_sha256, encoder_binding, store_binding, dataset_id):
        self.root = Path(directory)
        require(self.root.is_dir() and not self.root.is_symlink(), "Owned cache root required")
        catalog_path = self.root / "catalog.json"
        require(file_sha(catalog_path) == expected_catalog_sha256, "Physical H0 catalog differs")
        self.catalog = sealed(json.loads(catalog_path.read_bytes()), "cache_sha256")
        require(self.catalog["schema_version"] == CACHE_SCHEMA and self.catalog["encoder_binding"] == encoder_binding
                and self.catalog["store_binding"] == store_binding and self.catalog["dataset_id"] == dataset_id,
                "Cache is from another encoder/source/dataset")
        require(self.catalog["byte_order"] == sys.byteorder == "little" and self.catalog["dtype"] == "torch.float32", "Feature cache byte order/dtype differs")
        blob = self.root / "h0.f32.bin"
        require(blob.is_file() and not blob.is_symlink() and blob.stat().st_size == self.catalog["h0_bytes"]
                and file_sha(blob) == self.catalog["h0_file_sha256"], "Cached FP32 H0 bytes differ")
        self.records = {row["member_index"]: row for row in self.catalog["records"]}
        require(len(self.records) == len(self.catalog["records"]), "Duplicate cache member")
        self.stream = blob.open("rb")

    def get(self, sample):
        row = self.records[sample.member_index]
        require(row["member_uid"] == sample.member_uid and row["input_sha256"] == native_input_sha(sample)
                and row["provenance_sha256"] == digest(sample.provenance), "Cached H0 native source/coordinates/provenance drift")
        self.stream.seek(row["byte_offset"])
        raw = self.stream.read(row["atoms"] * 384 * 4)
        require(len(raw) == row["atoms"] * 384 * 4 and hashlib.sha256(raw).hexdigest() == row["h0_sha256"], "Cached member H0 bytes differ")
        h0 = torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(row["atoms"], 384)
        require(bool(torch.isfinite(h0).all()), "Cached H0 is nonfinite")
        return h0

    def close(self):
        self.stream.close()


def prepare_h0_cache(model, store, fit, *, encoder_binding, store_binding, directory,
                     cache_cap_bytes, max_atoms_per_forward, wall_check):
    """Stream every source member once; never filter by a target or task value."""
    _, roles = validate_store_group(store, fit)
    indices = sorted(set(index for view in roles.values() for index in view))
    root = Path(directory)
    require(sys.byteorder == "little", "The declared FP32 feature cache format requires little-endian host bytes")
    root.mkdir(parents=True, exist_ok=False)
    before = _tree_hash(model.state_dict())
    records, unavailable, byte_offset = [], [], 0
    model.eval()
    device = next(model.parameters()).device
    with (root / "h0.f32.bin").open("xb") as stream, torch.no_grad():
        for index in indices:
            wall_check()
            sample = store.get(fit["dataset_id"], index)
            validate_sample(sample, fit)
            if not sample.geometry_ready:
                unavailable.append({"member_index": index, "member_uid": sample.member_uid,
                                    "reason": sample.unavailable_reason})
                continue
            n = sample.x.numel()
            require(n <= max_atoms_per_forward, "Native member exceeds declared H0 forward cap; no dropping or replacement")
            safe = Data(x=sample.x.to(device).clone(), pos=sample.pos.to(device).clone(),
                        batch=torch.zeros(n, dtype=torch.long, device=device),
                        ptr=torch.tensor([0, n], dtype=torch.long, device=device))
            input_hash = native_input_sha(sample)
            h0 = model.encode_atoms(safe)
            require(h0.shape == (n, 384) and h0.dtype == torch.float32 and bool(torch.isfinite(h0).all()), "Actual native384 H0 forward failed")
            raw = h0.detach().cpu().contiguous().numpy().tobytes()
            require(byte_offset + len(raw) <= cache_cap_bytes, "Whole-phase H0 cache allowance exhausted")
            stream.write(raw)
            records.append({"member_index": index, "member_uid": sample.member_uid, "atoms": n,
                "byte_offset": byte_offset, "h0_sha256": hashlib.sha256(raw).hexdigest(),
                "input_sha256": input_hash, "provenance_sha256": digest(sample.provenance)})
            byte_offset += len(raw)
            require(native_input_sha(sample) == input_hash, "H0 extraction mutated source input")
            del safe, h0, raw
        stream.flush()
        os.fsync(stream.fileno())
    require(_tree_hash(model.state_dict()) == before and all(parameter.grad is None for parameter in model.parameters()), "Frozen encoder state/gradient changed")
    catalog = {"schema_version": CACHE_SCHEMA, "dataset_id": fit["dataset_id"],
        "byte_order": sys.byteorder, "dtype": "torch.float32",
        "encoder_binding": deepcopy(encoder_binding), "store_binding": deepcopy(store_binding),
        "records": records, "unavailable": unavailable, "native_inventory_members": len(indices),
        "h0_bytes": byte_offset, "h0_file_sha256": file_sha(root / "h0.f32.bin"),
        "representation": "actual frozen encode_atoms(x,pos,batch,ptr) FP32 native row order",
        "target_values_in_feature_cache": False, "encoder_state_sha256": before}
    catalog["cache_sha256"] = digest(catalog)
    require(byte_offset + len(canonical(catalog)) + 1 <= cache_cap_bytes, "Cache metadata plus features exceed accounted allowance")
    write_json(root / "catalog.json", catalog)
    return {"path": str(root), "catalog_sha256": file_sha(root / "catalog.json"), "cache_sha256": catalog["cache_sha256"]}


def role_members(store, fit, contract, role):
    """Validate once per operation, avoiding full 100k-member deepcopy per B32."""
    require(role in ROLES, "Explicit formal role required")
    actual = store.view(fit["dataset_id"], fit["fold_id"], role)
    require(type(actual) is tuple and len(set(actual)) == len(actual), "Original ordered role view differs")
    lookup = dict(zip(actual, contract["ordered_members"][role], strict=True))
    return actual, lookup


def cached_batch(store, cache, fit, indices, *, role, role_uid_lookup, device):
    require(role in ROLES, "Explicit formal role required")
    require(type(role_uid_lookup) is dict, "Previously checked role/UID lookup required")
    require(0 < len(indices) <= 32 and len(set(indices)) == len(indices), "Fixed B32 native minibatch required")
    samples, features = [], []
    for index in indices:
        require(index in role_uid_lookup, "Member is outside the actual frozen role view")
        sample = store.get(fit["dataset_id"], index)
        validate_sample(sample, fit, expected_uid=role_uid_lookup[index])
        require(sample.geometry_ready, "Unready geometry entered model input")
        samples.append(sample)
        features.append(cache.get(sample))
    lengths = [sample.x.numel() for sample in samples]
    ptr = torch.tensor([0] + list(_prefix_sum(lengths)), dtype=torch.long, device=device)
    batch = torch.repeat_interleave(torch.arange(len(samples), device=device), torch.tensor(lengths, device=device))
    return {"h0": torch.cat(features).to(device), "batch": batch, "ptr": ptr,
        "source_atom_ids": torch.cat([sample.source_atom_ids for sample in samples]).to(device),
        "targets": torch.cat([sample.targets for sample in samples]).to(device),
        "candidate_mask": torch.cat([sample.candidate_mask for sample in samples]).to(device),
        "supervision_mask": torch.cat([sample.supervision_mask for sample in samples]).to(device),
        "member_uids": tuple(sample.member_uid for sample in samples), "indices": tuple(indices),
        "role": role, "native_input_sha256": tuple(native_input_sha(sample) for sample in samples)}


def _prefix_sum(values):
    total = 0
    for value in values:
        total += value
        yield total


def forward_readout(readout, batch):
    output = readout(batch["h0"], source_atom_ids=batch["source_atom_ids"], batch=batch["batch"], ptr=batch["ptr"])
    require(torch.equal(output.ptr, batch["ptr"]) and bool(torch.isfinite(output.predictions).all()), "Actual readout source partition/finite output failed")
    if readout.output_level == "atom":
        require(torch.equal(output.source_atom_ids, batch["source_atom_ids"]) and torch.equal(output.graph_ids, batch["batch"]), "Actual atom output loses native source map")
    else:
        require(torch.equal(output.graph_ids, torch.arange(len(batch["member_uids"]), device=batch["h0"].device)), "Graph readout output order differs")
    return output.predictions


def observed_loss(predictions, batch, normalization, *, level):
    mask = batch["supervision_mask"] & batch["candidate_mask"]
    counts = [int(mask[:, task].sum()) for task in range(mask.shape[1])]
    losses, raw = [], []
    for task, count in enumerate(counts):
        if not count:
            raw.append(None)
            continue
        require(normalization["availability"][task], "An unavailable train-fitted task acquired an optimizer label")
        active, target = mask[:, task], batch["targets"][mask[:, task], task]
        prediction = predictions[active, task]
        if level == "graph":
            mean, scale = normalization["means"][task], normalization["scales"][task]
            value = (prediction - (target - mean) / scale).square().mean()
        else:
            value = torch.nn.functional.binary_cross_entropy_with_logits(prediction, target)
        losses.append(value / len(counts))  # complete fixed task denominator
        raw.append(float(value.detach()))
    require(losses and all(value is None or math.isfinite(value) for value in raw), "No finite observed training task")
    return torch.stack(losses).sum(), raw, counts


def evaluate_outer(readout, store, cache, fit, contract, *, device, encoder_binding, wall_check, metric_cell_bindings=None):
    """Independent test role, actual readout forward; no caller metric input."""
    before = _tree_hash(readout.state_dict())
    metrics, unavailable, seen = {}, [], set()
    tasks = fit["tasks"]
    error_abs, error_sq, counts = [0.] * len(tasks), [0.] * len(tasks), [0] * len(tasks)
    observed_test_counts = [0] * len(tasks)
    states = {task: {name: 0 for name in ("no_candidate", "unknown", "partial_supervision", "no_positive", "evaluable")} for task in tasks}
    hits = {task: {str(k): 0 for k in (1, 2, 3)} for task in tasks}
    sequence = hashlib.sha256()
    masks, scores = hashlib.sha256(), hashlib.sha256()
    eligible = []
    test, test_lookup = role_members(store, fit, contract, "test")
    for index, uid in zip(test, contract["ordered_members"]["test"], strict=True):
        sample = store.get(fit["dataset_id"], index)
        validate_sample(sample, fit, expected_uid=uid)
        require(uid not in seen, "Duplicate test member")
        seen.add(uid)
        if sample.geometry_ready:
            eligible.append(index)
        else:
            unavailable.append({"member_uid": uid, "reason": sample.unavailable_reason})
    readout.eval()
    with torch.no_grad(), torch.random.fork_rng(devices=[0] if str(device).startswith("cuda") else []):
        for start in range(0, len(eligible), 32):
            wall_check()
            batch = cached_batch(store, cache, fit, eligible[start:start + 32], role="test", role_uid_lookup=test_lookup, device=device)
            batch_hash = _tree_hash(batch)
            prediction = forward_readout(readout, batch)
            sequence.update(canonical({"batch_index": start // 32, "typed_batch_sha256": batch_hash}))
            masks.update(canonical({"member_uids": batch["member_uids"], "typed_masks_sha256": _tree_hash(
                {"candidate": batch["candidate_mask"], "supervision": batch["supervision_mask"]})}))
            scores.update(canonical({"member_uids": batch["member_uids"], "typed_prediction_sha256": _tree_hash(prediction)}))
            if fit["output_level"] == "graph":
                for task in range(len(tasks)):
                    active = batch["candidate_mask"][:, task] & batch["supervision_mask"][:, task]
                    observed_test_counts[task] += int(active.sum())
                    if not contract["normalization"]["availability"][task]:
                        continue
                    raw = prediction[active, task].double() * contract["normalization"]["scales"][task]
                    raw += contract["normalization"]["means"][task]
                    error = raw - batch["targets"][active, task].double()
                    counts[task] += int(active.sum())
                    error_abs[task] = math.fsum((error_abs[task], float(error.abs().sum())))
                    error_sq[task] = math.fsum((error_sq[task], float(error.square().sum())))
            else:
                boundaries = batch["ptr"].cpu().tolist()
                cpu_scores, ids = prediction.cpu(), batch["source_atom_ids"].cpu().tolist()
                candidate, observed, target = (batch[name].cpu() for name in ("candidate_mask", "supervision_mask", "targets"))
                for lo, hi in zip(boundaries[:-1], boundaries[1:], strict=True):
                    for t, task in enumerate(tasks):
                        eligible_atoms = torch.nonzero(candidate[lo:hi, t], as_tuple=False).flatten().tolist()
                        known = int(observed[lo:hi, t].sum())
                        state = "no_candidate" if not eligible_atoms else "unknown" if not known else "partial_supervision" if known < len(eligible_atoms) else "evaluable"
                        positives = {ids[lo + atom] for atom in eligible_atoms if state == "evaluable" and target[lo + atom, t].item() == 1}
                        if state == "evaluable" and not positives:
                            state = "no_positive"
                        states[task][state] += 1
                        if state == "evaluable":
                            order = sorted(eligible_atoms, key=lambda atom: (-cpu_scores[lo + atom, t].item(), ids[lo + atom]))
                            for k in (1, 2, 3):
                                hits[task][str(k)] += int(bool(positives.intersection(ids[lo + atom] for atom in order[:min(k, len(order))])))
            require(_tree_hash(batch) == batch_hash, "Test forward mutated source/cached batch tensors")
    require(_tree_hash(readout.state_dict()) == before, "Outer evaluation mutated readout parameters/buffers")
    for t, task in enumerate(tasks):
        if fit["output_level"] == "graph":
            metrics[task] = {"n_valid": counts[t], "n_observed_test_labels": observed_test_counts[t], "MAE": error_abs[t] / counts[t] if counts[t] else None,
                "RMSE": math.sqrt(error_sq[t] / counts[t]) if counts[t] else None,
                "status": "OK" if counts[t] else "NO_VALID_LABELS" if contract["normalization"]["availability"][t] else "NO_TRAIN_LABELS"}
        else:
            n = states[task]["evaluable"]
            available = contract["normalization"]["availability"][t]
            metrics[task] = {"partitions": states[task], "molecule_hit_at_k": {k: value / n if n and available else None for k, value in hits[task].items()},
                "hit_counts": hits[task], "status": "NO_TRAIN_LABELS" if not available else "OK" if n else "NO_EVALUABLE_INSTANCES"}
    result = {"schema_version": REPORT_SCHEMA, "role": "test", "fit": deepcopy(fit),
        "encoder_binding": deepcopy(encoder_binding), "metrics": metrics,
        "native_test_inventory_count": len(test), "geometry_ready_test_count": len(eligible),
        "unready_geometry": unavailable, "computation": "actual cached native FP32 H0 + live fixed FINAL readout",
        "graph_recipe": "FP64 inverse-affine errors, summed observed label errors/counts",
        "som_recipe": "all source candidates; complete supervision; raw logits desc/native ID asc; unknown not negative",
        "actual_test_sequence_sha256": sequence.hexdigest(), "actual_two_mask_sequence_sha256": masks.hexdigest(),
        "actual_prediction_sequence_sha256": scores.hexdigest(), "actual_readout_state_sha256": before,
        "source_contract_sha256": digest(contract), "unavailable_metric_values_remain_null": True,
        "frozen_source_cell_bindings": deepcopy(metric_cell_bindings),
        "runtime_sequence_hashes_are_frozen_mask_oracles": False,
        "paired_statistics_envelope_issued": False}
    result["metric_file_content_sha256"] = digest(result)
    return result


class TypedOfflineJournal:
    """Actual W&B ACK plus an fsynced complete source-typed payload ledger.

    Persistence is claimed only after real closed binary decoding. Source-typed
    equality is exact, including restoration of backend integral float spelling;
    it uses no floating tolerance and never reruns an update to repair telemetry.
    """
    def __init__(self, run, directory, *, maximum_rows, maximum_journal_bytes):
        require(run.settings.mode == "offline" and not getattr(run, "disabled", False), "Functional offline W&B required")
        self.run, self.root = run, Path(directory)
        self.run_dir = Path(run.dir).absolute()
        require(self.run_dir.is_dir() and self.run_dir.resolve().is_relative_to(self.root.resolve()), "Actual W&B run files escape owned fit directory")
        self.maximum_rows, self.maximum_bytes = maximum_rows, maximum_journal_bytes
        self.rows, self.bytes = 0, 0
        self.path = self.root / "typed_history.jsonl"
        self.stream = self.path.open("xb")
        self.finished = False

    def log(self, payload):
        require(not self.finished and self.rows < self.maximum_rows and type(payload) is dict
                and all(type(value) in (str, int, float, bool) for value in payload.values()), "Bounded typed history row required")
        canonical(payload)  # refuses NaN/Inf and unsupported values
        row = {"step": self.rows, "payload": deepcopy(payload), "payload_sha256": digest(payload)}
        encoded = canonical(row) + b"\n"
        require(self.bytes + len(encoded) <= self.maximum_bytes, "Typed readout ledger budget exhausted")
        wire = {**payload, "tracking/payload_sha256": row["payload_sha256"]}
        self.run.log(wire, step=self.rows, commit=True)
        require(self.run.step == self.rows + 1, "Actual W&B cursor did not ACK one committed row")
        self.stream.write(encoded)
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.rows += 1
        self.bytes += len(encoded)

    def finish(self, *, success, decode_history):
        from formal_plan import verify_wire_payload
        require(not self.finished, "Offline history was already finalized")
        self.finished = True
        try:
            self.run.finish(exit_code=0 if success else 1)
        finally:
            self.stream.close()
        if not success:
            return None
        matches = list(self.run_dir.parent.glob("run-*.wandb"))
        require(len(matches) == 1 and matches[0].name == "run-" + self.run.id + ".wandb", "Exact closed W&B binary required")
        decoded = decode_history(matches[0])
        require(type(decoded) is list and len(decoded) == self.rows, "Closed W&B scientific history count differs")
        with self.path.open("rb") as stream:
            for step, (line, observed) in enumerate(zip(stream, decoded, strict=True)):
                expected = json.loads(line)
                require(expected["step"] == step and expected["payload_sha256"] == digest(expected["payload"])
                        and type(observed.get("_step")) is int and observed["_step"] == step
                        and observed.get("tracking/payload_sha256") == expected["payload_sha256"], "Closed W&B ACK/source row seal differs")
                values = {key: value for key, value in observed.items() if key != "tracking/payload_sha256"}
                verify_wire_payload(values, expected["payload"])
        return {"schema_version": "phase1_formal_readout_closed_history_v1", "actual_rows": self.rows,
            "run_id": self.run.id, "run_path": self.run.path, "mode": "offline", "synced": False,
            "run_file_sha256": file_sha(matches[0]), "typed_journal_sha256": file_sha(self.path),
            "source_typed_payload_exact": True, "numeric_tolerance_used": False}


def _make_readout(fit, device):
    with torch.random.fork_rng(devices=[0] if str(device).startswith("cuda") else []):
        torch.manual_seed(fit["readout_seed"])
        if fit["readout"] == MAIN:
            readout = SourceAlignedH0Readout(384, len(fit["tasks"]), output_level=fit["output_level"],
                hidden_dim=64, atom_layers=1, pooling="mean" if fit["output_level"] == "graph" else None)
        else:
            require(fit["readout"] == AUX and fit["output_level"] == "graph", "Only predeclared graph linear complement is supported")
            readout = SourceAlignedLinearGraphReadout(384, len(fit["tasks"]), pooling="mean")
    return readout.to(device)


def validate_readout_binding(contract, fit, readout):
    role = "main" if fit["readout"] == MAIN else "aux"
    binding = contract["readout_binding"][role]
    require(set(binding) == {"config", "config_sha256", "file", "config_hash_recipe", "file_hash_recipe"}
            and binding["config_hash_recipe"] == "canonical finite sorted UTF8 JSON ensure_ascii=false"
            and binding["file_hash_recipe"] == "physical raw JSON file bytes including newline",
            "Actual readout canonical and physical hash domains must remain separate")
    config = readout.config_dict()
    require(canonical(config) == canonical(binding["config"])
            and binding["config_sha256"] == digest(config)
            and canonical(read_bound_json(binding["file"], 64 << 10)) == canonical(config),
            "Actual native384 readout differs from its independently bound physical configuration")
    return deepcopy(binding)


def validate_store_readout_bridge(manifest, protocol, contract, fit):
    """Consume the actual execution sidecar; historical512 hashes stay historical."""
    cells = sealed(read_bound_json(manifest["primary_cells"]), "content_sha256")
    bridge_ref = cells["historical_512_reference_bridge"]
    require(bridge_ref in manifest["input_files"], "Actual readout bridge is outside the physically bound producer inputs")
    bridge = sealed(read_bound_json(bridge_ref), "content_sha256")
    require(bridge["schema_version"] == "phase1_frozen_input_dimension_actual_readout_metadata_bridge_v1"
            and bridge["complete"] is True and bridge["protocol_content_sha256"] == protocol["content_sha256"]
            and bridge["scientific_readout_rules_changed"] is False and bridge["targets_or_dataset_read"] is False
            and bridge["immutable_protocol_file_modified"] is False,
            "Historical512 to actual384 execution binding is not an actual frozen-rule bridge")
    role = "main" if fit["readout"] == MAIN else "aux"
    bridge_role = "main" if role == "main" else "auxiliary"
    expected = bridge["configs"][fit["dataset_id"]][bridge_role]
    binding = contract["readout_binding"][role]
    require(canonical(binding["config"]) == canonical(expected)
            and binding["config_sha256"] == bridge["configs"][fit["dataset_id"]][bridge_role + "_config_sha256"]
            and expected["input_dim"] == 384,
            "Physical consumer readout does not match the actual384 metadata bridge")
    return deepcopy(bridge_ref)


def frozen_metric_cells(manifest, protocol, contract, fit):
    """Keep actual239/269 source-mask bindings distinct from forward-sequence hashes."""
    document = sealed(read_bound_json(manifest["primary_cells"]), "content_sha256")
    require(document["cell_count"] == 239 and document["all_report_cells"] == 269
            and document["all_report_endpoints"] == 35 and document["all_cells_complete"] is True,
            "Complete primary/all-report source cell oracle required")
    fold = "official_test" if fit["dataset_id"] == "expansionrx" else fit["fold_id"]
    result = []
    for endpoint, primary in zip(fit["endpoints"], fit["primary_inference"], strict=True):
        definition = (document["endpoints"] if primary else document["auxiliary_report_endpoints"])[endpoint]
        matches = [cell for cell in definition["cells"] if cell["fold_id"] == fold
                   and type(cell["readout_seed"]) is int and cell["readout_seed"] == fit["readout_seed"]]
        require(len(matches) == 1 and matches[0]["complete"] is True, "Actual selected original cell is missing/incomplete")
        cell = matches[0]
        for name in ("sample_set_sha256", "label_mask_sha256"):
            require(type(cell[name]) is str and len(cell[name]) == 64
                    and all(character in "0123456789abcdef" for character in cell[name]), "Actual source cell SHA malformed")
        if primary:
            declared = protocol["downstream"]["analysis_rules"]["endpoints"][endpoint]
            require(any(original["fold_id"] == fold and original["readout_seed"] == fit["readout_seed"]
                        for original in declared["cells"]), "Cell is outside frozen original analysis rules")
        role = "main" if fit["readout"] == MAIN else "aux"
        require(definition["readout_config_sha256"] == contract["readout_binding"]["main"]["config_sha256"],
                "Main source-mask cell readout binding differs from actual384 contract")
        result.append({"endpoint_id": endpoint, "fold_id": fold, "readout_seed": fit["readout_seed"],
            "primary_inference": bool(primary and fit["readout"] == MAIN),
            "sample_set_sha256": cell["sample_set_sha256"], "label_mask_sha256": cell["label_mask_sha256"],
            "source_cell_file": deepcopy(manifest["primary_cells"]), "mask_hash_recipe": document["mask_hash_recipe"],
            "main_mask_oracle_readout_config_sha256": definition["readout_config_sha256"],
            "selected_readout_config_sha256": contract["readout_binding"][role]["config_sha256"],
            "forward_sequence_digest_is_source_mask_hash": False})
    return result


def train_fixed_readout(store, cache, fit, contract, *, protocol, encoder_binding, tracker,
                        directory, device, wall_check, resume_ref=None):
    """Natural final partial minibatch, fixed task denominator, 20 epochs FINAL."""
    require(torch.get_default_dtype() == torch.float32, "FP32 fixed readout recipe required")
    eligible, unready, unknown = [], [], []
    train_indices, train_lookup = role_members(store, fit, contract, "train")
    for index, uid in zip(train_indices, contract["ordered_members"]["train"], strict=True):
        wall_check()
        sample = store.get(fit["dataset_id"], index)
        validate_sample(sample, fit, expected_uid=uid)
        if not sample.geometry_ready:
            unready.append(uid)
        elif not bool(sample.supervision_mask.any()):
            unknown.append(uid)
        else:
            eligible.append(index)
    readout = _make_readout(fit, device)
    readout_binding = validate_readout_binding(contract, fit, readout)
    initial_state = _tree_hash(readout.state_dict())
    batches = [eligible[start:start + 32] for start in range(0, len(eligible), 32)]
    total_updates = 20 * len(batches)
    options = protocol["downstream"]["optimization_policy"]["optimizer"]
    require(canonical(contract["optimizer"]) == canonical(protocol["downstream"]["optimization_policy"]),
            "Physical data contract changed the fixed readout optimization recipe")
    require(options["implementation"] == "single_tensor_adamw_v1", "Frozen single-tensor optimizer required")
    optimizer = torch.optim.AdamW(readout.parameters(), lr=options["lr"], betas=tuple(options["betas"]),
        eps=options["eps"], weight_decay=options["weight_decay"], amsgrad=options["amsgrad"], foreach=False, fused=False)
    config = {"schema_version": FIT_SCHEMA, "fit": deepcopy(fit), "encoder_binding": deepcopy(encoder_binding),
        "protocol_content_sha256": protocol["content_sha256"], "source_contract_sha256": digest(contract),
        "cache_content_sha256": cache.catalog["cache_sha256"], "actual_readout_config": readout.config_dict(),
        "readout_config_sha256": digest(readout.config_dict()), "initial_readout_state_sha256": initial_state,
        "readout_physical_binding": readout_binding,
        "train_order_sha256": digest({"recipe": "source_role_order_retained_known_geometry_v1", "member_indices": eligible}),
        "train_only_normalization": deepcopy(contract["normalization"]), "optimizer": deepcopy(options),
        "total_updates": total_updates, "epochs": 20, "batch_graphs": 32,
        "retained_train_count": len(eligible), "selection": "FIXED_20_EPOCH_FINAL",
        "heldout_model_selection": False}
    root = Path(directory)
    counters = {"optimizer_updates": 0, "sample_exposures": 0, "native_atom_exposures": 0,
                "task_observed_label_exposures": [0] * len(fit["tasks"])}
    rng_state = {"cpu": torch.Generator(device="cpu").manual_seed(fit["readout_seed"]).get_state(),
        "cuda": torch.Generator(device=device).manual_seed(fit["readout_seed"]).get_state().cpu()
                if str(device).startswith("cuda") else None}
    parent = None
    if resume_ref is not None:
        require(file_sha(resume_ref["path"]) == resume_ref["sha256"]
                and Path(resume_ref["path"]).stat().st_size == resume_ref["bytes"]
                and resume_ref["bytes"] <= 64 << 20, "Physical readout resume bytes differ")
        payload = torch.load(resume_ref["path"], map_location="cpu", weights_only=True)
        require(payload["checkpoint_content_sha256"] == checkpoint_content_sha256(payload)
                and payload["schema_version"] == FIT_SCHEMA and payload["config"] == config
                and payload["status"] in ("partial", "complete")
                and payload["config_sha256"] == digest(config), "Readout resume contract/typed seal differs")
        counters = deepcopy(payload["counters"])
        updates = counters["optimizer_updates"]
        require(type(updates) is int and 0 <= updates <= total_updates
                and (payload["status"] != "complete" or updates == total_updates), "Readout resume cursor is not a valid fixed endpoint")
        expected_exposure = sum(len(batches[index % len(batches)]) for index in range(updates)) if batches else 0
        require(counters["sample_exposures"] == expected_exposure, "Readout resume source exposure/cursor differs")
        require(type(counters["native_atom_exposures"]) is int and counters["native_atom_exposures"] >= 0
                and type(counters["task_observed_label_exposures"]) is list
                and len(counters["task_observed_label_exposures"]) == len(fit["tasks"])
                and all(type(value) is int and value >= 0 for value in counters["task_observed_label_exposures"]), "Resume observed-label/native exposure counters differ")
        require(set(payload["rng_state"]) == {"cpu", "cuda"}, "Complete readout RNG checkpoint required")
        for name, value in payload["rng_state"].items():
            if name == "cuda" and not str(device).startswith("cuda"):
                require(value is None, "CPU readout checkpoint has a CUDA RNG")
            else:
                require(isinstance(value, torch.Tensor) and value.dtype == torch.uint8 and value.device.type == "cpu"
                        and value.ndim == 1, "Readout RNG state type differs")
                generator = torch.Generator(device=device if name == "cuda" else "cpu")
                generator.set_state(value)
        rng_state = _copy_cpu(payload["rng_state"])
        # Candidate copies reject invalid state before changing the live receiver.
        candidate = _make_readout(fit, device)
        candidate.load_state_dict(payload["readout_state"], strict=True)
        opt_candidate = torch.optim.AdamW(candidate.parameters(), lr=options["lr"], betas=tuple(options["betas"]),
            eps=options["eps"], weight_decay=options["weight_decay"], amsgrad=options["amsgrad"], foreach=False, fused=False)
        require(payload["optimizer_state"]["param_groups"] == opt_candidate.state_dict()["param_groups"], "Resume AdamW parameter/options changed")
        parameters = list(candidate.parameters())
        require(set(payload["optimizer_state"]["state"]) == (set(range(len(parameters))) if updates else set()), "Complete readout AdamW moments required")
        for index, moments in payload["optimizer_state"]["state"].items():
            names = {"step", "exp_avg", "exp_avg_sq"} | ({"max_exp_avg_sq"} if options["amsgrad"] else set())
            require(set(moments) == names and isinstance(moments["step"], torch.Tensor)
                    and moments["step"].numel() == 1 and float(moments["step"]) == updates, "Resume optimizer step differs")
            for name in names - {"step"}:
                tensor = moments[name]
                require(isinstance(tensor, torch.Tensor) and tensor.dtype == torch.float32
                        and tensor.shape == parameters[index].shape and bool(torch.isfinite(tensor).all()), "Readout moments are incomplete/nonfinite")
        readout.load_state_dict(payload["readout_state"], strict=True)
        optimizer.load_state_dict(payload["optimizer_state"])
        parent = {"checkpoint_file_sha256": resume_ref["sha256"], "run_id": payload["tracking"]["run_id"]}
        require(parent["run_id"] != tracker.run.id, "Resumed offline fit needs a new real run ID")
    require(all(parameter.requires_grad for parameter in readout.parameters()), "Readout gradients disabled")
    status = "partial"
    def set_status(value):
        nonlocal status
        status = value
    @contextmanager
    def owned_rng():
        with torch.random.fork_rng(devices=[0] if str(device).startswith("cuda") else []):
            torch.set_rng_state(rng_state["cpu"])
            if rng_state["cuda"] is not None:
                torch.cuda.set_rng_state(rng_state["cuda"], 0)
            yield
    def save_checkpoint(destination="latest.pt"):
        state = {"schema_version": FIT_SCHEMA, "status": status, "config": deepcopy(config),
            "config_sha256": digest(config), "counters": deepcopy(counters), "readout_state": _copy_cpu(readout.state_dict()),
            "optimizer_state": _copy_cpu(optimizer.state_dict()),
            "rng_state": {"cpu": torch.get_rng_state().clone(),
                          "cuda": torch.cuda.get_rng_state(0).cpu() if str(device).startswith("cuda") else None},
            "tracking": {"run_id": tracker.run.id, "run_path": tracker.run.path,
                         "next_step": tracker.rows, "parent": deepcopy(parent)}}
        state["checkpoint_content_sha256"] = checkpoint_content_sha256(state)
        pending = root / "latest.pending.pt"
        with pending.open("xb") as stream:
            torch.save(state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, root / destination)
    with owned_rng():
        return _run_fixed_updates(readout, optimizer, counters, batches, total_updates, store, cache, fit,
            contract, tracker, root, device, wall_check, save_checkpoint, status_ref=set_status,
            config=config, unready=unready, unknown=unknown, parent=parent, train_lookup=train_lookup)


def _run_fixed_updates(readout, optimizer, counters, batches, total_updates, store, cache, fit,
                       contract, tracker, root, device, wall_check, save_checkpoint, status_ref,
                       *, config, unready, unknown, parent, train_lookup):
    # Keep the actual optimization loop in one place. The save callback is owned
    # by the caller and captures complete config/state/RNG at each real cursor.
    try:
        for update in range(counters["optimizer_updates"], total_updates):
            wall_check()
            batch_index, epoch = update % len(batches), update // len(batches)
            batch = cached_batch(store, cache, fit, batches[batch_index], role="train", role_uid_lookup=train_lookup, device=device)
            before_input = _tree_hash(batch)
            readout.train()
            optimizer.zero_grad(set_to_none=True)
            prediction = forward_readout(readout, batch)
            loss, losses, counts = observed_loss(prediction, batch, contract["normalization"], level=fit["output_level"])
            loss.backward()
            require(all(parameter.grad is not None and bool(torch.isfinite(parameter.grad).all()) for parameter in readout.parameters()), "Actual readout gradients missing/nonfinite")
            optimizer.step()
            require(all(bool(torch.isfinite(parameter).all()) for parameter in readout.parameters()), "Readout update is nonfinite")
            counters["optimizer_updates"] += 1
            counters["sample_exposures"] += len(batch["member_uids"])
            counters["native_atom_exposures"] += batch["h0"].shape[0]
            counters["task_observed_label_exposures"] = [left + right for left, right in zip(counters["task_observed_label_exposures"], counts, strict=True)]
            require(_tree_hash(batch) == before_input, "Readout training mutated H0/source/mask tensors")
            row = {"readout/optimizer_updates": counters["optimizer_updates"], "readout/epoch": epoch,
                "readout/batch_index": batch_index, "readout/loss": float(loss.detach()),
                "readout/sample_exposures": counters["sample_exposures"],
                "readout/native_atom_exposures": counters["native_atom_exposures"]}
            for t, task in enumerate(fit["tasks"]):
                row["readout/observed/" + task] = counts[t]
                if losses[t] is not None:
                    row["readout/normalized_loss/" + task] = losses[t]
            tracker.log(row)
            if batch_index + 1 == len(batches):
                save_checkpoint()
        status_ref("complete")
        require(counters["sample_exposures"] == 20 * config["retained_train_count"], "Fixed twenty-epoch eligible source coverage differs")
        save_checkpoint()
    except Exception:
        # Actual updated state survives telemetry/budget failure. Its checkpoint
        # does not assert persistent W&B closure and is never silently replayed.
        status_ref("failed")
        save_checkpoint("failed_state.pt")
        raise
    return readout, {"status": "COMPLETE" if config["retained_train_count"] else "NO_TRAIN_LABELS", "config": config,
        "counters": counters, "unready_train_geometry": unready, "all_unknown_train_members": unknown,
        "parent_lineage": parent, "actual_final_readout_state_sha256": _tree_hash(readout.state_dict()),
        "checkpoint_file_sha256": file_sha(root / "latest.pt"), "source_order_preserved": True}
