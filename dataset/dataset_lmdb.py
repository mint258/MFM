# dataset_lmdb.py
# Read-only LMDB dataset with compatibility normalization.

import logging
import pickle

import lmdb
import torch
from torch_geometric.data import Dataset

from dataset.descriptor_schema import RDKIT_GRAPH_DESC_DIM


LOGGER = logging.getLogger(__name__)

RDKIT_NODE_LONG_FIELDS = (
    "rdkit_node_formal_charge",
    "rdkit_node_hybridization",
    "rdkit_node_min_ring_size",
    "rdkit_node_total_degree",
    "rdkit_node_total_num_Hs",
    "rdkit_node_total_valence",
    "rdkit_node_estate_type",
    "rdkit_node_chiral_tag",
    "rdkit_node_cip_code",
)
RDKIT_NODE_FLOAT_FIELDS = ("rdkit_node_estate_index",)
RDKIT_NODE_BOOL_FIELDS = (
    "rdkit_node_is_aromatic",
    "rdkit_node_is_in_ring",
    "rdkit_node_donor",
    "rdkit_node_acceptor",
    "rdkit_node_mask",
)


class LmdbMoleculeDataset(Dataset):
    def __init__(
        self,
        lmdb_path,
        start_idx=None,
        end_idx=None,
        limit=None,
        transform=None,
        pre_transform=None,
        filter_missing_on_init: bool = False,
        normalize_samples: bool = True,
    ):
        super().__init__(None, transform, pre_transform)
        self.lmdb_path = lmdb_path
        self.normalize_samples = normalize_samples
        self.env = lmdb.open(
            lmdb_path,
            subdir=False,
            readonly=True,
            lock=False,
            readahead=True,
        )

        with self.env.begin() as txn:
            raw_len = txn.get(b"__len__")
            if raw_len is None:
                raise KeyError(
                    f"LMDB shard '{lmdb_path}' is missing '__len__'. "
                    "The file may be corrupted or produced by an unexpected writer."
                )
            self._len = pickle.loads(raw_len)
            self._key_fmt = self._detect_key_fmt(txn)

        self.start = int(start_idx) if start_idx is not None else 0
        if self.start < 0:
            self.start = 0
        raw_end = int(end_idx) if end_idx is not None else (self._len - 1)
        self.end = min(raw_end, self._len - 1) if self._len > 0 else -1

        if self._len <= 0 or self.end < self.start:
            self.idx_list = []
            LOGGER.warning(
                "LMDB %s: empty index range (len=%s, start=%s, end=%s)",
                lmdb_path,
                self._len,
                self.start,
                self.end,
            )
            return

        self.idx_list = list(range(self.start, self.end + 1))
        if limit:
            self.idx_list = self.idx_list[: int(limit)]

        if filter_missing_on_init:
            valid = []
            with self.env.begin() as txn:
                for real in range(self.start, self.end + 1):
                    if txn.get(self._format_key(real)) is not None:
                        valid.append(real)
            self.idx_list = valid

        if limit:
            self.idx_list = self.idx_list[: int(limit)]

        if filter_missing_on_init and len(self.idx_list) == 0:
            LOGGER.warning(
                "LMDB %s: 0 valid samples after filtering (key_fmt=%s). "
                "Possible causes: corrupted LMDB, wrong key formatting, or start/end out of range.",
                lmdb_path,
                self._key_fmt,
            )

    def _format_key(self, real: int) -> bytes:
        if self._key_fmt == "raw":
            return str(real).encode()
        return f"{real:{self._key_fmt}}".encode()

    def _detect_key_fmt(self, txn) -> str:
        candidates = ["09d", "08d", "010d", "raw"]
        probes = {0, 1, 2}
        if isinstance(getattr(self, "_len", None), int) and self._len > 0:
            probes.add(self._len - 1)
        probes = [
            p
            for p in probes
            if isinstance(p, int) and p >= 0 and (self._len is None or p < self._len)
        ]

        best_fmt, best_hits = "09d", -1
        for fmt in candidates:
            hits = 0
            for i in probes:
                key = str(i).encode() if fmt == "raw" else f"{i:{fmt}}".encode()
                if txn.get(key) is not None:
                    hits += 1
            if hits > best_hits:
                best_hits, best_fmt = hits, fmt

        if best_hits <= 0:
            LOGGER.warning(
                "LMDB %s: could not detect key format from probes=%s; fallback to 09d. "
                "If this shard uses a different key format, it may appear empty.",
                self.lmdb_path,
                probes,
            )
            best_fmt = "09d"
        return best_fmt

    def _normalize_item(self, item, real_idx: int):
        if not self.normalize_samples:
            return item

        sample_key = getattr(item, "sample_key", None)
        if not isinstance(sample_key, str) or not sample_key:
            item.sample_key = self._format_key(real_idx).decode("utf-8", errors="ignore")

        smiles = getattr(item, "smiles", None)
        if not isinstance(smiles, str):
            item.smiles = ""

        energy_unit = getattr(item, "energy_unit", None)
        if not isinstance(energy_unit, str) or not energy_unit:
            item.energy_unit = "unknown"

        energy = getattr(item, "energy", None)
        if isinstance(energy, torch.Tensor) and energy.numel() == 1:
            item.energy = float(energy.item())

        pos = getattr(item, "pos", None)
        n_atom = int(pos.size(0)) if isinstance(pos, torch.Tensor) else 0

        y = getattr(item, "y", None)
        if y is None and n_atom > 0:
            item.y = torch.zeros((n_atom, 1), dtype=torch.float)
            y = item.y
        elif isinstance(y, torch.Tensor) and y.dtype != torch.float:
            item.y = y.float()
            y = item.y

        charge_mask = getattr(item, "charge_mask", None)
        if charge_mask is None and n_atom > 0:
            if isinstance(y, torch.Tensor) and y.shape[0] == n_atom:
                item.charge_mask = torch.ones((n_atom, 1), dtype=torch.float)
            else:
                item.charge_mask = torch.zeros((n_atom, 1), dtype=torch.float)
        elif isinstance(charge_mask, torch.Tensor) and charge_mask.dtype != torch.float:
            item.charge_mask = charge_mask.float()

        rdkit_status = getattr(item, "rdkit_status", None)
        if not isinstance(rdkit_status, str) or not rdkit_status:
            item.rdkit_status = "missing"

        rdkit_fail_reason = getattr(item, "rdkit_fail_reason", None)
        if not isinstance(rdkit_fail_reason, str):
            item.rdkit_fail_reason = ""

        for name in (
            "canonical_smiles",
            "isomeric_smiles",
            "canonical_smiles_from_rdkit",
            "registration_hash",
            "rdkit_schema_version",
            "rdkit_build_mode",
        ):
            value = getattr(item, name, None)
            if not isinstance(value, str):
                setattr(item, name, "")

        match_is_unique = getattr(item, "match_is_unique", None)
        if not isinstance(match_is_unique, bool):
            item.match_is_unique = False

        total_charge = getattr(item, "total_charge", None)
        if not isinstance(total_charge, int):
            item.total_charge = int(total_charge) if total_charge is not None else 0

        graph_desc = getattr(item, "rdkit_graph_desc", None)
        if graph_desc is None and n_atom >= 0:
            item.rdkit_graph_desc = torch.zeros((RDKIT_GRAPH_DESC_DIM,), dtype=torch.float32)
        elif isinstance(graph_desc, torch.Tensor) and graph_desc.dtype != torch.float32:
            item.rdkit_graph_desc = graph_desc.float()

        graph_mask = getattr(item, "rdkit_graph_desc_mask", None)
        if graph_mask is None and n_atom >= 0:
            item.rdkit_graph_desc_mask = torch.zeros((RDKIT_GRAPH_DESC_DIM,), dtype=torch.bool)
        elif isinstance(graph_mask, torch.Tensor) and graph_mask.dtype != torch.bool:
            item.rdkit_graph_desc_mask = graph_mask.bool()

        for name in RDKIT_NODE_LONG_FIELDS:
            value = getattr(item, name, None)
            if value is None and n_atom > 0:
                setattr(item, name, torch.zeros((n_atom, 1), dtype=torch.long))
            elif isinstance(value, torch.Tensor) and value.dtype != torch.long:
                setattr(item, name, value.long())

        for name in RDKIT_NODE_FLOAT_FIELDS:
            value = getattr(item, name, None)
            if value is None and n_atom > 0:
                setattr(item, name, torch.zeros((n_atom, 1), dtype=torch.float32))
            elif isinstance(value, torch.Tensor) and value.dtype != torch.float32:
                setattr(item, name, value.float())

        for name in RDKIT_NODE_BOOL_FIELDS:
            value = getattr(item, name, None)
            if value is None and n_atom > 0:
                setattr(item, name, torch.zeros((n_atom, 1), dtype=torch.bool))
            elif isinstance(value, torch.Tensor) and value.dtype != torch.bool:
                setattr(item, name, value.bool())

        return item

    def len(self):
        return len(self.idx_list)

    def get(self, i):
        with self.env.begin() as txn:
            n = len(self.idx_list)
            if n == 0:
                raise IndexError("Empty LMDB dataset")

            real = self.idx_list[i]
            buf = txn.get(self._format_key(real))
            if buf is not None:
                return self._normalize_item(pickle.loads(buf), real)

            for j in range(i + 1, n):
                buf = txn.get(self._format_key(self.idx_list[j]))
                if buf is not None:
                    self.idx_list[i] = self.idx_list[j]
                    return self._normalize_item(pickle.loads(buf), self.idx_list[j])

            for j in range(i - 1, -1, -1):
                buf = txn.get(self._format_key(self.idx_list[j]))
                if buf is not None:
                    self.idx_list[i] = self.idx_list[j]
                    return self._normalize_item(pickle.loads(buf), self.idx_list[j])

        raise IndexError(f"LMDB sample missing at logical index {i}")
