"""Native adapter: unchanged S-prime numerical parameters, explicit no retry.

The existing no-PM7 core supplies graph validation, the original SHA-pinned
S-prime science and descriptor function objects. Its old 10-output process,
select_fill fallback, embedding fallback and scheduling code are never called.
"""
from __future__ import annotations

import math
from .core import RECIPE, IntegrityError, canonical, geometry_sha, seed_for, sha


_PROVENANCE = None


def kernel_provenance(old):
    global _PROVENANCE
    if _PROVENANCE is None:
        import sys
        from rdkit import rdBase
        recipe = old.C.Q.pin(old.C.RECIPE)
        if recipe['sha256'] != old.C.RECIPE_SHA256:
            raise IntegrityError('ORIGINAL_SPRIME_RECIPE_SOURCE_CHANGED')
        frozen = old.C.meta(recipe)
        for ref in frozen['science_source_pins']:
            if old.C.Q.pin(ref['path']) != ref:
                raise IntegrityError('ORIGINAL_SPRIME_SCIENTIFIC_SOURCE_CHANGED')
        refs = {name: old.C.Q.pin(path) for name, path in old.C.catalog_paths().items()}
        identity = {'recipe_sha256': recipe['sha256'], 'rdkit': rdBase.rdkitVersion,
            'python': sys.version.split()[0],
            'sources': {name: {'bytes': ref['bytes'], 'sha256': ref['sha256']} for name, ref in refs.items()},
            'frozen_science_source_sha256': [ref['sha256'] for ref in frozen['science_source_pins']]}
        _PROVENANCE = {'fingerprint': sha(canonical(identity)), 'identity': identity,
            'actual_source_references': refs, 'original_recipe_reference': recipe,
            'original_science_source_references': frozen['science_source_pins']}
    return _PROVENANCE


def embed_once(mol, allchem, seed, count=30):
    """One call only; normal ETKDGv3 original parameters. No zero-return fallback."""
    if count != RECIPE["candidate_budget"]:
        raise ValueError("FIXED_THIRTY_CANDIDATE_VERSION")
    params = allchem.ETKDGv3()
    params.randomSeed = seed
    params.numThreads = 1
    params.enforceChirality = True
    params.pruneRmsThresh = -1.0
    params.maxIterations = 200
    params.useRandomCoords = False
    return list(allchem.EmbedMultipleConfs(mol, numConfs=count, params=params))


def minimize_once(field):
    return field.MinimizeTrajectory(snapshotFreq=1, maxIts=2000,
                                    energyTol=1e-6, forceTol=1e-4)


class NativeKernel:
    def __init__(self):
        self.source = self.mol = self.template = self.original_graph = None
        self.old = self.kernels = self.numbers = None

    def _graph(self, source):
        from workflows.expansion.no_pm7_uff_d_main_v1 import core as old
        from rdkit import Chem
        self.old = old
        self.kernels = old.load()
        self.provenance = kernel_provenance(old)
        self.template, self.mol, unresolved = old.graph(source["isomeric_smiles"])
        if Chem.MolToInchiKey(self.template) != source["full_key"]:
            raise IntegrityError("SOURCE_FULLKEY_GRAPH_MISMATCH")
        self.source = source
        self.numbers = [a.GetAtomicNum() for a in self.mol.GetAtoms()]
        self.original_graph = self.kernels["science"].ordered_graph(self.mol)
        return unresolved

    def prepare(self, source):
        from rdkit.Chem import AllChem
        unresolved = self._graph(source)
        d20, _, _ = self.old.d20(self.template)
        return {"atomic_numbers": self.numbers, "D20": d20, "kernel_provenance": self.provenance,
                "unassigned_stereo": unresolved,
                "uff_supported": bool(AllChem.UFFHasAllMoleculeParams(self.mol))}

    def attach(self, cache):
        """Restore graph context only; no descriptor, embedding or UFF call."""
        unresolved = self._graph(cache["source"])
        if (cache.get('kernel_provenance') or {}).get('fingerprint') != self.provenance['fingerprint']:
            raise IntegrityError('CLOSED_CACHE_ORIGINAL_SCIENCE_FINGERPRINT_CHANGED')
        if self.numbers != cache["atomic_numbers"] or unresolved != cache.get("unassigned_stereo", []):
            raise ValueError("CACHED_GRAPH_ATOM_OR_STEREO_CONTEXT_CHANGED")

    def embed(self, seed, count):
        from rdkit.Chem import AllChem
        original = self.kernels["seed_for"]("expansion-pubchem:{pubchem_version}:{cid}:{full_key}".format(**self.source), False)
        if seed != original:
            raise ValueError("ORIGINAL_SPRIME_SEED_MISMATCH")
        return embed_once(self.mol, AllChem, seed, count)

    def optimize(self, candidate_id):
        from rdkit.Chem import AllChem, rdtrajectory
        field = AllChem.UFFGetMoleculeForceField(self.mol, confId=candidate_id)
        if field is None:
            raise ValueError("UFF_FORCEFIELD_UNAVAILABLE")
        code, trajectory = minimize_once(field)
        coordinates = [[float(v) for v in point] for point in self.mol.GetConformer(candidate_id).GetPositions()]
        energy = float(field.CalcEnergy())
        finite = math.isfinite(energy) and all(math.isfinite(v) for p in coordinates for v in p)
        if (self.kernels["science"].ordered_graph(self.mol) != self.original_graph
                or [a.GetAtomicNum() for a in self.mol.GetAtoms()] != self.numbers):
            raise IntegrityError("GENERATED_GRAPH_OR_ATOM_ORDER_CHANGED")
        stereo_valid = finite and bool(self.kernels["science"].check_geometry_stereo(self.mol, candidate_id))
        return {"candidate_id": int(candidate_id), "coordinates": coordinates,
                "energy": energy, "optimizer_code": int(code),
                "iterations": len(trajectory), "finite": finite,
                "stereo_valid": stereo_valid, "origin": "fixed30_original_sprime_UFF_no_retry"}

    def distance(self, first, second):
        return float(self.kernels["science"].rmsd(self.mol, first["coordinates"], second["coordinates"]))

    def check_original_selection(self, candidates, canonical_rows):
        if not canonical_rows:
            return
        # There are exactly this many >=0.5A survivors. The original selector
        # necessarily reaches target in its first phase, before its fill loop.
        original = self.kernels["selection"].select_fill([], candidates, len(canonical_rows), self.distance, 0.5)
        if canonical(original) != canonical(canonical_rows) or any(r["below_dedup_threshold"] for r in original):
            raise ValueError("ORIGINAL_NO_FILL_SELECTION_PARITY_FAILED")

    def d3(self, row):
        """Original corrected_base D3 APIs/parameters, without recomputing D20.

        The original wire computes HBA again while copying graph descriptors;
        this method calls the same original RDKit APIs for D3 directly. The
        independent compare_original_wire() exercises equality on actual coords.
        """
        from rdkit import Chem
        from rdkit.Chem import AllChem, Descriptors3D, rdFreeSASA
        mol = Chem.Mol(self.mol)
        mol.RemoveAllConformers()
        conf = Chem.Conformer(len(self.numbers))
        for i, point in enumerate(row["coordinates"]):
            conf.SetAtomPosition(i, tuple(float(v) for v in point))
        conf.Set3D(True)
        mol.AddConformer(conf, assignId=True)
        values, issues = {}, []
        for name in ("PMI1", "PMI2", "PMI3", "PBF"):
            key = "PBF_A" if name == "PBF" else name
            try:
                value = float(getattr(Descriptors3D, name)(mol))
                if not math.isfinite(value):
                    raise ValueError("NONFINITE")
                values[key] = value
            except Exception as exc:
                values[key] = None
                issues.append(key + ":" + str(exc))
        try:
            value = float(AllChem.ComputeMolVolume(mol, gridSpacing=0.2, boxMargin=2.0))
            if not math.isfinite(value):
                raise ValueError("NONFINITE")
            values["volume_A3"] = value
        except Exception as exc:
            values["volume_A3"] = None
            issues.append("volume:" + str(exc))
        try:
            radii = [Chem.GetPeriodicTable().GetRvdw(int(z)) for z in self.numbers]
            opts = rdFreeSASA.SASAOpts(rdFreeSASA.SASAAlgorithm.LeeRichards,
                                     rdFreeSASA.SASAClassifier.Protor, 1.4)
            total = float(rdFreeSASA.CalcSASA(mol, radii, opts=opts))
            atoms = [float(atom.GetProp("SASA")) for atom in mol.GetAtoms()]
            if not math.isfinite(total) or not all(math.isfinite(v) for v in atoms):
                raise ValueError("NONFINITE_ATOM_SASA")
            values["SASA_total_A2"], values["SASA_atom_A2"] = total, atoms
        except Exception as exc:
            values["SASA_total_A2"] = values["SASA_atom_A2"] = None
            issues.append("SASA:" + str(exc))
        return values, issues

    def orders(self, rows, mid, seed):
        return self.kernels["selection"].conformer_orders(rows, self.distance, mid, "uff_sprime", seed)

    def compare_original_wire(self, row, d20):
        """Independent actual-coordinate seam check; no embedding or optimizer."""
        import numpy as np
        self.old.load()
        _, shell, flags = self.old.d20(self.template)
        expected, expected_issues, wire_d20 = self.old.descriptors(self.source, self.template, self.mol,
            np.asarray(self.numbers, dtype="<i8"), np.asarray(row["coordinates"], dtype="<f8"), shell, flags)
        if (np.asarray(wire_d20['values'], dtype='<f8').tobytes() != np.asarray(d20['values'], dtype='<f8').tobytes()
                or wire_d20['valid_mask'] != d20['valid_mask']):
            raise ValueError('ORIGINAL_CORRECTED_D20_BINARY64_OR_MASK_SEAM')
        actual, actual_issues = self.d3(row)
        for name in expected:
            if expected[name] is None or actual[name] is None:
                if expected[name] is not None or actual[name] is not None:
                    raise ValueError("ORIGINAL_D3_NULL_SEAM:" + name)
            elif np.asarray(expected[name], dtype="<f8").tobytes() != np.asarray(actual[name], dtype="<f8").tobytes():
                raise ValueError("ORIGINAL_D3_BINARY64_SEAM:" + name)
        return {"original_corrected_base_binary64_equal": True,
                "fields": list(expected), "actual_issues": actual_issues,
                "original_issues": expected_issues}