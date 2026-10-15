"""Train-only, molecule-grouped development CV of frozen shared H0.

This module never loads benchmark fold-test or official-test files. Its fixed
readout and fixed ridge supplement are development diagnostics, not final-test
results or checkpoint-selection rules.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Sequence
import uuid

import numpy as np
from rdkit import Chem, rdBase
from rdkit.Chem import AllChem
import torch
from torch import nn
from torch_geometric.data import Batch, Data

from ..model.routes import TaskRouteConfig
from ..model.shared import SharedBackboneMFM
from ..training.checkpoint import CHECKPOINT_FORMAT_VERSION, contract_hash, source_provenance
from .identity import IDENTITY_POLICY, MoleculeIdentityError, canonical_hash, molecule_identity


DEFAULT_TRAIN_CSV = Path(
    "/share/home/zixiao/descriptor_analysis/data/"
    "OpenADMET_ExpansionRx_MLQSAR_paper_reproduction/log_train_data.csv"
)
DEV_TARGETS = (
    "LogD", "LogS", "Log_HLM_CLint", "Log_MLM_CLint", "Log_Caco_Papp_AB",
    "Log_Caco_ER", "Log_Mouse_PPB", "Log_Mouse_BPB", "Log_Mouse_MPB",
)
DEV_SCOPE = "DEV ONLY: fixed CV within ExpansionRx training data; no final test"
CONFORMER_RECIPE = {
    "name": "phase1_ETKDGv3_MMFF_one_conformer_AddHs_Zminus1_v1",
    "num_conformers": 1,
    "add_hs": True,
    "atom_encoding": "atomic_number_minus_one",
    "embedding_max_iterations": 100,
    "mmff_max_iterations": 100,
    "mmff_variant": "MMFF94",
    "num_threads": 1,
}


class DevelopmentDataError(RuntimeError):
    def __init__(self, message, *, ledger, metadata):
        super().__init__(message)
        self.ledger = ledger
        self.metadata = metadata


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_train_csv(path: str | Path) -> Path:
    """Reject test sources before opening a file, including fold-local aliases."""
    resolved = Path(path).resolve()
    forbidden_parent = any(
        part.lower().startswith(("fold_", "fold-", "official_test"))
        or re.fullmatch(r"fold\d+", part.lower())
        for part in resolved.parts[:-1]
    )
    if resolved.name != "log_train_data.csv" or forbidden_parent:
        raise ValueError("Development CV may read only the global log_train_data.csv training source")
    return resolved


def grouped_fold_assignments(keys: Sequence[str], *, seed: int, n_folds: int = 3) -> np.ndarray:
    if n_folds != 3:
        raise ValueError("Phase 1 development CV uses exactly three fixed folds")
    unique = sorted(set(keys), key=lambda key: canonical_hash({"seed": int(seed), "inchikey": key}))
    if len(unique) < n_folds:
        raise ValueError("At least three distinct molecular identities are required")
    mapping = {key: index % n_folds for index, key in enumerate(unique)}
    folds = np.asarray([mapping[key] for key in keys], dtype=np.int64)
    for fold in range(n_folds):
        train = {key for key, value in zip(keys, folds) if value != fold}
        validation = {key for key, value in zip(keys, folds) if value == fold}
        if train & validation:
            raise RuntimeError("Molecular identity leaked across a development fold")
    return folds


def read_train_records(train_csv: str | Path, *, max_molecules: int = 192, seed: int = 0):
    source = require_train_csv(train_csv)
    if not 3 <= max_molecules <= 192:
        raise ValueError("max_molecules must be between 3 and the fixed development cap of 192")
    source_hash = file_sha256(source)
    candidates, excluded = [], []
    with source.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"SMILES", *DEV_TARGETS}
        if not required.issubset(reader.fieldnames or ()):
            missing = sorted(required - set(reader.fieldnames or ()))
            raise ValueError(f"Training CSV is missing fixed development columns: {missing}")
        for row_index, row in enumerate(reader):
            row_id = canonical_hash({"source_sha256": source_hash, "source_row": row_index,
                                     "smiles": row.get("SMILES"), "name": row.get("Molecule Name")})
            ledger = {"source_row": row_index, "source_line": row_index + 2, "row_identity": row_id}
            try:
                identity = molecule_identity(row.get("SMILES", ""), source_field="SMILES")
            except MoleculeIdentityError as exc:
                excluded.append({**ledger, "reason": "invalid_identity", "detail": str(exc)})
                continue
            labels = []
            for name in DEV_TARGETS:
                try:
                    value = float(row.get(name, ""))
                except (TypeError, ValueError):
                    value = float("nan")
                labels.append(value if np.isfinite(value) else float("nan"))
            if not any(np.isfinite(labels)):
                excluded.append({**ledger, "inchikey": identity.inchikey, "reason": "no_finite_development_labels"})
                continue
            candidates.append({**ledger, "inchikey": identity.inchikey,
                               "canonical_smiles": identity.canonical_isomeric_smiles,
                               "labels": labels})
    unique = sorted({row["inchikey"] for row in candidates},
                    key=lambda key: canonical_hash({"seed": int(seed), "inchikey": key}))
    selected = set(unique[:max_molecules])
    records = []
    for row in candidates:
        if row["inchikey"] in selected:
            records.append(row)
        else:
            excluded.append({"source_row": row["source_row"], "source_line": row["source_line"],
                             "row_identity": row["row_identity"], "inchikey": row["inchikey"],
                             "reason": "fixed_development_molecule_cap"})
    metadata = {"source_path": str(source), "source_csv_sha256": source_hash,
                "identity_policy": IDENTITY_POLICY, "target_names": list(DEV_TARGETS),
                "selected_unique_molecules": len(selected), "selected_rows": len(records)}
    try:
        folds = grouped_fold_assignments([row["inchikey"] for row in records], seed=seed)
    except ValueError as exc:
        raise DevelopmentDataError(str(exc), ledger=excluded, metadata=metadata) from exc
    for row, fold in zip(records, folds):
        row["fold"] = int(fold)
    return records, excluded, metadata


def _conformer_seed(inchikey: str, seed: int) -> int:
    return int(canonical_hash({"inchikey": inchikey, "seed": int(seed)})[:8], 16) % (2**31 - 1)


def make_dev_conformer(smiles: str, *, inchikey: str, seed: int, max_atoms: int):
    with rdBase.BlockLogs():
        molecule = Chem.MolFromSmiles(smiles)
        if molecule is None:
            raise ValueError("invalid_canonical_smiles")
        molecule = Chem.AddHs(molecule)
        if not 2 <= molecule.GetNumAtoms() <= max_atoms:
            raise ValueError("atom_count_outside_development_limit")
        atomic_numbers = [atom.GetAtomicNum() for atom in molecule.GetAtoms()]
        if any(number < 1 or number > 118 for number in atomic_numbers):
            raise ValueError("unsupported_atomic_number")
        parameters = AllChem.ETKDGv3()
        parameters.randomSeed = _conformer_seed(inchikey, seed)
        parameters.maxIterations = CONFORMER_RECIPE["embedding_max_iterations"]
        parameters.numThreads = CONFORMER_RECIPE["num_threads"]
        if AllChem.EmbedMolecule(molecule, parameters) != 0:
            raise ValueError("etkdg_embedding_failed")
        if not AllChem.MMFFHasAllMoleculeParams(molecule):
            raise ValueError("mmff_parameters_unavailable")
        optimization_status = int(AllChem.MMFFOptimizeMolecule(
            molecule, mmffVariant=CONFORMER_RECIPE["mmff_variant"],
            maxIters=CONFORMER_RECIPE["mmff_max_iterations"],
        ))
        if optimization_status not in (0, 1):
            raise ValueError("mmff_optimization_failed")
        coordinates = np.asarray(molecule.GetConformer().GetPositions(), dtype=np.float32)
    if not np.isfinite(coordinates).all():
        raise ValueError("nonfinite_conformer")
    return {"x": torch.tensor([number - 1 for number in atomic_numbers], dtype=torch.long).view(-1, 1),
            "pos": torch.from_numpy(coordinates), "mmff_status": optimization_status,
            "mmff_converged": optimization_status == 0}


def conformer_cache_metadata(records, source_metadata, *, seed, max_atoms, source_sha256):
    return {"cache_schema_version": 1, "cache_kind": "phase1_train_only_conformers",
            "scope": DEV_SCOPE, "source_csv_sha256": source_metadata["source_csv_sha256"],
            "source_code_sha256": str(source_sha256), "identity_policy": IDENTITY_POLICY,
            "row_identities": [row["row_identity"] for row in records],
            "row_molecule_identities": [row["inchikey"] for row in records],
            "fold_assignments": [row["fold"] for row in records],
            "target_names": list(DEV_TARGETS), "seed": int(seed), "max_atoms": int(max_atoms),
            "recipe": dict(CONFORMER_RECIPE), "rdkit_version": rdBase.rdkitVersion}


def validate_conformer_cache(payload, expected_metadata):
    if not isinstance(payload, dict) or payload.get("metadata") != expected_metadata:
        raise RuntimeError("Development conformer cache identity/recipe/source contract mismatch")
    if payload.get("metadata_sha256") != canonical_hash(expected_metadata):
        raise RuntimeError("Development conformer cache metadata hash mismatch")
    molecules = payload.get("molecules")
    failures = payload.get("failures")
    expected_keys = set(expected_metadata["row_molecule_identities"])
    if not isinstance(molecules, dict) or not isinstance(failures, dict) or set(molecules) & set(failures):
        raise RuntimeError("Development cache has malformed conformer/exclusion records")
    if set(molecules) | set(failures) != expected_keys:
        raise RuntimeError("Development cache molecule identities do not match the selected rows")
    for molecule in molecules.values():
        if not isinstance(molecule, dict):
            raise RuntimeError("Development cache has malformed conformer records")
        x, pos = molecule.get("x"), molecule.get("pos")
        if not isinstance(x, torch.Tensor) or not isinstance(pos, torch.Tensor) or pos.ndim != 2:
            raise RuntimeError("Development cache has malformed atom alignment")
        if x.shape != (pos.size(0), 1):
            raise RuntimeError("Development cache has malformed atom alignment")
        if pos.size(1) != 3 or not torch.isfinite(pos).all() or not 2 <= pos.size(0) <= expected_metadata["max_atoms"]:
            raise RuntimeError("Development cache has invalid conformer geometry")
        if x.dtype != torch.long or not bool(x.ge(0).all()) or not bool(x.lt(118).all()):
            raise RuntimeError("Development cache has invalid Z-1 atom encoding")
    return payload


@dataclass
class PreparedDevData:
    records: list[dict]
    molecules: dict[str, dict]
    labels: np.ndarray
    folds: np.ndarray
    ledger: list[dict]
    metadata: dict


def prepare_train_only_data(train_csv, *, max_molecules=192, max_atoms=256, seed=0,
                            source_sha256, cache_dir=None):
    if not 2 <= max_atoms <= 512:
        raise ValueError("max_atoms must be bounded between 2 and 512")
    records, ledger, source = read_train_records(train_csv, max_molecules=max_molecules, seed=seed)
    metadata = conformer_cache_metadata(records, source, seed=seed, max_atoms=max_atoms, source_sha256=source_sha256)
    metadata_hash = canonical_hash(metadata)
    cache_path = None if cache_dir is None else Path(cache_dir) / f"conformers_{metadata_hash}.pt"
    if cache_path is not None and cache_path.is_file():
        payload = validate_conformer_cache(torch.load(cache_path, map_location="cpu", weights_only=True), metadata)
    else:
        molecules, failures = {}, {}
        for row in records:
            key = row["inchikey"]
            if key in molecules or key in failures:
                continue
            try:
                molecules[key] = make_dev_conformer(row["canonical_smiles"], inchikey=key, seed=seed, max_atoms=max_atoms)
            except Exception as exc:
                failures[key] = {"reason": "conformer_excluded", "detail": f"{type(exc).__name__}: {exc}"}
        payload = {"metadata": metadata, "metadata_sha256": metadata_hash,
                   "molecules": molecules, "failures": failures}
        validate_conformer_cache(payload, metadata)
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
            torch.save(payload, temporary)
            temporary.replace(cache_path)
    retained = []
    for row in records:
        if row["inchikey"] in payload["failures"]:
            ledger.append({"source_row": row["source_row"], "source_line": row["source_line"],
                           "row_identity": row["row_identity"], "inchikey": row["inchikey"],
                           **payload["failures"][row["inchikey"]]})
        else:
            retained.append(row)
    source.update(cache_metadata=metadata, cache_metadata_sha256=metadata_hash,
                  cache_path=None if cache_path is None else str(cache_path.resolve()),
                  retained_rows=len(retained), retained_unique_molecules=len({row["inchikey"] for row in retained}),
                  excluded_rows=len(ledger),
                  mmff_nonconverged_molecules=sum(not value["mmff_converged"] for value in payload["molecules"].values()))
    if len({row["inchikey"] for row in retained}) < 3 or set(row["fold"] for row in retained) != {0, 1, 2}:
        raise DevelopmentDataError(
            "Conformer exclusions leave insufficient data in a fixed development fold; no reassignment performed",
            ledger=ledger, metadata=source,
        )
    return PreparedDevData(retained, payload["molecules"],
                           np.asarray([row["labels"] for row in retained], dtype=np.float32),
                           np.asarray([row["fold"] for row in retained], dtype=np.int64), ledger, source)


def fit_fold_target_scaler(labels: np.ndarray, train_indices):
    training = np.asarray(labels[train_indices], dtype=np.float64)
    valid = np.isfinite(training)
    counts = valid.sum(axis=0)
    means = np.where(valid, training, 0.0).sum(axis=0) / np.maximum(1, counts)
    variance = np.where(valid, (training - means) ** 2, 0.0).sum(axis=0) / np.maximum(1, counts)
    standard_deviations = np.sqrt(variance)
    standard_deviations = np.where(standard_deviations > 1e-8, standard_deviations, 1.0)
    return {"mean": means, "std": standard_deviations, "counts": counts}


class FixedAtomReadout(nn.Module):
    """The same atom MLP -> mean pooling -> linear readout for every condition."""

    def __init__(self, input_dim: int, output_dim: int):
        super().__init__()
        self.atom_mlp = nn.Sequential(nn.Linear(input_dim, 64), nn.ReLU())
        self.output = nn.Linear(64, output_dim)

    def forward(self, features: Sequence[torch.Tensor]):
        return self.output(torch.stack([self.atom_mlp(atoms).mean(dim=0) for atoms in features]))


def _raw_mae(predictions, labels, indices, training_counts):
    result = {}
    for target, name in enumerate(DEV_TARGETS):
        valid = np.isfinite(labels[indices, target]) & np.isfinite(predictions[:, target])
        count = int(valid.sum())
        result[name] = {"label_count": count, "train_label_count": int(training_counts[target]),
                        "mae": float(np.abs(predictions[valid, target] - labels[indices[valid], target]).mean())
                        if count and training_counts[target] else None}
    return result


def _predict_readout(readout, features, indices, scaler, *, batch_size, device):
    readout.eval()
    predictions = []
    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            selected = indices[start : start + batch_size]
            predictions.append(readout([features[int(index)].to(device) for index in selected]).cpu().numpy())
    normalized = np.concatenate(predictions, axis=0)
    if not np.isfinite(normalized).all():
        raise RuntimeError("Nonfinite development readout prediction")
    return normalized * scaler["std"] + scaler["mean"]


def _fixed_ridge(pooled, labels, train_indices, validation_indices, scaler, *, alpha=1.0):
    predictions = np.broadcast_to(scaler["mean"], (len(validation_indices), len(DEV_TARGETS))).copy()
    for target in range(len(DEV_TARGETS)):
        valid = np.isfinite(labels[train_indices, target])
        selected = train_indices[valid]
        if not len(selected):
            continue
        training = pooled[selected].astype(np.float64)
        feature_mean, feature_std = training.mean(axis=0), training.std(axis=0)
        feature_std = np.where(feature_std > 1e-8, feature_std, 1.0)
        training = (training - feature_mean) / feature_std
        response = (labels[selected, target] - scaler["mean"][target]) / scaler["std"][target]
        dual = np.linalg.solve(training @ training.T + alpha * np.eye(len(selected)), response)
        weights = training.T @ dual
        predictions[:, target] = ((pooled[validation_indices] - feature_mean) / feature_std) @ weights
        predictions[:, target] = predictions[:, target] * scaler["std"][target] + scaler["mean"][target]
    if not np.isfinite(predictions).all():
        raise RuntimeError("Nonfinite fixed-ridge development prediction")
    return _raw_mae(predictions, labels, validation_indices, scaler["counts"])


def _extract_frozen_h0(model, data, *, batch_size, device):
    keys = sorted(data.molecules)
    by_identity = {}
    with torch.no_grad():
        for start in range(0, len(keys), batch_size):
            selected = keys[start : start + batch_size]
            batch = Batch.from_data_list([Data(x=data.molecules[key]["x"], pos=data.molecules[key]["pos"]) for key in selected]).to(device)
            if hasattr(model, "n_atom_types") and bool(batch.x.ge(model.n_atom_types - 1).any()):
                raise RuntimeError("Development atom type is outside the encoder vocabulary; no clamping permitted")
            h0 = model.encode_atoms(batch).detach().float().cpu()
            if h0.ndim != 2 or h0.size(0) != batch.num_nodes or not h0.size(1) or not torch.isfinite(h0).all():
                raise RuntimeError("Invalid or nonfinite frozen H0 during development feature extraction")
            offset = 0
            for key in selected:
                count = data.molecules[key]["x"].size(0)
                by_identity[key] = h0[offset : offset + count]
                offset += count
    return [by_identity[row["inchikey"]] for row in data.records]


def run_train_only_cv(model, *, train_csv=DEFAULT_TRAIN_CSV, output_dir,
                      max_molecules=192, max_atoms=256, epochs=20, batch_size=32, seed=0,
                      cache_dir=None, source_sha256=None, model_metadata=None, device="cpu",
                      project_root=None, wandb_project="phychem-mfm-phase1-dev"):
    """Run fixed training-only CV; persist each epoch and never select on final test."""
    require_train_csv(train_csv)
    if not 1 <= epochs <= 20 or not 1 <= batch_size <= 64:
        raise ValueError("Development epochs must be 1..20 and batch_size 1..64")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if source_sha256 is None:
        source_sha256 = source_provenance(project_root or Path(__file__).resolve().parents[2])["source_sha256"]
    source_sha256 = str(source_sha256)
    policy = {"scope": DEV_SCOPE, "n_folds": 3, "seed": int(seed), "epochs": int(epochs),
              "max_molecules": int(max_molecules), "max_atoms": int(max_atoms), "batch_size": int(batch_size),
              "readout": "atom_linear64_ReLU_mean_linear", "optimizer": "AdamW", "lr": 1e-3,
              "weight_decay": 0.01, "selection": "fixed_last_epoch_no_early_stopping",
              "ridge_alpha": 1.0, "normalization": "train_fold_only",
              "source_code_sha256": source_sha256, "conformer_recipe": dict(CONFORMER_RECIPE),
              "model_metadata": dict(model_metadata or {})}
    run_id = f"dev-{uuid.uuid4().hex}"
    started = time.perf_counter()
    try:
        import wandb
        run = wandb.init(project=wandb_project, id=run_id, name=run_id, mode="offline",
                         dir=str(output), config=policy, reinit=True)
        if (run is None or getattr(run, "disabled", False)
                or not callable(getattr(run, "log", None))
                or not callable(getattr(run, "finish", None))
                or getattr(run, "id", None) != run_id):
            if run is not None and callable(getattr(run, "finish", None)):
                run.finish(exit_code=1)
            raise RuntimeError("Functional W&B offline tracking is required before development training")
    except Exception as exc:
        failure = {"scope": DEV_SCOPE, "status": "failed", "wandb_run_id": run_id,
                   "error_type": type(exc).__name__, "error": str(exc),
                   "elapsed_seconds": time.perf_counter() - started, "policy": policy}
        (output / "failure.json").write_text(json.dumps(failure, indent=2, sort_keys=True), encoding="utf-8")
        raise
    modes = [(module, module.training) for module in model.modules()]
    requires_grad = [(parameter, parameter.requires_grad) for parameter in model.parameters()]
    status, summary = "failed", {}
    try:
        device = torch.device(device)
        model.eval()
        for parameter, _ in requires_grad:
            parameter.requires_grad_(False)
        model.to(device)
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        data = prepare_train_only_data(train_csv, max_molecules=max_molecules, max_atoms=max_atoms,
                                       seed=seed, source_sha256=source_sha256, cache_dir=cache_dir)
        (output / "exclusion_ledger.json").write_text(json.dumps(data.ledger, indent=2, sort_keys=True), encoding="utf-8")
        (output / "development_data.json").write_text(json.dumps(data.metadata, indent=2, sort_keys=True), encoding="utf-8")
        features = _extract_frozen_h0(model, data, batch_size=batch_size, device=device)
        pooled = np.stack([value.mean(dim=0).numpy() for value in features])
        fold_results = []
        for fold in range(3):
            train_indices = np.flatnonzero(data.folds != fold)
            validation_indices = np.flatnonzero(data.folds == fold)
            train_keys = {data.records[int(index)]["inchikey"] for index in train_indices}
            validation_keys = {data.records[int(index)]["inchikey"] for index in validation_indices}
            if train_keys & validation_keys or not len(train_indices) or not len(validation_indices):
                raise RuntimeError("Invalid train-only molecular development CV fold")
            scaler = fit_fold_target_scaler(data.labels, train_indices)
            torch.manual_seed(int(seed) + fold)
            if device.type == "cuda":
                torch.cuda.manual_seed(int(seed) + fold)
            readout = FixedAtomReadout(features[0].size(1), len(DEV_TARGETS)).to(device)
            optimizer = torch.optim.AdamW(readout.parameters(), lr=1e-3, weight_decay=0.01)
            order_generator = np.random.default_rng(int(seed) + fold)
            history = []
            for epoch in range(1, epochs + 1):
                readout.train()
                ordered = order_generator.permutation(train_indices)
                for start in range(0, len(ordered), batch_size):
                    selected = ordered[start : start + batch_size]
                    target = (data.labels[selected] - scaler["mean"]) / scaler["std"]
                    valid = np.isfinite(target) & (scaler["counts"] > 0)
                    if not valid.any():
                        continue
                    target_tensor = torch.as_tensor(np.nan_to_num(target), dtype=torch.float32, device=device)
                    mask = torch.as_tensor(valid, dtype=torch.float32, device=device)
                    prediction = readout([features[int(index)].to(device) for index in selected])
                    per_target = ((prediction - target_tensor).square() * mask).sum(0) / mask.sum(0).clamp_min(1)
                    loss = per_target[mask.sum(0) > 0].mean()
                    if not torch.isfinite(loss):
                        raise RuntimeError("Nonfinite development readout loss")
                    optimizer.zero_grad(set_to_none=True)
                    loss.backward()
                    optimizer.step()
                training_predictions = _predict_readout(readout, features, train_indices, scaler, batch_size=batch_size, device=device)
                validation_predictions = _predict_readout(readout, features, validation_indices, scaler, batch_size=batch_size, device=device)
                training_metrics = _raw_mae(training_predictions, data.labels, train_indices, scaler["counts"])
                validation_metrics = _raw_mae(validation_predictions, data.labels, validation_indices, scaler["counts"])
                epoch_result = {"epoch": epoch, "train": training_metrics, "validation": validation_metrics}
                history.append(epoch_result)
                logged = {"dev/fold": fold, "dev/epoch": epoch}
                for split, metrics in (("train", training_metrics), ("validation", validation_metrics)):
                    for name, metric in metrics.items():
                        logged[f"fold/{fold}/{split}/{name}/label_count"] = metric["label_count"]
                        if metric["mae"] is not None:
                            logged[f"fold/{fold}/{split}/{name}/mae_original_log_units"] = metric["mae"]
                run.log(logged, step=fold * epochs + epoch)
                (output / f"fold_{fold}_history.json").write_text(json.dumps(history, indent=2, sort_keys=True), encoding="utf-8")
            fold_results.append({"fold": fold, "train_rows": len(train_indices), "validation_rows": len(validation_indices),
                                 "train_unique_molecules": len(train_keys), "validation_unique_molecules": len(validation_keys),
                                 "identity_overlap": 0, "train_identity_sha256": canonical_hash(sorted(train_keys)),
                                 "validation_identity_sha256": canonical_hash(sorted(validation_keys)),
                                 "train_target_mean": scaler["mean"].tolist(), "train_target_std": scaler["std"].tolist(),
                                 "train_target_counts": scaler["counts"].tolist(),
                                 "atom_readout_final": history[-1],
                                 "pooled_h0_ridge_fixed_alpha": _fixed_ridge(pooled, data.labels, train_indices, validation_indices, scaler)})
        resources = {"elapsed_seconds": time.perf_counter() - started,
                     "device": str(device), "torch_cpu_threads": torch.get_num_threads(),
                     "peak_cuda_allocated_gib": torch.cuda.max_memory_allocated(device) / 1024**3 if device.type == "cuda" else 0.0}
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            resources["process_peak_rss_mib"] = usage.ru_maxrss / 1024
            resources["process_cpu_seconds"] = usage.ru_utime + usage.ru_stime
        except ImportError:
            resources["process_peak_rss_mib"] = None
            resources["process_cpu_seconds"] = None
        summary = {"scope": DEV_SCOPE, "status": "complete", "wandb_run_id": run.id,
                   "wandb_mode": "offline", "wandb_local_dir": run.dir,
                   "policy": policy, "data": data.metadata, "folds": fold_results, "resources": resources}
        run.log({"dev/completed_folds": 3, "dev/elapsed_seconds": resources["elapsed_seconds"]}, step=3 * epochs + 1)
        run.summary.update({"scope": DEV_SCOPE, "status": "complete", "completed_folds": 3})
        (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        status = "complete"
        return summary
    except Exception as exc:
        if isinstance(exc, DevelopmentDataError):
            (output / "exclusion_ledger.json").write_text(json.dumps(exc.ledger, indent=2, sort_keys=True), encoding="utf-8")
            (output / "development_data.json").write_text(json.dumps(exc.metadata, indent=2, sort_keys=True), encoding="utf-8")
        failure = {"scope": DEV_SCOPE, "status": "failed", "wandb_run_id": run.id,
                   "error_type": type(exc).__name__, "error": str(exc),
                   "elapsed_seconds": time.perf_counter() - started, "policy": policy}
        (output / "failure.json").write_text(json.dumps(failure, indent=2, sort_keys=True), encoding="utf-8")
        run.summary.update(failure)
        raise
    finally:
        for parameter, original in requires_grad:
            parameter.requires_grad_(original)
        for module, original in modes:
            module.training = original
        run.finish(exit_code=0 if status == "complete" else 1)


def load_phase1_probe_checkpoint(checkpoint_path: str | Path, *, device="cpu"):
    """Load only newly identified Phase 1 checkpoints, never historical weights."""
    path = Path(checkpoint_path).resolve()
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict):
        raise RuntimeError("Development checkpoint must be a new Phase 1 shared-H0 checkpoint")
    model_config = payload.get("model_config", {})
    if payload.get("architecture_type") != "shared_multitask" or model_config.get("head_config", {}).get("profile") != "phase1":
        raise RuntimeError("Development checkpoint must be a new Phase 1 shared-H0 checkpoint")
    if payload.get("format_version") != CHECKPOINT_FORMAT_VERSION:
        raise RuntimeError("Unsupported Phase 1 development checkpoint format")
    semantic = payload.get("semantic_config")
    manifest = payload.get("dataset_manifest")
    if not isinstance(semantic, dict) or payload.get("semantic_config_sha256") != contract_hash(semantic):
        raise RuntimeError("Phase 1 checkpoint lacks a verified scientific configuration")
    if semantic.get("head", {}).get("profile") != "phase1":
        raise RuntimeError("Phase 1 checkpoint scientific configuration has no Phase 1 head profile")
    if not isinstance(manifest, dict) or payload.get("dataset_manifest_sha256") != contract_hash(manifest):
        raise RuntimeError("Phase 1 checkpoint lacks a verified data/protocol manifest")
    source_hash = payload.get("source", {}).get("source_sha256", "")
    if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        raise RuntimeError("Phase 1 checkpoint has no source SHA-256")
    model = SharedBackboneMFM(model_config["backbone_config"],
                              task_routes=TaskRouteConfig.from_mapping(model_config["task_route_per_task"]),
                              expert_config=model_config.get("expert_config"), head_config=model_config.get("head_config"))
    if model.config_dict() != model_config:
        raise RuntimeError("Phase 1 checkpoint complete model semantics mismatch")
    model.load_state_dict(payload["model_state"], strict=True)
    model.to(torch.device(device)).eval()
    return model, {"checkpoint_path": str(path), "checkpoint_sha256": file_sha256(path),
                   "checkpoint_source_sha256": source_hash, "variant": payload.get("supervision", {}).get("variant"),
                   "pretraining_data_manifest_sha256": payload["dataset_manifest_sha256"],
                   "pretraining_semantic_config_sha256": payload["semantic_config_sha256"]}
