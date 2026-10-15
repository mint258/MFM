"""In-memory, source-aligned downstream optimization; NOT_FROZEN preparation.

The caller owns data/geometry/target selection and persistent tracking. This
core owns the supplied model's modes/requires_grad and updates only its H0
backbone (finetune) plus the readout. It does not select checkpoints, fit
normalizers, access files, freeze a protocol or authorize formal execution.
RNG replay covers CPU/single-device Torch, conditional on identical environment
and deterministic kernels; it does not cover Python/NumPy or arbitrary loaders.
Wall checks are cooperative. An outer supervisor must bound blocking operations,
RSS and output, including the temporary copies needed for atomic resume.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import time

import torch
from torch import Tensor
from torch_geometric.data import Data

from ..model.shared import SharedBackboneMFM
from .downstream_readout import SourceAlignedH0Readout, SourceAlignedLinearGraphReadout
from .identity import canonical_hash


TRAINING_SCHEMA = "phase1_downstream_training_v1"
CHECKPOINT_SCHEMA = "phase1_downstream_training_checkpoint_v1"


class DownstreamTrainingError(RuntimeError):
    """The explicit optimization, data, tracking or resume contract failed."""


@dataclass(frozen=True)
class DownstreamTrainBatch:
    encoder_batch: Data
    sample_ids: tuple[str, ...]
    source_atom_ids: Tensor
    targets: Tensor
    candidate_mask: Tensor
    supervision_mask: Tensor
    role: str


def _require(condition, message):
    if not condition:
        raise DownstreamTrainingError(message)


def _integer(value, name, minimum=1):
    _require(type(value) is int and value >= minimum, name + " must be an explicit integer")
    return value


def _number(value, name, *, positive=False, nonnegative=False):
    _require(type(value) in (int, float), name + " must be numeric")
    try:
        _require(math.isfinite(value), name + " must be finite")
    except OverflowError as exc:
        raise DownstreamTrainingError(name + " exceeds finite numeric range") from exc
    _require(not positive or value > 0, name + " must be positive")
    _require(not nonnegative or value >= 0, name + " must be nonnegative")
    return float(value)


def _weight_sum(weights):
    try:
        value = math.fsum(weights)
    except OverflowError as exc:
        raise DownstreamTrainingError("Task weight sum overflows") from exc
    _require(math.isfinite(value) and value > 0, "Task weight sum is invalid")
    return value


def _keys(value, keys, name):
    _require(type(value) is dict and set(value) == set(keys), name + " requires its exact contract fields")


def _sha(value, name):
    _require(isinstance(value, str) and len(value) == 64
             and all(char in "0123456789abcdef" for char in value), name + " must be a lowercase SHA256")
    return value


def validate_training_config(config):
    """Validate all scientific choices explicitly; return detached JSON config."""
    _keys(config, ("schema_version", "mode", "total_updates", "seed", "device", "readout_config",
                   "tasks", "loss", "reduction", "task_weights", "normalization", "optimizer",
                   "gradient_clip_norm", "caps", "bindings"), "config")
    try:
        value = json.loads(json.dumps(config, allow_nan=False))
    except (TypeError, ValueError, RecursionError) as exc:
        raise DownstreamTrainingError("config must be finite JSON metadata") from exc
    _require(value["schema_version"] == TRAINING_SCHEMA, "Unsupported training schema")
    _require(value["mode"] in ("frozen", "finetune"), "Explicit frozen/finetune mode required")
    _require(value["device"] in ("cpu", "cuda:0"), "Only explicit CPU or single CUDA:0 is supported")
    _integer(value["total_updates"], "total_updates")
    _require(_integer(value["seed"], "seed", 0) < 2 ** 63, "seed exceeds Torch seed scope")
    _require(value["loss"] in ("mse", "bce_logits"), "Explicit supported loss required")
    _require(value["reduction"] == "task_then_observed_label_mean", "Unsupported reduction")
    tasks = value["tasks"]
    _require(type(tasks) is list and 0 < len(tasks) <= 64
             and all(isinstance(task, str) and 0 < len(task) <= 128 for task in tasks)
             and len(set(tasks)) == len(tasks), "Tasks must be a bounded unique ordered list")
    weights = value["task_weights"]
    _require(type(weights) is list and len(weights) == len(tasks), "One fixed weight per task is required")
    weights = [_number(weight, "task_weight", positive=True) for weight in weights]
    denominator = _weight_sum(weights)
    coefficients = torch.tensor([weight / denominator for weight in weights], dtype=torch.float32)
    _require(bool(torch.isfinite(coefficients).all()) and bool((coefficients > 0).all()),
             "Every enabled task coefficient must remain positive finite in FP32")
    bindings = value["bindings"]
    _keys(bindings, ("train_data_sha256", "split_manifest_sha256", "normalizer_sha256",
                     "source_sha256", "initial_encoder_sha256"), "bindings")
    for name, digest in bindings.items():
        _sha(digest, name)
    norm = value["normalization"]
    _keys(norm, ("kind", "means", "scales", "train_only", "train_data_sha256",
                 "split_manifest_sha256", "fit_source_sha256"), "normalization")
    _require(norm["kind"] in ("identity", "train_affine") and norm["train_only"] is True,
             "Explicit train-only normalization declaration required")
    _require(norm["train_data_sha256"] == bindings["train_data_sha256"]
             and norm["split_manifest_sha256"] == bindings["split_manifest_sha256"],
             "Normalizer declares another training/split source")
    _sha(norm["fit_source_sha256"], "normalizer fit source")
    _require(canonical_hash(norm) == bindings["normalizer_sha256"], "Normalizer contract hash differs")
    _require(type(norm["means"]) is list and type(norm["scales"]) is list
             and len(norm["means"]) == len(norm["scales"]) == len(tasks), "Normalizer task dimensions differ")
    means = [_number(item, "normalization mean") for item in norm["means"]]
    scales = [_number(item, "normalization scale", positive=True) for item in norm["scales"]]
    _require(bool(torch.isfinite(torch.tensor(means, dtype=torch.float32)).all())
             and bool(torch.isfinite(torch.tensor(scales, dtype=torch.float32)).all())
             and bool((torch.tensor(scales, dtype=torch.float32) > 0).all()), "Normalizer is invalid in FP32")
    if norm["kind"] == "identity" or value["loss"] == "bce_logits":
        _require(all(item == 0 for item in means) and all(item == 1 for item in scales)
                 and norm["kind"] == "identity", "BCE/identity normalization requires exactly mean=0, scale=1")
    opt = value["optimizer"]
    _keys(opt, ("implementation", "lr", "betas", "eps", "weight_decay", "amsgrad"), "optimizer")
    _require(opt["implementation"] == "single_tensor_adamw_v1", "Unsupported optimizer implementation")
    _number(opt["lr"], "learning rate", positive=True)
    _number(opt["eps"], "epsilon", positive=True)
    _number(opt["weight_decay"], "weight decay", nonnegative=True)
    _require(type(opt["amsgrad"]) is bool and type(opt["betas"]) is list and len(opt["betas"]) == 2,
             "Explicit AdamW amsgrad and two betas required")
    for beta in opt["betas"]:
        _require(0 <= _number(beta, "AdamW beta") < 1, "AdamW beta outside [0,1)")
    if value["gradient_clip_norm"] is not None:
        _number(value["gradient_clip_norm"], "gradient cap", positive=True)
    caps = value["caps"]
    _keys(caps, ("wall_seconds", "max_sequence_batches", "max_graphs_per_batch",
                 "max_atoms_per_batch", "max_unique_samples"), "caps")
    _number(caps["wall_seconds"], "wall cap", positive=True)
    for name in set(caps) - {"wall_seconds"}:
        _integer(caps[name], name)
    _require(type(value["readout_config"]) is dict, "Explicit full readout config required")
    return value


def _copy_cpu(value):
    if isinstance(value, Tensor):
        return value.detach().cpu().clone()
    if isinstance(value, dict):
        return {key: _copy_cpu(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_cpu(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_copy_cpu(item) for item in value)
    return deepcopy(value)


def _tree_hash(value):
    digest = hashlib.sha256()
    def add(item):
        if isinstance(item, Tensor):
            tensor = item.detach().cpu().contiguous()
            _require(tensor.layout == torch.strided, "Sparse checkpoint tensors are unsupported")
            digest.update(f"tensor:{tensor.dtype}:{tuple(tensor.shape)}\n".encode())
            digest.update(tensor.reshape(-1).view(torch.uint8).numpy().tobytes())
        elif isinstance(item, dict):
            digest.update(b"dict{")
            for key in sorted(item, key=lambda entry: (type(entry).__name__, repr(entry))):
                add(key)
                add(item[key])
            digest.update(b"}")
        elif isinstance(item, (tuple, list)):
            digest.update((type(item).__name__ + "[").encode())
            for entry in item:
                add(entry)
            digest.update(b"]")
        else:
            digest.update((type(item).__name__ + ":" + json.dumps(item, allow_nan=False)).encode())
    try:
        add(value)
    except (TypeError, ValueError, RecursionError) as exc:
        raise DownstreamTrainingError("Checkpoint contains unsupported state") from exc
    return digest.hexdigest()


def checkpoint_content_sha256(payload):
    return _tree_hash({key: value for key, value in payload.items() if key != "checkpoint_content_sha256"})


def _encoder_hash(model):
    # Exact existing formal_runtime.backbone_state_hash tensor-byte recipe.
    digest = hashlib.sha256()
    for name, value in sorted(model.backbone.state_dict().items()):
        _require(isinstance(value, Tensor), "Backbone state must consist of tensors")
        tensor = value.detach().cpu().contiguous()
        digest.update(f"{name}:{tensor.dtype}:{tuple(tensor.shape)}\n".encode())
        digest.update(tensor.reshape(-1).view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def _batch_spec(item, config, model, *, expected_role, require_observed):
    _require(expected_role in ("train", "train_inner_validation"), "Only explicit train or train_inner_validation roles are supported")
    _require(type(require_observed) is bool, "require_observed must be an explicit boolean")
    _require(isinstance(item, DownstreamTrainBatch) and item.role == expected_role,
             "Batch role differs from the explicit consumer role")
    data, device, tasks = item.encoder_batch, torch.device(config["device"]), len(config["tasks"])
    _require(isinstance(data, Data), "encoder_batch must be PyG Data")
    x, pos, batch, ptr = (getattr(data, name, None) for name in ("x", "pos", "batch", "ptr"))
    _require(isinstance(x, Tensor) and x.dtype == torch.long and x.ndim == 1 and x.numel() > 0,
             "x must be nonempty 1D long zero-based atom IDs")
    n = x.numel()
    _require(n <= config["caps"]["max_atoms_per_batch"] and x.device == device
             and bool(((x >= 0) & (x < model.pad_elem_index)).all()), "Illegal atom IDs/device/atom budget")
    _require(isinstance(pos, Tensor) and pos.dtype == torch.float32 and pos.shape == (n, 3)
             and pos.device == device and not pos.requires_grad and bool(torch.isfinite(pos).all()),
             "pos must be finite non-learned FP32 [N,3]")
    for name, tensor in (("batch", batch), ("ptr", ptr), ("source_atom_ids", item.source_atom_ids)):
        _require(isinstance(tensor, Tensor) and tensor.dtype == torch.long and tensor.ndim == 1
                 and tensor.device == device, name + " must be a same-device long vector")
    _require(2 <= ptr.numel() <= n + 1 and ptr[0].item() == 0 and ptr[-1].item() == n
             and bool((ptr[1:] > ptr[:-1]).all()), "ptr must cover nonempty complete graphs")
    graphs = ptr.numel() - 1
    _require(graphs <= config["caps"]["max_graphs_per_batch"]
             and batch.shape == (n,) and item.source_atom_ids.shape == (n,), "Graph/atom coverage or cap differs")
    expected = torch.repeat_interleave(torch.arange(graphs, device=device), ptr[1:] - ptr[:-1])
    _require(torch.equal(batch, expected), "batch/ptr graph partition differs")
    for start, end in zip(ptr[:-1].tolist(), ptr[1:].tolist()):
        _require(torch.equal(torch.sort(item.source_atom_ids[start:end]).values,
                             torch.arange(end - start, device=device)), "Source IDs must completely permute each native graph")
    ids = item.sample_ids
    _require(type(ids) is tuple and len(ids) == graphs
             and all(type(sample) is str and 0 < len(sample) <= 256 for sample in ids)
             and len(set(ids)) == graphs, "Explicit unique graph sample IDs required")
    level = config["readout_config"].get("output_level")
    _require(level in ("atom", "graph"), "Explicit atom or graph readout level required")
    rows = n if level == "atom" else graphs
    _require(isinstance(item.targets, Tensor) and item.targets.dtype == torch.float32
             and item.targets.shape == (rows, tasks) and item.targets.device == device
             and not item.targets.requires_grad, "Targets require native/graph FP32 [rows,tasks]")
    for name, mask in (("candidate", item.candidate_mask), ("supervision", item.supervision_mask)):
        _require(isinstance(mask, Tensor) and mask.dtype == torch.bool
                 and mask.shape == item.targets.shape and mask.device == device, name + " mask shape/dtype/device differs")
    _require(not bool((item.supervision_mask & ~item.candidate_mask).any()), "Supervision must be a candidate subset")
    active = item.targets[item.supervision_mask]
    _require(not require_observed or active.numel() > 0, "A training batch requires observed labels")
    _require(bool(torch.isfinite(active).all()), "Observed labels must be finite")
    if config["loss"] == "bce_logits":
        _require(bool(((active == 0) | (active == 1)).all()), "BCE targets must be exactly binary")
    content = {"role": item.role, "sample_ids": ids, "x": x, "pos": pos, "batch": batch, "ptr": ptr,
               "source_atom_ids": item.source_atom_ids, "targets": item.targets,
               "candidate_mask": item.candidate_mask, "supervision_mask": item.supervision_mask}
    return {"hash": _tree_hash(content), "samples": graphs, "atoms": n,
            "valid": [int(item.supervision_mask[:, task].sum()) for task in range(tasks)]}


def validate_downstream_batch(batch, config, model, *, expected_role, require_observed):
    """Validate supplied structure/target tensors without changing their role.

    The role must explicitly be train or train_inner_validation. Setting
    require_observed=False permits zero supervision, for which consumers must
    report an unavailable metric rather than invent targets. Active targets,
    masks, native IDs, graph boundaries, elements and coordinates retain the
    same checks used by optimization. The returned hash/counts bind the supplied
    tensors; they do not independently prove source or split membership.

    This does not call the model, rebuild a readout or verify initial weights:
    evaluation can validate the same contract against a trained encoder.
    """
    _require(isinstance(model, SharedBackboneMFM), "Actual SharedBackboneMFM is required")
    return _batch_spec(batch, validate_training_config(config), model,
                       expected_role=expected_role, require_observed=require_observed)


def _sequence_specs(batches, config, model):
    _require(type(batches) in (list, tuple) and 0 < len(batches) <= config["caps"]["max_sequence_batches"],
             "A bounded fixed train batch sequence is required")
    specs, ids = [], set()
    for item in batches:
        specs.append(_batch_spec(item, config, model, expected_role="train", require_observed=True))
        ids.update(item.sample_ids)
        _require(len(ids) <= config["caps"]["max_unique_samples"], "Unique sample cap exceeded")
    return canonical_hash([spec["hash"] for spec in specs]), specs


def training_sequence_sha256(batches, config, model):
    return _sequence_specs(batches, validate_training_config(config), model)[0]


def _tracker_identity(tracker):
    mode = getattr(getattr(tracker, "settings", None), "mode", getattr(tracker, "mode", None))
    run_id, path, step = (getattr(tracker, name, None) for name in ("id", "path", "step"))
    log = getattr(tracker, "log", None)
    _require(mode in ("online", "offline") and not getattr(tracker, "disabled", False), "Active tracking is required")
    _require(type(run_id) is str and bool(run_id) and type(path) is str and bool(path), "Tracker run ID/path are required")
    _require(callable(log) and getattr(log, "__self__", None) is tracker
             and getattr(log, "__name__", None) != "<lambda>", "An identified bound tracker.log method is required")
    _integer(step, "tracker history cursor", 0)
    return {"id": run_id, "path": path, "mode": mode, "next_step": step}


def _optimizer(parameters, config):
    opt = config["optimizer"]
    return torch.optim.AdamW(parameters, lr=opt["lr"], betas=tuple(opt["betas"]), eps=opt["eps"],
                            weight_decay=opt["weight_decay"], amsgrad=opt["amsgrad"],
                            foreach=False, fused=False, capturable=False, differentiable=False, maximize=False)


class DownstreamTrainer:
    """Fixed-iteration AdamW, without endpoint selection or implicit data scope.

    The trainer takes ownership of supplied model modes/requires_grad/gradients.
    Missing downstream tasks can share a Linear parameter with observed tasks;
    normal AdamW weight decay still applies to that parameter's zero-grad rows.
    Unused pretraining modules are excluded completely and must remain fixed.
    Every selected backbone/readout parameter must participate in each update;
    custom backbones with unused registered parameters are unsupported.
    """

    def __init__(self, model, readout, config, *, tracker):
        self.config = validate_training_config(config)
        _require(isinstance(model, SharedBackboneMFM)
                 and isinstance(readout, (SourceAlignedH0Readout, SourceAlignedLinearGraphReadout)),
                 "Actual SharedBackboneMFM and source-aligned readout are required")
        _require(readout.config_dict() == self.config["readout_config"]
                 and readout.output_dim == len(self.config["tasks"]) and readout.input_dim == model.latent_dim,
                 "Readout architecture/dimensions differ from explicit config")
        self.model, self.readout, self.tracker = model, readout, tracker
        self.device = torch.device(self.config["device"])
        _require(torch.get_default_dtype() == torch.float32, "This optimizer recipe requires the standard FP32 default dtype")
        _require(not {id(parameter) for parameter in model.parameters()} & {id(parameter) for parameter in readout.parameters()},
                 "Model/readout parameters must be independent")
        for module in (model, readout):
            for tensor in list(module.parameters()) + list(module.buffers()):
                _require(tensor.device == self.device and (not tensor.is_floating_point() or tensor.dtype == torch.float32),
                         "Model/readout must already be FP32 on the single declared device")
                _require(not tensor.is_floating_point() or bool(torch.isfinite(tensor).all()), "Initial state must be finite")
        self.initial_encoder_sha256 = _encoder_hash(model)
        _require(self.initial_encoder_sha256 == self.config["bindings"]["initial_encoder_sha256"], "Initial H0 hash differs")
        self.initial_readout_sha256 = _tree_hash(readout.state_dict())
        self._unused_hash = self._unused_state_hash()
        self._tracker = _tracker_identity(tracker)
        for parameter in model.parameters():
            parameter.requires_grad_(False)
            parameter.grad = None
        for parameter in model.backbone.parameters():
            parameter.requires_grad_(self.config["mode"] == "finetune")
        for parameter in readout.parameters():
            parameter.requires_grad_(True)
            parameter.grad = None
        self.parameters = self._parameters(model, readout)
        self.optimizer = _optimizer(self.parameters, self.config)
        self.rng_state = {"cpu": torch.Generator(device="cpu").manual_seed(self.config["seed"]).get_state(),
                          "device_type": self.device.type, "cuda": None}
        if self.device.type == "cuda":
            self.rng_state["cuda"] = torch.Generator(device=self.device).manual_seed(self.config["seed"]).get_state()
        self.environment = {"torch_version": str(torch.__version__), "cuda_version": torch.version.cuda,
            "device": str(self.device), "default_dtype": str(torch.get_default_dtype()), "num_threads": torch.get_num_threads(),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "cudnn_deterministic": torch.backends.cudnn.deterministic,
            "cudnn_benchmark": torch.backends.cudnn.benchmark,
            "matmul_precision": torch.get_float32_matmul_precision()}
        self.optimizer_updates = self.sample_exposure = self.atom_exposure = 0
        self.attempted_forward_steps = self.forward_sample_exposure = self.forward_atom_exposure = 0
        self.task_valid_label_exposure = [0] * len(self.config["tasks"])
        self.total_wall_seconds = 0.0
        self.train_sequence_sha256, self._specs, self.last_step = None, None, {}
        self.status = "ready"
        self._set_modes()

    def _parameters(self, model, readout):
        return ((list(model.backbone.parameters()) if self.config["mode"] == "finetune" else [])
                + list(readout.parameters()))

    def _set_modes(self):
        self.model.eval()
        if self.config["mode"] == "finetune":
            self.model.backbone.train()
        self.readout.train()

    def _unused_state_hash(self):
        return _tree_hash({name: value for name, value in self.model.state_dict().items() if not name.startswith("backbone.")})

    def _verify_fixed_state(self):
        _require(self._unused_state_hash() == self._unused_hash, "Unused pretraining state changed")
        _require(all(parameter.grad is None for name, parameter in self.model.named_parameters()
                     if not name.startswith("backbone.")), "Unused pretraining parameters received gradients")
        if self.config["mode"] == "frozen":
            _require(_encoder_hash(self.model) == self.initial_encoder_sha256
                     and all(parameter.grad is None for parameter in self.model.backbone.parameters()),
                     "Frozen H0 parameters or buffers changed")

    @contextmanager
    def _owned_rng(self):
        devices = [0] if self.device.type == "cuda" else []
        with torch.random.fork_rng(devices=devices):
            torch.set_rng_state(self.rng_state["cpu"])
            if devices:
                torch.cuda.set_rng_state(self.rng_state["cuda"], 0)
            try:
                yield
            finally:
                self.rng_state["cpu"] = torch.get_rng_state().clone()
                if devices:
                    self.rng_state["cuda"] = torch.cuda.get_rng_state(0).clone()

    def _wall_check(self, started):
        if self.total_wall_seconds + time.monotonic() - started >= self.config["caps"]["wall_seconds"]:
            self.status = "budget_stop"
            raise DownstreamTrainingError("Cumulative downstream wall budget exhausted")

    def _loss(self, output, item):
        index = (output.ptr[output.graph_ids] + output.source_atom_ids
                 if output.output_level == "atom" else output.graph_ids)
        targets, mask = item.targets[index], item.supervision_mask[index]
        _require(bool(mask.any()), "No observed labels remain after source alignment")
        losses, raw, counts = [], [], []
        weights = self.config["task_weights"]
        denominator = _weight_sum(weights)
        for task, weight in enumerate(weights):
            active = mask[:, task]
            count = int(active.sum())
            counts.append(count)
            if not count:
                raw.append(None)
                continue
            prediction, target = output.predictions[active, task], targets[active, task]
            if self.config["loss"] == "mse":
                mean, scale = self.config["normalization"]["means"][task], self.config["normalization"]["scales"][task]
                raw_prediction = mean + scale * prediction
                residual = raw_prediction - target
                loss = (prediction - (target - mean) / scale).square().mean()
                raw.append(float(residual.detach().square().mean()))
            else:
                loss = torch.nn.functional.binary_cross_entropy_with_logits(prediction, target)
                raw.append(float(loss.detach()))
            losses.append(loss * (weight / denominator))
        loss = torch.stack(losses).sum()
        _require(bool(torch.isfinite(loss)), "Active loss is nonfinite")
        _require(all(value is None or math.isfinite(value) for value in raw), "Active original-unit task loss is nonfinite")
        return loss, raw, counts

    def _step(self, item, spec, batch_index):
        self._set_modes()
        self._verify_fixed_state()
        self.optimizer.zero_grad(set_to_none=True)
        data = item.encoder_batch
        # Only target-free fields enter encode_atoms; caller tensors are copied.
        safe = Data(x=data.x.detach().clone(), pos=data.pos.detach().clone(),
                    batch=data.batch.detach().clone(), ptr=data.ptr.detach().clone())
        started = time.monotonic()
        self.attempted_forward_steps += 1
        self.forward_sample_exposure += spec["samples"]
        self.forward_atom_exposure += spec["atoms"]
        with self._owned_rng():
            if self.config["mode"] == "frozen":
                with torch.no_grad():
                    h0 = self.model.encode_atoms(safe)
            else:
                h0 = self.model.encode_atoms(safe)
            output = self.readout(h0, source_atom_ids=item.source_atom_ids,
                                  batch=safe.batch, ptr=safe.ptr)
            loss, raw, counts = self._loss(output, item)
            loss.backward()
            grads = [parameter.grad for parameter in self.parameters if parameter.grad is not None]
            _require(len(grads) == len(self.parameters) and bool(grads)
                     and all(bool(torch.isfinite(grad).all()) for grad in grads), "Selected optimizer gradients are nonfinite/missing")
            backbone_grads = [parameter.grad for parameter in self.model.backbone.parameters() if parameter.grad is not None]
            if self.config["mode"] == "finetune":
                _require(bool(backbone_grads), "Finetune has no connected H0 gradient")
            backbone_norm = math.sqrt(math.fsum(float(grad.detach().double().square().sum()) for grad in backbone_grads))
            norm = math.sqrt(math.fsum(float(grad.detach().double().square().sum()) for grad in grads))
            _require(math.isfinite(norm), "Gradient norm is nonfinite")
            cap = self.config["gradient_clip_norm"]
            if cap is not None:
                torch.nn.utils.clip_grad_norm_(self.parameters, cap, error_if_nonfinite=True)
                _require(all(bool(torch.isfinite(grad).all()) for grad in grads), "Clipped gradients are nonfinite")
            self.optimizer.step()
        self.optimizer_updates += 1
        self.sample_exposure += spec["samples"]
        self.atom_exposure += spec["atoms"]
        self.task_valid_label_exposure = [left + right for left, right in zip(self.task_valid_label_exposure, counts)]
        self.last_step = {"optimizer_update": self.optimizer_updates, "loss": float(loss.detach()),
            "raw_task_losses": raw, "task_valid_labels": counts, "gradient_norm": norm,
            "backbone_gradient_norm": backbone_norm, "backbone_gradient_present": bool(backbone_grads),
            "learning_rate": self.optimizer.param_groups[0]["lr"], "batch_index": batch_index,
            "sample_ids": item.sample_ids, "samples": spec["samples"], "atoms": spec["atoms"],
            "step_seconds": time.monotonic() - started}
        self._verify_fixed_state()
        for module in (self.model.backbone, self.readout):
            _require(all(not tensor.is_floating_point() or bool(torch.isfinite(tensor).all())
                         for tensor in module.state_dict().values() if isinstance(tensor, Tensor)), "Updated state is nonfinite")
        _require(_tracker_identity(self.tracker) == self._tracker, "Tracker identity/history changed outside this trainer")
        payload = {"downstream/optimizer_update": self.optimizer_updates, "downstream/loss": self.last_step["loss"],
            "downstream/sample_exposure": self.sample_exposure, "downstream/atom_exposure": self.atom_exposure,
            "downstream/gradient_norm": norm, "downstream/learning_rate": self.last_step["learning_rate"],
            "downstream/backbone_gradient_norm": backbone_norm,
            "downstream/step_seconds": self.last_step["step_seconds"]}
        for task, name in enumerate(self.config["tasks"]):
            payload["downstream/observed_labels/" + name] = counts[task]
            if raw[task] is not None:
                payload["downstream/raw_task_loss/" + name] = raw[task]
        try:
            self.tracker.log(payload, step=self._tracker["next_step"], commit=True)
            observed = _tracker_identity(self.tracker)
            _require({key: observed[key] for key in ("id", "path", "mode")} ==
                     {key: self._tracker[key] for key in ("id", "path", "mode")}
                     and observed["next_step"] == self._tracker["next_step"] + 1, "Tracker did not advance exactly one actual history step")
            self._tracker = observed
        except Exception as exc:
            self.status = "tracker_failed"
            raise DownstreamTrainingError("Tracking failed after the actual optimizer update; no update replay is allowed") from exc

    def fit(self, batches, *, max_updates):
        _integer(max_updates, "max_updates", 0)
        _require(self.optimizer_updates <= max_updates <= self.config["total_updates"], "Requested total cursor exceeds fixed endpoint")
        _require(self.status in ("ready", "partial", "complete"), "Failed/exhausted trainer cannot silently continue")
        started = time.monotonic()
        try:
            self._wall_check(started)
            sequence_hash, specs = _sequence_specs(batches, self.config, self.model)
            _require(self.train_sequence_sha256 in (None, sequence_hash), "Fixed training sequence changed")
            self.train_sequence_sha256, self._specs = sequence_hash, specs
            while self.optimizer_updates < max_updates:
                self._wall_check(started)
                index = self.optimizer_updates % len(batches)
                spec = _batch_spec(batches[index], self.config, self.model,
                                   expected_role="train", require_observed=True)
                _require(spec == specs[index], "Training batch mutated after sequence binding")
                self._step(batches[index], spec, index)
                self._wall_check(started)
            self.status = "complete" if self.optimizer_updates == self.config["total_updates"] else "partial"
            result = self.summary()
            self._wall_check(started)
        except BaseException as exc:
            if self.status not in ("budget_stop", "tracker_failed"):
                self.status = "failed"
            if isinstance(exc, (DownstreamTrainingError, KeyboardInterrupt, SystemExit)):
                raise
            raise DownstreamTrainingError("Downstream optimization failed") from exc
        finally:
            self.total_wall_seconds += time.monotonic() - started
        if self.total_wall_seconds >= self.config["caps"]["wall_seconds"]:
            self.status = "budget_stop"
            raise DownstreamTrainingError("Cumulative active-fit wall budget exhausted during finalization")
        result["total_wall_seconds"] = self.total_wall_seconds
        return result

    def summary(self):
        return {"schema_version": TRAINING_SCHEMA, "state": "NOT_FROZEN", "formal_eligible": False,
            "status": self.status, "optimizer_updates": self.optimizer_updates,
            "sample_exposure": self.sample_exposure, "atom_exposure": self.atom_exposure,
            "task_valid_label_exposure": list(self.task_valid_label_exposure),
            "attempted_forward_steps": self.attempted_forward_steps,
            "forward_sample_exposure": self.forward_sample_exposure, "forward_atom_exposure": self.forward_atom_exposure,
            "total_wall_seconds": self.total_wall_seconds, "train_sequence_sha256": self.train_sequence_sha256,
            "initial_encoder_sha256": self.initial_encoder_sha256, "endpoint_encoder_sha256": _encoder_hash(self.model),
            "initial_readout_sha256": self.initial_readout_sha256, "tracker_next_step": self._tracker["next_step"],
            "last_step": deepcopy(self.last_step), "metadata_source_truth_independently_verified": False,
            "tracker_persistence_independently_verified": False,
            "wall_clock_scope": "cumulative active fit including validation/summary; excludes construction/checkpoint/restore; caller bounds full attempt"}

    def checkpoint(self):
        _require(self.train_sequence_sha256 is not None, "Bind a validated train sequence before checkpointing")
        payload = {"schema_version": CHECKPOINT_SCHEMA, "status": self.status, "config": deepcopy(self.config),
            "config_sha256": canonical_hash(self.config), "model_config": deepcopy(self.model.config_dict()),
            "readout_config": self.readout.config_dict(), "environment": deepcopy(self.environment),
            "initial_encoder_sha256": self.initial_encoder_sha256, "initial_readout_sha256": self.initial_readout_sha256,
            "train_sequence_sha256": self.train_sequence_sha256,
            "model_state": _copy_cpu(self.model.state_dict()), "readout_state": _copy_cpu(self.readout.state_dict()),
            "optimizer_state": _copy_cpu(self.optimizer.state_dict()), "rng_state": _copy_cpu(self.rng_state),
            "counters": {name: deepcopy(getattr(self, name)) for name in ("optimizer_updates", "sample_exposure",
                "atom_exposure", "task_valid_label_exposure", "total_wall_seconds", "attempted_forward_steps",
                "forward_sample_exposure", "forward_atom_exposure")}, "tracker": deepcopy(self._tracker),
            "last_step": deepcopy(self.last_step)}
        payload["checkpoint_content_sha256"] = checkpoint_content_sha256(payload)
        return payload

    def _validate_optimizer_state(self, state, optimizer, parameters, updates):
        _keys(state, ("state", "param_groups"), "optimizer state")
        reference = optimizer.state_dict()["param_groups"]
        _require(type(state["param_groups"]) is list and len(state["param_groups"]) == 1, "Optimizer group count differs")
        _require(state["param_groups"] == reference, "Optimizer parameter order/options changed")
        _require(type(state["state"]) is dict, "Optimizer moments require a dictionary")
        allowed = {"step", "exp_avg", "exp_avg_sq"} | ({"max_exp_avg_sq"} if self.config["optimizer"]["amsgrad"] else set())
        _require(updates > 0 or not state["state"], "Zero-update checkpoint has optimizer moments")
        if updates:
            _require(set(state["state"]) == set(range(len(parameters))),
                     "Checkpoint omitted selected backbone/readout moments")
        for index, moments in state["state"].items():
            _require(type(index) is int and 0 <= index < len(parameters) and type(moments) is dict
                     and set(moments) == allowed, "Optimizer moment IDs/fields differ")
            step = moments["step"]
            _require(isinstance(step, Tensor) and step.shape == () and step.dtype == torch.float32
                     and bool(torch.isfinite(step)) and 1 <= step.item() <= updates and step.item().is_integer(), "Optimizer step is invalid")
            _require(step.item() == updates, "Every selected optimizer step must equal the actual update cursor")
            for name in allowed - {"step"}:
                tensor = moments[name]
                _require(isinstance(tensor, Tensor) and tensor.shape == parameters[index].shape
                         and tensor.dtype == parameters[index].dtype and bool(torch.isfinite(tensor).all()), "Optimizer moment shape/dtype/values differ")
                if name != "exp_avg":
                    _require(bool((tensor >= 0).all()), "Optimizer squared moment is negative")

    def load_checkpoint(self, payload, batches):
        """Validate an owned staged candidate before copying live state.

        Initial model/readout must be reconstructed identically. Only fully
        logged partial/complete states resume; tracker failures cannot replay a
        committed optimizer update. Byte integrity is internal, not historical
        source/model truth. Rejection leaves live objects/counters/RNG unchanged.
        Payload copies are CPU; candidate modules retain the declared device.
        The caller must measure/budget temporary GPU memory as well as CPU RSS.
        """
        _require(self.status == "ready" and self.optimizer_updates == 0 and self.train_sequence_sha256 is None,
                 "Resume requires a fresh receiver reconstructed from the same initialization")
        _require(_encoder_hash(self.model) == self.initial_encoder_sha256
                 and _tree_hash(self.readout.state_dict()) == self.initial_readout_sha256,
                 "Fresh receiver initial parameters changed before resume")
        _keys(payload, ("schema_version", "status", "config", "config_sha256", "model_config", "readout_config",
                       "environment", "initial_encoder_sha256", "initial_readout_sha256", "train_sequence_sha256",
                       "model_state", "readout_state", "optimizer_state", "rng_state", "counters", "tracker",
                       "last_step", "checkpoint_content_sha256"), "checkpoint")
        _require(payload.get("schema_version") == CHECKPOINT_SCHEMA,
                 "Unsupported downstream checkpoint")
        _require(payload.get("checkpoint_content_sha256") == checkpoint_content_sha256(payload), "Checkpoint content hash differs")
        _require(payload.get("status") in ("partial", "complete"), "Only fully logged fixed-sequence states can resume")
        _require(payload.get("config") == self.config and payload.get("config_sha256") == canonical_hash(self.config)
                 and payload.get("model_config") == self.model.config_dict()
                 and payload.get("readout_config") == self.readout.config_dict()
                 and payload.get("environment") == self.environment, "Checkpoint complete config/environment differs")
        _require(payload.get("initial_encoder_sha256") == self.initial_encoder_sha256
                 and payload.get("initial_readout_sha256") == self.initial_readout_sha256, "Checkpoint initial encoder/readout binding differs")
        sequence_hash, specs = _sequence_specs(batches, self.config, self.model)
        _require(payload.get("train_sequence_sha256") == sequence_hash
                 and self.train_sequence_sha256 in (None, sequence_hash), "Checkpoint sequence differs")
        _require(payload.get("tracker") == _tracker_identity(self.tracker), "Checkpoint tracker identity/history differs")
        counters = payload.get("counters")
        names = ("optimizer_updates", "sample_exposure", "atom_exposure", "task_valid_label_exposure",
                 "total_wall_seconds", "attempted_forward_steps", "forward_sample_exposure", "forward_atom_exposure")
        _keys(counters, names, "checkpoint counters")
        updates = _integer(counters["optimizer_updates"], "saved update cursor", 0)
        _require(updates <= self.config["total_updates"]
                 and (payload["status"] == "complete") == (updates == self.config["total_updates"]), "Checkpoint endpoint cursor is inconsistent")
        wall = _number(counters["total_wall_seconds"], "saved wall clock", nonnegative=True)
        _require(wall < self.config["caps"]["wall_seconds"], "Saved wall budget is exhausted")
        turns, remainder = divmod(updates, len(specs))
        expected = {name: turns * sum(spec[name] for spec in specs) + sum(spec[name] for spec in specs[:remainder])
                    for name in ("samples", "atoms")}
        valid = [turns * sum(spec["valid"][task] for spec in specs)
                 + sum(spec["valid"][task] for spec in specs[:remainder]) for task in range(len(self.config["tasks"]))]
        for name, value in (("sample_exposure", expected["samples"]), ("atom_exposure", expected["atoms"]),
                            ("forward_sample_exposure", expected["samples"]), ("forward_atom_exposure", expected["atoms"]),
                            ("attempted_forward_steps", updates)):
            _require(type(counters[name]) is int and counters[name] == value, "Checkpoint exposure cursor differs at " + name)
        _require(type(counters["task_valid_label_exposure"]) is list
                 and all(type(item) is int for item in counters["task_valid_label_exposure"])
                 and counters["task_valid_label_exposure"] == valid, "Checkpoint task label counts differ")
        rng = payload.get("rng_state")
        _keys(rng, ("cpu", "device_type", "cuda"), "owned RNG")
        _require(rng["device_type"] == self.device.type, "RNG device scope differs")
        for name, device in (("cpu", "cpu"), ("cuda", self.device)):
            if name == "cuda" and self.device.type == "cpu":
                _require(rng[name] is None, "CPU checkpoint cannot contain CUDA RNG")
                continue
            _require(isinstance(rng[name], Tensor) and rng[name].dtype == torch.uint8 and rng[name].ndim == 1
                     and rng[name].shape == self.rng_state[name].shape, "Owned RNG shape/dtype differs")
            try:
                torch.Generator(device=device).set_state(rng[name].cpu())
            except Exception as exc:
                raise DownstreamTrainingError("Owned RNG contents are invalid") from exc
        _require(isinstance(payload.get("last_step"), dict)
                 and (not updates or payload["last_step"].get("optimizer_update") == updates), "Checkpoint last-step cursor differs")
        try:
            with torch.random.fork_rng(devices=[0] if self.device.type == "cuda" else []):
                candidate_model, candidate_readout = deepcopy(self.model), deepcopy(self.readout)
                for module, state in ((candidate_model, payload["model_state"]), (candidate_readout, payload["readout_state"])):
                    reference = module.state_dict()
                    _require(set(reference) == set(state), "Checkpoint state keys differ")
                    for name, tensor in reference.items():
                        if isinstance(tensor, Tensor):
                            found = state[name]
                            _require(isinstance(found, Tensor) and found.shape == tensor.shape and found.dtype == tensor.dtype
                                     and (not found.is_floating_point() or bool(torch.isfinite(found).all())), "Checkpoint state shape/dtype/values differ")
                    module.load_state_dict(state, strict=True)
                _require(_tree_hash({name: value for name, value in candidate_model.state_dict().items()
                                     if not name.startswith("backbone.")}) == self._unused_hash, "Checkpoint changed unused pretraining modules")
                if self.config["mode"] == "frozen":
                    _require(_encoder_hash(candidate_model) == self.initial_encoder_sha256, "Checkpoint changed frozen encoder state")
                parameters = self._parameters(candidate_model, candidate_readout)
                candidate_optimizer = _optimizer(parameters, self.config)
                self._validate_optimizer_state(payload["optimizer_state"], candidate_optimizer, parameters, updates)
                candidate_optimizer.load_state_dict(_copy_cpu(payload["optimizer_state"]))
        except DownstreamTrainingError:
            raise
        except Exception as exc:
            raise DownstreamTrainingError("Candidate model/optimizer checkpoint validation failed") from exc
        # Staged validation completed. Keep a bounded rollback copy for any
        # unexpected live-copy failure; caller must budget these temporary states.
        backup = (_copy_cpu(self.model.state_dict()), _copy_cpu(self.readout.state_dict()),
                  _copy_cpu(self.optimizer.state_dict()))
        try:
            self.model.load_state_dict(candidate_model.state_dict(), strict=True)
            self.readout.load_state_dict(candidate_readout.state_dict(), strict=True)
            self.optimizer.load_state_dict(_copy_cpu(candidate_optimizer.state_dict()))
        except Exception as exc:
            self.model.load_state_dict(backup[0], strict=True)
            self.readout.load_state_dict(backup[1], strict=True)
            self.optimizer.load_state_dict(backup[2])
            raise DownstreamTrainingError("Live checkpoint copy failed and was rolled back") from exc
        for name in names:
            setattr(self, name, deepcopy(counters[name]))
        self.rng_state, self._tracker, self.last_step = _copy_cpu(rng), deepcopy(payload["tracker"]), deepcopy(payload["last_step"])
        self.train_sequence_sha256, self._specs, self.status = sequence_hash, specs, payload["status"]
        self._set_modes()
