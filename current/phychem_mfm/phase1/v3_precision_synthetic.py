"""Small S-only precision harness inputs, explicitly never a D5 proxy."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
from pathlib import Path

import torch
from torch_geometric.data import Batch, Data

from .v3_contract import FieldSpec, LabelRegistry, canonical_hash
from .v3_precision_experiment import PrecisionInputs, PrecisionStepTrainer, PrecisionExperiment, ROLES, PREREGISTERED_PLAN
from .v3_sampling import ConformerRef, MoleculeEntry, InMemorySamplingIndex, UniformMoleculeSampler
from .v3_structural import StructuralFieldBinding, StructuralViewConfig, build_structural_views, eligibility_from_choices
from .v3_trainer import PreparedV3Batch, SampleLRScheduler
from .v3_training import SampleClock
from ..model.v3_multiview import V3MultiViewModel
from ..model.v3_performance import PerformanceOptions, build_performance_model, make_adamw
from ..training.losses import LossWeights


class SyntheticPrecisionProvider:
    read_only, node_local = True, True
    source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    data_version = "synthetic_precision_harness_not_D5_v1"

    def __init__(self, index, registry, binding):
        self.index, self.registry, self.binding = index, registry, binding
        self.calls = 0

    def state_dict(self):
        return {"prepare_calls": self.calls}

    def load_state_dict(self, state):
        self.calls = state["prepare_calls"]

    def prepare(self, choices, *, role, view_config, enabled_groups, enabled_fields):
        self.calls += 1
        records = []
        for choice in choices:
            n = choice.native_atoms
            phase = .2 * choice.molecule_index + (.15 if role == "VAL" else .07 if role != "TRAIN" else 0.)
            axis = torch.arange(n, dtype=torch.float32)
            records.append(Data(x=torch.full((n, 1), 5, dtype=torch.long),
                pos=torch.stack((axis * .7, (axis + phase).sin() * .3, (axis * .6 + phase).cos() * .2), -1),
                rdkit_bond_index=torch.stack((torch.arange(n - 1), torch.arange(1, n))),
                rdkit_bond_order=(torch.arange(n - 1) % 5 + 1).long(), rdkit_bond_status="ok"))
        masks = eligibility_from_choices(choices, self.registry, self.binding, enabled_fields=enabled_fields)
        views = build_structural_views(Batch.from_data_list(records), ordinals=tuple(c.ordinal for c in choices),
            config=view_config, include_structural=True, graph_eligibility=masks)
        return PreparedV3Batch(tuple(choices), views, {}, self.source_sha256, self.data_version, role)

    def validation_batches(self, *, role, view_config, enabled_groups, enabled_fields):
        sampler = UniformMoleculeSampler(self.index, seed=37, sample_budget=2)
        choices = tuple(sampler.choice(i) for i in range(2))
        choices = tuple(replace(c, ordinal=(100 if role == "VAL" else 200) + i,
            molecule_id="synthetic-unseen-" + str(i) if role == "VAL" else c.molecule_id,
            conformer_id="synthetic-unseen-conformer-" + str(i)) for i, c in enumerate(choices))
        # Exactly two tiny molecules; no population size or authority is implied.
        batch = self.prepare(choices, role=role, view_config=view_config,
                             enabled_groups=enabled_groups, enabled_fields=enabled_fields)
        return 1, iter((batch,))

    def close(self):
        return None


def synthetic_inputs(*, layers=1):
    fields = (FieldSpec("s_element", "S", "structural", "atom", kind="classification", classes=119, unit="element_class"),
              FieldSpec("s_noise", "S", "structural", "atom", kind="denoise_eps_mse", representation="vector", unit="angstrom"),
              FieldSpec("s_bond", "S", "structural", "pair", kind="classification", classes=5, unit="bond_order_class"))
    registry = LabelRegistry(fields, SyntheticPrecisionProvider.data_version, SyntheticPrecisionProvider.source_sha256)
    binding = StructuralFieldBinding("s_element", "s_noise", "s_bond")
    index = InMemorySamplingIndex(tuple(MoleculeEntry(f"synthetic-m{i}",
        tuple(ConformerRef(f"synthetic-c{i}-{j}", j, 6 + i, (("PM7", f"synthetic-only:{i}:{j}"),)) for j in range(2)),
        (("S", True), ("D", False), ("P", False)), (("structural", True),)) for i in range(2)),
        SyntheticPrecisionProvider.data_version)
    config = {"architecture": {"preset": "shared_light"},
        "backbone": {"dim": 512, "layers": layers, "heads": 8, "ff_mult": 2, "n_atom_types": 119},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise", "geometry_hidden_dim": 64,
                 "geometry_message_layers": 0, "geometry_pair_chunk_size": 8192}}
    populations = {role: canonical_hash({"role": role, "fixture_source": SyntheticPrecisionProvider.source_sha256}) for role in ROLES}
    role_sources = {role: {"authority": "synthetic_fixture_not_proxy_TRAIN", "population_binding_sha256": populations[role],
        "purpose": "SYNTHETIC_HARNESS_GATE" if role == "VAL" else "DIAGNOSTIC_ONLY"} for role in ROLES}
    return PrecisionInputs(index, SyntheticPrecisionProvider(index, registry, binding), registry, binding, {}, config,
        {"scope": "synthetic_harness_only_not_authoritative_D5", "molecules": 2},
        populations, role_sources)


def build_precision_member(inputs, plan, *, seed, precision, tracker, source_bindings, code_sha,
                           device="cpu", allow_unit_tracker=False, run_bindings=None):
    """Explicit model-side builder, independent of the data line's storage schema."""
    from .v3_contract import require
    require(plan.input_kind == "synthetic" or getattr(inputs.index, "authority", None) == "data_line",
            "Synthetic inputs cannot enter real proxy training")
    if plan.input_kind == "authoritative_proxy":
        require(len(inputs.index) == 240000 and len(inputs.verified_request_sha256) == 64,
                "Verified240000-molecule D5 request required before model construction")
    require(all(type(v) is str and len(v) == 64 and all(c in "0123456789abcdef" for c in v)
                for v in source_bindings.values()) and source_bindings,
            "Complete explicit source file bindings required")
    require(type(code_sha) is str and len(code_sha) == 40 and all(c in "0123456789abcdef" for c in code_sha),
            "Explicit actual code commit required")
    require(all(field.group == "S" for field in inputs.registry.fields), "Explicit S-only authoritative registry projection required")
    torch.manual_seed(seed)
    import json
    directory = PREREGISTERED_PLAN.parent
    option_files = {mode: directory / ("b00_fp32.json" if mode == "fp32" else "b01_bf16.json") for mode in ("fp32", "bf16")}
    pinned_options = {mode: json.loads(path.read_text()) for mode, path in option_files.items()}
    require({k: v for k, v in pinned_options["fp32"].items() if k != "precision"}
            == {k: v for k, v in pinned_options["bf16"].items() if k != "precision"}, "Published B options must differ only in precision")
    options = PerformanceOptions(**pinned_options[precision])
    encoder = build_performance_model(inputs.model_configuration, options).to(device)
    model = V3MultiViewModel(encoder, None, inputs.registry, inputs.structural_binding)
    optimizer_config = {"lr": 3e-4, "betas": [.9, .95], "weight_decay": .01}
    optimizer = make_adamw(model, optimizer_config, options)
    sampler = UniformMoleculeSampler(inputs.index, seed=seed, sample_budget=plan.sample_budget)
    scheduler = SampleLRScheduler(optimizer, sample_budget=plan.sample_budget)
    common = {"plan_sha256": plan.sha256, "source_files": dict(source_bindings), "actual_code_sha": code_sha,
        "model": inputs.model_configuration, "optimizer": optimizer_config,
        "base_performance_options": pinned_options["fp32"], "index_sha256": inputs.index.content_sha256,
        "data_version": inputs.index.version, "registry_sha256": inputs.registry.content_sha256,
        "normalization_sha256": canonical_hash({key: asdict(value) for key, value in inputs.normalizations.items()}),
        "authority_receipt_sha256": canonical_hash(inputs.authority_receipt),
        "verified_authority_request_sha256": inputs.verified_request_sha256,
        "published_protocol_files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                     for path in (PREREGISTERED_PLAN, *option_files.values())},
        "validation_population_bindings": inputs.validation_population_bindings, "noise_field": inputs.structural_binding.noise,
        "validation_role_sources": inputs.validation_role_sources,
        "schedule": scheduler.contract, "loss_weights": asdict(LossWeights()),
        "run_bindings": dict(run_bindings or {}),
        "loss_semantics": "V3_S_group_mean_of_observed_original_A4_raw_fields_not_old_weighted_runner_total"}
    common["runtime"] = {"torch": str(torch.__version__), "cuda_runtime": torch.version.cuda,
        "device_type": torch.device(device).type, "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
        "gpu_name": torch.cuda.get_device_name(device) if torch.device(device).type == "cuda" else None}
    member = {**common, "seed": seed, "precision": precision}
    bindings = {"code_sha": code_sha, "configuration_sha256": canonical_hash(member),
        "registry_sha256": inputs.registry.source_sha256, "normalization_sha256": common["normalization_sha256"],
        "data_version": inputs.index.version, "precision_source_inventory_sha256": canonical_hash(source_bindings)}
    trainer = PrecisionStepTrainer(model, optimizer, scheduler, sampler, SampleClock(plan.sample_budget, ()),
        inputs.provider, inputs.normalizations, LossWeights(), tracker, bindings, enabled_groups=("S",),
        view_config=StructuralViewConfig(seed=seed), validation_seed=plan.validation_seed,
        allow_unit_tracker=allow_unit_tracker, probe_samples=1)
    return PrecisionExperiment(trainer, plan, seed=seed, precision=precision, comparison_binding=common)
