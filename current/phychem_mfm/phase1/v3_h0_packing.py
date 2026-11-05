"""Deterministic, label-free native atom packing for frozen H0 export."""
from __future__ import annotations

import hashlib
import json


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def packing_budget(*, max_graphs=32, max_native_atoms=65536,
                   max_padded_pairs=1_000_000, atom_bucket_width=16):
    values = dict(max_graphs=max_graphs, max_native_atoms=max_native_atoms,
                  max_padded_pairs=max_padded_pairs, atom_bucket_width=atom_bucket_width)
    if any(type(value) is not int or value <= 0 for value in values.values()):
        raise ValueError("H0 packing budgets must be positive builtin integers")
    return {"schema": "model_v3_h0_packing_budget_v1", **values,
            "order": "stable_native_atom_bucket_then_count_then_original_ordinal",
            "bucket_boundary": "flush",
            "padded_pairs": "graphs_times_max_native_atoms_squared_single_view",
            "oversized_policy": "retain_complete_singleton_plan_then_fail_declared_budget",
            "capacity_measurement": "preset_only_not_a_verified_GPU_capacity"}


def budget_arguments(budget):
    keys = ("max_graphs", "max_native_atoms", "max_padded_pairs", "atom_bucket_width")
    try:
        arguments = {key: budget[key] for key in keys}
    except (KeyError, TypeError) as exc:
        raise ValueError("An explicit versioned H0 packing budget is required") from exc
    if budget != packing_budget(**arguments):
        raise ValueError("H0 packing recipe or policy differs from its versioned contract")
    return arguments


def packing_plan(native_n_atoms, *, record_order_sha256, **arguments):
    budget = packing_budget(**arguments)
    counts = tuple(native_n_atoms)
    if not counts or any(type(n) is not int or n < 1 for n in counts):
        raise ValueError("Positive native atom counts for every source record required")
    if type(record_order_sha256) is not str or len(record_order_sha256) != 64:
        raise ValueError("Exact ordered native source-record binding required")
    order = sorted(range(len(counts)), key=lambda i: (
        (counts[i]-1)//budget["atom_bucket_width"], counts[i], i))
    batches, group, atoms, largest, bucket = [], [], 0, 0, None
    for index in order:
        n = counts[index]
        next_bucket = (n-1)//budget["atom_bucket_width"]
        padded = (len(group)+1)*max(largest, n)**2
        if group and (next_bucket != bucket or len(group) >= budget["max_graphs"]
                      or atoms+n > budget["max_native_atoms"] or padded > budget["max_padded_pairs"]):
            batches.append(group); group, atoms, largest = [], 0, 0
        group.append(index); atoms += n; largest = max(largest, n); bucket = next_bucket
        if n > budget["max_native_atoms"] or n*n > budget["max_padded_pairs"]:
            # Keep the native member in the plan as a whole singleton. Never
            # drop it, trim its atoms, or silently relax the declared budget.
            batches.append(group); group, atoms, largest, bucket = [], 0, 0, None
    if group:
        batches.append(group)
    flat = [index for batch in batches for index in batch]
    if sorted(flat) != list(range(len(counts))):
        raise RuntimeError("Native packing lost or duplicated source records")
    statistics = []
    oversized = []
    for batch in batches:
        n_atoms = sum(counts[i] for i in batch)
        pairs = len(batch)*max(counts[i] for i in batch)**2
        too_large = n_atoms > budget["max_native_atoms"] or pairs > budget["max_padded_pairs"]
        if too_large:
            if len(batch) != 1:
                raise RuntimeError("Only retained singleton records may exceed a packing budget")
            oversized.extend(batch)
        statistics.append({"graphs": len(batch), "native_atoms": n_atoms, "padded_pairs": pairs})
    value = {"schema": "model_v3_h0_packing_plan_v1", "budget": budget,
             "budget_sha256": canonical(budget), "record_order_sha256": record_order_sha256,
             "native_n_atoms": list(counts), "batches": batches, "batch_statistics": statistics,
             "oversized_singleton_ordinals": oversized, "records_retained": len(counts),
             "native_atoms_retained": sum(counts), "labels_consulted": False}
    return {**value, "plan_sha256": canonical(value)}


def packing_plans_for_views(store, views, budget):
    """Plan only from bound source shape/identity metadata; never call get()."""
    arguments = budget_arguments(budget)
    plans = {}
    for dataset, view in views.items():
        records = []
        for role in ("train", "train_inner_validation"):
            for index in view.view(role):
                row = store.native_geometry_metadata(dataset, index)
                if row["geometry_ready"]:
                    records.append(row)
        order_sha = canonical([[dataset, row["member_index"], row["member_uid"]] for row in records])
        plans[dataset] = packing_plan([row["native_n_atoms"] for row in records],
                                     record_order_sha256=order_sha, **arguments)
    return plans


class H0PackingBudgetError(ValueError):
    def __init__(self, plan):
        self.packing_plan = plan
        super().__init__("Native H0 records retained as singletons exceed the declared packing budget; "
                         "this is a preset-budget failure, not a measured GPU-capacity result")
