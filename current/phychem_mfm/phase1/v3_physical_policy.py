"""Model consumer for the exact Data native-frame30 exposure decision.

This is a loss-eligibility binding, never Data release/Model ACK authority.
It does not change labels, masks, normalization, geometry or model parameters.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat

LOSS_DISABLED_PHYSICAL = "LOSS_DISABLED_PHYSICAL_POLICY_UNBOUND"
POLICY_SCHEMA = "ROOT_D1_V3_PHYSICAL_EXPOSURE_AFTER_NATIVE30_V1"
POLICY_STATUS = "ROOT_DECISION_AFTER_ACTUAL_BOUNDED_TEST_NOT_MODEL_JOINT_ACK"
POLICY_PATH = "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/interfaces/physical_exposure_after_native_frame30_20261029_v1.json"
POLICY_SHA256 = "f0738ab48a3f8517aec955e64001e96710ee9921f6b666122a8595f28cddc43c"
TENSOR_SELECTOR = "REGISTRY674_ALL_SYMMETRIC6_CONDITIONS"
CHARGE_SELECTOR = "ORIGIN_SENSITIVE_ACTUAL_QM_CHARGE_NONZERO_TARGETS"
NOT_TARGETED = "NOT_TARGETED_BY_BOUND_PHYSICAL_POLICY"

def _need(ok, message):
    if not ok: raise ValueError(message)

def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def _read(reference):
    _need(type(reference) is dict and set(reference) == {"path", "bytes", "sha256"}
          and type(reference["path"]) is str and Path(reference["path"]).is_absolute()
          and type(reference["bytes"]) is int and 0 < reference["bytes"] <= 2 << 20
          and type(reference["sha256"]) is str and len(reference["sha256"]) == 64
          and all(c in "0123456789abcdef" for c in reference["sha256"]), "Exact bounded physical-policy rawref required")
    p = Path(reference["path"]); before = p.lstat()
    _need(stat.S_ISREG(before.st_mode) and not p.is_symlink() and before.st_uid == os.getuid()
          and before.st_nlink == 1 and before.st_size == reference["bytes"], "Physical-policy file identity differs")
    raw = p.read_bytes(); after = p.lstat()
    _need(all(getattr(before, k) == getattr(after, k) for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns"))
          and hashlib.sha256(raw).hexdigest() == reference["sha256"], "Physical-policy bytes changed")
    def unique(pairs):
        result = {}
        for k, v in pairs:
            _need(k not in result, "Duplicate physical-policy key"); result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite policy JSON")))

@dataclass(frozen=True)
class PhysicalLossPolicy:
    """Explicit per-target application of Data's unchanged registry674 selector."""
    reference: dict
    targets: dict
    engineering_only: bool = False

    def __post_init__(self):
        object.__setattr__(self, "reference", deepcopy(self.reference))
        object.__setattr__(self, "targets", deepcopy(self.targets))
        self.reverify()

    def reverify(self):
        _need(type(self.engineering_only) is bool, "Explicit physical-policy fixture scope required")
        doc = _read(self.reference)
        if self.engineering_only:
            _need(doc.get("UNIT_FIXTURE_ONLY_NOT_REAL_AUTHORITY") is True, "Explicit physical-policy UNIT fixture required")
        else:
            _need(self.reference["path"] == POLICY_PATH and self.reference["sha256"] == POLICY_SHA256
                  and doc.get("UNIT_FIXTURE_ONLY_NOT_REAL_AUTHORITY") is not True,
                  "Only the exact actual Data physical decision is admitted; a fixture cannot upgrade")
        _need(doc.get("schema") == POLICY_SCHEMA and doc.get("status") == POLICY_STATUS
              and doc.get("contract_version") == "v3.0" and doc.get("reviewer") == "root"
              and doc.get("global_physical_PASS") is False and doc.get("Model_same_version_ACK") is False
              and doc.get("original_numerical_accuracy_and_thresholds_unchanged") is True
              and doc.get("user_choices_1_to_4_unchanged") is True,
              "Unknown physical decision or false release/physical-PASS claim")
        rules = doc.get("xtb_singlepoint_rules")
        _need(type(rules) is list and len(rules) == 2, "Both exact Data exposure rules must be present")
        table = {r["selector"]: r for r in rules}
        _need(set(table) == {TENSOR_SELECTOR, CHARGE_SELECTOR}, "Unknown/duplicate physical selector")
        tensor, charge = table[TENSOR_SELECTOR], table[CHARGE_SELECTOR]
        _need(tensor.get("loss_status") == LOSS_DISABLED_PHYSICAL
              and type(tensor.get("reason")) is str and bool(tensor["reason"])
              and tensor.get("sampling_molecules_changed") is False
              and tensor.get("diagnostic_PASS_samples_not_selected_for_training") is True
              and tensor.get("components_values_masks_reasons_and_F64_retained") is True
              and tensor.get("scale_unbound_status_remains_separate") == "LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE"
              and tensor.get("other_ready_targets_continue") is True
              and charge.get("training_exposure") == "DISABLED_PER_USER_5A_FALLBACK"
              and charge.get("original_values_component_masks_reasons_preserved") is True
              and charge.get("new_numeric_mask") is False, "Physical exposure/source preservation policy differs")
        _need(type(self.targets) is dict, "Explicit Model target application map required")
        for name, binding in self.targets.items():
            _need(type(name) is str and bool(name) and type(binding) is dict
                  and set(binding) == {"registry_id", "target_id", "task", "condition"}
                  and type(binding["registry_id"]) is int and binding["registry_id"] == 674
                  and binding["task"] == "xtb_singlepoint"
                  and all(type(binding[k]) is str and bool(binding[k]) for k in ("target_id", "condition")),
                  "Only exact registry674/actual-task/condition target application is implemented")
        return doc

    @property
    def projection(self):
        self.reverify()
        return {"schema": "model_v3_physical_loss_policy_binding_v1", "Data_decision": deepcopy(self.reference),
                "targets": deepcopy(self.targets), "engineering_only": self.engineering_only,
                "consumer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "release_authority_granted": False, "charged_selector_support": "UNKNOWN_ORIGIN_SENSITIVE_TARGETS_HOLD"}

    @property
    def sha256(self): return _hash(self.projection)

    def validate_for_registry(self, registry, *, enabled_fields=None):
        self.reverify(); fields = registry.by_name()
        active = set(fields) if enabled_fields is None else set(enabled_fields)
        _need(active <= set(fields), "Unknown enabled physical-policy field")
        _need(set(self.targets) <= set(fields), "Physical target not in the actual model registry")
        for name, field in fields.items():
            if name in self.targets:
                _need(field.group in ("P", "D") and field.level == "graph" and field.kind == "regression"
                      and field.representation == "symmetric_tensor6", "Registry674 must be the complete tensor domain")
            elif name in active and field.group in ("P", "D") and field.kind == "regression" and field.representation in ("vector", "magnitude", "symmetric_tensor6"):
                raise ValueError("HOLD: origin-sensitive target lacks actual Data target/QM-charge policy binding: " + name)
        return self

    def disabled(self, name): return name in self.targets
    def reason(self, name):
        if name not in self.targets: return None
        return next(r["reason"] for r in self.reverify()["xtb_singlepoint_rules"] if r["selector"] == TENSOR_SELECTOR)

def physical_policy_for_release(release, registry, reference):
    """Consume existing joint evidence_source_references; invent no Data schema."""
    from .v3_data_adapter import VerifiedDataRelease, bound_json
    _need(isinstance(release, VerifiedDataRelease), "Verified same-request Data release required")
    release.reverify()
    joint = bound_json(release.evidence["joint_contract"])
    _need(reference in joint.get("evidence_source_references", []),
          "Same-version joint contract must bind the exact physical decision as existing evidence")
    policy = PhysicalLossPolicy(reference, {
        field.name: {"registry_id": release.projection["D4_bindings"][field.name]["registry_id"],
                     "target_id": release.projection["targets"][field.name]["target_id"],
                     "task": release.projection["D4_bindings"][field.name]["task"],
                     "condition": release.projection["D4_bindings"][field.name]["condition"]}
        for field in registry.fields if field.representation == "symmetric_tensor6"},
        engineering_only=not release.is_actual_data_release)
    for name, target in policy.targets.items():
        _need(target["condition"] == release.projection["targets"][name]["condition"],
              "Physical/D4 target condition differs")
    return policy.validate_for_registry(registry, enabled_fields=())
