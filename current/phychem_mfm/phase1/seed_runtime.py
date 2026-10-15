"""Pure metadata authority for a paired pretraining seed's runtime profile.

No device, process, filesystem or environment observation occurs here. Both
the scientific CLI and its supervisor must separately compare the selection
with their actual allocation/device/environment. UUID is intentionally absent:
segments and conditions may use another physical device in the same family.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import PurePosixPath
import re

SCHEMA = "phase1_seed_runtime_selection_v1"
PROFILE_FIELDS = {"gpu_model", "runtime_environment", "allowed_nodes"}
ENVIRONMENT_FIELDS = {"python_executable", "torch", "cuda_runtime", "default_dtype"}
NODES = {"compute-0-20", "compute-0-21", "compute-0-22"}
SUPPORTED_PAIRED_RUNTIMES = {
    "NVIDIA GeForce RTX 4090": ("2.10.0+cu126", "12.6"),
    "NVIDIA GeForce RTX 5090": ("2.10.0+cu128", "12.8"),
}
SHA = re.compile(r"[0-9a-f]{64}\Z")


class RuntimeBindingError(ValueError):
    pass


def _need(condition, message):
    if not condition:
        raise RuntimeBindingError(message)


def _seed(value):
    _need(type(value) is int and value in (0, 1, 2), "Paired seed must be the integer 0, 1 or 2")


def _text(value):
    return type(value) is str and bool(value) and value == value.strip() and not any(c in value for c in "\x00\n\r")


def _profile(value, *, strict_pairing):
    _need(type(value) is dict and set(value) == PROFILE_FIELDS, "Runtime profile fields differ")
    _need(_text(value["gpu_model"]), "GPU model must be an explicit nonempty string")
    nodes = value["allowed_nodes"]
    _need(type(nodes) is list and nodes and all(type(node) is str and node in NODES for node in nodes)
          and len(set(nodes)) == len(nodes), "Allowed nodes must be a nonempty unique subset of compute-0-20/21/22")
    environment = value["runtime_environment"]
    _need(type(environment) is dict and set(environment) == ENVIRONMENT_FIELDS
          and all(_text(item) for item in environment.values()), "Exact four-field runtime environment is required")
    _need(PurePosixPath(environment["python_executable"]).is_absolute()
          and environment["default_dtype"] == "torch.float32", "Absolute runtime interpreter and FP32 default are required")
    if strict_pairing:
        expected = SUPPORTED_PAIRED_RUNTIMES.get(value["gpu_model"])
        _need(expected is not None and (environment["torch"], environment["cuda_runtime"]) == expected,
              "Per-seed GPU family/Torch/CUDA runtime pairing is not the observed cu126/4090 or cu128/5090 pair")
    return deepcopy(value)


def profile_sha256(profile):
    """Hash the complete typed profile, including allowed-node order."""
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def select_runtime_binding(compute, *, seed):
    """Validate the sole authority and detach this seed's immutable selection.

The new table must contain all three profiles even when only one condition is
launched. Presence of that table forbids all legacy profile fields. Absence
keeps the original declared single-profile semantics, including exact runtime
comparison at each live entry; it does not silently interpret a mixed table.
    """
    _seed(seed)
    _need(type(compute) is dict, "Compute declaration must be a JSON object")
    if "runtime_bindings_by_seed" in compute:
        _need(not PROFILE_FIELDS.intersection(compute), "Per-seed and legacy runtime fields are conflicting authorities")
        table = compute["runtime_bindings_by_seed"]
        _need(type(table) is dict and set(table) == {"0", "1", "2"}
              and all(type(key) is str for key in table), "Runtime table requires exactly string keys 0, 1 and 2")
        validated = {key: _profile(value, strict_pairing=True) for key, value in table.items()}
        mode, selected = "per_seed", validated[str(seed)]
    else:
        _need(PROFILE_FIELDS.issubset(compute), "Legacy single-profile declaration is incomplete")
        mode = "legacy_single_profile"
        selected = _profile({key: compute[key] for key in PROFILE_FIELDS}, strict_pairing=False)
    return {"schema_version": SCHEMA, "binding_mode": mode, "paired_seed": seed,
            "profile": selected, "profile_sha256": profile_sha256(selected)}


def validate_runtime_selection(selection, *, seed):
    """Validate checkpoint/log binding metadata; this is not live device proof."""
    _seed(seed)
    _need(type(selection) is dict and set(selection) == {
        "schema_version", "binding_mode", "paired_seed", "profile", "profile_sha256"}, "Runtime selection fields differ")
    _need(selection["schema_version"] == SCHEMA and type(selection["binding_mode"]) is str
          and selection["binding_mode"] in {"per_seed", "legacy_single_profile"},
          "Unknown runtime binding schema or mode")
    _seed(selection["paired_seed"])
    _need(selection["paired_seed"] == seed, "Runtime binding belongs to another paired seed")
    profile = _profile(selection["profile"], strict_pairing=selection["binding_mode"] == "per_seed")
    _need(type(selection["profile_sha256"]) is str and SHA.fullmatch(selection["profile_sha256"])
          and selection["profile_sha256"] == profile_sha256(profile), "Runtime profile hash differs from its exact metadata")
    return deepcopy(selection)
