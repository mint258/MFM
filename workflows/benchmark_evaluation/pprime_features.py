"""Read unchanged pretraining P fields from sealed native P-prime outcomes.

No quantum execution, conformer selection by success, value filling, unit
conversion, averaging, or new physical masks are performed here.
"""
import math
import numpy as np
from workflows.data_v1_final.labels.common import component_values, MISSING

class NativePprimeLayout:
    def __init__(self, schema, lookup):
        self.lookup = lookup
        self.molecule = [dict(c) for c in schema["columns"]["mol_labels"]
                         if c["field_key"].startswith("P.")]
        self.atom = [dict(c) for c in schema["columns"]["atom_labels"]
                     if c["field_key"].startswith("P.")]
        if not self.molecule or not self.atom:
            raise ValueError("Original pretraining P scalar columns are required")
        for column in self.molecule + self.atom:
            key = column["field_key"].split(".")
            if len(key) < 4 or not key[1] or not column["source_path"] or not column["unit"]:
                raise ValueError("Original P field task, source path and unit are required")
            column["native_task"] = key[1]

    def extract(self, result, n_atoms):
        if type(n_atoms) is not int or n_atoms <= 0:
            raise ValueError("Original geometry atom count is required")
        if result.get("Pprime_ready") is not True:
            return None, None, {"status": "NATIVE_PPRIME_UNAVAILABLE", "state": result.get("state")}
        tasks = {}
        for detail in result["tasks"]:
            name = detail["task"]
            if name in tasks:
                raise ValueError("A native quantum task is duplicated")
            tasks[name] = detail
        molecule = np.full(len(self.molecule), np.nan, dtype=np.float64)
        atom = np.full((n_atoms, len(self.atom)), np.nan, dtype=np.float64)
        issues = []
        for kind, columns in (("molecule", self.molecule), ("atom", self.atom)):
            for index, column in enumerate(columns):
                detail = tasks.get(column["native_task"])
                if detail is None or detail.get("scope_status", detail.get("status")) != "SUCCESS":
                    issues.append({"field": column["field_key"], "reason": "NATIVE_TASK_MISSING_OR_FAILED"})
                    continue
                value = self.lookup(detail, column["source_path"])
                field = {name: column[name] for name in ("source_path", "component", "level")}
                values, indices, reason = component_values(field, value, n_atoms)
                if reason is not None:
                    issues.append({"field": column["field_key"], "reason": reason})
                    continue
                if column["registry_id"] in (detail.get("numeric_issues") or []):
                    issues.append({"field": column["field_key"], "reason": "SOURCE_NUMERIC_ISSUE"})
                    continue
                if kind == "molecule":
                    if len(values) != 1 or indices != [None]:
                        raise ValueError("Original molecular P component no longer has a scalar layout")
                    if type(values[0]) in (int, float) and math.isfinite(values[0]):
                        molecule[index] = values[0]
                else:
                    if len(values) != len(indices) or len(set(indices)) != len(indices):
                        raise ValueError("Original atomic P source indices are incomplete or duplicated")
                    for native_index, scalar in zip(indices, values):
                        if type(native_index) is not int or not 0 <= native_index < n_atoms:
                            raise ValueError("Native P atom index is outside the original geometry")
                        if type(scalar) in (int, float) and math.isfinite(scalar):
                            atom[native_index, index] = scalar
        return molecule, atom, {"status": "NATIVE_PPRIME_COMPONENTS_BOUND",
                                "native_missing_components": issues}

def first_actual_conformer(source):
    """Use producer order and the actual ID; never look for a later successful P-prime."""
    conformers = (source.get("result") or {}).get("conformers") or []
    if not conformers:
        return None
    first = conformers[0]
    if first.get("geometry_source") != "UFF_Sprime" or first.get("converged") is not True:
        raise ValueError("The first delivered geometry is not an accepted native UFF conformer")
    return int(first["conformer_id"])

def remap_to_original_atoms(atom_features, model_atom_to_source, original_atom_count):
    """Missing source atom mappings remain NaN; never assign a predicted pKa site."""
    if atom_features is None:
        return None
    values = np.asarray(atom_features, dtype=np.float64)
    if values.ndim != 2 or len(model_atom_to_source) != len(values):
        raise ValueError("Original geometry atom map and P-prime rows differ")
    output = np.full((original_atom_count, values.shape[1]), np.nan, dtype=np.float64)
    used = set()
    for model_index, source_index in enumerate(model_atom_to_source):
        if source_index is None or source_index == -1:
            continue
        if type(source_index) is not int or not 0 <= source_index < original_atom_count or source_index in used:
            raise ValueError("Source atom mapping is not an unambiguous original atom identity")
        used.add(source_index)
        output[source_index] = values[model_index]
    return output
