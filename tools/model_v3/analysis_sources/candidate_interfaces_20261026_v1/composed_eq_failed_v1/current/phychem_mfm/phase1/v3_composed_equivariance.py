"""Independent FP32 encoder-to-head rigid-motion checks, never model selection.

All fixtures, seeds, transforms and nontrivial parameter assignments are fixed
before execution. A failed case is returned with its measurements, not retried
with another fixture, seed, weight scale or tolerance. No dataset is opened.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import time

import numpy as np
import torch
from torch_geometric.data import Batch, Data

from ..model.v3_architecture import ArchitectureOptions, build_source_s_architecture_model
from ..model.v3_heads import V3HeadBank
from ..model.v3_multiview import V3MultiViewModel
from .v3_architecture_views import V3TwoViewModel, build_two_structural_views
from .v3_contract import FieldSpec, LabelRegistry, canonical_hash, require
from .v3_structural import StructuralFieldBinding, StructuralViewConfig, build_structural_views


SCHEMA = "model_v3_composed_equivariance_v1"
BASE_REVISION = "e47d066e53f000d71c05bf1c772597f2a5c42c30"
ABSOLUTE_TOLERANCE = 1e-5
RELATIVE_TOLERANCE = 0.0
NONZERO_NORM_FLOOR = 1e-8
HARD_BOUNDARY_MARGIN_A = 1e-4
WEIGHT_SEEDS = (20261026, 20261027)
VIEW_CONFIGURATION = StructuralViewConfig(seed=271828, epoch=2)
ORDINALS = (700, 701, 702)
HEAD_POLICIES = ("H1_fixed", "H1_learned", "H2_fixed", "H3_fixed")
TRANSFORM_DECLARATIONS = (
    ("general_rotation", (1., 2., -1.), .713, (0., 0., 0.)),
    ("translation_only", (1., 0., 0.), 0., (1.25, -.75, 2.)),
    ("other_rotation_and_translation", (-2., 1., 3.), -1.137, (-2., .5, 1.25)),
)
LEGACY_CUDA_NODES = (
    "current/tests/test_model_v3_transfer.py::test_custom_batch_pin_protocol_and_nonblocking_cuda_transfer",
    "current/tests/test_model_v3_native_bond_transport.py::test_pinned_bond_arrays_and_nonblocking_cuda_transfer",
)
EXTRA_SOURCE_FILES = (
    "current/tests/conftest.py", "current/tests/test_model_v3_composed_equivariance.py",
    "current/tests/test_model_v3_transfer.py", "current/tests/test_model_v3_native_bond_transport.py",
    "tools/model_v3/check_composed_equivariance.py", "docs/model_v3/COMPOSED_EQUIVARIANCE.md",
    "workflows/sprime_s/scripts/s_model_memory_v1.py",
)


@dataclass(frozen=True)
class CaseSpec:
    distance_bias: str
    views: str
    head_policy: str
    weight_seed: int

    @property
    def identity(self):
        return f"{self.distance_bias}__{self.views}__{self.head_policy}__seed{self.weight_seed}"


CASE_SPECS = tuple(CaseSpec(*values) for values in itertools.product(
    ("C1-0", "C1-a", "C1-b"), ("two", "three"), HEAD_POLICIES, WEIGHT_SEEDS))


def protocol():
    return {"schema": SCHEMA, "base_revision": BASE_REVISION,
        "absolute_tolerance": ABSOLUTE_TOLERANCE, "relative_tolerance": RELATIVE_TOLERANCE,
        "nonzero_norm_floor": NONZERO_NORM_FLOOR, "hard_boundary_margin_A": HARD_BOUNDARY_MARGIN_A,
        "cases": [asdict(case) for case in CASE_SPECS], "case_count": 48,
        "view_configuration": asdict(VIEW_CONFIGURATION), "ordinals": list(ORDINALS),
        "fixture_native_atoms": [3, 9, 32], "transforms": [
            {"name": name, "declared_axis_before_normalization": list(axis), "angle_radians": angle, "translation_A": list(shift),
             "construction": "normalize declared axis, Rodrigues float64, row-vector x@R+t"}
            for name, axis, angle, shift in TRANSFORM_DECLARATIONS],
        "parameter_policy": {
            "factory_initialization": "unchanged defaults, fork CPU RNG and seed only CPU default_generator per case",
            "zero_initialized_head_replacement": "none; existing A4 final normal(std=1e-3), all other existing initializers retained",
            "C1_b_pair_scale": "1 + 0.1*sin(0.37*ordered_pair_code)",
            "C1_b_pair_shift": "0.03*cos(0.11*ordered_pair_code)",
            "H1_learned_logits": [-0.7, 0.4], "error_dependent_parameter_selection": False},
        "attention": "actual global production S path; cutoff=None; unused radius8 is not an attention cutoff",
        "model": {"layers": 6, "dim": 512, "heads": 8, "ff_mult": 2},
        "FP32": {"autocast": False, "TF32": False, "matmul_precision": "highest", "dropout": 0.0},
        "raw_terminal_artifacts": {"per_case_numeric_bytes_limit": 320*1024,
            "per_case_NPZ_bytes_limit": 512*1024, "preserve_original_and_three_moved_terminals": True},
        "acceptance": "all 48 cases/all fields/all 3 transforms, finite/nonempty, nonzero vector terminals, raw absolute error <=1e-5",
        "real_data_read": False, "scientific_selection": False,
        "claim_scope": "finite declared fixtures and parameter states; not a theorem for all coordinates/weights/hardware"}


@dataclass(frozen=True)
class RigidTransform:
    name: str
    rotation: torch.Tensor
    translation: torch.Tensor

    def document(self):
        return {"name": self.name, "row_vector_rule": "x @ R + t",
            "rotation_float64": self.rotation.tolist(), "translation_A": self.translation.tolist(),
            "determinant": float(torch.linalg.det(self.rotation)),
            "orthogonality_maxabs": float((self.rotation.T @ self.rotation - torch.eye(3, dtype=torch.float64)).abs().max())}


def _rotation(axis, angle):
    axis = torch.tensor(axis, dtype=torch.float64)
    axis /= axis.norm()
    x, y, z = axis.tolist()
    skew = torch.tensor([[0., -z, y], [z, 0., -x], [-y, x, 0.]], dtype=torch.float64)
    result = torch.eye(3, dtype=torch.float64)*math.cos(angle)
    result += (1-math.cos(angle))*torch.outer(axis, axis) + math.sin(angle)*skew
    require(float(torch.linalg.det(result)) > 1-1e-12
            and float((result.T @ result-torch.eye(3, dtype=torch.float64)).abs().max()) < 1e-12,
            "A proper, orthogonal fixed rotation is required")
    return result


def transforms():
    return tuple(RigidTransform(name, _rotation(axis, angle), torch.tensor(shift, dtype=torch.float64))
        for name, axis, angle, shift in TRANSFORM_DECLARATIONS)


def _record(elements, coordinates, pairs, name):
    return Data(x=torch.tensor(elements, dtype=torch.long)[:, None],
        pos=torch.tensor(coordinates, dtype=torch.float32),
        rdkit_bond_index=torch.tensor(pairs, dtype=torch.long).T.contiguous(),
        rdkit_bond_order=torch.ones(len(pairs), dtype=torch.long), rdkit_bond_status="ok",
        is_feasible=torch.ones(1, dtype=torch.long), neg_type=torch.zeros(1, dtype=torch.long),
        fixture_name=name)


def fixture_batch():
    """Literal water/ethanol plus a formula-defined approximate decane geometry.

    These are synthetic molecular geometries in Angstrom, not PM7/D5 records,
    minimized conformers, targets or a claim about chemical stability.
    """
    water = _record([7, 0, 0], [[0., 0., 0.], [.7586, 0., .5043], [-.7586, 0., .5043]],
        [(0, 1), (0, 2)], "water_like_3")
    ethanol = _record([5, 5, 7, 0, 0, 0, 0, 0, 0],
        [[-.75, 0., 0.], [.75, 0., 0.], [1.35, 1.15, .2],
         [-1.14, .5, .89], [-1.13, .5, -.9], [-1.1, -1.04, .07],
         [1.11, -.48, .93], [1.1, -.5, -.9], [2.28, 1.01, .35]],
        [(0, 1), (1, 2), (0, 3), (0, 4), (0, 5), (1, 6), (1, 7), (2, 8)], "ethanol_like_9")
    carbon = [[1.26*i, (-1.)**i*.42, .12*math.sin(1.2*i)] for i in range(10)]
    coordinates, edges = list(carbon), [(i, i+1) for i in range(9)]
    for i, (x, y, z) in enumerate(carbon):
        for sign in (-1., 1.):
            edges.append((i, len(coordinates)))
            coordinates.append([x, y+(-1.)**i*.48, z+sign*.94])
    for i, direction in ((0, -1.), (9, 1.)):
        x, y, z = carbon[i]
        edges.append((i, len(coordinates)))
        coordinates.append([x+direction*.96, y-.2, z+.15])
    center = [sum(row[j] for row in coordinates)/32 for j in range(3)]
    coordinates = [[row[j]-center[j] for j in range(3)] for row in coordinates]
    decane = _record([5]*10+[0]*22, coordinates, edges, "decane_like_32_not_optimized")
    result = Batch.from_data_list([water, ethanol, decane])
    require((result.ptr[1:]-result.ptr[:-1]).tolist() == [3, 9, 32], "Frozen fixture population changed")
    return result


def registry_for(policy):
    require(policy in HEAD_POLICIES, "Unknown declared head policy")
    def pooling(fixed):
        return "learned" if policy == "H1_learned" else fixed
    fields = (
        FieldSpec("s_element", "S", "structural", "atom", kind="classification", classes=119, unit="class_logit"),
        FieldSpec("s_noise", "S", "structural", "atom", kind="denoise_eps_mse", representation="vector", unit="Angstrom"),
        FieldSpec("s_bond", "S", "structural", "pair", kind="classification", classes=5, unit="class_logit"),
        FieldSpec("p_extensive", "P", "synthetic_physics", "graph", pooling=pooling("sum"), unit="synthetic_energy"),
        FieldSpec("p_intensive", "P", "synthetic_physics", "graph", pooling=pooling("mean"), unit="synthetic_energy"),
        FieldSpec("d_intensive", "D", "synthetic_descriptor", "graph", pooling=pooling("mean"), unit="synthetic_scalar"),
        FieldSpec("d_binary", "D", "synthetic_descriptor", "graph", kind="binary", pooling=pooling("mean"), unit="logit"),
        FieldSpec("d_atom", "D", "synthetic_descriptor", "atom", unit="synthetic_scalar"),
        FieldSpec("p_pair", "P", "synthetic_physics", "pair", unit="synthetic_scalar"),
        FieldSpec("p_gradient", "P", "synthetic_physics", "atom", representation="vector", unit="synthetic_energy/Angstrom"),
        FieldSpec("p_dipole", "P", "synthetic_physics", "graph", representation="vector", unit="synthetic_charge*Angstrom"),
        FieldSpec("p_dipole_magnitude", "P", "synthetic_physics", "graph", representation="magnitude", unit="synthetic_charge*Angstrom"),
    )
    return LabelRegistry(fields, "composed-equivariance-synthetic-v1", canonical_hash({"fixture": SCHEMA, "policy": policy}))


def build_composition(spec):
    require(spec in CASE_SPECS, "Case must be in the frozen full matrix")
    config = {"architecture": {"preset": "shared_light"},
        "backbone": {"n_atom_types": 119, "dim": 512, "layers": 6, "heads": 8, "ff_mult": 2,
            "dropout": 0., "use_dist_bias": True, "use_radius_mask": False, "radius": 8., "activation_checkpointing": False},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise", "geometry_radius": 5.,
            "geometry_hidden_dim": 64, "geometry_rbf_count": 32, "geometry_message_layers": 0,
            "geometry_normalization": "none", "geometry_pair_chunk_size": 8192}}
    # Build on CPU as required by the actual production S architecture builder.
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(spec.weight_seed)
        encoder = build_source_s_architecture_model(config, ArchitectureOptions(distance_bias=spec.distance_bias))
        registry = registry_for(spec.head_policy)
        bank = V3HeadBank(replace(registry, fields=tuple(f for f in registry.fields if f.group != "S")),
            dim=512, forms=spec.head_policy.split("_")[0], hidden_dim=64, vector_radius=5., vector_rbf_count=32)
        with torch.no_grad():
            if spec.distance_bias == "C1-b":
                pairs = encoder.backbone.pair_encoder
                code = torch.arange(pairs.pair_scale.num_embeddings, dtype=torch.float32)[:, None]
                pairs.pair_scale.weight.copy_(1.+.1*torch.sin(.37*code))
                pairs.pair_shift.weight.copy_(.03*torch.cos(.11*code))
            for mixer in bank.pooling_mixers.values():
                mixer.logits.copy_(torch.tensor([-.7, .4]))
        model_class = V3TwoViewModel if spec.views == "two" else V3MultiViewModel
        model = model_class(encoder, bank, registry, StructuralFieldBinding("s_element", "s_noise", "s_bond")).eval()
    require(model.latent_dim == 512 and len(model.encoder.backbone.layers) == 6,
            "The composition must use the actual six-layer/512 encoder")
    require(all(p.dtype == torch.float32 and p.device.type == "cpu" for p in model.parameters()), "CPU FP32 initialization required")
    if spec.distance_bias == "C1-0":
        require(all(layer.attn.dist_mlp.__class__.__name__ == "TiledDistanceMLP" for layer in encoder.backbone.layers),
                "C1-0 must use the actual tiled65536 production S path")
    return model, registry


def _tensor_digest(value):
    value = value.detach().cpu().contiguous()
    header = json.dumps({"dtype": str(value.dtype), "shape": list(value.shape)}, sort_keys=True).encode()
    return hashlib.sha256(header+b"\0"+value.numpy().tobytes()).hexdigest()


def weight_summary(model):
    digest, count = hashlib.sha256(), 0
    for name, value in sorted(model.named_parameters()):
        require(bool(torch.isfinite(value).all()), "Declared initialized parameters must be finite")
        digest.update(name.encode()+b"\0"+_tensor_digest(value).encode()+b"\n")
        count += value.numel()
    terminals = {}
    for name, module in model.named_modules():
        if module.__class__.__name__ in ("EquivariantDenoisingHead", "_DipoleHead", "_PoolingMixer", "SharedGaussianPairEncoder"):
            pins = {n: _tensor_digest(v) for n, v in module.named_parameters()}
            terminals[name] = {"class": module.__class__.__name__, "parameter_sha256": canonical_hash(pins),
                "parameter_count": sum(v.numel() for v in module.parameters()),
                "parameter_squared_norm": sum(float(v.detach().double().square().sum()) for v in module.parameters())}
    return {"all_named_parameter_sha256": digest.hexdigest(), "parameters": count, "terminal_modules": terminals,
        "state_selection": "predeclared seed and assignments; no retry/zero-output fallback"}


@contextmanager
def numerical_policy(*, threads=1):
    require(type(threads) is int and threads > 0, "Explicit positive CPU thread count required")
    prior = (torch.get_num_threads(), torch.get_float32_matmul_precision(),
        torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
    try:
        torch.set_num_threads(threads)
        torch.set_float32_matmul_precision("highest")
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        yield
    finally:
        torch.set_num_threads(prior[0]); torch.set_float32_matmul_precision(prior[1])
        torch.backends.cuda.matmul.allow_tf32 = prior[2]; torch.backends.cudnn.allow_tf32 = prior[3]


def _view_identity(views):
    values = {}
    for key in sorted(views.batch.keys()):
        if key not in ("pos", "target_pos"):
            value = views.batch[key]
            values[key] = {"tensor_sha256": _tensor_digest(value)} if isinstance(value, torch.Tensor) else value
    for key in ("clean_atom_rows", "clean_graph_rows", "base_graph_index", "base_atom_index"):
        values[key] = _tensor_digest(getattr(views, key))
    values["graph_eligibility"] = {key: _tensor_digest(value) for key, value in views.graph_eligibility.items()}
    values["ordinals"] = list(views.ordinals)
    values["configuration"] = asdict(views.config)
    return canonical_hash(values)


def pushed_views(original, transform):
    moved = original.batch.clone()
    # Transform the existing physical views, not a second random draw.
    moved.pos = (original.batch.pos.double() @ transform.rotation + transform.translation).float()
    moved.target_pos = (original.batch.target_pos.double() @ transform.rotation + transform.translation).float()
    result = replace(original, batch=moved)
    require(_view_identity(result) == _view_identity(original), "Rigid transformation changed masks/elements/IDs/native bonds")
    old_epsilon = original.batch.pos.double()-original.batch.target_pos.double()
    actual_epsilon = moved.pos.double()-moved.target_pos.double()
    residual = float((actual_epsilon-old_epsilon @ transform.rotation).abs().max())
    require(residual <= 2e-6, "Pushed view no longer represents the same rotated displacement")
    return result, {"discrete_view_identity_sha256": _view_identity(result),
        "same_noise_pushforward_maxabs_A": residual, "random_views_regenerated": False}


def geometry_domain(views):
    minima, maxima, margins = [], [], []
    for record in views.batch.to_data_list():
        p = record.pos.double()
        distance = torch.cdist(p, p, compute_mode="donot_use_mm_for_euclid_dist")
        off_diagonal = ~torch.eye(len(p), dtype=torch.bool)
        d = distance[off_diagonal]
        minima.append(float(d.min())); maxima.append(float(d.max())); margins.append(float((d-5.).abs().min()))
    return {"minimum_distinct_atom_distance_A": min(minima), "maximum_within_graph_distance_A": max(maxima),
        "minimum_distance_to_hard5_boundary_A": min(margins), "required_hard5_margin_A": HARD_BOUNDARY_MARGIN_A,
        "domain_pass": min(minima) > .05 and min(margins) >= HARD_BOUNDARY_MARGIN_A,
        "attention_scope": "global/unbounded, no hard8 cutoff", "pair_scalar_envelope_radius_A": 8.,
        "physical_graph_counts": (views.batch.ptr[1:]-views.batch.ptr[:-1]).tolist(),
        "default_cdist_MM_size_branch_exercised": max((views.batch.ptr[1:]-views.batch.ptr[:-1]).tolist()) > 25}


def transform_expected(value, transform, law):
    require(law in ("invariant", "vector", "coordinate"), "Unknown rigid-motion output law")
    original = value.detach().cpu().double()
    if law == "invariant": return original
    expected = original @ transform.rotation
    return expected+transform.translation if law == "coordinate" else expected


def field_measurement(field, actual, expected, *, law, unit, require_nonzero=False, reference=None):
    """An absolute-only oracle; finite inputs still fail if relative error is tiny."""
    a, e = actual.detach().cpu().double(), expected.detach().cpu().double()
    require(a.shape == e.shape and a.ndim == 2 and a.numel() > 0, "Nonempty corresponding terminal matrices required")
    reference = a if reference is None else reference.detach().cpu().double()
    finite = bool(torch.isfinite(a).all() and torch.isfinite(e).all() and torch.isfinite(reference).all())
    result = {"field": field, "unit": unit, "law": law, "count": len(a), "components": a.shape[1],
        "absolute_tolerance": ABSOLUTE_TOLERANCE, "relative_tolerance": RELATIVE_TOLERANCE, "finite": finite,
        "nonzero_required": require_nonzero, "nonzero_norm_floor": NONZERO_NORM_FLOOR,
        "maxabs": None, "argmax": None, "reference_max_row_norm": None, "actual_max_row_norm": None,
        "reference_nonzero_rows": 0, "actual_nonzero_rows": 0, "passed": False}
    if finite:
        difference = (a-e).abs()
        index = int(difference.reshape(-1).argmax()); row, component = divmod(index, a.shape[1])
        before_norm, after_norm = reference.norm(dim=-1), a.norm(dim=-1)
        nonzero = (float(before_norm.max()) > NONZERO_NORM_FLOOR and float(after_norm.max()) > NONZERO_NORM_FLOOR)
        result.update(maxabs=float(difference.max()), argmax={"row": row, "component": component,
            "actual": float(a[row, component]), "expected": float(e[row, component])},
            reference_max_row_norm=float(before_norm.max()), actual_max_row_norm=float(after_norm.max()),
            reference_nonzero_rows=int((before_norm > NONZERO_NORM_FLOOR).sum()),
            actual_nonzero_rows=int((after_norm > NONZERO_NORM_FLOOR).sum()),
            passed=float(difference.max()) <= ABSOLUTE_TOLERANCE and (nonzero or not require_nonzero))
    return result


def _terminals(prediction, registry):
    result = {}
    for field in registry.fields:
        if field.group == "S": continue
        law = "vector" if field.representation == "vector" else "invariant"
        result["PD/"+field.name] = (prediction.pd_predictions[field.name], law, field.unit,
            field.representation in ("vector", "magnitude"))
    source = prediction.source_outputs
    mask = source.node_mask.squeeze(-1).bool()
    result["S/noise"] = (source.noise_pred[mask], "vector", "Angstrom", True)
    result["S/coordinate"] = (source.coordinate_pred[mask], "coordinate", "Angstrom", True)
    result["S/element_logits"] = (source.element_logits[mask], "invariant", "class_logit", False)
    result["S/clean_bond_logits"] = (source.bond.order, "invariant", "class_logit", False)
    require(source.bond.order.numel() > 0 and int(source.bond.valid_graph_count) == 3,
            "All three clean fixtures must provide actual nonempty native bond predictions")
    return result


def _edge_identity(head, views):
    edges = torch.stack(head._edges(views.batch.pos, views.batch.batch))
    return {"count": edges.shape[1], "sha256": _tensor_digest(edges)}


def _capture_terminals(archive, prefix, tables):
    for name, (value, law, unit, nonzero) in tables.items():
        key = prefix+"__"+name.replace("/", "__")
        archive[key] = value.detach().cpu().contiguous().numpy().copy()


def _save_terminal_archive(directory, spec, arrays):
    """Preserve all actual FP32 terminal values, including a partial failure."""
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), "Owned existing external terminal-output directory required")
    require(arrays and all(a.dtype == np.float32 and a.ndim == 2 for a in arrays.values()),
            "Only fixed FP32 terminal matrices are archived")
    numeric_bytes = sum(a.nbytes for a in arrays.values())
    require(numeric_bytes <= 320*1024, "Frozen terminal numeric-output bound exceeded")
    path = directory/(spec.identity+"__terminals.npz")
    pending = path.with_suffix(".npz.pending")
    require(not path.exists() and not pending.exists(), "Never overwrite earlier raw terminal output")
    with pending.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, path)
    raw = path.read_bytes()
    require(len(raw) <= 512*1024, "Bounded compressed terminal artifact required")
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "numeric_bytes": numeric_bytes, "arrays": {k: {"dtype": str(a.dtype), "shape": list(a.shape)} for k, a in arrays.items()},
        "semantics": "actual original/three moved FP32 terminals; reconstruct expectation with recorded R/t, never refit",
        "contains_native_data": False, "contains_parameter_weights": False}


def measure_case(spec, *, device="cpu", threads=1, terminal_output_directory=None):
    """Run one complete actual model, returning failed measurements unchanged."""
    device = torch.device(device)
    require(device.type in ("cpu", "cuda"), "Only explicit CPU/CUDA FP32 checks are supported")
    started = time.perf_counter()
    with numerical_policy(threads=threads), torch.inference_mode(), torch.autocast(device_type=device.type, enabled=False):
        model, registry = build_composition(spec)
        weights = weight_summary(model)
        base = fixture_batch()
        builder = build_two_structural_views if spec.views == "two" else build_structural_views
        views = builder(base, ordinals=ORDINALS, config=VIEW_CONFIGURATION)
        domain = geometry_domain(views)
        identities = _view_identity(views)
        require(int(views.batch.element_corrupt_mask.sum()) > 0, "The fixed physical views must contain real element corruption")
        model.to(device)
        original_views = views.to(device)
        pairs = {"p_pair": base.rdkit_bond_index.to(device)}
        calls = []
        terminal_values, terminal_artifact = {}, None
        hook = model.encoder.backbone.register_forward_hook(lambda module, inputs, output: calls.append(tuple(output.shape)))
        try:
            original = model.forward_pretrain(original_views, enabled_groups=("S", "D", "P"), pair_indices=pairs)
            original_tables = _terminals(original, registry)
            if terminal_output_directory is not None: _capture_terminals(terminal_values, "original", original_tables)
            original_edges = _edge_identity(model.encoder.geometry_head, original_views)
            require(original_edges["count"] > 0, "Vector-head neighbor set must not be empty")
            actual_bond_graphs = original.source_outputs.bond.pair_graph_index
            require(bool(original_views.batch.sample_type_id[actual_bond_graphs].eq(0).all()), "Bond terminal must use clean views only")
            require(torch.equal(original.clean_h0, original.source_outputs.atom_repr[original_views.clean_atom_rows]),
                    "PD must receive clean H0 from the same actual encoder pass")
            measurements = []
            for transform_number, transform in enumerate(transforms()):
                pushed, view_proof = pushed_views(views, transform)
                moved_views = pushed.to(device)
                moved = model.forward_pretrain(moved_views, enabled_groups=("S", "D", "P"), pair_indices=pairs)
                moved_tables = _terminals(moved, registry)
                if terminal_output_directory is not None: _capture_terminals(terminal_values, "transform"+str(transform_number), moved_tables)
                require(tuple(moved_tables) == tuple(original_tables), "Terminal coverage changed")
                require(torch.equal(original.source_outputs.node_mask, moved.source_outputs.node_mask)
                        and torch.equal(original.source_outputs.bond.pair_index, moved.source_outputs.bond.pair_index),
                        "Output native masks/bond identities changed under rigid transformation")
                moved_edges = _edge_identity(model.encoder.geometry_head, moved_views)
                rows = []
                for name, (reference, law, unit, nonzero) in original_tables.items():
                    actual = moved_tables[name][0]
                    require(reference.dtype == actual.dtype == torch.float32, "Every complete terminal must remain FP32")
                    rows.append(field_measurement(name, actual, transform_expected(reference, transform, law),
                        law=law, unit=unit, require_nonzero=nonzero, reference=reference))
                h0_error = float((moved.clean_h0.detach().cpu().double()-original.clean_h0.detach().cpu().double()).abs().max())
                measurements.append({"transform": transform.document(), "fields": rows, "view_proof": view_proof,
                    "original_vector_edges": original_edges, "transformed_vector_edges": moved_edges,
                    "vector_edges_unchanged": original_edges == moved_edges,
                    "H0_maxabs_diagnostic_not_raw_unit_terminal": h0_error,
                    "passed": original_edges == moved_edges and all(row["passed"] for row in rows)})
            require(len(calls) == 4 and all(shape[1] == 512 for shape in calls),
                    "Four complete encoder passes, not standalone-head reuse, are required")
        finally:
            hook.remove()
            if terminal_output_directory is not None and terminal_values:
                terminal_artifact = _save_terminal_archive(terminal_output_directory, spec, terminal_values)
        require(_view_identity(views) == identities, "The original physical views were mutated")
        if device.type == "cuda": torch.cuda.synchronize(device)
        return {"schema": SCHEMA+"_case", "case": asdict(spec), "case_id": spec.identity,
            "device": str(device), "weight_summary": weights, "encoder_configuration": model.encoder.config_dict(),
            "registry_sha256": registry.content_sha256, "fixture_native_atoms": [3, 9, 32],
            "fixture_geometry_sha256": _tensor_digest(base.pos), "original_physical_geometry_sha256": _tensor_digest(views.batch.pos),
            "original_view_identity_sha256": identities, "domain": domain, "encoder_forward_shapes": [list(s) for s in calls],
            "actual_terminal_output_artifact": terminal_artifact,
            "measurements": measurements, "complete_terminal_count": len(original_tables),
            "runtime": runtime_description(device), "wall_seconds": time.perf_counter()-started,
            "passed": domain["domain_pass"] and all(row["passed"] for row in measurements),
            "trained_or_selected_model": False, "actual_native_data_reads": 0}


def assert_case_passed(result):
    failures = [(t["transform"]["name"], f["field"], f["maxabs"], f["argmax"])
        for t in result["measurements"] for f in t["fields"] if not f["passed"]]
    require(result["passed"], f"{result['case_id']}: absolute/nonzero/domain/edge check FAILED; domain={result['domain']}; terminals={failures}")


def runtime_description(device):
    value = {"python": platform.python_version(), "torch": torch.__version__, "device": str(device),
        "default_dtype": str(torch.get_default_dtype()), "intraop_threads": torch.get_num_threads(),
        "TF32_matmul": torch.backends.cuda.matmul.allow_tf32, "TF32_cudnn": torch.backends.cudnn.allow_tf32,
        "float32_matmul_precision": torch.get_float32_matmul_precision(), "autocast_enabled": torch.is_autocast_enabled(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled()}
    if torch.device(device).type == "cuda":
        prop = torch.cuda.get_device_properties(device)
        value.update(cuda=torch.version.cuda, gpu_name=prop.name, gpu_uuid=str(prop.uuid),
            peak_allocated_bytes=torch.cuda.max_memory_allocated(device), peak_reserved_bytes=torch.cuda.max_memory_reserved(device))
    return value


def execution_source_inventory(repository):
    root = Path(repository).absolute()
    package = root/"current/phychem_mfm"
    paths = sorted({p.relative_to(root).as_posix() for p in package.rglob("*.py")} | set(EXTRA_SOURCE_FILES))
    require(paths and "current/phychem_mfm/phase1/v3_composed_equivariance.py" in paths, "Complete current package source required")
    result = {}
    for name in paths:
        path = root/name
        require(path.is_file() and not path.is_symlink(), "Ordinary frozen source file required: "+name)
        raw = path.read_bytes()
        result[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    return result
