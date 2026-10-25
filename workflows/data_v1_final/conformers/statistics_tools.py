"""Pilot-only conformer statistics; never substitutes for a full-population scan."""
from __future__ import annotations

import math


def molecule_statistics(result, science):
    import numpy as np
    from rdkit import Chem
    rows, pm7 = result["conformers"], result["pm7"]
    if not rows or not pm7:
        return None
    mol = Chem.RWMol()
    for z in rows[0]["atomic_numbers"]:
        mol.AddAtom(Chem.Atom(int(z)))
    def unique_count(items, energy_key):
        selected = []
        for row in sorted(items, key=lambda item: (item[energy_key] is None,
                                                  item[energy_key] if item[energy_key] is not None else 0)):
            if all(science.rmsd(mol, row["coordinates"], other["coordinates"]) >= 0.5 for other in selected):
                selected.append(row)
        return len(selected)
    energies = [row["energy"] for row in pm7 if row["energy"] is not None]
    cross = [value for row in rows for value in row["pm7_rmsds_A"]]
    return {"molecule_id": result["summary"]["molecule_id"], "pm7_conformers": len(pm7),
            "pm7_unique_0p5A": unique_count(pm7, "energy"), "sprime_conformers": len(rows),
            "sprime_unique_0p5A": unique_count(rows, "uff_energy_kcal_mol"),
            "pm7_native_anchor_heat_range_kcal_mol": max(energies) - min(energies) if energies else None,
            "cross_rmsd_A": cross,
            "heavy_atoms": result["summary"]["heavy_atoms"],
            "rotatable_bonds": result["summary"]["rotatable_bonds"],
            "rings": result["summary"]["rings"],
            "energy_order_authority": "native_PM7_anchor_diagnostic; final_v1_requires_canonical_WP5_HOF"}


def aggregate_statistics(results):
    import numpy as np
    from scipy.stats import spearmanr
    rows = [result["statistics"] for result in results if result.get("statistics")]
    if not rows:
        return {"status": "NO_PILOT_STATISTICS", "molecules": 0}
    out = {"status": "PILOT_DESCRIPTIVE_ONLY", "molecules": len(rows),
           "rmsd_definition": "source-index heavy atoms, proper Kabsch, 0.5 A",
           "counts": {}, "correlations": {},
           "pm7_heat_authority": "legacy_native_energy_used_for_original_stereo_anchor; not final WP5 energy order"}
    for source in ("pm7", "sprime"):
        values = [row[source + "_unique_0p5A"] for row in rows]
        out["counts"][source] = {"unique_count_histogram": {str(value): values.count(value) for value in sorted(set(values))},
                                  "fractions_ge": {str(k): sum(value >= k for value in values) / len(values) for k in (2, 5, 10)},
                                  "duplicate_conformer_fraction": 1 - sum(values) / sum(row[source + "_conformers"] for row in rows)}
        for feature in ("heavy_atoms", "rotatable_bonds", "rings"):
            inputs = [row[feature] for row in rows]
            rho = None
            if len(set(inputs)) > 1 and len(set(values)) > 1:
                value = float(spearmanr(values, inputs).statistic)
                rho = value if math.isfinite(value) else None
            out["correlations"][source + "_unique_vs_" + feature] = {"spearman_rho": rho,
                                                                   "population": len(rows),
                                                                   "undefined_if_constant": rho is None}
    cross = [value for row in rows for value in row["cross_rmsd_A"]]
    percentiles = [0, 25, 50, 75, 90, 95, 99, 100]
    out["cross_rmsd_A_quantiles"] = {str(p): float(np.percentile(cross, p, method="linear")) for p in percentiles}
    ranges = [row["pm7_native_anchor_heat_range_kcal_mol"] for row in rows if row["pm7_native_anchor_heat_range_kcal_mol"] is not None]
    out["pm7_native_anchor_heat_range_quantiles_kcal_mol"] = {str(p): float(np.percentile(ranges, p, method="linear")) for p in percentiles}
    return out
