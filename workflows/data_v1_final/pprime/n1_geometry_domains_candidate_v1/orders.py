"""Original physical-int64 orders and fixed-map proper-Kabsch function binding."""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
from . import contracts as C
from workflows.data_v1_final.conformers import selection as original_selection

stable_key = original_selection.stable_key
conformer_orders = original_selection.conformer_orders

class FixedMappingDistance:
    def __init__(self, science_module, source_reference, mol):
        ref = C.reference(source_reference, small=True)
        expected = C.source_bindings()["proper_Kabsch_science"]["origin_reference"]
        C.need((ref["bytes"], ref["sha256"]) == (expected["bytes"], expected["sha256"]),
               "ORIGINAL_FROZEN_PROPER_KABSCH_SOURCE_BYTES_REQUIRED")
        p = Path(science_module.__file__)
        C.need(str(p.absolute()) == ref["path"] and p.is_file() and not p.is_symlink() and
               p.stat().st_size == ref["bytes"], "EXACT_ORIGINAL_SCIENCE_MODULE_SOURCE_REQUIRED")
        body = p.read_bytes()
        C.need(hashlib.sha256(body).hexdigest() == ref["sha256"] and
               science_module.rmsd.__globals__ is science_module.__dict__ and
               science_module.rmsd.__code__.co_filename == str(p), "ORIGINAL_PROPER_KABSCH_FUNCTION_OBJECT_REQUIRED")
        self.function = science_module.rmsd
        self.module = science_module
        self.mol = mol
        self.reference = ref

    def __call__(self, left, right):
        C.need(self.function is self.module.rmsd, "KABSCH_FUNCTION_OBJECT_REPLACED")
        return self.function(self.mol, left["coordinates"], right["coordinates"])

def expanded_orders(molecule_id, base_rows, distance):
    C.need(type(distance) is FixedMappingDistance, "ORIGINAL_FIXED_MAPPING_DISTANCE_BINDING_REQUIRED")
    C.text(molecule_id)
    expected = C.source_bindings()["selection"]["origin_reference"]
    path = Path(original_selection.__file__)
    C.need(path.is_file() and not path.is_symlink() and path.stat().st_size == expected["bytes"] and
           hashlib.sha256(path.read_bytes()).hexdigest() == expected["sha256"] and
           stable_key is original_selection.stable_key and conformer_orders is original_selection.conformer_orders,
           "ORIGINAL_FROZEN_ORDER_FUNCTION_OBJECTS_AND_SOURCE_REQUIRED")
    rows = []
    for row in base_rows:
        C.need(row["geometry_source"] == C.SOURCE and row["parent_geometry_id"] is None and
               row["view_id"] is None, "REAL_UFF_BASE_NOT_EXPANDED_VIEW_MARKER_REQUIRED")
        idx = C.physical_id(row["sprime_conf_idx"])
        C.need(type(row["uff_energy_kcal_mol"]) in (int, float) and
               math.isfinite(row["uff_energy_kcal_mol"]), "ACTUAL_FINITE_UFF_ENERGY_ONLY_FOR_UFF_ORDER")
        rows.append({**row, "conformer_id": idx, "energy": row["uff_energy_kcal_mol"]})
    C.need(len(rows) >= 2 and len({r["geometry_id"] for r in rows}) == len(rows), "TWO_DISTINCT_REAL_BASES_REQUIRED")
    # The old objects perform energy tie-breaks, proper-Kabsch diversity and
    # stable-key random order. Native producer order arrays remain provenance.
    value = conformer_orders(rows, distance, molecule_id, C.SOURCE, C.ORDER_SEED)
    by_id = {r["conformer_id"]: r["geometry_id"] for r in rows}
    return {"physical_int64_orders": value,
            "geometry_id_orders": {k: [by_id[idx] for idx in ids] for k, ids in value.items()},
            "producer_native_orders_preserved_separately": True, "order_seed": C.ORDER_SEED,
            "order_identity_source": C.SOURCE, "not_final_order_authority": True,
            "proper_Kabsch_source_reference": distance.reference}

