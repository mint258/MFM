"""Native development geometry without reading labels or choosing an H policy.

The caller must explicitly supply native_only or B6_fixed_native_H. Existing
source coordinates are mandatory; no embedding/missing-conformer fallback is
permitted. Numerical D3 evaluation is delegated to the original program.
"""
import collections
from contextlib import contextmanager
import struct

import numpy as np

from workflows.data_v1_final.labels.common import D20_NAMES


D3_NAMES = ("PMI1", "PMI2", "PMI3", "PBF", "volume_A3", "SASA_total_A2")

# Original B6 chemistry failures make this member unavailable, without a retry
# or new geometry. Coordinate-invariant and unexpected errors remain fatal.
H_COMPLETION_UNAVAILABLE = frozenset((
    "EXISTING_RECIPE_DISCONNECTED_GRAPH_UNSUPPORTED",
    "H_COMPLETION_SOURCE_ATOM_ORDER_OR_COMPOSITION_MISMATCH",
    "BASELINE_MMFF94_PARAMETERS_UNAVAILABLE",
    "BASELINE_MMFF94_FORCEFIELD_UNAVAILABLE",
    "BASELINE_MMFF94_NOT_CONVERGED_500",
    "BASELINE_GEOMETRY_NONFINITE",
))


class UnavailableD3(ValueError):
    pass


@contextmanager
def cached_original_hba(value):
    """Supply the old scalar to the legacy D3 wire's unused HBA correction.

    The original wire computes D3 independently of HBA, but also assigns an
    updated HBA to its copied 2D shell. Reuse the canonical old value in this
    sequential process only; never recalculate a D20 field or edit RDKit files.
    """
    from rdkit.Chem import Lipinski
    original = Lipinski.NumHAcceptors
    try:
        Lipinski.NumHAcceptors = lambda _molecule: float("nan") if value is None else value
        yield
    finally:
        Lipinski.NumHAcceptors = original


def native_geometry(store, dataset, member_index):
    """Read only the original packed Z/F64 coordinate prefix, never its labels.

    Reuse the native store's validated metadata and physical offsets. Its
    ordinary get() decodes target arrays, so it is deliberately not called.
    """
    metadata = store.native_geometry_metadata(dataset, member_index)
    row = store._rows[dataset, member_index]
    if not metadata["geometry_ready"]:
        raise UnavailableD3("ORIGINAL_NATIVE_GEOMETRY_UNAVAILABLE")
    n = metadata["native_n_atoms"]
    with store._path.open("rb") as stream:
        if stream.read(8) != b"P1DS1\x00\x00\x00":
            raise ValueError("Original native packed format differs")
        stream.seek(row["offset"])
        header = stream.read(16)
        if len(header) != 16:
            raise ValueError("Native geometry frame header truncated")
        observed_n, _, _, ready = struct.unpack("<4I", header)
        if observed_n != n or ready != 1:
            raise ValueError("Original geometry frame differs from native metadata")
        atom_bytes, xyz_bytes = stream.read(2 * n), stream.read(24 * n)
        if len(atom_bytes) != 2 * n or len(xyz_bytes) != 24 * n:
            raise ValueError("Original geometry prefix truncated")
    numbers = np.frombuffer(atom_bytes, dtype="<u2").astype(np.int64) + 1
    coordinates = np.frombuffer(xyz_bytes, dtype="<f8").reshape(n, 3).copy()
    if not ((numbers >= 1) & (numbers <= 118)).all() or not np.isfinite(coordinates).all():
        raise UnavailableD3("ORIGINAL_NATIVE_GEOMETRY_NONFINITE_OR_ELEMENT_INVALID")
    return dict(member_uid=metadata["member_uid"], atomic_numbers=numbers,
                coordinates_A=coordinates, source_atom_ids=list(range(n)),
                physical_source=str(store._path), physical_offset=row["offset"],
                endpoint_label_bytes_read=False)


def structure(smiles, numbers, coordinates, *, hydrogen_policy, complete=None):
    from rdkit import Chem
    if hydrogen_policy not in ("native_only", "B6_fixed_native_H"):
        raise ValueError("Explicit registered development hydrogen policy required")
    molecule = Chem.MolFromSmiles(smiles) if smiles else None
    if molecule is None:
        raise UnavailableD3("ORIGINAL_SOURCE_GRAPH_UNAVAILABLE")
    numbers = np.asarray(numbers, dtype=np.int64)
    coordinates = np.asarray(coordinates, dtype=np.float64)
    if (numbers.ndim != 1 or coordinates.shape != (len(numbers), 3)
            or not len(numbers) or not np.isfinite(coordinates).all()):
        raise UnavailableD3("ORIGINAL_NATIVE_GEOMETRY_UNAVAILABLE")
    full = Chem.AddHs(molecule)
    full_numbers = [atom.GetAtomicNum() for atom in full.GetAtoms()]
    if collections.Counter(full_numbers) == collections.Counter(numbers.tolist()):
        result = dict(atomic_numbers=numbers.tolist(), coordinates_A=coordinates.tolist(),
                      geometry_policy="REUSED_COMPLETE_EXISTING_NATIVE_GEOMETRY",
                      xtb_source_atom_ids=list(range(len(numbers))))
    elif hydrogen_policy == "native_only":
        raise UnavailableD3("NATIVE_EXPLICIT_H_UNAVAILABLE")
    else:
        if complete is None:
            from workflows.data_v1_final.downstream_descriptors_v2.geometry import complete_geometry as complete
        # Passing mandatory coordinates makes the existing helper use its
        # fixed-native H-completion branch, never ETKDG/missing-geometry rebuild.
        try:
            result = complete(dict(mol=molecule, atomic_numbers=numbers.tolist(),
                                   coordinates_A=coordinates.tolist()))
        except ValueError as error:
            if str(error) not in H_COMPLETION_UNAVAILABLE:
                raise
            raise UnavailableD3(str(error)) from error
        if not np.array_equal(np.asarray(result["coordinates_A"])[:len(numbers)], coordinates):
            raise ValueError("Existing H-completion program changed original source coordinates")
    if result["atomic_numbers"] != full_numbers:
        raise UnavailableD3("NATIVE_ATOM_ORDER_DIFFERS_FROM_ORIGINAL_D3_GRAPH")
    return dict(result, mol=full, native_n_atoms=len(numbers),
                native_coordinates_changed=False, new_conformer_embedded=False)


def original_d3(smiles, numbers, coordinates, canonical_d20, *, hydrogen_policy,
                calculator, complete=None):
    """Call original geometry_descriptors; keep original D20 values untouched."""
    if set(canonical_d20) != set(D20_NAMES):
        raise ValueError("Explicit original canonical D20 values/missing mask required")
    prepared = structure(smiles, numbers, coordinates, hydrogen_policy=hydrogen_policy, complete=complete)
    d20 = dict(names=list(D20_NAMES), values=[canonical_d20[name] for name in D20_NAMES],
               valid_mask=[canonical_d20[name] is not None for name in D20_NAMES])
    # The original adapter's tensor shell expects NaN for unavailable values.
    d20["values"] = [float(value) if value is not None else float("nan") for value in d20["values"]]
    with cached_original_hba(canonical_d20["NumHAcceptors"]):
        values, issues = calculator(smiles, prepared["mol"], prepared["atomic_numbers"],
                                    prepared["coordinates_A"], d20)
    raw = np.array([np.nan if values.get(name) is None else values[name] for name in D3_NAMES], dtype=np.float64)
    status = np.array([0 if values.get(name) is None else
                       1 if np.isfinite(raw[index]) and abs(raw[index]) <= np.finfo(np.float32).max else 2
                       for index, name in enumerate(D3_NAMES)], dtype=np.uint8)
    return dict(raw_values=raw, status=status, fields=D3_NAMES, issues=issues,
                geometry_policy=prepared["geometry_policy"],
                work_atom_to_native_source=prepared["xtb_source_atom_ids"],
                native_n_atoms=prepared["native_n_atoms"],
                native_coordinates_changed=False, new_conformer_embedded=False,
                atomic_SASA_source_values=values.get("SASA_atom_A2"),
                atomic_SASA_in_molecular_vector=False,
                canonical_D20_replaced=False, canonical_D20_recomputed=False, normalization_fitted=False)
