"""Analysis-only, TRAIN-fitted radial lookup producing consistent 3D coordinates.

Feature construction sees noisy coordinates and input elements only. Targets
are additive displacements y-x in Angstrom; no property label is generated.
Sparse LSQR avoids forming the coefficient-by-coefficient dense Gram matrix.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, lsqr

from .v3_contract import canonical_hash, require

ROLES = ("TRAIN", "PRETRAIN_VAL")


@dataclass(frozen=True)
class CoordinateLookupConfig:
    radius_A: float = 5.0
    bin_width_A: float = 0.1
    element_types: int = 119
    ridge: float = 1e-4
    atol: float = 1e-8
    btol: float = 1e-8
    condition_limit: float = 1e8
    maximum_iterations: int = 500
    max_record_atoms: int = 512
    max_train_records: int = 8192
    max_train_atoms: int = 524288
    max_directed_edges: int = 16000000
    max_coo_entries: int = 48000000
    matrix_budget_bytes: int = 8 * 1024**3

    def __post_init__(self):
        require(all(type(value) in (int, float) and math.isfinite(value) and value > 0 for value in (
            self.radius_A, self.bin_width_A, self.ridge, self.atol, self.btol, self.condition_limit)),
            "Positive finite geometry/ridge/solver values required")
        require(all(type(value) is int and value > 0 for value in (
            self.element_types, self.maximum_iterations, self.max_record_atoms, self.max_train_records,
            self.max_train_atoms, self.max_directed_edges, self.max_coo_entries, self.matrix_budget_bytes)),
            "Positive integer lookup resource limits required")
        require(self.element_types == 119 and math.isclose(self.radius_A / self.bin_width_A,
            round(self.radius_A / self.bin_width_A), rel_tol=0., abs_tol=1e-12),
            "119 source element types and an integral number of radial bins required")

    @property
    def bins(self):
        return round(self.radius_A / self.bin_width_A)

    @property
    def columns(self):
        return self.element_types**2 * self.bins


@dataclass(frozen=True)
class LookupRecord:
    record_id: str
    molecule_id: str
    role: str
    elements: np.ndarray
    noisy: np.ndarray
    clean: np.ndarray
    payload_sha256: str

    def validate(self, config):
        require(type(self.record_id) is str and bool(self.record_id) and type(self.molecule_id) is str
                and bool(self.molecule_id) and self.role in ROLES, "Explicit existing S record/molecule/role required")
        require(isinstance(self.payload_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", self.payload_sha256),
                "Source payload SHA256 required")
        validate_geometry(self.elements, self.noisy, config)
        require(isinstance(self.clean, np.ndarray) and self.clean.shape == self.noisy.shape
                and self.clean.dtype in (np.dtype("float32"), np.dtype("float64"))
                and np.isfinite(self.clean).all(), "Finite native-order clean geometry required")


def validate_geometry(elements, noisy, config):
    require(isinstance(elements, np.ndarray) and elements.ndim == 1 and elements.dtype.kind in "iu"
            and 0 < len(elements) <= config.max_record_atoms
            and ((elements >= 0) & (elements < config.element_types-1)).all(),
            "Bounded native zero-based element array required; reserved padding is not an atom")
    require(isinstance(noisy, np.ndarray) and noisy.shape == (len(elements), 3)
            and noisy.dtype in (np.dtype("float32"), np.dtype("float64")) and np.isfinite(noisy).all(),
            "Finite native-order noisy geometry required")


def source_binding():
    path = Path(__file__).absolute()
    return {"module": "phychem_mfm.phase1.v3_coordinate_lookup", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def radial_features(elements, noisy, config=CoordinateLookupConfig()):
    """Return directed edges, codes and relative y_i-y_j; never accepts clean x."""
    validate_geometry(elements, noisy, config)
    coordinates = noisy.astype(np.float64, copy=False)
    relative = coordinates[:, None, :] - coordinates[None, :, :]
    squared = np.einsum("ijk,ijk->ij", relative, relative)
    keep = (squared > 0.) & (squared < config.radius_A**2)
    src, dst = np.nonzero(keep)
    distances = np.sqrt(squared[src, dst])
    bins = np.floor(distances / config.bin_width_A).astype(np.int64)
    require(((bins >= 0) & (bins < config.bins)).all(), "Radial bin boundary mismatch")
    codes = ((elements[src].astype(np.int64) * config.element_types + elements[dst]) * config.bins + bins)
    return src, dst, codes, relative[src, dst]


def design_matrix(elements, noisy, config=CoordinateLookupConfig()):
    src, dst, codes, relative = radial_features(elements, noisy, config)
    rows = (3 * src[:, None] + np.arange(3, dtype=np.int64)).reshape(-1)
    columns = np.repeat(codes, 3)
    data = relative.reshape(-1)
    matrix = sparse.coo_matrix((data, (rows, columns)), shape=(3 * len(elements), config.columns)).tocsr()
    matrix.sum_duplicates(); matrix.eliminate_zeros()
    return matrix, codes


def matrix_capacity_estimate(*, atoms, directed_edges, columns):
    """Conservative numeric-array bound; Python/native-reader RSS is separate.

    Count uncoalesced three-coordinate entries. Assume int64 indices even when
    SciPy selects int32, retain three CSR copies plus a complete COO inventory,
    and reserve dense LSQR vectors. This never contains a columns-squared term.
    """
    rows, entries = 3 * atoms, 3 * directed_edges
    csr = 16 * entries + 8 * (rows + 1)
    coo = 24 * entries
    vectors = 8 * (6 * rows + 8 * columns)
    return {"atoms": atoms, "rows": rows, "columns": columns, "uncoalesced_entries": entries,
        "csr_single_upper_bytes": csr, "coo_upper_bytes": coo,
        "lsqr_vector_upper_bytes": vectors, "numeric_upper_bytes": 3 * csr + coo + vectors,
        "dense_gram_constructed": False, "python_and_native_reader_RSS_included": False}


def _record_receipt(record):
    return {"record_id": record.record_id, "molecule_id": record.molecule_id,
            "role": record.role, "payload_sha256": record.payload_sha256, "atoms": len(record.elements)}


@dataclass(frozen=True)
class CoordinateLookup:
    config: CoordinateLookupConfig
    coefficients: np.ndarray
    train_edge_counts: np.ndarray
    fit_receipt: dict

    def predict_noise(self, elements, noisy):
        matrix, codes = design_matrix(elements, noisy, self.config)
        prediction = np.asarray(matrix @ self.coefficients).reshape(len(elements), 3)
        known = self.train_edge_counts[codes] > 0
        return prediction, {"directed_edges": len(codes), "known_directed_edges": int(known.sum()),
                            "unknown_directed_edges": int((~known).sum())}

    def document(self):
        observed = np.flatnonzero(self.train_edge_counts)
        require(np.isfinite(self.coefficients).all() and np.equal(self.coefficients[self.train_edge_counts == 0], 0).all(),
                "Finite fitted coefficients with exact unknown-bin zero fallback required")
        return {"schema": "model_v3_C2_coordinate_lookup_v1", "status": "ANALYSIS_ONLY_NOT_MODEL_SELECTION",
            "configuration": asdict(self.config), "source": source_binding(), "fit_receipt": self.fit_receipt,
            "codes": observed.tolist(), "coefficients": self.coefficients[observed].tolist(),
            "train_directed_edge_counts": self.train_edge_counts[observed].tolist()}

    @classmethod
    def from_document(cls, value):
        require(value["schema"] == "model_v3_C2_coordinate_lookup_v1" and value["source"] == source_binding()
                and value["status"] == "ANALYSIS_ONLY_NOT_MODEL_SELECTION", "Bound analysis lookup schema/source required")
        config = CoordinateLookupConfig(**value["configuration"])
        require(all(type(code) is int for code in value["codes"])
                and all(type(count) is int for count in value["train_directed_edge_counts"])
                and all(type(coefficient) in (int, float) for coefficient in value["coefficients"]),
                "Lookup codes/counts must be integers and coefficients numeric")
        codes = np.asarray(value["codes"], dtype=np.int64)
        coefs = np.asarray(value["coefficients"], dtype=np.float64)
        counts = np.asarray(value["train_directed_edge_counts"], dtype=np.int64)
        require(codes.ndim == 1 and coefs.shape == counts.shape == codes.shape
                and np.isfinite(coefs).all() and ((codes >= 0) & (codes < config.columns)).all()
                and (counts > 0).all() and (np.diff(codes) > 0).all(), "Sorted unique finite lookup table required")
        coefficients = np.zeros(config.columns, dtype=np.float64)
        edge_counts = np.zeros(config.columns, dtype=np.int64)
        coefficients[codes], edge_counts[codes] = coefs, counts
        require(value["fit_receipt"]["fit_role"] == "TRAIN", "Only TRAIN-fitted tables are accepted")
        return cls(config, coefficients, edge_counts, value["fit_receipt"])


def fit_coordinate_lookup(records, *, config=CoordinateLookupConfig(), expected_records,
                          source_plan_sha256, check=lambda: None):
    """One declared TRAIN stream, sparse least squares; no validation tuning."""
    require(type(expected_records) is int and 0 < expected_records <= config.max_train_records,
            "Exact bounded TRAIN record count required")
    require(re.fullmatch(r"[0-9a-f]{64}", source_plan_sha256) is not None, "Frozen source-plan SHA required")
    matrices, targets, receipts, identities = [], [], [], set()
    support = np.zeros(config.columns, dtype=np.int64)
    atoms = edges = 0
    capacity = matrix_capacity_estimate(atoms=0, directed_edges=0, columns=config.columns)
    for record in records:
        check()
        require(len(receipts) < expected_records, "TRAIN provider exceeded its declared record count")
        require(isinstance(record, LookupRecord) and record.role == "TRAIN", "Only TRAIN records may enter fitting")
        record.validate(config)
        require(record.record_id not in identities, "Duplicate TRAIN record ID")
        matrix, codes = design_matrix(record.elements, record.noisy, config)
        atoms += len(record.elements); edges += len(codes)
        capacity = matrix_capacity_estimate(atoms=atoms, directed_edges=edges, columns=config.columns)
        require(atoms <= config.max_train_atoms and edges <= config.max_directed_edges
                and 3 * edges <= config.max_coo_entries and capacity["numeric_upper_bytes"] <= config.matrix_budget_bytes,
                "Sparse lookup resource budget exceeded; do not drop records or build a dense Gram matrix")
        matrices.append(matrix)
        targets.append((record.noisy.astype(np.float64) - record.clean.astype(np.float64)).reshape(-1))
        np.add.at(support, codes, 1)
        receipts.append(_record_receipt(record)); identities.add(record.record_id)
    require(len(receipts) == expected_records, "TRAIN stream ended before its declared population")
    check()
    matrix = sparse.vstack(matrices, format="csr")
    target = np.concatenate(targets)
    del matrices, targets
    root_atoms = math.sqrt(atoms)
    def matvec(vector):
        check(); return matrix @ vector / root_atoms
    def rmatvec(vector):
        check(); return matrix.T @ vector / root_atoms
    operator = LinearOperator(matrix.shape, matvec=matvec, rmatvec=rmatvec, dtype=np.float64)
    solved = lsqr(operator, target / root_atoms, damp=math.sqrt(config.ridge), atol=config.atol,
        btol=config.btol, conlim=config.condition_limit, iter_lim=config.maximum_iterations, show=False)
    check()
    coefficients, stop, iterations = np.asarray(solved[0]), int(solved[1]), int(solved[2])
    require(stop in (0, 1, 2, 4, 5) and np.isfinite(coefficients).all(),
            "Sparse LSQR did not satisfy the preregistered stopping condition")
    require(np.equal(coefficients[support == 0], 0).all(), "Unknown bins must retain exact zero coefficients")
    receipt = {"fit_role": "TRAIN", "source_plan_sha256": source_plan_sha256,
        "TRAIN_records": len(receipts), "TRAIN_atoms": atoms, "TRAIN_directed_edges": edges,
        "TRAIN_membership_sha256": canonical_hash(receipts), "TRAIN_record_ids": sorted(identities),
        "TRAIN_molecule_ids": sorted({record["molecule_id"] for record in receipts}),
        "configuration_sha256": canonical_hash(asdict(config)), "observed_codes": int((support > 0).sum()),
        "matrix_shape": list(matrix.shape), "matrix_nonzeros": int(matrix.nnz), "capacity_estimate": capacity,
        "solver": {"name": "scipy.sparse.linalg.lsqr", "stop_code": stop, "iterations": iterations,
            "residual_norm": float(solved[3]), "damped_residual_norm": float(solved[4]),
            "operator_norm_estimate": float(solved[5]), "condition_estimate": float(solved[6]),
            "normal_equation_residual_norm": float(solved[7]), "coefficient_norm": float(solved[8])},
        "target_units": "Angstrom displacement epsilon=y-x", "normalization": "sum_squared_vector_error/TRAIN_atoms",
        "lsqr_operator_scale": "A/sqrt(TRAIN_atoms), b/sqrt(TRAIN_atoms)",
        "lsqr_damp_squared_normalized_operator": config.ridge,
        "equivalent_damp_squared_unscaled_operator": config.ridge * atoms,
        "dense_gram_constructed": False, "validation_used_for_fit_or_tuning": False}
    return CoordinateLookup(config, coefficients.copy(), support, receipt)


def evaluate_coordinate_lookup(model, records, *, expected_records, local_cutoff_A=2.0,
                               sigma_A=0.1, check=lambda: None):
    require(type(expected_records) is int and expected_records > 0 and local_cutoff_A > 0 and sigma_A > 0,
            "Bounded evaluation population and explicit metric geometry required")
    train_records = set(model.fit_receipt["TRAIN_record_ids"])
    train_molecules = set(model.fit_receipt["TRAIN_molecule_ids"])
    seen = set(); receipts = []
    vector_error = noisy_vector_error = pair_error = noisy_pair_error = 0.
    atoms = pair_count = edges = known = unknown = 0
    for record in records:
        check()
        require(len(receipts) < expected_records, "Validation provider exceeded its declared population")
        require(isinstance(record, LookupRecord) and record.role == "PRETRAIN_VAL",
                "Analysis evaluation permits only the existing S pretraining validation role")
        record.validate(model.config)
        require(record.record_id not in seen and record.record_id not in train_records
                and record.molecule_id not in train_molecules, "TRAIN/validation record or molecule overlap")
        predicted_noise, coverage = model.predict_noise(record.elements, record.noisy)
        noisy, clean = record.noisy.astype(np.float64), record.clean.astype(np.float64)
        predicted_clean = noisy - predicted_noise
        error = predicted_clean - clean
        vector_error += float(np.square(error).sum())
        noisy_vector_error += float(np.square(noisy - clean).sum())
        true_distance = np.linalg.norm(clean[:, None] - clean[None, :], axis=-1)
        src, dst = np.where(np.triu(true_distance < local_cutoff_A, 1))
        expected = true_distance[src, dst]
        reconstructed = np.linalg.norm(predicted_clean[src] - predicted_clean[dst], axis=-1)
        original = np.linalg.norm(noisy[src] - noisy[dst], axis=-1)
        pair_error += float(np.square(reconstructed - expected).sum())
        noisy_pair_error += float(np.square(original - expected).sum())
        atoms += len(clean); pair_count += len(expected)
        edges += coverage["directed_edges"]; known += coverage["known_directed_edges"]
        unknown += coverage["unknown_directed_edges"]
        seen.add(record.record_id); receipts.append(_record_receipt(record))
    require(len(receipts) == expected_records, "Validation stream ended before its declared population")
    return {"status": "ANALYSIS_ONLY_NOT_MODEL_SELECTION", "role": "PRETRAIN_VAL", "records": len(receipts),
        "atoms": atoms, "local_pairs": pair_count, "directed_edges": edges,
        "known_directed_edges": known, "unknown_directed_edges": unknown,
        "displacement_vector_MSE_A2": vector_error / atoms,
        "coordinate_vector_RMSE_A": math.sqrt(vector_error / atoms),
        "coordinate_component_RMSE_A": math.sqrt(vector_error / (3 * atoms)),
        "explicit_sigma_normalized_component_MSE": vector_error / (3 * atoms * sigma_A**2),
        "noisy_identity_vector_MSE_A2": noisy_vector_error / atoms,
        "local_pair_RMSE_A": math.sqrt(pair_error / pair_count) if pair_count else None,
        "noisy_identity_local_pair_RMSE_A": math.sqrt(noisy_pair_error / pair_count) if pair_count else None,
        "local_cutoff_A": local_cutoff_A, "sigma_A_for_normalized_metric_only": sigma_A,
        "evaluation_membership_sha256": canonical_hash(receipts), "all_atoms_in_coordinate_denominator": True,
        "unknown_bins_use_zero_correction_without_exclusion": True, "downstream_records_or_scores_read": False}
