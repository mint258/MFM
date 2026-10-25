"""Strict source-identity rows; no downstream targets, features or common filter."""
from __future__ import annotations

from collections import Counter

from ..common import KEY_RE, require
from .readers_v2 import EMBARGO_COLUMNS, FORMAL_COLUMNS


SMILES_FIELDS = ("smiles", "canonical_smiles", "isomeric_smiles", "reidentified_smiles")
KEY_FIELDS = ("stored_inchikey", "reidentified_inchikey")


def full_keys(values, *, strict=True):
    valid, invalid = set(), []
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, str) and KEY_RE.fullmatch(value):
            valid.add(value)
        else:
            require(not strict, "Invalid full-InChIKey in a claimed resolved identity source")
            invalid.append(value)
    return sorted(valid), invalid


def native_composition(pairs):
    require(pairs is not None, "Native non-H composition is absent")
    counts = Counter()
    source_pairs = pairs.items() if isinstance(pairs, dict) else pairs
    for z, count in source_pairs:
        require(type(z) is int and 1 <= z <= 118 and type(count) is int and count > 0,
                "Native element counts must be actual positive integers")
        if z != 1:
            counts[z] += count
    require(counts, "No conservative non-H composition can be established")
    return [[z, counts[z]] for z in sorted(counts)]


def identity(dataset, source_id, role, smiles, keys, *, memberships=None, composition=None, reason=None,
             unresolved_variant=False, invalid_cached_keys=None):
    require(isinstance(source_id, str) and source_id and dataset and role, "Original source ID/dataset/role required")
    require(all(s is None or isinstance(s, str) for s in smiles), "Source SMILES must be original strings/nulls")
    valid, _ = full_keys(keys)
    # Resolved sources never export composition as an extra broad exclusion.
    require(composition is None or reason is not None, "Composition exclusion requires a declared conservative source reason")
    return {"dataset": dataset, "source_id": source_id, "role": role,
            "memberships": sorted(set(memberships or [role])),
            "smiles_variants": sorted({s for s in smiles if s is not None and s.strip()}),
            "inchikeys": valid, "non_h_composition": composition, "conservative_reason": reason,
            "unresolved_source_variant": bool(unresolved_variant), "invalid_cached_identity_tokens": invalid_cached_keys or [],
            "missing_full_key": not valid, "missing_identity_or_composition": not valid and composition is None}


def formal_row(row):
    require(set(row) == set(FORMAL_COLUMNS), "Only the exact complete formal identity/original-role projection may enter")
    train, full, routine = (row[k] for k in ("member_train", "member_full", "member_routine"))
    require(all(type(v) is bool for v in (train, full, routine)) and train != full and (not routine or full),
            "Original unique TRAIN/FULL authority and ROUTINE subset must be retained")
    require(isinstance(row["molecule_id"], str) and row["molecule_id"] and all(row[k] for k in KEY_FIELDS),
            "Formal source lost frozen molecule ID or one of its two key authorities")
    keys, _ = full_keys([row[k] for k in KEY_FIELDS])
    require(len({(key[:14], key[-1]) for key in keys}) == 1, "Formal stored/reidentified WP5 identity invariant changed")
    role = "VAL" if routine else "FULL" if full else "TRAIN"
    result = identity("v1_all_roles_and_embargo", row["record_id"], role, [row[k] for k in SMILES_FIELDS], keys,
                      memberships=["FULL", "VAL"] if routine else [role])
    result["molecule_id"] = row["molecule_id"]
    return result


def embargo_row(row):
    require(set(row) == set(EMBARGO_COLUMNS), "Only the complete original4900 embargo identity projection may enter")
    source_reason = row["legacy_QA_status"]
    require(source_reason in {"known_fullkey_embargo", "unknown_non_h_composition_embargo"}, "Unexpected original embargo class")
    unknown = source_reason == "unknown_non_h_composition_embargo"
    keys, invalid = full_keys([row[k] for k in KEY_FIELDS], strict=not unknown)
    require(unknown or keys, "Original known-fullkey embargo lost every full identity key")
    result = identity("v1_all_roles_and_embargo", row["record_id"], "EMBARGO", [row[k] for k in SMILES_FIELDS], keys,
                      composition=native_composition(row["element_counts"]) if unknown else None,
                      reason="ORIGINAL_UNKNOWN_NON_H_COMPOSITION_EMBARGO" if unknown else None,
                      unresolved_variant=unknown, invalid_cached_keys=invalid)
    result.update(molecule_id=row["molecule_id"], original_embargo_class=source_reason)
    return result


def rdkit_identity_modules():
    from rdkit import Chem, rdBase
    require(rdBase.rdkitVersion == "2025.09.5", "Identity-only graph parsing must use frozen RDKit2025.09.5")
    return Chem


def source_smiles_keys(smiles_variants):
    """No neutralization, tautomer/stereo/isotope edits or chemical exclusions."""
    Chem = rdkit_identity_modules()
    keys, unresolved = [], []
    for name, smiles in smiles_variants.items():
        require(isinstance(smiles, str) and smiles, "Missing original source SMILES")
        try:
            mol = Chem.MolFromSmiles(smiles)
            key = None if mol is None else Chem.MolToInchiKey(mol)
            require(key is not None and KEY_RE.fullmatch(key), "Source SMILES has no valid standard full key")
            keys.append(key)
        except Exception as exc:
            unresolved.append({"source_field": name, "exception_type": type(exc).__name__, "message": str(exc)})
    return sorted(set(keys)), unresolved


def expansionrx_row(row, role, ordinal):
    require(set(row) == {"Molecule Name", "SMILES"} and role in {"train", "test"} and ordinal > 0,
            "Only whole official train/test identity columns, without targets, are accepted")
    require(isinstance(row["Molecule Name"], str) and row["Molecule Name"], "Original ExpansionRx ID missing")
    keys, errors = source_smiles_keys({"SMILES": row["SMILES"]})
    result = identity("expansionrx", f"{role}:{ordinal}:{row['Molecule Name']}", role, [row["SMILES"]], keys,
                      unresolved_variant=bool(errors))
    result.update(original_source_id=row["Molecule Name"], source_record_1based=ordinal, identity_errors=errors)
    return result


def qm7_row(sample_id, z_values, fold):
    require(type(sample_id) is int and 1 <= sample_id <= 7165 and type(fold) is int and 0 <= fold < 10,
            "Original MAT row ID/all-fold membership required")
    counts = Counter()
    for value in z_values:
        z = int(value)
        require(z == value and 0 <= z <= 118, "Invalid original Z nuclear number/padding")
        if z:
            counts[z] += 1
    return identity("qm7", str(sample_id), "all", [], [], memberships=["all", "fold_" + str(fold)],
                    composition=native_composition(counts), reason="QM7_AUTHOR_GRAPH_CHARGE_STEREO_UNPROVEN_NATIVE_Z_ONLY",
                    unresolved_variant=True)


def qm9_row(sample_id, payload, fold, historical_source=None):
    require(type(sample_id) is int and 1 <= sample_id <= 133885 and type(fold) is int and 0 <= fold < 10,
            "Original whole133885 source ID/all-fold membership required")
    if historical_source is not None:
        require(historical_source["source_sha256"] == payload["source_sha256"] and
                historical_source["source_bytes"] == payload["source_bytes"],
                "Current original archive member does not match previously used source bytes")
    smiles = {"original_gdb": payload["original_gdb_smiles"], "relaxed": payload["relaxed_smiles"]}
    keys, errors = source_smiles_keys(smiles)
    composition = None
    if errors:
        Chem = rdkit_identity_modules()
        table = Chem.GetPeriodicTable()
        composition = native_composition([(table.GetAtomicNumber(symbol), count)
                                          for symbol, count in payload["native_symbol_counts"].items()])
    result = identity("qm9", str(sample_id), "all", list(smiles.values()), keys,
                      memberships=["all", "fold_" + str(fold)], composition=composition,
                      reason="QM9_UNRESOLVED_SOURCE_VARIANT_NATIVE_COMPOSITION" if errors else None,
                      unresolved_variant=bool(errors))
    result.update(identity_errors=errors, original_member_sha256=payload["source_sha256"],
                  original_member_bytes=payload["source_bytes"])
    return result
