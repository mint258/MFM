"""Candidate nested subsets; frozen roles/common population/orders are mandatory."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from .codec import canonical_json


def read_manifest(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def require_frozen(roles, common, orders, roles_sha, common_sha):
    if roles.get("status") != "FROZEN" or roles.get("validation_source") != "ROUTINE":
        raise ValueError("ROUTINE_ROLES_NOT_FROZEN")
    if not roles.get("all_conformers_same_role"):
        raise ValueError("MOLECULAR_ROLE_AUTHORITY_REQUIRED")
    if common.get("status") != "FROZEN" or not common.get("geometries_frozen"):
        raise ValueError("FINAL_COMMON_POPULATION_NOT_FROZEN")
    if common.get("roles_authority_sha256") != roles_sha:
        raise ValueError("COMMON_ROLE_BINDING_MISMATCH")
    if orders.get("status") != "FROZEN" or orders.get("common_manifest_sha256") != common_sha:
        raise ValueError("CONFORMER_ORDERS_NOT_FROZEN_OR_UNBOUND")
    if orders.get("roles_authority_sha256") != roles_sha:
        raise ValueError("ORDER_ROLE_BINDING_MISMATCH")
    if set(orders.get("order_types", [])) != {"random", "energy", "diversity"}:
        raise ValueError("THREE_CONFORMER_ORDERS_REQUIRED")
    if set(orders.get("geometry_sources", [])) != {"pm7", "uff_sprime"}:
        raise ValueError("BOTH_GEOMETRY_SOURCES_REQUIRED")


def _permutation(values, seed):
    values = sorted(values)
    rng = np.random.Generator(np.random.PCG64(seed))
    return [values[i] for i in rng.permutation(len(values))]


def plan_subsets(common_rows, conformer_orders, *, roles, common, orders,
                 roles_sha, common_sha, orders_sha, seed, sizes=(120000, 240000, 600000),
                 pilot_train=50000, pilot_val=5000, diagnostic=20000, fixture=False):
    require_frozen(roles, common, orders, roles_sha, common_sha)
    if type(seed) is not int or seed < 0 or seed >= 2 ** 63 - 2:
        raise ValueError("EXPLICIT_BOUNDED_RANDOM_SEED_REQUIRED")
    if not fixture and (sizes != (120000, 240000, 600000) or
                        (pilot_train, pilot_val, diagnostic) != (50000, 5000, 20000)):
        raise ValueError("PRODUCTION_SUBSET_COUNTS_MUST_MATCH_GUIDE")
    population = {}
    for row in common_rows:
        mid, role = row["molecule_id"], row["effective_role"]
        if mid in population or not isinstance(mid, str) or role not in {"TRAIN", "VAL"}:
            raise ValueError("INVALID_OR_DUPLICATE_COMMON_MOLECULE")
        population[mid] = role
    train = _permutation([m for m, r in population.items() if r == "TRAIN"], seed)
    val = _permutation([m for m, r in population.items() if r == "VAL"], seed + 2)
    if not sizes or tuple(sorted(set(sizes))) != tuple(sizes) or sizes[0] < pilot_train:
        raise ValueError("INVALID_NESTED_SUBSET_SIZES")
    if len(train) < sizes[-1] or len(val) < pilot_val:
        raise ValueError("COMMON_POPULATION_TOO_SMALL_FOR_REQUIRED_SUBSETS")
    if set(conformer_orders) != {(m, g) for m in population for g in ("pm7", "uff_sprime")}:
        raise ValueError("MISSING_DUPLICATE_OR_EXTRA_MOLECULE_GEOMETRY_ORDERS")
    eligible = []
    for mid in population:
        for source in ("pm7", "uff_sprime"):
            table = conformer_orders[mid, source]
            lists = [table[name] for name in ("random", "energy", "diversity")]
            if any(not x or len(x) != len(set(x)) or any(not isinstance(v, str) for v in x) for x in lists):
                raise ValueError("INVALID_CONFORMER_ORDER")
            if any(set(x) != set(lists[0]) for x in lists[1:]):
                raise ValueError("CONFORMER_ORDER_MEMBERSHIP_MISMATCH")
        if population[mid] == "TRAIN" and all(
                len(conformer_orders[mid, g]["random"]) >= 2 for g in ("pm7", "uff_sprime")):
            eligible.append(mid)
    if len(eligible) < diagnostic:
        raise ValueError("NOT_ENOUGH_DIAGNOSTIC_MOLECULES")
    diagnostic_ids = _permutation(eligible, seed + 1)[:diagnostic]
    excluded = [{"molecule_id": mid, "geometry_source": source,
                 "conformer_id": conformer_orders[mid, source]["random"][-1],
                 "reason": "TRAIN_MOLECULE_HELDOUT_GEOMETRY_DIAGNOSTIC_ONLY"}
                for mid in diagnostic_ids for source in ("pm7", "uff_sprime")]
    return {"status": "CANDIDATE_D5_PLAN_NOT_A_RELEASE", "seed": seed, "bit_generator": "PCG64",
            "numpy_version": str(np.__version__), "fixture": fixture, "roles_authority_sha256": roles_sha,
            "common_manifest_sha256": common_sha, "orders_manifest_sha256": orders_sha,
            "nested_train": {str(n): train[:n] for n in sizes}, "all_train": train,
            "pilot_train": train[:pilot_train], "pilot_val": val[:pilot_val],
            "diagnostic_molecules": diagnostic_ids, "exclude_from_every_training_condition": excluded,
            "diagnostic_use": "pretraining-loss diagnostics only; never model selection"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roles", type=Path, required=True)
    parser.add_argument("--common", type=Path, required=True)
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--metadata-only-preflight", action="store_true", required=True)
    args = parser.parse_args()
    roles, roles_sha = read_manifest(args.roles)
    common, common_sha = read_manifest(args.common)
    orders, orders_sha = read_manifest(args.orders)
    require_frozen(roles, common, orders, roles_sha, common_sha)
    print(canonical_json({"status": "FROZEN_INPUT_METADATA_PREFLIGHT_PASS_NOT_D5_GENERATED",
                          "roles_sha256": roles_sha, "common_sha256": common_sha,
                          "orders_sha256": orders_sha}).decode())


if __name__ == "__main__":
    main()
