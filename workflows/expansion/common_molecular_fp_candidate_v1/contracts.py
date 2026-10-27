"""Pure contracts. DATA locators are validated structurally, never opened here."""
from __future__ import annotations

import json
import re

KEY = "common_molecular_fp_candidate_v1"
REQUEST_SCHEMA = "COMMON_MOLECULAR_FP_CANDIDATE_REQUEST_V1"
CANDIDATE_SCHEMA = "COMMON_MOLECULAR_FP_PRODUCER_CANDIDATE_V1"
EXECUTION_IMPLEMENTED = False
FINGERPRINT_RECIPE = "ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5"
PROJECTION_SCHEMA = "expansion_common_v1_structure_projection_v1"
PROJECTION_FIELDS = frozenset(("molecule_id", "full_key", "ecfp4_2048_hex",
                               "generic_murcko", "generic_ring_systems"))
ROLES = ("TRAIN", "VAL")
REQUIRED_IDENTITY_COLUMNS = (
    "molecule_id", "record_id", "smiles", "canonical_smiles", "isomeric_smiles",
    "stored_inchikey", "reidentified_inchikey", "wp5_backbone_proton_key",
    "source_path", "real_index", "conformer_id", "record_payload_sha256",
    "QC_key_reproduction_mismatch_accepted_difference", "QC_other_layer_accepted_difference",
)
OPTIONAL_IDENTITY_COLUMNS = (
    "reidentified_smiles", "stored_backbone_proton_key", "reidentified_backbone_proton_key",
    "reidentified_connectivity_key", "shard_id", "shard_name", "source_family",
    "original_member_train", "original_member_full", "original_member_routine",
    "stereo_pair_difference_class", "stereo_difference_class", "stereo_chirality_changed",
    "stereo_ez_changed", "stereo_other_layer_changed", "source_smiles_has_chiral",
    "source_smiles_has_ez", "stereo_cache_parse_error", "QC_stereo_cache_missing",
    "QC_molecule_chirality_conflict", "QC_molecule_ez_conflict",
    "QC_stereo_consistency_assessed", "QC_molecule_unresolved_stereo_conformers",
    "QC_key_reproduction_mismatch", "QC_other_layer_present",
)
IDENTITY_COLUMNS = frozenset(REQUIRED_IDENTITY_COLUMNS + OPTIONAL_IDENTITY_COLUMNS)
KERNEL_PATHS = (
    "workflows/expansion/common.py", "workflows/expansion/screen.py",
    "workflows/expansion/features_generic_candidate_v1.py",
    "workflows/expansion/features_legacy_compatible_v2.py",
)
METHODS = 3


class ContractError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise ContractError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def reference(value, *, small=False):
    need(type(value) is dict and set(value) == {"path", "bytes", "sha256"},
         "EXACT_PRODUCER_TRIPLE_REQUIRED")
    path, size, digest = value["path"], value["bytes"], value["sha256"]
    need(type(path) is str and path and not any(c in path for c in "\x00\r\n"),
         "LITERAL_REFERENCE_PATH_REQUIRED")
    need(type(size) is int and size > 0 and (not small or size <= 2 << 20),
         "POSITIVE_INTEGER_REFERENCE_SIZE_REQUIRED")
    need(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
         "SHA256_64_LOWER_HEX_REQUIRED")
    return dict(value)


def data_reference(value):
    ref = reference(value)
    need(ref["path"].startswith(("/share/home/zixiao/descriptor_analysis/runs/",
                                 "/gfshome/alpha/codex_data_v1_20261026/")),
         "EXPLICIT_MAIN_OR_ALPHA_DATA_LOCATOR_REQUIRED")
    need(".." not in ref["path"].split("/") and "//" not in ref["path"],
         "NONTRAVERSING_DATA_LOCATOR_REQUIRED")
    return ref


def valid_full_key(value):
    return type(value) is str and re.fullmatch(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", value) is not None


def membership(row):
    """Inspect the finalizer's actual column names; do not reconstruct membership."""
    need(type(row) is dict, "MEMBERSHIP_ROW_REQUIRED")
    for name in ("molecule_id", "effective_role", "records", "common_population"):
        need(name in row, "MISSING_FINAL_COMMON_MEMBERSHIP_FIELD:" + name)
    need(type(row["molecule_id"]) is str and row["molecule_id"], "NATIVE_MID_REQUIRED")
    need(type(row["common_population"]) is bool, "ACTUAL_COMMON_BOOLEAN_REQUIRED")
    if "common_population_v1" in row:
        need(row["common_population_v1"] is row["common_population"], "COMMON_ALIASES_DISAGREE")
    if not row["common_population"]:
        return None
    need(row["effective_role"] in ROLES, "COMMON_MUST_BE_FINAL_TRAIN_OR_ROUTINE_VAL")
    need(type(row["records"]) is int and row["records"] > 0, "FINAL_NATIVE_RECORD_CENSUS_REQUIRED")
    return {"molecule_id": row["molecule_id"], "effective_role": row["effective_role"],
            "records": row["records"]}

