"""Generate the v3 metadata registry from pinned, closed audit metadata only."""
from __future__ import annotations

import argparse
import collections
import csv
from pathlib import Path

from common import D20_NAMES, read_json, reference, verify_reference, write_json_new


def family_for(group, path, level):
    leaf = path.split(".")[-1]
    if group == "D":
        if level == "atom":
            return "atom-level"
        if leaf in ("PMI1", "PMI2", "PMI3", "PBF_A", "volume_A3", "SASA_total_A2"):
            return "3D shape"
        if leaf in ("ExactMolWt", "NumValenceElectrons", "HeavyAtomCount", "NumHeteroatoms", "LabuteASA", "MolMR"):
            return "size"
        if leaf in ("MolLogP", "TPSA", "NumHAcceptors", "NumHDonors"):
            return "polarity/H-bond"
        return "topology/rings"
    if leaf in ("cosmo_area_A2", "cosmo_volume_A3"):
        return "size"
    if "gradient" in leaf.lower() or leaf == "forces_eV_A":
        return "off-equilibrium"
    if "dipole" in leaf or "quadrupole" in leaf:
        return "multipole"
    if "fukui" in path.lower() or leaf in ("super_heavy_atom_rows", "FOD_atom_e", "NFOD_e"):
        return "reactivity"
    if "charges" in leaf or "shell_population" in leaf:
        return "charge"
    if leaf in ("bond_orders", "wiberg_pairs", "mulliken_overlap_population_pairs", "sigma_pi_entries", "valences"):
        return "bonding"
    if leaf in ("D4_atomic_C6_au", "D4_atomic_alpha_bohr3"):
        return "response"
    if leaf in ("homo_eV", "lumo_eV", "EA_eV", "IP_eV", "vertical_EA_eV", "vertical_IP_eV"):
        return "frontier/IP-EA"
    if leaf in ("dielectric_energy_eV", "Gsolv_Eh") or "HOF_difference" in leaf:
        return "solvation"
    if "energy" in leaf.lower() or "formation" in leaf or leaf in (
            "core_core_repulsion_eV", "enpart_one_center_eV", "enpart_pairs_eV"):
        return "energy"
    raise ValueError("UNCLASSIFIED_LABEL_FAMILY:" + path)


def physical_semantics(group, path, level, component):
    leaf = path.split(".")[-1]
    extensive_energy = leaf in {"heat_of_formation_kcal_mol", "energy_Eh", "total_energy_eV",
        "electronic_energy_eV", "core_core_repulsion_eV", "dispersion_energy_kcal_mol",
        "hydrogen_bond_energy_kcal_mol", "dielectric_energy_eV", "Gsolv_Eh",
        "pm7_octanol_HOF_difference_kcal_mol", "pm7_water_HOF_difference_kcal_mol"}
    if level in ("atom", "atom_vector", "sparse_atom_pair"):
        nature = "local"
    elif leaf in ("dipole_Debye", "molecular_quadrupole_traceless_au"):
        nature = "vector_or_tensor_moment"
    elif extensive_energy or leaf.startswith("Num") or leaf in {
        "ExactMolWt", "HeavyAtomCount", "RingCount", "TPSA", "LabuteASA", "MolMR",
        "cosmo_area_A2", "cosmo_volume_A3", "volume_A3", "SASA_total_A2", "NFOD_e"}:
        nature = "extensive"
    elif leaf.startswith("PMI"):
        nature = "mass_and_geometry_moment"
    else:
        nature = "intensive"
    lower = None
    exclusive = False
    if leaf in {"IP_eV", "vertical_IP_eV"}:
        lower, exclusive = 0.0, True
    elif (group == "D" and (leaf.startswith("Num") or leaf.startswith("PMI") or leaf in {
            "HeavyAtomCount", "RingCount", "ExactMolWt", "TPSA", "LabuteASA", "PBF_A",
            "volume_A3", "SASA_total_A2", "SASA_atom_A2", "FractionCSP3"})
          or leaf in {"cosmo_area_A2", "cosmo_volume_A3"}):
        lower = 0.0
    upper = 1.0 if leaf == "FractionCSP3" else None
    vector = level in ("molecule_vector", "atom_vector")
    return {
        "extensivity": nature,
        "pooling_guidance": "local_output" if nature == "local" else (
            "sum_candidate" if nature == "extensive" else "architecture_decision_required"),
        "definition_based_not_inferred_from_rho": True,
        "element_reference_eligible": level == "molecule" and extensive_energy,
        "physical_range": {"lower": lower, "lower_exclusive": exclusive, "upper": upper,
            "basis": "definition_only; unbounded sides deliberately unspecified"},
        "value_type": "vector" if vector else "tensor_component" if level == "molecule_tensor" else "scalar_component",
        "reference_frame": ({"required": "stored geometry Cartesian axes", "verification": "PENDING_CONTROLLED_READBACK",
            "source_policy": "input coordinates rendered without a rotation; output axis equivalence must be verified",
            "gradient_sign": "dE/dR" if "gradient" in leaf else "force=-dE/dR" if leaf == "forces_eV_A" else None}
            if vector or level == "molecule_tensor" else None),
    }


def generate(pins):
    sources = {name: verify_reference(ref) for name, ref in pins["sources"].items()}
    dictionary = read_json(sources["field_dictionary"])
    physical = {(int(x["registry_id"]), x["task"]): x for x in dictionary
                if x.get("registry_id") is not None and x.get("classification") == "physical_label"}
    descriptor = {x["canonical_target"]: x for x in dictionary
                  if x.get("registry_id") is None and x.get("family") in ("D20", "D3")}
    with sources["closed_statistics"].open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    entries = []
    for old in rows:
        rid = int(old["registry_id"]) if old["domain"] == "P" else None
        n = int(old["n"])
        inactive = old["coverage_scope"] == "inactive_expected_legacy_ESP"
        # The old table's scope string is kept verbatim; a five-field explicit
        # check below prevents a changed spelling from silently enabling ESP.
        inactive = inactive or "esp_charges_e" in old["source_path"]
        constant = n > 0 and float(old["std_ddof0"]) == 0.0
        status = "legacy_inactive" if inactive else "N/A" if n == 0 else "deleted" if constant else "enabled"
        source = physical[(rid, old["task"])] if rid is not None else descriptor[old["source_path"]]
        group = "P" if rid is not None else "D"
        semantics = physical_semantics(group, old["source_path"], old["level"], old["component"])
        entry = {
            "field_key": old["feature_key"], "registry_id": rid, "group": group,
            "family_source": old["family"], "task": old["task"], "source_path": old["source_path"],
            "component": old["component"], "level": old["level"], "status": status,
            "status_reason": {"enabled": "finite_nonconstant_in_closed_audit",
                "N/A": "explicit_all_missing_nonrequired_scope; no recomputation",
                "deleted": "constant_zero_f_or_unknown_shell_component",
                "legacy_inactive": "historical_ESP_placeholder_outside_current_task_scope"}[status],
            "family_v1_provisional": family_for(group, old["source_path"], old["level"]),
            "family_v1_final": None,
            "size_rule": {"status": "PENDING_FROZEN_TRAIN", "abs_spearman_threshold": 0.95,
                "rho": None, "pair_n": None, "hof_after_element_reference": "heat_of_formation" in old["source_path"]},
            "shape": source["array_shape"], "unit": old["unit"], "source_unit": old["source_unit"],
            "source_semantic_layout": source.get("semantic_layout"),
            "method": source.get("method") or "RDKit", "charge": source.get("charge"),
            "source_canonical_target": source.get("canonical_target"),
            "geometry_sources": ["pm7", "uff_sprime"],
            "geometry_context": source.get("geometry_context") or "descriptor_on_stored_geometry",
            "source_representation": "registry_CELL" if rid is not None else "D20_name_indexed" if old["domain"] == "D20" else "D3_column",
            "field_masks": ["source_status", "source_cell_kind", "source_numeric_issue", "shape", "finite", "physical_definition", "cross_field"],
            "observed_audit": {"scope": "historical canonical TRAIN, before new family VAL assignment",
                "numeric_leaves": n, "valid_records": int(old["valid_records"]),
                "missing_records": int(old["missing_records"]), "denominator_records": int(old["denominator_records"]),
                "not_final_normalization": True},
            **semantics,
        }
        entries.append(entry)
    counts = collections.Counter(x["status"] for x in entries)
    na_ids = {x["registry_id"] for x in entries if x["status"] == "N/A"}
    enabled = [x for x in entries if x["status"] == "enabled"]
    scalar = collections.Counter(x["group"] for x in enabled if x["level"] == "molecule")
    if (len(entries), counts["enabled"], counts["N/A"], counts["deleted"], counts["legacy_inactive"], len(na_ids)) != (264,146,103,10,5,63):
        raise ValueError("REGISTRY_COUNTS_DIFFER_FROM_CLOSED_AUDIT:" + str(counts))
    if scalar != {"P": 43, "D": 26}:
        raise ValueError("MOLECULE_SCALAR_COUNTS_DIFFER:" + str(scalar))
    if any(x["status"] == "deleted" and not (x["component"] in {"f", "unknown"} and x["source_path"].endswith("atomic_shell_population_e")) for x in entries):
        raise ValueError("UNEXPECTED_CONSTANT_FIELD_REQUIRES_REVIEW")
    return {
        "schema_version": "label_registry_v3.0.0-draft.1",
        "status": "DRAFT_METADATA_MAPPED_NOT_SCIENTIFICALLY_FINAL",
        "inputs": pins["sources"],
        "input_pins": pins.get("lineage", {}),
        "counts": {"source_components": 264, **dict(counts), "NA_source_registry_fields": 63,
            "enabled_P_molecule_scalars":43,"enabled_D_molecule_scalars":26,
            "enabled_D_fields":27,"enabled_D_atom_SASA":1},
        "guide_count_correction": "69 molecule scalars are 43 P + 26 D; D has one additional atom-level SASA field",
        "structural_targets": {"group":"S", "status":"generated_by_model_recipe_not_extra_WP5_labels",
            "atomic_numbers":"source atom order", "coordinates":"Angstrom, stored geometry Cartesian frame"},
        "pprime": {"inherits_group":"P", "geometry_source":"uff_sprime", "statistics":"separate TRAIN-only fit required",
            "same_field_keys":True,"computed_labels_available":False},
        "D20_names": D20_NAMES,
        "scalar_value_policy":"permanent float64; training float32 conversion only at export",
        "freeze_dependencies":["new TRAIN/VAL/common population frozen", "TRAIN-only size rho and HOF element reference",
            "new masks scanned with <=1% new invalid rule", "vector reference frame controlled verification", "model-line interface agreement"],
        "fields": entries,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pins",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--summary",required=True)
    args=p.parse_args()
    pins=read_json(args.pins)
    result=generate(pins)
    write_json_new(args.output,result)
    write_json_new(args.summary,{"status":"D2_METADATA_GENERATED", "registry":reference(args.output),
        "pins":reference(args.pins), "generator":reference(__file__), "counts":result["counts"],
        "scientific_freeze":False,"new_scientific_data_read":False})
    print("D2_METADATA_GENERATED", result["counts"])


if __name__=="__main__":
    main()
