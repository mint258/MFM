import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from rdkit import Chem
from rdkit.Chem import AllChem
from sklearn.metrics import mean_absolute_error as mae
from sklearn.metrics import r2_score as r2
try:
    from sklearn.metrics import root_mean_squared_error as rmse
except ImportError:
    from sklearn.metrics import mean_squared_error

    def rmse(y_true, y_pred):
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm

from torch_geometric.data import Data
from torch_geometric.nn import global_mean_pool
try:
    from filelock import FileLock
except Exception:
    FileLock = None  # type: ignore[assignment]

THIS_DIR = Path(__file__).resolve().parent
MFM_DIR = THIS_DIR.parent
if str(MFM_DIR) not in sys.path:
    sys.path.insert(0, str(MFM_DIR))

from models.moe import MultiTaskMoE  # noqa: E402


DEFAULT_TARGETS = [
    "LogD",
    "LogS",
    "Log_HLM_CLint",
    "Log_MLM_CLint",
    "Log_Caco_Papp_AB",
    "Log_Caco_ER",
    "Log_Mouse_PPB",
    "Log_Mouse_BPB",
    "Log_Mouse_MPB",
]

DEFAULT_TASK_WEIGHTS = [1.018, 1.000, 1.364, 1.134, 2.377, 2.373, 3.939, 5.259, 23.099]
EMBEDDING_BASE_MODE_CHOICES = ["backbone", "moe_concat", "moe_fused", "backbone_moe_fused"]
EMBEDDING_MODE_CHOICES = list(EMBEDDING_BASE_MODE_CHOICES) + [f"{mode}_late" for mode in EMBEDDING_BASE_MODE_CHOICES]
POOLING_TIMING_CHOICES = ["early", "late"]
DEFAULT_XYZ_POOL_NAME = "xyz_pool"


def resolve_embedding_and_pooling(embedding_mode: str, pooling_timing: str = "early") -> Tuple[str, str]:
    mode = str(embedding_mode).strip().lower()
    timing = str(pooling_timing).strip().lower()
    if timing not in set(POOLING_TIMING_CHOICES):
        raise ValueError(f"Unsupported pooling_timing: {pooling_timing}")
    if mode.endswith("_late"):
        base_mode = mode[: -len("_late")]
        if base_mode in set(EMBEDDING_BASE_MODE_CHOICES):
            return base_mode, "late"
    if mode in set(EMBEDDING_BASE_MODE_CHOICES):
        return mode, timing
    raise ValueError(f"Unsupported embedding_mode: {embedding_mode}")


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def parse_fold_spec(spec: str) -> List[int]:
    spec = spec.strip()
    if re.fullmatch(r"\d+", spec):
        return [int(spec)]
    if re.fullmatch(r"\d+\-\d+", spec):
        left, right = spec.split("-")
        l_int = int(left)
        r_int = int(right)
        if l_int > r_int:
            raise ValueError(f"Invalid fold range: {spec}")
        return list(range(l_int, r_int + 1))
    if "," in spec:
        values = [int(x.strip()) for x in spec.split(",") if x.strip()]
        if not values:
            raise ValueError(f"Invalid fold list: {spec}")
        return values
    raise ValueError(f"Unsupported fold spec: {spec}")


def resolve_device(device: str) -> torch.device:
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


def load_fold_split(data_dir: str, fold: int, split: str) -> pd.DataFrame:
    csv_path = Path(data_dir) / f"fold_{fold}" / f"{split}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing split file: {csv_path}")
    return pd.read_csv(csv_path)


def prepare_task_df(df: pd.DataFrame, targets: Sequence[str]) -> pd.DataFrame:
    out = df.copy()
    out["smiles"] = out["SMILES"].astype(str)
    out = out.dropna(how="all", subset=list(targets)).reset_index(drop=True)
    return out


def split_train_val(n_rows: int, val_frac: float, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    if n_rows < 2:
        raise ValueError("Need at least 2 rows for train/val split.")
    val_size = max(1, int(n_rows * val_frac))
    if val_size >= n_rows:
        val_size = n_rows - 1
    idx = np.arange(n_rows)
    rng = np.random.default_rng(seed)
    rng.shuffle(idx)
    val_idx = np.sort(idx[:val_size])
    train_idx = np.sort(idx[val_size:])
    return train_idx, val_idx


def _cfg_get(cfg: Dict, keys: Sequence[str], default):
    for key in keys:
        if key in cfg:
            return cfg[key]
    return default


def _strip_module_prefix(state: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
    if not state:
        return state
    if all(k.startswith("module.") for k in state.keys()):
        return {k[len("module.") :]: v for k, v in state.items()}
    return state


def _strip_prefix_if_all(state: Dict[str, torch.Tensor], prefix: str) -> Dict[str, torch.Tensor]:
    if not state:
        return state
    if all(k.startswith(prefix) for k in state.keys()):
        return {k[len(prefix) :]: v for k, v in state.items()}
    return state


def _count_param_total(state_dict: Dict[str, torch.Tensor]) -> int:
    total = 0
    for value in state_dict.values():
        total += int(value.numel())
    return total


def _resolve_xyz_pool_root(explicit_root: Optional[str]) -> Path:
    if explicit_root:
        return Path(str(explicit_root)).expanduser().resolve()
    return (MFM_DIR / DEFAULT_XYZ_POOL_NAME).resolve()


def _lock_path_for_target(path: Path) -> Path:
    return path.with_name(f"{path.name}.lock")


def _optional_file_lock(path: Path, *, timeout: float = 600.0):
    return FileLock(str(path), timeout=timeout) if FileLock is not None else nullcontext()


def _cache_lock_path(cache_path: Path) -> Path:
    return _lock_path_for_target(cache_path)


def _xyz_sample_lock_path(smiles: str, xyz_root: Path) -> Path:
    return xyz_root / f"{_smiles_cache_key(smiles)}.lock"


def _safe_torch_load(path: Path, *, map_location: str = "cpu"):
    try:
        return torch.load(path, map_location=map_location)
    except Exception as exc:
        ts = int(time.time())
        corrupt_path = path.with_name(f"{path.stem}.corrupt_{ts}{path.suffix}")
        try:
            os.replace(path, corrupt_path)
            print(f"[cache] Corrupted cache moved to {corrupt_path}: {exc}")
        except Exception:
            print(f"[cache] Corrupted cache ignored at {path}: {exc}")
        return None


def _atomic_torch_save(payload: Dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        torch.save(payload, tmp_path)
        os.replace(tmp_path, path)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def load_pretrained_mfm(
    ckpt_path: str,
    device: torch.device,
    return_load_info: bool = False,
):
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    cfg = ckpt.get("model_cfg", ckpt.get("cfg", {}))
    if not isinstance(cfg, dict):
        raise KeyError("Checkpoint is missing a valid model_cfg/cfg dictionary.")
    bb_cfg = cfg.get("backbone_config", cfg.get("backbone_cfg", {}))
    if not isinstance(bb_cfg, dict) or not bb_cfg:
        raise KeyError("Checkpoint config is missing backbone_config.")

    model_kwargs = {
        "backbone_config": bb_cfg,
        "n_atom_types": int(_cfg_get(cfg, ["n_atom_types"], 95)),
        "n_experts_geom": int(_cfg_get(cfg, ["n_experts_geom", "expert_number_G"], 4)),
        "n_experts_energy": int(_cfg_get(cfg, ["n_experts_energy", "expert_number_E"], 2)),
        "n_experts_charge": int(_cfg_get(cfg, ["n_experts_charge", "expert_number_Q"], 2)),
        "n_experts_elem": int(_cfg_get(cfg, ["n_experts_elem", "expert_number_Z"], 1)),
        "n_experts_bond": int(_cfg_get(cfg, ["n_experts_bond", "expert_number_B"], 1)),
        "top_k_geom": int(_cfg_get(cfg, ["top_k_geom", "topk_geom", "topkG"], 1)),
        "top_k_energy": int(_cfg_get(cfg, ["top_k_energy", "topk_energy", "topkE"], 1)),
        "top_k_charge": int(_cfg_get(cfg, ["top_k_charge", "topk_charge", "topkQ"], 1)),
        "top_k_elem": int(_cfg_get(cfg, ["top_k_elem", "topk_elem", "topkZ"], 1)),
        "top_k_bond": int(_cfg_get(cfg, ["top_k_bond", "topk_bond", "topkB"], 1)),
        "expert_layers": int(_cfg_get(cfg, ["expert_layers"], 2)),
        "expert_int_layers": int(_cfg_get(cfg, ["expert_int_layers"], 0)),
        "expert_heads": int(_cfg_get(cfg, ["expert_heads"], 4)),
        "expert_ff_mult": int(_cfg_get(cfg, ["expert_ff_mult"], 2)),
        "balance_weight": float(_cfg_get(cfg, ["balance_weight"], 1e-2)),
        "bond_negative_ratio": float(_cfg_get(cfg, ["bond_negative_ratio"], 1.0)),
    }
    if "expert_real_layers" in cfg or "expert_layers" in cfg:
        model_kwargs["expert_real_layers"] = int(_cfg_get(cfg, ["expert_real_layers", "expert_layers"], 2))
    if "fused_dim" in cfg:
        model_kwargs["fused_dim"] = int(cfg["fused_dim"])
    if "graph_descriptor_names" in cfg:
        model_kwargs["graph_descriptor_names"] = cfg.get("graph_descriptor_names")

    model = MultiTaskMoE(**model_kwargs)

    state_raw = ckpt.get("model_state", ckpt.get("moe_state", ckpt.get("state_dict")))
    state_key_prefix = "raw"
    if state_raw is None:
        raise KeyError("Checkpoint missing 'model_state', 'moe_state', or 'state_dict'.")
    if isinstance(state_raw, dict) and state_raw and all(str(k).startswith("module.") for k in state_raw.keys()):
        state_key_prefix = "module_stripped"
    state = state_raw
    if state is None:
        raise KeyError("Checkpoint missing 'model_state', 'moe_state', or 'state_dict'.")
    state = _strip_module_prefix(state)
    if state_key_prefix == "raw" and isinstance(state, dict) and state and all(str(k).startswith("model.") for k in state.keys()):
        state = _strip_prefix_if_all(state, "model.")
        state_key_prefix = "model_stripped"
    if state_key_prefix == "raw" and isinstance(state, dict) and state and all(str(k).startswith("moe.") for k in state.keys()):
        state = _strip_prefix_if_all(state, "moe.")
        state_key_prefix = "moe_stripped"
    load_result = model.load_state_dict(state, strict=False)
    model_sd = model.state_dict()
    total_params = _count_param_total(model_sd)
    matched_params = 0
    for k, v in model_sd.items():
        src = state.get(k)
        if isinstance(src, torch.Tensor) and tuple(src.shape) == tuple(v.shape):
            matched_params += int(v.numel())

    load_info = {
        "loaded": True,
        "checkpoint": ckpt_path,
        "checkpoint_format": str(ckpt.get("checkpoint_kind", "mfm_multitask")),
        "matched_param_ratio": float(matched_params / max(1, total_params)),
        "n_missing_keys": int(len(getattr(load_result, "missing_keys", []))),
        "n_unexpected_keys": int(len(getattr(load_result, "unexpected_keys", []))),
        "state_key_prefix": state_key_prefix,
        "mp_kwargs": None,
        "error": None,
    }
    model.to(device)
    model.eval()
    if return_load_info:
        return model, cfg, load_info
    return model, cfg


def _rdkit_conformers(
    smiles: str,
    num_conformers: int,
    seed: int,
    optimize: bool,
    max_opt_iters: int,
    add_hs: bool,
) -> Optional[Tuple[Chem.Mol, List[int]]]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    if add_hs:
        mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = int(seed)
    if hasattr(params, "maxAttempts"):
        params.maxAttempts = 50
    conf_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=int(num_conformers), params=params))
    if not conf_ids:
        return None
    if optimize:
        for conf_id in conf_ids:
            try:
                AllChem.UFFOptimizeMolecule(mol, confId=int(conf_id), maxIters=int(max_opt_iters))
            except Exception:
                continue
    return mol, conf_ids


def _sanitize_filename(text: str, max_len: int = 48) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text))
    out = out.strip("._-")
    if not out:
        out = "item"
    return out[:max_len]


def _smiles_cache_key(smiles: str) -> str:
    digest = hashlib.sha1(smiles.encode("utf-8")).hexdigest()[:12]
    head = _sanitize_filename(smiles, max_len=24)
    return f"{head}_{digest}"


def _shared_xyz_root_from_cache_path(cache_path: Optional[Path]) -> Optional[Path]:
    if cache_path is None:
        return None
    parent = cache_path.parent
    if re.fullmatch(r"fold_\d+", parent.name):
        return parent.parent / "xyz_pool"
    return parent / "xyz_pool"


def _smiles_xyz_dir(smiles: str, xyz_root: Path) -> Path:
    return xyz_root / _smiles_cache_key(smiles)


def _list_smiles_xyz_files(smiles: str, xyz_root: Optional[Path]) -> List[Path]:
    if xyz_root is None:
        return []
    smi_dir = _smiles_xyz_dir(smiles, xyz_root)
    if not smi_dir.exists():
        return []
    files = sorted(smi_dir.glob("conf_*.xyz"))
    return [p for p in files if p.is_file()]


def _smiles_xyz_count(smiles: str, xyz_root: Optional[Path]) -> int:
    return len(_list_smiles_xyz_files(smiles, xyz_root))


def _write_single_conf_xyz(
    mol: Chem.Mol,
    conf_id: int,
    out_path: Path,
    *,
    smiles: str,
    seed: int,
) -> None:
    conf = mol.GetConformer(int(conf_id))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"{mol.GetNumAtoms()}\n")
        f.write(f"smiles={smiles} conf_id={int(conf_id)} seed={int(seed)}\n")
        for atom_idx, atom in enumerate(mol.GetAtoms()):
            pos = conf.GetAtomPosition(atom_idx)
            f.write(
                f"{atom.GetSymbol()} {pos.x:.8f} {pos.y:.8f} {pos.z:.8f}\n"
            )


def _write_single_atoms_coords_xyz(
    atom_symbols: Sequence[str],
    coords: np.ndarray,
    out_path: Path,
    *,
    smiles: str,
    seed: int,
) -> None:
    arr = np.asarray(coords, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[1] != 3 or arr.shape[0] != len(atom_symbols):
        raise ValueError(f"Invalid xyz rows for {out_path}: atoms={len(atom_symbols)} coords_shape={tuple(arr.shape)}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"{len(atom_symbols)}\n")
        f.write(f"smiles={smiles} seed={int(seed)}\n")
        for symbol, xyz in zip(atom_symbols, arr):
            f.write(f"{str(symbol)} {float(xyz[0]):.8f} {float(xyz[1]):.8f} {float(xyz[2]):.8f}\n")


def _write_xyz_meta(smiles: str, xyz_root: Path, seed: int) -> None:
    sample_dir = _smiles_xyz_dir(smiles, xyz_root)
    meta = {
        "smiles": smiles,
        "last_seed": int(seed),
        "n_conformers_cached": int(_smiles_xyz_count(smiles, xyz_root)),
    }
    with open(sample_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def _read_single_conf_xyz(path: Path) -> Tuple[List[str], np.ndarray]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        raise ValueError(f"XYZ file is too short: {path}")
    n_atoms = int(lines[0].strip())
    body = lines[2 : 2 + n_atoms]
    if len(body) != n_atoms:
        raise ValueError(f"XYZ atom count mismatch in {path}: expected {n_atoms}, found {len(body)}")
    atom_symbols: List[str] = []
    coords: List[List[float]] = []
    for line in body:
        parts = line.strip().split()
        if len(parts) < 4:
            raise ValueError(f"Malformed xyz atom line in {path}: {line!r}")
        atom_symbols.append(str(parts[0]))
        coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
    arr = np.asarray(coords, dtype=np.float32)
    if arr.shape != (n_atoms, 3):
        raise ValueError(f"Unexpected xyz coordinate shape in {path}: {tuple(arr.shape)}")
    return atom_symbols, arr


def _load_xyz_rows(smiles: str, xyz_root: Optional[Path], required_conformers: int) -> Tuple[List[List[str]], List[np.ndarray]]:
    files = _list_smiles_xyz_files(smiles, xyz_root)
    atom_rows: List[List[str]] = []
    coord_rows: List[np.ndarray] = []
    ref_atoms: Optional[List[str]] = None
    for path in files:
        try:
            atoms, coords = _read_single_conf_xyz(path)
        except Exception:
            continue
        if ref_atoms is None:
            ref_atoms = list(atoms)
        if list(atoms) != ref_atoms:
            continue
        atom_rows.append(list(atoms))
        coord_rows.append(np.asarray(coords, dtype=np.float32))
        if len(atom_rows) >= int(required_conformers):
            break
    return atom_rows, coord_rows


def _mol_conf_atoms_coords(mol: Chem.Mol, conf_id: int) -> Tuple[List[str], np.ndarray]:
    conf = mol.GetConformer(int(conf_id))
    atoms = [atom.GetSymbol() for atom in mol.GetAtoms()]
    coords = conf.GetPositions().astype(np.float32)
    return atoms, coords


def _append_conformers_to_xyz_pool(
    smiles: str,
    *,
    num_new_conformers: int,
    start_index: int,
    seed: int,
    optimize: bool,
    max_opt_iters: int,
    add_hs: bool,
    xyz_root: Path,
) -> bool:
    if int(num_new_conformers) <= 0:
        return True
    ref_atom_rows, _ = _load_xyz_rows(smiles, xyz_root, required_conformers=1)
    ref_atoms = list(ref_atom_rows[0]) if ref_atom_rows else None
    conf_pack = _rdkit_conformers(
        smiles=smiles,
        num_conformers=max(1, int(num_new_conformers)),
        seed=int(seed),
        optimize=bool(optimize),
        max_opt_iters=int(max_opt_iters),
        add_hs=bool(add_hs),
    )
    if conf_pack is None:
        return False
    mol, conf_ids = conf_pack
    if ref_atoms is not None:
        try:
            gen_atoms, _ = _mol_conf_atoms_coords(mol, int(conf_ids[0]))
        except Exception:
            return False
        if list(gen_atoms) != ref_atoms:
            return False
    sample_dir = _smiles_xyz_dir(smiles, xyz_root)
    sample_dir.mkdir(parents=True, exist_ok=True)
    for write_idx, conf_id in enumerate(conf_ids[: int(num_new_conformers)], start=int(start_index)):
        out_path = sample_dir / f"conf_{write_idx:05d}.xyz"
        _write_single_conf_xyz(
            mol,
            int(conf_id),
            out_path,
            smiles=smiles,
            seed=int(seed),
        )
    _write_xyz_meta(smiles, xyz_root, seed=seed)
    return True


def _ensure_required_conformers_in_xyz_pool(
    smiles: str,
    *,
    required_conformers: int,
    seed: int,
    optimize: bool,
    max_opt_iters: int,
    add_hs: bool,
    xyz_root: Optional[Path],
) -> bool:
    if xyz_root is None:
        return False
    xyz_root.mkdir(parents=True, exist_ok=True)
    required = max(1, int(required_conformers))
    lock_path = _xyz_sample_lock_path(smiles, xyz_root)
    with _optional_file_lock(lock_path):
        existing = _smiles_xyz_count(smiles, xyz_root)
        if existing >= required:
            return True
        start_index = int(existing)
        extra_needed = int(required - existing)
        extra_seed = int(seed) + max(0, start_index) * 1009
        ok = _append_conformers_to_xyz_pool(
            smiles,
            num_new_conformers=extra_needed,
            start_index=start_index,
            seed=extra_seed,
            optimize=optimize,
            max_opt_iters=max_opt_iters,
            add_hs=add_hs,
            xyz_root=xyz_root,
        )
        return bool(ok and _smiles_xyz_count(smiles, xyz_root) >= required)


def _export_conformers_to_xyz(
    smiles: str,
    mol: Chem.Mol,
    conf_ids: Sequence[int],
    *,
    seed: int,
    xyz_root: Optional[Path],
    row_tag: Optional[str],
) -> None:
    if xyz_root is None:
        return
    sample_dir = _smiles_xyz_dir(smiles, xyz_root)
    lock_path = _xyz_sample_lock_path(smiles, xyz_root)
    with _optional_file_lock(lock_path):
        sample_dir.mkdir(parents=True, exist_ok=True)
        existing = _list_smiles_xyz_files(smiles, xyz_root)
        start_idx = len(existing)
        if start_idx < len(conf_ids):
            for i, conf_id in enumerate(conf_ids[start_idx:], start=start_idx):
                out_path = sample_dir / f"conf_{i:05d}.xyz"
                _write_single_conf_xyz(
                    mol,
                    conf_id,
                    out_path,
                    smiles=smiles,
                    seed=seed,
                )
        _write_xyz_meta(smiles, xyz_root, seed=seed)


def _xyz_tree_has_files(xyz_root: Path) -> bool:
    if not xyz_root.exists():
        return False
    for _ in xyz_root.rglob("*.xyz"):
        return True
    return False


def _mol_to_data(mol: Chem.Mol, conf_id: int, atom_index_offset: int) -> Data:
    atom_indices = [atom.GetAtomicNum() + int(atom_index_offset) for atom in mol.GetAtoms()]
    conf = mol.GetConformer(int(conf_id))
    pos = []
    for atom_i in range(mol.GetNumAtoms()):
        xyz = conf.GetAtomPosition(atom_i)
        pos.append([xyz.x, xyz.y, xyz.z])
    x = torch.as_tensor(atom_indices, dtype=torch.long).view(-1, 1)
    coords = torch.as_tensor(pos, dtype=torch.float32)
    return Data(x=x, pos=coords)


def _atoms_coords_to_data(atom_symbols: Sequence[str], coords: np.ndarray, atom_index_offset: int) -> Data:
    periodic_table = Chem.GetPeriodicTable()
    atom_indices = [int(periodic_table.GetAtomicNumber(str(symbol))) + int(atom_index_offset) for symbol in atom_symbols]
    x = torch.as_tensor(atom_indices, dtype=torch.long).view(-1, 1)
    pos = torch.as_tensor(np.asarray(coords, dtype=np.float32), dtype=torch.float32)
    return Data(x=x, pos=pos)


@dataclass
class EmbedderConfig:
    num_conformers: int = 8
    optimize_conformers: bool = True
    max_opt_iters: int = 200
    add_hs: bool = True
    embedding_mode: str = "backbone"
    xyz_pool_root: Optional[str] = None
    # Downstream RDKit atomic numbers (H=1, C=6, ...) are shifted to the
    # model's 0-based element ids by default.
    atom_index_offset: int = -1


class MFMConformerEmbedder:
    def __init__(self, model: MultiTaskMoE, device: torch.device, cfg: EmbedderConfig):
        self.model = model
        self.device = device
        self.cfg = cfg
        self.base_latent_dim = int(getattr(model, "latent_dim"))
        self.fused_latent_dim = int(getattr(model, "fused_dim", self.base_latent_dim))
        self.base_embedding_mode, _ = resolve_embedding_and_pooling(self.cfg.embedding_mode, "early")
        if self.base_embedding_mode == "backbone":
            self.latent_dim = self.base_latent_dim
        elif self.base_embedding_mode == "moe_concat":
            self.latent_dim = self.base_latent_dim * 6
        elif self.base_embedding_mode == "moe_fused":
            self.latent_dim = self.fused_latent_dim
        elif self.base_embedding_mode == "backbone_moe_fused":
            self.latent_dim = self.base_latent_dim + self.fused_latent_dim
        else:
            raise ValueError(f"Unsupported base embedding mode: {self.base_embedding_mode}")
        self.shared_xyz_pool_root = _resolve_xyz_pool_root(self.cfg.xyz_pool_root)
        self.shared_xyz_pool_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _self_attention_pool_tokens(tokens: torch.Tensor) -> torch.Tensor:
        if tokens.dim() != 2:
            raise ValueError(f"tokens must be [T, D], got shape={tuple(tokens.shape)}")
        n_tokens = int(tokens.shape[0])
        if n_tokens <= 1:
            return tokens[0]
        dim = int(tokens.shape[1])
        scale = float(dim) ** -0.5
        context = tokens.mean(dim=0, keepdim=True)
        scores = (tokens * context).sum(dim=1) * scale
        attn = torch.softmax(scores, dim=0)
        return (attn.unsqueeze(-1) * tokens).sum(dim=0)

    def _effective_xyz_root(self, xyz_root: Optional[Path]) -> Optional[Path]:
        if xyz_root is not None:
            return Path(xyz_root)
        return Path(self.shared_xyz_pool_root) if self.shared_xyz_pool_root is not None else None

    def _required_conformer_count(self) -> int:
        return max(1, int(self.cfg.num_conformers))

    def _ensure_xyz_pool_for_smiles(self, smiles: str, seed: int, xyz_root: Optional[Path]) -> bool:
        root = self._effective_xyz_root(xyz_root)
        if root is None:
            return False
        return _ensure_required_conformers_in_xyz_pool(
            smiles,
            required_conformers=self._required_conformer_count(),
            seed=int(seed),
            optimize=bool(self.cfg.optimize_conformers),
            max_opt_iters=int(self.cfg.max_opt_iters),
            add_hs=bool(self.cfg.add_hs),
            xyz_root=root,
        )

    def _get_conformer_rows(
        self,
        smiles: str,
        seed: int,
        xyz_root: Optional[Path],
    ) -> Tuple[List[List[str]], List[np.ndarray], bool]:
        root = self._effective_xyz_root(xyz_root)
        required = self._required_conformer_count()
        if root is not None:
            ok = self._ensure_xyz_pool_for_smiles(smiles, seed=int(seed), xyz_root=root)
            if ok:
                atom_rows, coord_rows = _load_xyz_rows(smiles, root, required)
                if len(atom_rows) >= required and len(coord_rows) >= required:
                    return atom_rows[:required], coord_rows[:required], True

        conf_pack = _rdkit_conformers(
            smiles=smiles,
            num_conformers=required,
            seed=int(seed),
            optimize=bool(self.cfg.optimize_conformers),
            max_opt_iters=int(self.cfg.max_opt_iters),
            add_hs=bool(self.cfg.add_hs),
        )
        if conf_pack is None:
            return [], [], False
        mol, conf_ids = conf_pack
        atom_rows: List[List[str]] = []
        coord_rows: List[np.ndarray] = []
        for conf_id in conf_ids[:required]:
            try:
                atoms, coords = _mol_conf_atoms_coords(mol, int(conf_id))
            except Exception:
                continue
            atom_rows.append(list(atoms))
            coord_rows.append(np.asarray(coords, dtype=np.float32))

        if root is not None and atom_rows:
            pooled_ref_atoms, _ = _load_xyz_rows(smiles, root, required_conformers=1)
            if pooled_ref_atoms and list(pooled_ref_atoms[0]) != list(atom_rows[0]):
                return atom_rows[:required], coord_rows[:required], len(atom_rows) >= required
            lock_path = _xyz_sample_lock_path(smiles, root)
            with _optional_file_lock(lock_path):
                sample_dir = _smiles_xyz_dir(smiles, root)
                existing = _smiles_xyz_count(smiles, root)
                sample_dir.mkdir(parents=True, exist_ok=True)
                for write_idx, (atoms, coords) in enumerate(zip(atom_rows, coord_rows), start=existing):
                    out_path = sample_dir / f"conf_{write_idx:05d}.xyz"
                    if out_path.exists():
                        continue
                    _write_single_atoms_coords_xyz(
                        atoms,
                        coords,
                        out_path,
                        smiles=smiles,
                        seed=int(seed),
                    )
                _write_xyz_meta(smiles, root, seed=seed)
            pooled_atoms, pooled_coords = _load_xyz_rows(smiles, root, required)
            if len(pooled_atoms) >= required and len(pooled_coords) >= required:
                return pooled_atoms[:required], pooled_coords[:required], True

        return atom_rows[:required], coord_rows[:required], len(atom_rows) >= required

    def ensure_xyz_pool_for_smiles_list(
        self,
        smiles: Sequence[str],
        *,
        seed: int,
        desc: str,
        xyz_root: Optional[Path] = None,
    ) -> np.ndarray:
        root = self._effective_xyz_root(xyz_root)
        valid = np.zeros(len(smiles), dtype=bool)
        if root is None:
            return valid
        for i, smi in enumerate(tqdm(smiles, desc=desc)):
            s = str(smi)
            if not s:
                continue
            if Chem.MolFromSmiles(s) is None:
                continue
            valid[i] = bool(self._ensure_xyz_pool_for_smiles(s, seed=int(seed) + i, xyz_root=root))
        return valid

    @staticmethod
    def _self_attention_pool_conf_axis(x_conf: torch.Tensor) -> torch.Tensor:
        if x_conf.dim() != 3:
            raise ValueError(f"x_conf must be [C, N, D], got shape={tuple(x_conf.shape)}")
        n_conf = int(x_conf.shape[0])
        if n_conf <= 1:
            return x_conf[0]
        dim = int(x_conf.shape[2])
        scale = float(dim) ** -0.5
        context = x_conf.mean(dim=0, keepdim=True)
        scores = (x_conf * context).sum(dim=2) * scale
        attn = torch.softmax(scores, dim=0)
        return (attn.unsqueeze(-1) * x_conf).sum(dim=0)

    def _compute_latent_bundle(self, data_obj: Data) -> Dict[str, torch.Tensor]:
        node_latent = self.model.backbone(data_obj)
        if self.base_embedding_mode == "backbone":
            return {
                "backbone": node_latent,
            }

        batch = getattr(data_obj, "batch", None)
        if batch is None:
            batch = torch.zeros(node_latent.shape[0], dtype=torch.long, device=node_latent.device)
        pos = getattr(data_obj, "pos", None)

        latent_E, _ = self.model._route(
            node_latent, batch, gate_layer=self.model.gate_energy, experts=self.model.experts_energy, top_k=self.model.top_k_energy, pos=pos
        )
        latent_Q, _ = self.model._route(
            node_latent, batch, gate_layer=self.model.gate_charge, experts=self.model.experts_charge, top_k=self.model.top_k_charge, pos=pos
        )
        latent_Z, _ = self.model._route(
            node_latent, batch, gate_layer=self.model.gate_elem, experts=self.model.experts_elem, top_k=self.model.top_k_elem, pos=pos
        )
        latent_G, _ = self.model._route(
            node_latent, batch, gate_layer=self.model.gate_geom, experts=self.model.experts_geom, top_k=self.model.top_k_geom, pos=pos
        )
        latent_B, _ = self.model._route(
            node_latent, batch, gate_layer=self.model.gate_bond, experts=self.model.experts_bond, top_k=self.model.top_k_bond, pos=pos
        )

        h_fused = self.model._fuse_latents(latent_E, latent_Q, latent_Z, latent_G, latent_B)
        fused_graph_repr = torch.squeeze(global_mean_pool(h_fused, batch), dim=0)
        raw_moe_concat = torch.cat([node_latent, latent_E, latent_Q, latent_Z, latent_G, latent_B], dim=1)

        return {
            "backbone": node_latent,
            "latent_e": latent_E,
            "latent_q": latent_Q,
            "latent_z": latent_Z,
            "latent_g": latent_G,
            "latent_b": latent_B,
            "raw_moe_concat": raw_moe_concat,
            "fused_node_repr": h_fused,
            "fused_graph_repr": fused_graph_repr,
        }

    def _node_embed_single_conf(self, data_obj: Data) -> torch.Tensor:
        bundle = self._compute_latent_bundle(data_obj)
        if self.base_embedding_mode == "backbone":
            return bundle["backbone"]
        if self.base_embedding_mode == "moe_concat":
            return bundle["raw_moe_concat"]
        if self.base_embedding_mode == "moe_fused":
            return bundle["fused_node_repr"]
        if self.base_embedding_mode == "backbone_moe_fused":
            return torch.cat([bundle["backbone"], bundle["fused_node_repr"]], dim=1)
        raise ValueError(f"Unsupported base embedding mode: {self.base_embedding_mode}")

    def _graph_embed_single_conf(self, data_obj: Data) -> torch.Tensor:
        bundle = self._compute_latent_bundle(data_obj)
        if self.base_embedding_mode == "backbone":
            return self._self_attention_pool_tokens(bundle["backbone"])
        if self.base_embedding_mode == "moe_concat":
            return self._self_attention_pool_tokens(bundle["raw_moe_concat"])
        if self.base_embedding_mode == "moe_fused":
            return bundle["fused_graph_repr"]
        if self.base_embedding_mode == "backbone_moe_fused":
            return torch.cat(
                [
                    self._self_attention_pool_tokens(bundle["backbone"]),
                    bundle["fused_graph_repr"],
                ],
                dim=0,
            )
        raise ValueError(f"Unsupported base embedding mode: {self.base_embedding_mode}")

    @torch.no_grad()
    def embed_smiles(self, smiles: str, seed: int) -> Tuple[torch.Tensor, bool]:
        return self.embed_smiles_with_xyz(
            smiles,
            seed,
            xyz_root=None,
            row_tag=None,
        )

    @torch.no_grad()
    def embed_smiles_with_xyz(
        self,
        smiles: str,
        seed: int,
        *,
        xyz_root: Optional[Path],
        row_tag: Optional[str],
    ) -> Tuple[torch.Tensor, bool]:
        atom_rows, coord_rows, ok = self._get_conformer_rows(smiles, seed=seed, xyz_root=xyz_root)
        if not ok:
            return torch.zeros(self.latent_dim, dtype=torch.float32), False
        embeds: List[torch.Tensor] = []
        for atoms, coords in zip(atom_rows, coord_rows):
            data_obj = _atoms_coords_to_data(atoms, coords, self.cfg.atom_index_offset).to(self.device)
            graph_latent = self._graph_embed_single_conf(data_obj)
            embeds.append(graph_latent.detach().cpu())
        if not embeds:
            return torch.zeros(self.latent_dim, dtype=torch.float32), False
        conf_tokens = torch.stack(embeds, dim=0)
        token = self._self_attention_pool_tokens(conf_tokens)
        return token, True

    @torch.no_grad()
    def embed_smiles_atoms_with_xyz(
        self,
        smiles: str,
        seed: int,
        *,
        xyz_root: Optional[Path],
        row_tag: Optional[str],
    ) -> Tuple[torch.Tensor, bool]:
        atom_rows, coord_rows, ok = self._get_conformer_rows(smiles, seed=seed, xyz_root=xyz_root)
        if not ok:
            return torch.zeros((1, self.latent_dim), dtype=torch.float32), False
        atom_embeds: List[torch.Tensor] = []
        for atoms, coords in zip(atom_rows, coord_rows):
            data_obj = _atoms_coords_to_data(atoms, coords, self.cfg.atom_index_offset).to(self.device)
            atom_latent = self._node_embed_single_conf(data_obj)
            atom_embeds.append(atom_latent.detach().cpu())
        if not atom_embeds:
            return torch.zeros((1, self.latent_dim), dtype=torch.float32), False
        conf_atom = torch.stack(atom_embeds, dim=0)
        atom_token = conf_atom.mean(dim=0)
        if atom_token.dim() != 2 or atom_token.shape[1] != self.latent_dim:
            return torch.zeros((1, self.latent_dim), dtype=torch.float32), False
        return atom_token.float(), True

    @torch.no_grad()
    def embed_smiles_conformer_atoms_with_xyz(
        self,
        smiles: str,
        seed: int,
        *,
        xyz_root: Optional[Path],
        row_tag: Optional[str],
    ) -> Tuple[torch.Tensor, bool]:
        atom_rows, coord_rows, ok = self._get_conformer_rows(smiles, seed=seed, xyz_root=xyz_root)
        if not ok:
            return torch.zeros((1, 1, self.latent_dim), dtype=torch.float32), False
        conf_atom_embeds: List[torch.Tensor] = []
        for atoms, coords in zip(atom_rows, coord_rows):
            data_obj = _atoms_coords_to_data(atoms, coords, self.cfg.atom_index_offset).to(self.device)
            atom_latent = self._node_embed_single_conf(data_obj).detach().cpu().float()
            if atom_latent.dim() != 2 or atom_latent.shape[1] != self.latent_dim or atom_latent.shape[0] <= 0:
                continue
            conf_atom_embeds.append(atom_latent)
        if not conf_atom_embeds:
            return torch.zeros((1, 1, self.latent_dim), dtype=torch.float32), False
        conf_tensor = torch.stack(conf_atom_embeds, dim=0).float()
        return conf_tensor, True

    def export_xyz_only(
        self,
        smiles: str,
        seed: int,
        *,
        xyz_root: Optional[Path],
        row_tag: Optional[str],
    ) -> bool:
        return bool(self._ensure_xyz_pool_for_smiles(smiles, seed=seed, xyz_root=xyz_root))

    def export_xyz_only_list(
        self,
        smiles: Sequence[str],
        *,
        seed: int,
        desc: str,
        xyz_root: Optional[Path],
    ) -> np.ndarray:
        return self.ensure_xyz_pool_for_smiles_list(
            smiles,
            seed=seed,
            desc=desc,
            xyz_root=xyz_root,
        )

    @torch.no_grad()
    def embed_smiles_list(
        self,
        smiles: Sequence[str],
        *,
        seed: int,
        desc: str,
        xyz_root: Optional[Path] = None,
    ) -> Tuple[torch.Tensor, np.ndarray]:
        all_vecs: List[torch.Tensor] = []
        valid = np.zeros(len(smiles), dtype=bool)
        for i, smi in enumerate(tqdm(smiles, desc=desc)):
            vec, ok = self.embed_smiles_with_xyz(
                str(smi),
                seed=seed + i,
                xyz_root=xyz_root,
                row_tag=f"row_{i:07d}",
            )
            all_vecs.append(vec)
            valid[i] = bool(ok)
        x = torch.stack(all_vecs, dim=0).float()
        return x, valid

    @torch.no_grad()
    def embed_smiles_atoms_list(
        self,
        smiles: Sequence[str],
        *,
        seed: int,
        desc: str,
        xyz_root: Optional[Path] = None,
    ) -> Tuple[List[torch.Tensor], np.ndarray]:
        atom_vecs: List[torch.Tensor] = []
        valid = np.zeros(len(smiles), dtype=bool)
        for i, smi in enumerate(tqdm(smiles, desc=desc)):
            vec, ok = self.embed_smiles_atoms_with_xyz(
                str(smi),
                seed=seed + i,
                xyz_root=xyz_root,
                row_tag=f"row_{i:07d}",
            )
            atom_vecs.append(vec.float())
            valid[i] = bool(ok)
        return atom_vecs, valid

    @torch.no_grad()
    def embed_smiles_conformer_atoms_list(
        self,
        smiles: Sequence[str],
        *,
        seed: int,
        desc: str,
        xyz_root: Optional[Path] = None,
    ) -> Tuple[List[torch.Tensor], np.ndarray]:
        conf_atom_vecs: List[torch.Tensor] = []
        valid = np.zeros(len(smiles), dtype=bool)
        for i, smi in enumerate(tqdm(smiles, desc=desc)):
            vec, ok = self.embed_smiles_conformer_atoms_with_xyz(
                str(smi),
                seed=seed + i,
                xyz_root=xyz_root,
                row_tag=f"row_{i:07d}",
            )
            conf_atom_vecs.append(vec.float())
            valid[i] = bool(ok)
        return conf_atom_vecs, valid


def _cache_payload_ok(payload: Dict, expected_smiles: Sequence[str], expected_dim: int) -> bool:
    if "embeddings" not in payload or "valid_mask" not in payload or "smiles" not in payload:
        return False
    x = payload["embeddings"]
    if not isinstance(x, torch.Tensor) or x.dim() != 2 or x.shape[1] != expected_dim:
        return False
    cached_smiles = list(payload["smiles"])
    return cached_smiles == list(expected_smiles)


def get_embeddings_with_cache(
    embedder: MFMConformerEmbedder,
    smiles: Sequence[str],
    *,
    cache_path: Optional[Path],
    seed: int,
    desc: str,
) -> Tuple[torch.Tensor, np.ndarray]:
    fp = _global_cache_fingerprint(embedder)
    requested_cache_path = cache_path
    cache_path = _cache_path_with_fingerprint(cache_path, fp)
    xyz_root = getattr(embedder, "shared_xyz_pool_root", None)
    for existing_cache_path in _existing_cache_candidates(requested_cache_path, fp):
        lock_path = _cache_lock_path(existing_cache_path)
        with _optional_file_lock(lock_path):
            if existing_cache_path.exists():
                payload = _safe_torch_load(existing_cache_path, map_location="cpu")
                payload_fp = payload.get("fingerprint", {}) if isinstance(payload, dict) else {}
                if payload_fp != fp:
                    continue
                if _cache_payload_ok(payload or {}, smiles, embedder.latent_dim):
                    if existing_cache_path != cache_path:
                        print(f"[cache] Reusing legacy embedding cache: {existing_cache_path}")
                    if xyz_root is not None:
                        required = max(1, int(getattr(embedder.cfg, "num_conformers", 1)))
                        missing_xyz = [str(smi) for smi in smiles if _smiles_xyz_count(str(smi), xyz_root) < required]
                        if missing_xyz:
                            embedder.ensure_xyz_pool_for_smiles_list(
                                missing_xyz,
                                seed=seed,
                                desc=f"{desc}-xyz-refill",
                                xyz_root=xyz_root,
                            )
                    valid_mask = np.asarray(payload["valid_mask"]).astype(bool)
                    return payload["embeddings"].float(), valid_mask

    x, valid = embedder.embed_smiles_list(smiles, seed=seed, desc=desc, xyz_root=xyz_root)
    if cache_path is not None:
        lock_path = _cache_lock_path(cache_path)
        with _optional_file_lock(lock_path):
            if cache_path.exists():
                payload = _safe_torch_load(cache_path, map_location="cpu")
                payload_fp = payload.get("fingerprint", {}) if isinstance(payload, dict) else {}
                if payload_fp == fp and _cache_payload_ok(payload or {}, smiles, embedder.latent_dim):
                    valid_mask = np.asarray(payload["valid_mask"]).astype(bool)
                    return payload["embeddings"].float(), valid_mask
            _atomic_torch_save(
                {
                    "embeddings": x,
                    "valid_mask": valid,
                    "smiles": list(smiles),
                    "fingerprint": fp,
                    "xyz_dir": None if xyz_root is None else str(xyz_root),
                },
                cache_path,
            )
    return x, valid


def _global_cache_fingerprint(embedder: "MFMConformerEmbedder") -> Dict:
    fp = {
        "embedder_impl_version": "mfm_descriptor_v2",
        "latent_dim": int(embedder.latent_dim),
        "num_conformers": int(embedder.cfg.num_conformers),
        "optimize_conformers": bool(embedder.cfg.optimize_conformers),
        "max_opt_iters": int(embedder.cfg.max_opt_iters),
        "add_hs": bool(embedder.cfg.add_hs),
        "embedding_mode": str(embedder.cfg.embedding_mode),
        "atom_index_offset": int(embedder.cfg.atom_index_offset),
        "xyz_pool_root": None if getattr(embedder.cfg, "xyz_pool_root", None) is None else str(embedder.cfg.xyz_pool_root),
    }
    checkpoint_fingerprint = getattr(embedder, "checkpoint_fingerprint", None)
    if checkpoint_fingerprint is not None:
        fp["checkpoint_fingerprint"] = checkpoint_fingerprint
    return fp


def _fingerprint_key(fp: Dict) -> str:
    raw = json.dumps(fp, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _cache_path_with_fingerprint(cache_path: Optional[Path], fp: Dict) -> Optional[Path]:
    if cache_path is None:
        return None
    key = _fingerprint_key(fp)
    return cache_path.with_name(f"{cache_path.stem}__{key}{cache_path.suffix}")


def _existing_cache_candidates(cache_path: Optional[Path], fp: Dict) -> List[Path]:
    if cache_path is None:
        return []
    candidates: List[Path] = []
    exact_fp_path = _cache_path_with_fingerprint(cache_path, fp)
    if exact_fp_path is not None:
        candidates.append(exact_fp_path)
    candidates.append(cache_path)
    try:
        legacy_matches = sorted(
            cache_path.parent.glob(f"{cache_path.stem}__*{cache_path.suffix}"),
            key=lambda p: p.stat().st_mtime_ns,
            reverse=True,
        )
    except Exception:
        legacy_matches = []
    for path in legacy_matches:
        if path not in candidates:
            candidates.append(path)
    return candidates


def get_embeddings_with_global_cache(
    embedder: "MFMConformerEmbedder",
    smiles: Sequence[str],
    *,
    cache_path: Optional[Path],
    seed: int,
    desc: str,
) -> Tuple[torch.Tensor, np.ndarray]:
    if cache_path is None:
        return get_embeddings_with_cache(
            embedder,
            smiles,
            cache_path=None,
            seed=seed,
            desc=desc,
        )

    fp = _global_cache_fingerprint(embedder)
    requested_cache_path = cache_path
    cache_path = _cache_path_with_fingerprint(cache_path, fp)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    xyz_root = getattr(embedder, "shared_xyz_pool_root", None)
    db: Dict[str, Dict] = {}
    loaded_cache_path: Optional[Path] = None
    for existing_cache_path in _existing_cache_candidates(requested_cache_path, fp):
        lock_path = _cache_lock_path(existing_cache_path)
        with _optional_file_lock(lock_path):
            if existing_cache_path.exists():
                payload = _safe_torch_load(existing_cache_path, map_location="cpu")
                if (
                    isinstance(payload, dict)
                    and payload.get("fingerprint", {}) == fp
                    and isinstance(payload.get("db"), dict)
                ):
                    db = payload["db"]
                    loaded_cache_path = existing_cache_path
                    break
    if loaded_cache_path is not None and loaded_cache_path != cache_path:
        print(f"[cache] Reusing legacy global embedding cache: {loaded_cache_path}")

    order = [str(s) for s in smiles]
    needed_unique = []
    seen = set()
    for smi in order:
        if smi not in db and smi not in seen:
            seen.add(smi)
            needed_unique.append(smi)

    if db and xyz_root is not None:
        required = max(1, int(getattr(embedder.cfg, "num_conformers", 1)))
        refill_unique = []
        seen_refill = set()
        for smi in order:
            if smi in db and smi not in seen_refill and _smiles_xyz_count(smi, xyz_root) < required:
                seen_refill.add(smi)
                refill_unique.append(smi)
        if refill_unique:
            embedder.ensure_xyz_pool_for_smiles_list(
                refill_unique,
                seed=seed,
                desc=f"{desc}-xyz-refill",
                xyz_root=xyz_root,
            )

    if needed_unique:
        new_x, new_valid = embedder.embed_smiles_list(
            needed_unique,
            seed=seed,
            desc=desc,
            xyz_root=xyz_root,
        )
        with _optional_file_lock(lock_path):
            latest_db: Dict[str, Dict] = {}
            if cache_path.exists():
                payload = _safe_torch_load(cache_path, map_location="cpu")
                if isinstance(payload, dict) and payload.get("fingerprint", {}) == fp and isinstance(payload.get("db"), dict):
                    latest_db = payload["db"]
            for i, smi in enumerate(needed_unique):
                latest_db[smi] = {
                    "embedding": new_x[i].cpu(),
                    "valid": bool(new_valid[i]),
                }
            _atomic_torch_save(
                {
                    "fingerprint": fp,
                    "db": latest_db,
                    "xyz_dir": None if xyz_root is None else str(xyz_root),
                },
                cache_path,
            )
            db = latest_db

    vecs: List[torch.Tensor] = []
    valid = np.zeros(len(order), dtype=bool)
    for i, smi in enumerate(order):
        item = db.get(smi)
        if item is None:
            vecs.append(torch.zeros(embedder.latent_dim, dtype=torch.float32))
            valid[i] = False
        else:
            vecs.append(item["embedding"].float())
            valid[i] = bool(item.get("valid", True))
    return torch.stack(vecs, dim=0).float(), valid


def _pad_atom_embeddings(
    atom_embeddings: Sequence[torch.Tensor],
    *,
    latent_dim: int,
) -> Tuple[torch.Tensor, np.ndarray]:
    n_rows = len(atom_embeddings)
    max_atoms = 1
    for emb in atom_embeddings:
        if isinstance(emb, torch.Tensor) and emb.dim() == 2 and emb.shape[1] == latent_dim and emb.shape[0] > 0:
            max_atoms = max(max_atoms, int(emb.shape[0]))
    x = torch.zeros((n_rows, max_atoms, latent_dim), dtype=torch.float32)
    atom_mask = np.zeros((n_rows, max_atoms), dtype=bool)
    for i, emb in enumerate(atom_embeddings):
        if not isinstance(emb, torch.Tensor) or emb.dim() != 2 or emb.shape[1] != latent_dim or emb.shape[0] <= 0:
            continue
        n_atoms = int(emb.shape[0])
        x[i, :n_atoms, :] = emb.float()
        atom_mask[i, :n_atoms] = True
    return x, atom_mask


def get_atom_embeddings_with_global_cache(
    embedder: "MFMConformerEmbedder",
    smiles: Sequence[str],
    *,
    cache_path: Optional[Path],
    seed: int,
    desc: str,
) -> Tuple[torch.Tensor, np.ndarray, np.ndarray]:
    if cache_path is None:
        atom_vecs, valid = embedder.embed_smiles_atoms_list(
            smiles,
            seed=seed,
            desc=desc,
            xyz_root=getattr(embedder, "shared_xyz_pool_root", None),
        )
        x_pad, atom_mask = _pad_atom_embeddings(atom_vecs, latent_dim=embedder.latent_dim)
        return x_pad, atom_mask, valid

    fp = _global_cache_fingerprint(embedder)
    requested_cache_path = cache_path
    cache_path = _cache_path_with_fingerprint(cache_path, fp)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    xyz_root = getattr(embedder, "shared_xyz_pool_root", None)
    db: Dict[str, Dict] = {}
    loaded_cache_path: Optional[Path] = None
    for existing_cache_path in _existing_cache_candidates(requested_cache_path, fp):
        lock_path = _cache_lock_path(existing_cache_path)
        with _optional_file_lock(lock_path):
            if existing_cache_path.exists():
                payload = _safe_torch_load(existing_cache_path, map_location="cpu")
                if (
                    isinstance(payload, dict)
                    and payload.get("fingerprint", {}) == fp
                    and isinstance(payload.get("db"), dict)
                ):
                    db = payload["db"]
                    loaded_cache_path = existing_cache_path
                    break
    if loaded_cache_path is not None and loaded_cache_path != cache_path:
        print(f"[cache] Reusing legacy atom embedding cache: {loaded_cache_path}")
    converted_from_conf = False
    if db:
        for smi, item in list(db.items()):
            if not isinstance(item, dict):
                continue
            atom_emb = item.get("atom_embedding")
            if isinstance(atom_emb, torch.Tensor):
                continue
            conf_emb = item.get("conf_atom_embedding")
            if (
                isinstance(conf_emb, torch.Tensor)
                and conf_emb.dim() == 3
                and conf_emb.shape[2] == embedder.latent_dim
                and conf_emb.shape[0] > 0
                and conf_emb.shape[1] > 0
            ):
                # Backward-compatible upgrade for old late caches that stored
                # [C, N, D] tensors as "conf_atom_embedding".
                item["atom_embedding"] = conf_emb.float().mean(dim=0).cpu()
                item["valid"] = bool(item.get("valid", True))
                db[smi] = item
                converted_from_conf = True

    order = [str(s) for s in smiles]
    needed_unique = []
    seen = set()
    for smi in order:
        item = db.get(smi)
        emb = item.get("atom_embedding") if isinstance(item, dict) else None
        emb_ok = (
            isinstance(emb, torch.Tensor)
            and emb.dim() == 2
            and emb.shape[1] == embedder.latent_dim
            and emb.shape[0] > 0
        )
        if (not emb_ok) and smi not in seen:
            seen.add(smi)
            needed_unique.append(smi)

    if db and xyz_root is not None:
        required = max(1, int(getattr(embedder.cfg, "num_conformers", 1)))
        refill_unique = []
        seen_refill = set()
        for smi in order:
            if smi in db and smi not in seen_refill and _smiles_xyz_count(smi, xyz_root) < required:
                seen_refill.add(smi)
                refill_unique.append(smi)
        if refill_unique:
            embedder.ensure_xyz_pool_for_smiles_list(
                refill_unique,
                seed=seed,
                desc=f"{desc}-xyz-refill",
                xyz_root=xyz_root,
            )

    if needed_unique:
        new_x, new_valid = embedder.embed_smiles_atoms_list(
            needed_unique,
            seed=seed,
            desc=desc,
            xyz_root=xyz_root,
        )
        with _optional_file_lock(lock_path):
            latest_db: Dict[str, Dict] = {}
            if cache_path.exists():
                payload = _safe_torch_load(cache_path, map_location="cpu")
                if isinstance(payload, dict) and payload.get("fingerprint", {}) == fp and isinstance(payload.get("db"), dict):
                    latest_db = payload["db"]
            for i, smi in enumerate(needed_unique):
                emb = new_x[i]
                ok = bool(new_valid[i])
                if not isinstance(emb, torch.Tensor) or emb.dim() != 2 or emb.shape[1] != embedder.latent_dim or emb.shape[0] <= 0:
                    emb = torch.zeros((1, embedder.latent_dim), dtype=torch.float32)
                    ok = False
                latest_db[smi] = {
                    "atom_embedding": emb.cpu().float(),
                    "valid": bool(ok),
                }
            if converted_from_conf:
                for smi, item in db.items():
                    if smi not in latest_db:
                        latest_db[smi] = item
            _atomic_torch_save(
                {
                    "fingerprint": fp,
                    "db": latest_db,
                    "xyz_dir": None if xyz_root is None else str(xyz_root),
                },
                cache_path,
            )
            db = latest_db
    elif converted_from_conf:
        with _optional_file_lock(lock_path):
            latest_db = dict(db)
            _atomic_torch_save(
                {
                    "fingerprint": fp,
                    "db": latest_db,
                    "xyz_dir": None if xyz_root is None else str(xyz_root),
                },
                cache_path,
            )
            db = latest_db

    atom_vecs: List[torch.Tensor] = []
    valid = np.zeros(len(order), dtype=bool)
    for i, smi in enumerate(order):
        item = db.get(smi)
        if item is None:
            atom_vecs.append(torch.zeros((1, embedder.latent_dim), dtype=torch.float32))
            valid[i] = False
            continue
        emb = item.get("atom_embedding")
        if not isinstance(emb, torch.Tensor) or emb.dim() != 2 or emb.shape[1] != embedder.latent_dim or emb.shape[0] <= 0:
            atom_vecs.append(torch.zeros((1, embedder.latent_dim), dtype=torch.float32))
            valid[i] = False
            continue
        atom_vecs.append(emb.float())
        valid[i] = bool(item.get("valid", True))
    x_pad, atom_mask = _pad_atom_embeddings(atom_vecs, latent_dim=embedder.latent_dim)
    return x_pad, atom_mask, valid


def _pad_conformer_atom_embeddings(
    conf_atom_embeddings: Sequence[torch.Tensor],
    *,
    latent_dim: int,
) -> Tuple[torch.Tensor, np.ndarray, np.ndarray]:
    n_rows = len(conf_atom_embeddings)
    max_conf = 1
    max_atoms = 1
    for emb in conf_atom_embeddings:
        if not isinstance(emb, torch.Tensor) or emb.dim() != 3 or emb.shape[2] != latent_dim:
            continue
        if emb.shape[0] <= 0 or emb.shape[1] <= 0:
            continue
        max_conf = max(max_conf, int(emb.shape[0]))
        max_atoms = max(max_atoms, int(emb.shape[1]))

    x = torch.zeros((n_rows, max_conf, max_atoms, latent_dim), dtype=torch.float32)
    atom_mask = np.zeros((n_rows, max_conf, max_atoms), dtype=bool)
    conf_mask = np.zeros((n_rows, max_conf), dtype=bool)
    for i, emb in enumerate(conf_atom_embeddings):
        if not isinstance(emb, torch.Tensor) or emb.dim() != 3 or emb.shape[2] != latent_dim:
            conf_mask[i, 0] = True
            continue
        n_conf = int(emb.shape[0])
        n_atoms = int(emb.shape[1])
        if n_conf <= 0 or n_atoms <= 0:
            conf_mask[i, 0] = True
            continue
        x[i, :n_conf, :n_atoms, :] = emb.float()
        atom_mask[i, :n_conf, :n_atoms] = True
        conf_mask[i, :n_conf] = True
    return x, atom_mask, conf_mask


def get_conformer_atom_embeddings_with_global_cache(
    embedder: "MFMConformerEmbedder",
    smiles: Sequence[str],
    *,
    cache_path: Optional[Path],
    seed: int,
    desc: str,
) -> Tuple[torch.Tensor, np.ndarray, np.ndarray, np.ndarray]:
    if cache_path is None:
        conf_atom_vecs, valid = embedder.embed_smiles_conformer_atoms_list(
            smiles,
            seed=seed,
            desc=desc,
            xyz_root=getattr(embedder, "shared_xyz_pool_root", None),
        )
        x_pad, atom_mask, conf_mask = _pad_conformer_atom_embeddings(conf_atom_vecs, latent_dim=embedder.latent_dim)
        return x_pad, atom_mask, conf_mask, valid

    fp = _global_cache_fingerprint(embedder)
    requested_cache_path = cache_path
    cache_path = _cache_path_with_fingerprint(cache_path, fp)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    xyz_root = getattr(embedder, "shared_xyz_pool_root", None)
    db: Dict[str, Dict] = {}
    loaded_cache_path: Optional[Path] = None
    for existing_cache_path in _existing_cache_candidates(requested_cache_path, fp):
        lock_path = _cache_lock_path(existing_cache_path)
        with _optional_file_lock(lock_path):
            if existing_cache_path.exists():
                payload = _safe_torch_load(existing_cache_path, map_location="cpu")
                if (
                    isinstance(payload, dict)
                    and payload.get("fingerprint", {}) == fp
                    and isinstance(payload.get("db"), dict)
                ):
                    db = payload["db"]
                    loaded_cache_path = existing_cache_path
                    break
    if loaded_cache_path is not None and loaded_cache_path != cache_path:
        print(f"[cache] Reusing legacy conformer atom embedding cache: {loaded_cache_path}")

    order = [str(s) for s in smiles]
    needed_unique = []
    seen = set()
    for smi in order:
        if smi not in db and smi not in seen:
            seen.add(smi)
            needed_unique.append(smi)

    if db and xyz_root is not None:
        required = max(1, int(getattr(embedder.cfg, "num_conformers", 1)))
        refill_unique = []
        seen_refill = set()
        for smi in order:
            if smi in db and smi not in seen_refill and _smiles_xyz_count(smi, xyz_root) < required:
                seen_refill.add(smi)
                refill_unique.append(smi)
        if refill_unique:
            embedder.ensure_xyz_pool_for_smiles_list(
                refill_unique,
                seed=seed,
                desc=f"{desc}-xyz-refill",
                xyz_root=xyz_root,
            )

    if needed_unique:
        new_x, new_valid = embedder.embed_smiles_conformer_atoms_list(
            needed_unique,
            seed=seed,
            desc=desc,
            xyz_root=xyz_root,
        )
        with _optional_file_lock(lock_path):
            latest_db: Dict[str, Dict] = {}
            if cache_path.exists():
                payload = _safe_torch_load(cache_path, map_location="cpu")
                if isinstance(payload, dict) and payload.get("fingerprint", {}) == fp and isinstance(payload.get("db"), dict):
                    latest_db = payload["db"]
            for i, smi in enumerate(needed_unique):
                emb = new_x[i]
                ok = bool(new_valid[i])
                if not isinstance(emb, torch.Tensor) or emb.dim() != 3 or emb.shape[2] != embedder.latent_dim:
                    emb = torch.zeros((1, 1, embedder.latent_dim), dtype=torch.float32)
                    ok = False
                elif emb.shape[0] <= 0 or emb.shape[1] <= 0:
                    emb = torch.zeros((1, 1, embedder.latent_dim), dtype=torch.float32)
                    ok = False
                latest_db[smi] = {
                    "conf_atom_embedding": emb.cpu().float(),
                    "valid": bool(ok),
                }
            _atomic_torch_save(
                {
                    "fingerprint": fp,
                    "db": latest_db,
                    "xyz_dir": None if xyz_root is None else str(xyz_root),
                },
                cache_path,
            )
            db = latest_db

    conf_atom_vecs: List[torch.Tensor] = []
    valid = np.zeros(len(order), dtype=bool)
    for i, smi in enumerate(order):
        item = db.get(smi)
        if item is None:
            conf_atom_vecs.append(torch.zeros((1, 1, embedder.latent_dim), dtype=torch.float32))
            valid[i] = False
            continue
        emb = item.get("conf_atom_embedding")
        if not isinstance(emb, torch.Tensor) or emb.dim() != 3 or emb.shape[2] != embedder.latent_dim:
            conf_atom_vecs.append(torch.zeros((1, 1, embedder.latent_dim), dtype=torch.float32))
            valid[i] = False
            continue
        if emb.shape[0] <= 0 or emb.shape[1] <= 0:
            conf_atom_vecs.append(torch.zeros((1, 1, embedder.latent_dim), dtype=torch.float32))
            valid[i] = False
            continue
        conf_atom_vecs.append(emb.float())
        valid[i] = bool(item.get("valid", True))
    x_pad, atom_mask, conf_mask = _pad_conformer_atom_embeddings(conf_atom_vecs, latent_dim=embedder.latent_dim)
    return x_pad, atom_mask, conf_mask, valid


class LabelScaler:
    def __init__(self, mean: np.ndarray, std: np.ndarray):
        self.mean = mean.astype(np.float32)
        self.std = std.astype(np.float32)

    @classmethod
    def fit(cls, y: np.ndarray) -> "LabelScaler":
        mean = np.nanmean(y, axis=0)
        std = np.nanstd(y, axis=0)
        mean[~np.isfinite(mean)] = 0.0
        std[~np.isfinite(std)] = 1.0
        std[std < 1e-8] = 1.0
        return cls(mean=mean, std=std)

    def transform(self, y: np.ndarray) -> np.ndarray:
        return (y - self.mean[None, :]) / self.std[None, :]

    def inverse(self, y_scaled: np.ndarray) -> np.ndarray:
        return y_scaled * self.std[None, :] + self.mean[None, :]

    def to_dict(self) -> Dict:
        return {"mean": self.mean.tolist(), "std": self.std.tolist()}

    @classmethod
    def from_dict(cls, payload: Dict) -> "LabelScaler":
        return cls(
            mean=np.asarray(payload["mean"], dtype=np.float32),
            std=np.asarray(payload["std"], dtype=np.float32),
        )


class EmbeddingTransform:
    def __init__(
        self,
        mean: np.ndarray,
        std: np.ndarray,
        *,
        components: Optional[np.ndarray] = None,
        standardize: bool = True,
        eps: float = 1e-6,
        fit_count: int = 0,
        pca_dim_arg: int = 0,
    ):
        self.mean = np.asarray(mean, dtype=np.float32).reshape(-1)
        self.std = np.asarray(std, dtype=np.float32).reshape(-1)
        if self.mean.shape != self.std.shape:
            raise ValueError("mean/std shape mismatch in EmbeddingTransform.")
        self.standardize = bool(standardize)
        self.eps = float(eps)
        self.fit_count = int(fit_count)
        self.pca_dim_arg = int(pca_dim_arg)
        if components is None:
            self.components = None
        else:
            comp = np.asarray(components, dtype=np.float32)
            if comp.ndim != 2 or comp.shape[0] != self.mean.shape[0]:
                raise ValueError("components must be [input_dim, output_dim] and match mean/std dimension.")
            self.components = comp

    @property
    def input_dim(self) -> int:
        return int(self.mean.shape[0])

    @property
    def output_dim(self) -> int:
        if self.components is None:
            return int(self.input_dim)
        return int(self.components.shape[1])

    @property
    def pca_applied(self) -> bool:
        return self.components is not None

    @classmethod
    def fit(
        cls,
        x_fit: np.ndarray,
        *,
        standardize: bool = True,
        pca_dim: int = 0,
        eps: float = 1e-6,
    ) -> "EmbeddingTransform":
        x = np.asarray(x_fit, dtype=np.float32)
        if x.ndim != 2:
            raise ValueError(f"x_fit must be [N, D], got shape={tuple(x.shape)}")
        if x.shape[0] <= 0 or x.shape[1] <= 0:
            raise ValueError(f"x_fit must be non-empty [N, D], got shape={tuple(x.shape)}")

        d = int(x.shape[1])
        pca_dim_arg = int(pca_dim)
        eps_v = float(max(eps, 1e-12))
        do_standardize = bool(standardize)

        if do_standardize:
            mean = x.mean(axis=0).astype(np.float32)
            std = x.std(axis=0).astype(np.float32)
            mean[~np.isfinite(mean)] = 0.0
            std[~np.isfinite(std)] = 1.0
            std[std < eps_v] = 1.0
            x_for_pca = (x - mean[None, :]) / std[None, :]
        else:
            mean = np.zeros((d,), dtype=np.float32)
            std = np.ones((d,), dtype=np.float32)
            x_for_pca = x

        components = None
        if pca_dim_arg > 0:
            k = min(int(pca_dim_arg), int(d), int(x_for_pca.shape[0]))
            if k >= 1 and k < d:
                _, _, vt = np.linalg.svd(x_for_pca, full_matrices=False)
                components = vt[:k, :].T.astype(np.float32)

        return cls(
            mean=mean,
            std=std,
            components=components,
            standardize=do_standardize,
            eps=eps_v,
            fit_count=int(x.shape[0]),
            pca_dim_arg=pca_dim_arg,
        )

    def transform_np(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=np.float32)
        if arr.shape[-1] != self.input_dim:
            raise ValueError(
                f"Last dim mismatch in transform_np: expected {self.input_dim}, got {arr.shape[-1]}"
            )
        out = arr
        if self.standardize:
            out = (out - self.mean.reshape(*([1] * (out.ndim - 1)), -1)) / self.std.reshape(
                *([1] * (out.ndim - 1)),
                -1,
            )
        if self.components is not None:
            flat = out.reshape(-1, self.input_dim)
            flat = flat @ self.components
            out = flat.reshape(*arr.shape[:-1], self.output_dim)
        return out.astype(np.float32, copy=False)

    def transform_torch(self, x: torch.Tensor) -> torch.Tensor:
        if int(x.shape[-1]) != self.input_dim:
            raise ValueError(
                f"Last dim mismatch in transform_torch: expected {self.input_dim}, got {int(x.shape[-1])}"
            )
        out = x
        if self.standardize:
            mean_t = torch.as_tensor(self.mean, dtype=out.dtype, device=out.device).view(
                *([1] * (out.dim() - 1)),
                -1,
            )
            std_t = torch.as_tensor(self.std, dtype=out.dtype, device=out.device).view(
                *([1] * (out.dim() - 1)),
                -1,
            )
            out = (out - mean_t) / std_t
        if self.components is not None:
            comp_t = torch.as_tensor(self.components, dtype=out.dtype, device=out.device)
            out = torch.matmul(out, comp_t)
        return out

    def to_dict(self) -> Dict:
        return {
            "standardize": bool(self.standardize),
            "eps": float(self.eps),
            "fit_count": int(self.fit_count),
            "pca_dim_arg": int(self.pca_dim_arg),
            "input_dim": int(self.input_dim),
            "output_dim": int(self.output_dim),
            "mean": torch.from_numpy(self.mean).float(),
            "std": torch.from_numpy(self.std).float(),
            "components": None if self.components is None else torch.from_numpy(self.components).float(),
        }

    @classmethod
    def from_dict(cls, payload: Optional[Dict]) -> Optional["EmbeddingTransform"]:
        if not isinstance(payload, dict):
            return None
        if "mean" not in payload or "std" not in payload:
            return None
        mean = payload["mean"]
        std = payload["std"]
        if isinstance(mean, torch.Tensor):
            mean = mean.detach().cpu().numpy()
        if isinstance(std, torch.Tensor):
            std = std.detach().cpu().numpy()
        components = payload.get("components")
        if isinstance(components, torch.Tensor):
            components = components.detach().cpu().numpy()
        if components is not None:
            components = np.asarray(components, dtype=np.float32)
        return cls(
            mean=np.asarray(mean, dtype=np.float32),
            std=np.asarray(std, dtype=np.float32),
            components=components,
            standardize=bool(payload.get("standardize", True)),
            eps=float(payload.get("eps", 1e-6)),
            fit_count=int(payload.get("fit_count", 0)),
            pca_dim_arg=int(payload.get("pca_dim_arg", 0)),
        )


class RegressionHead(nn.Module):
    def __init__(
        self,
        in_dim: int,
        out_dim: int,
        hidden_dim: int,
        n_layers: int,
        dropout: float,
    ):
        super().__init__()
        if n_layers < 1:
            raise ValueError("n_layers must be >= 1")
        layers: List[nn.Module] = []
        if n_layers == 1:
            layers.append(nn.Linear(in_dim, out_dim))
        else:
            layers.append(nn.Linear(in_dim, hidden_dim))
            layers.append(nn.ReLU())
            if dropout > 0:
                layers.append(nn.Dropout(dropout))
            for _ in range(n_layers - 2):
                layers.append(nn.Linear(hidden_dim, hidden_dim))
                layers.append(nn.ReLU())
                if dropout > 0:
                    layers.append(nn.Dropout(dropout))
            layers.append(nn.Linear(hidden_dim, out_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class AtomwiseLatePoolRegressionHead(nn.Module):
    def __init__(
        self,
        in_dim: int,
        out_dim: int,
        hidden_dim: int,
        atom_layers: int,
        readout_layers: int,
        dropout: float,
    ):
        super().__init__()
        if atom_layers < 1:
            raise ValueError("atom_layers must be >= 1")
        atom_net: List[nn.Module] = []
        cur_dim = int(in_dim)
        for _ in range(int(atom_layers)):
            atom_net.append(nn.Linear(cur_dim, int(hidden_dim)))
            atom_net.append(nn.ReLU())
            if dropout > 0:
                atom_net.append(nn.Dropout(float(dropout)))
            cur_dim = int(hidden_dim)
        self.atom_net = nn.Sequential(*atom_net)
        pooled_dim = int(hidden_dim) * 3 + 1
        self.readout = RegressionHead(
            in_dim=pooled_dim,
            out_dim=int(out_dim),
            hidden_dim=int(hidden_dim),
            n_layers=int(readout_layers),
            dropout=float(dropout),
        )

    def forward(self, x_atoms: torch.Tensor, atom_mask: torch.Tensor) -> torch.Tensor:
        if x_atoms.dim() != 3:
            raise ValueError(f"x_atoms must be [B, N, D], got shape={tuple(x_atoms.shape)}")
        if atom_mask.dim() != 2:
            raise ValueError(f"atom_mask must be [B, N], got shape={tuple(atom_mask.shape)}")
        z = self.atom_net(x_atoms)
        mask_bool = atom_mask.bool()
        mask_f = mask_bool.unsqueeze(-1).float()
        denom = mask_f.sum(dim=1).clamp_min(1.0)

        mean = (z * mask_f).sum(dim=1) / denom
        neg_inf = torch.finfo(z.dtype).min
        z_for_max = z.masked_fill(~mask_bool.unsqueeze(-1), neg_inf)
        max_v = z_for_max.max(dim=1).values
        max_v = torch.where(torch.isfinite(max_v), max_v, torch.zeros_like(max_v))

        centered = z - mean.unsqueeze(1)
        var = ((centered * centered) * mask_f).sum(dim=1) / denom
        std = torch.sqrt(var.clamp_min(1e-12))
        log_n = torch.log(denom).to(z.dtype)

        pooled = torch.cat([mean, max_v, std, log_n], dim=1)
        return self.readout(pooled)


class ConformerAttentionLatePoolRegressionHead(nn.Module):
    def __init__(
        self,
        in_dim: int,
        out_dim: int,
        hidden_dim: int,
        atom_layers: int,
        readout_layers: int,
        dropout: float,
    ):
        super().__init__()
        if atom_layers < 1:
            raise ValueError("atom_layers must be >= 1")
        atom_net: List[nn.Module] = []
        cur_dim = int(in_dim)
        for _ in range(int(atom_layers)):
            atom_net.append(nn.Linear(cur_dim, int(hidden_dim)))
            atom_net.append(nn.ReLU())
            if dropout > 0:
                atom_net.append(nn.Dropout(float(dropout)))
            cur_dim = int(hidden_dim)
        self.atom_net = nn.Sequential(*atom_net)
        pooled_dim = int(hidden_dim) * 3 + 1
        self.conf_score = nn.Linear(pooled_dim, 1)
        self.readout = RegressionHead(
            in_dim=pooled_dim,
            out_dim=int(out_dim),
            hidden_dim=int(hidden_dim),
            n_layers=int(readout_layers),
            dropout=float(dropout),
        )

    def forward(
        self,
        x_conf_atoms: torch.Tensor,
        atom_mask: torch.Tensor,
        conf_mask: torch.Tensor,
    ) -> torch.Tensor:
        if x_conf_atoms.dim() != 4:
            raise ValueError(f"x_conf_atoms must be [B, C, N, D], got shape={tuple(x_conf_atoms.shape)}")
        if atom_mask.dim() != 3:
            raise ValueError(f"atom_mask must be [B, C, N], got shape={tuple(atom_mask.shape)}")
        if conf_mask.dim() != 2:
            raise ValueError(f"conf_mask must be [B, C], got shape={tuple(conf_mask.shape)}")

        z = self.atom_net(x_conf_atoms)
        atom_mask_bool = atom_mask.bool()
        atom_mask_f = atom_mask_bool.unsqueeze(-1).float()
        atom_denom = atom_mask_f.sum(dim=2).clamp_min(1.0)

        mean = (z * atom_mask_f).sum(dim=2) / atom_denom
        neg_inf = torch.finfo(z.dtype).min
        z_for_max = z.masked_fill(~atom_mask_bool.unsqueeze(-1), neg_inf)
        max_v = z_for_max.max(dim=2).values
        max_v = torch.where(torch.isfinite(max_v), max_v, torch.zeros_like(max_v))

        centered = z - mean.unsqueeze(2)
        var = ((centered * centered) * atom_mask_f).sum(dim=2) / atom_denom
        std = torch.sqrt(var.clamp_min(1e-12))
        log_n = torch.log(atom_denom).to(z.dtype)
        conf_vec = torch.cat([mean, max_v, std, log_n], dim=2)

        conf_mask_bool = conf_mask.bool()
        logits = self.conf_score(conf_vec).squeeze(-1)
        logits = logits.masked_fill(~conf_mask_bool, -1e9)
        attn = torch.softmax(logits, dim=1)
        attn = attn * conf_mask_bool.float()
        attn = attn / attn.sum(dim=1, keepdim=True).clamp_min(1e-8)

        mol_vec = (attn.unsqueeze(-1) * conf_vec).sum(dim=1)
        return self.readout(mol_vec)


def masked_weighted_mse(
    pred: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    task_weights: Optional[torch.Tensor],
) -> torch.Tensor:
    diff = torch.where(mask, pred - target, torch.zeros_like(pred))
    sq = diff * diff
    valid = mask.float()
    if task_weights is not None:
        valid = valid * task_weights[None, :]
    denom = valid.sum().clamp_min(1.0)
    return (sq * valid).sum() / denom


def build_feature_loader(
    x: np.ndarray | torch.Tensor,
    y_scaled: np.ndarray | torch.Tensor,
    y_mask: np.ndarray | torch.Tensor,
    batch_size: int,
    shuffle: bool,
    *,
    num_workers: int = 0,
    pin_memory: bool = False,
) -> DataLoader:
    ds = TensorDataset(
        torch.as_tensor(x).float(),
        torch.as_tensor(y_scaled).float(),
        torch.as_tensor(y_mask).bool(),
    )
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        drop_last=False,
        num_workers=int(num_workers),
        pin_memory=bool(pin_memory),
    )


def build_atom_feature_loader(
    x_atoms: torch.Tensor,
    atom_mask: np.ndarray | torch.Tensor,
    y_scaled: np.ndarray | torch.Tensor,
    y_mask: np.ndarray | torch.Tensor,
    batch_size: int,
    shuffle: bool,
    *,
    num_workers: int = 0,
    pin_memory: bool = False,
) -> DataLoader:
    ds = TensorDataset(
        torch.as_tensor(x_atoms).float(),
        torch.as_tensor(atom_mask).bool(),
        torch.as_tensor(y_scaled).float(),
        torch.as_tensor(y_mask).bool(),
    )
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        drop_last=False,
        num_workers=int(num_workers),
        pin_memory=bool(pin_memory),
    )


def build_conformer_atom_feature_loader(
    x_conf_atoms: torch.Tensor,
    atom_mask: np.ndarray | torch.Tensor,
    conf_mask: np.ndarray | torch.Tensor,
    y_scaled: np.ndarray | torch.Tensor,
    y_mask: np.ndarray | torch.Tensor,
    batch_size: int,
    shuffle: bool,
    *,
    num_workers: int = 0,
    pin_memory: bool = False,
) -> DataLoader:
    ds = TensorDataset(
        torch.as_tensor(x_conf_atoms).float(),
        torch.as_tensor(atom_mask).bool(),
        torch.as_tensor(conf_mask).bool(),
        torch.as_tensor(y_scaled).float(),
        torch.as_tensor(y_mask).bool(),
    )
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        drop_last=False,
        num_workers=int(num_workers),
        pin_memory=bool(pin_memory),
    )


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    *,
    device: torch.device,
    optimizer: Optional[torch.optim.Optimizer],
    task_weights: Optional[torch.Tensor],
    lr_scheduler: Optional[object] = None,
    non_blocking: bool = False,
) -> float:
    is_train = optimizer is not None
    model.train(is_train)
    total_loss = 0.0
    n_batches = 0
    for batch in loader:
        conf_mask_b = None
        if len(batch) == 3:
            xb, yb, mb = batch
            atom_mask_b = None
        elif len(batch) == 4:
            xb, atom_mask_b, yb, mb = batch
        elif len(batch) == 5:
            xb, atom_mask_b, conf_mask_b, yb, mb = batch
        else:
            raise ValueError(f"Unexpected batch size for run_epoch: {len(batch)}")
        xb = xb.to(device, non_blocking=non_blocking)
        yb = yb.to(device, non_blocking=non_blocking)
        mb = mb.to(device, non_blocking=non_blocking)
        if atom_mask_b is not None:
            atom_mask_b = atom_mask_b.to(device, non_blocking=non_blocking)
        if conf_mask_b is not None:
            conf_mask_b = conf_mask_b.to(device, non_blocking=non_blocking)
        if is_train:
            optimizer.zero_grad(set_to_none=True)
        if atom_mask_b is None and conf_mask_b is None:
            pred = model(xb)
        elif conf_mask_b is None:
            pred = model(xb, atom_mask_b)
        else:
            pred = model(xb, atom_mask_b, conf_mask_b)
        loss = masked_weighted_mse(pred, yb, mb, task_weights)
        if is_train:
            loss.backward()
            optimizer.step()
            if lr_scheduler is not None:
                lr_scheduler.step()
        total_loss += float(loss.item())
        n_batches += 1
    return total_loss / max(1, n_batches)


def select_best_checkpoint(model_dir: Path) -> Path:
    best_pt = model_dir / "best.pt"
    if best_pt.exists():
        return best_pt
    candidates = sorted(model_dir.glob("best-*.pt"))
    if not candidates:
        raise FileNotFoundError(f"No best checkpoint found in: {model_dir}")
    return candidates[0]


def compute_metrics_table(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    targets: Sequence[str],
) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for i, name in enumerate(targets):
        mask = np.isfinite(y_true[:, i])
        if mask.sum() < 2:
            out[name] = {"mae": float("nan"), "rmse": float("nan"), "r2": float("nan")}
            continue
        yt = y_true[mask, i]
        yp = y_pred[mask, i]
        try:
            r2_value = float(r2(yt, yp))
        except Exception:
            r2_value = float("nan")
        out[name] = {
            "mae": float(mae(yt, yp)),
            "rmse": float(rmse(yt, yp)),
            "r2": r2_value,
        }
    return out


def print_metrics(metrics: Dict[str, Dict[str, float]]) -> None:
    for task, vals in metrics.items():
        print(task)
        print(f"  MAE:  {vals['mae']}")
        print(f"  RMSE: {vals['rmse']}")
        print(f"  R2:   {vals['r2']}")


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, payload: Dict) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def parse_targets_from_args(mode: str, target: Optional[str], targets: Optional[List[str]]) -> List[str]:
    if mode == "st":
        if not target:
            raise ValueError("Single-task mode requires --target.")
        return [target]
    if targets:
        return targets
    return list(DEFAULT_TARGETS)


def add_shared_parser_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data_dir", type=str, default="data")
    parser.add_argument("--folds", type=str, default="1-10")
    parser.add_argument("--mode", type=str, choices=["st", "mt"], default="mt")
    parser.add_argument("--target", type=str, default=None)
    parser.add_argument("--targets", nargs="+", default=None)
    parser.add_argument("--pretrained_ckpt", type=str, default=None)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num_conformers", type=int, default=8)
    parser.add_argument("--optimize_conformers", dest="optimize_conformers", action="store_true")
    parser.add_argument("--no_optimize_conformers", dest="optimize_conformers", action="store_false")
    parser.add_argument("--max_opt_iters", type=int, default=200)
    parser.add_argument("--add_hs", dest="add_hs", action="store_true")
    parser.add_argument("--no_add_hs", dest="add_hs", action="store_false")
    parser.add_argument("--embedding_mode", type=str, choices=EMBEDDING_MODE_CHOICES, default="backbone")
    parser.add_argument("--pooling_timing", type=str, choices=POOLING_TIMING_CHOICES, default="early")
    parser.add_argument("--atom_index_offset", type=int, default=-1)
    parser.add_argument("--cache_dir", type=str, default=None)
    parser.add_argument("--xyz_pool_root", type=str, default=None)
    parser.set_defaults(optimize_conformers=True, add_hs=True)
