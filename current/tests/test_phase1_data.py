from __future__ import annotations

import pickle

import lmdb
import pytest
import torch
from rdkit import Chem
from torch_geometric.data import Data

from phychem_mfm.data.dataset_lmdb import LmdbMoleculeDataset
from phychem_mfm.phase1.data import (
    Phase1ViewDataset, StrictManifestDataset, audit_manifest_identities, fit_train_statistics,
)
from phychem_mfm.phase1.identity import (
    MoleculeIdentityError, SplitOverlapError, canonical_hash, identity_from_record, molecule_identity,
    build_identity_decontamination_plan, frozen_test_identities,
)
from phychem_mfm.training.degrade_molecules import DegradeConfig, degrade_once
from phychem_mfm.training.data import fast_collate


def sample(smiles="CCO", *, energy=3.0, missing_charge=False):
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    atoms = mol.GetNumAtoms()
    row = Data(
        x=torch.tensor([atom.GetAtomicNum() - 1 for atom in mol.GetAtoms()]).view(-1, 1),
        pos=torch.arange(atoms * 3).reshape(atoms, 3).float(),
        smiles=smiles, energy=energy, energy_unit="kcal/mol",
        rdkit_graph_desc=torch.arange(31).float(), rdkit_graph_desc_mask=torch.ones(31, dtype=torch.bool),
        rdkit_node_mask=torch.ones(atoms, 1, dtype=torch.bool),
    )
    if not missing_charge:
        row.y = torch.zeros(atoms, 1)
        row.charge_mask = torch.ones(atoms, 1)
    return row


def write_lmdb(path, rows, length=None):
    env = lmdb.open(str(path), subdir=False, map_size=8 * 1024 * 1024)
    with env.begin(write=True) as txn:
        txn.put(b"__len__", pickle.dumps(max(rows) + 1 if length is None else length))
        for index, row in rows.items():
            txn.put(f"{index:09d}".encode(), pickle.dumps(row))
    env.close()


def manifest(root, shard, ranges, *, kind="train"):
    payload = {
        "data_root": str(root), "kind": kind, "pool_id": "unit_fixture",
        "segments": [{"shard": shard, "start": start, "end": end, "count": end - start + 1} for start, end in ranges],
        "unique_structure_count": sum(end - start + 1 for start, end in ranges),
    }
    payload["pool_hash"] = canonical_hash(payload)
    return payload


def test_strict_missing_record_does_not_replace_or_mutate_indices(tmp_path):
    path = tmp_path / "samples.lmdb"
    write_lmdb(path, {0: sample(), 2: sample("CCCC")})
    strict = LmdbMoleculeDataset(path, strict_index=True)
    before = list(strict.idx_list)
    with pytest.raises(IndexError, match="exact sample missing"):
        strict[1]
    assert strict.idx_list == before
    with pytest.raises(IndexError, match="exact sample missing"):
        strict.get_by_real_index(1)
    compatibility = LmdbMoleculeDataset(path)
    assert compatibility[1].smiles == "CCCC"


def test_absent_charge_and_energy_are_not_valid_zero_labels(tmp_path):
    path = tmp_path / "missing.lmdb"
    row = sample(missing_charge=True)
    del row.energy
    write_lmdb(path, {0: row})
    loaded = LmdbMoleculeDataset(path, strict_index=True)[0]
    assert not loaded.charge_mask.any()
    assert not loaded.energy_mask.any()
    assert loaded.energy == 0.0


def test_strict_absent_descriptor_fields_are_not_true_zero_labels(tmp_path):
    path = tmp_path / "descriptor_missing.lmdb"
    row = sample()
    del row.rdkit_graph_desc
    # Deliberately retain a stale graph mask and a valid shared atom mask.
    row.rdkit_node_donor = torch.ones_like(row.rdkit_node_mask)
    write_lmdb(path, {0: row})
    dataset = StrictManifestDataset(manifest(tmp_path, path.name, [(0, 0)]))
    loaded = dataset[0]
    assert not loaded.rdkit_graph_desc_mask.any()
    assert loaded.rdkit_node_mask.all()
    assert loaded.rdkit_node_donor.eq(1).all()
    for field in ("rdkit_node_estate_index", "rdkit_node_min_ring_size", "rdkit_node_acceptor", "rdkit_node_is_aromatic", "rdkit_node_is_in_ring"):
        assert torch.isnan(getattr(loaded, field)).all()
    stats, provenance = fit_train_statistics(dataset)
    assert provenance["valid_label_counts"]["estate_index"] == 0
    assert sum(provenance["valid_label_counts"]["graph_descriptor"]) == 0
    batch = fast_collate([Phase1ViewDataset(dataset, mode="clean")[0], Phase1ViewDataset(dataset, mode="geom")[0]])
    assert batch.rdkit_node_estate_index.shape == (2 * len(loaded.x), 1)
    assert torch.isnan(batch.rdkit_node_estate_index).all()
    assert not batch.rdkit_graph_desc_mask.any()
    legacy = LmdbMoleculeDataset(path)[0]
    assert legacy.rdkit_graph_desc_mask.all()
    assert legacy.rdkit_node_estate_index.eq(0).all()
    assert legacy.rdkit_node_acceptor.eq(0).all()


def test_strict_binary_descriptor_does_not_coerce_invalid_labels_to_true(tmp_path):
    path = tmp_path / "descriptor_invalid.lmdb"
    row = sample()
    row.rdkit_node_donor = torch.full((len(row.x), 1), float("nan"))
    row.rdkit_node_acceptor = torch.full((len(row.x), 1), 3.)
    write_lmdb(path, {0: row})
    loaded = LmdbMoleculeDataset(path, strict_index=True)[0]
    assert torch.isnan(loaded.rdkit_node_donor).all()
    assert loaded.rdkit_node_acceptor.eq(3).all()
    legacy = LmdbMoleculeDataset(path)[0]
    assert legacy.rdkit_node_donor.all() and legacy.rdkit_node_acceptor.all()


def test_explicit_element_encoding_preserves_untouched_atoms_and_both_mask():
    # No hydrogen (no zero index) deliberately exercises the legacy heuristic
    # ambiguity while explicit zero_based must retain every untouched value.
    row = Data(x=torch.tensor([[5], [5], [6], [7]]), pos=torch.zeros(4, 3))
    for encoding, offset in (("zero_based", 0), ("atomic_number", 1)):
        clean = row.clone()
        clean.x = clean.x + offset
        topo = degrade_once(clean, DegradeConfig(mode="topo", level=1.0, atom_encoding=encoding), torch.Generator().manual_seed(4))
        both = degrade_once(clean, DegradeConfig(mode="both", level=1.0, atom_encoding=encoding), torch.Generator().manual_seed(4))
        changes = topo.x.ne(clean.x).any(dim=1)
        assert changes.any()
        assert torch.equal(changes, topo.element_corrupt_mask.view(-1))
        assert torch.equal(topo.x[~changes], clean.x[~changes])
        assert torch.equal(both.element_corrupt_mask, topo.element_corrupt_mask)


def test_full_inchikey_merges_field_and_smiles_order_but_preserves_stereo():
    first = Data(smiles="CCO", canonical_smiles="CCO")
    second = Data(smiles="OCC")
    assert identity_from_record(first).inchikey == identity_from_record(second).inchikey
    assert molecule_identity("C[C@H](O)Cl").inchikey != molecule_identity("C[C@@H](O)Cl").inchikey
    with pytest.raises(MoleculeIdentityError):
        molecule_identity("not a molecular structure")


def test_sparse_manifest_never_reads_excluded_bad_middle_record(tmp_path):
    path = tmp_path / "samples.lmdb"
    write_lmdb(path, {0: sample(), 1: sample("CCCC", energy=999999.0), 2: sample("CCN")})
    dataset = StrictManifestDataset(manifest(tmp_path, path.name, [(0, 0), (2, 2)]))
    assert len(dataset) == 2
    assert [dataset.record_ref(i)[1] for i in range(2)] == [0, 2]
    assert [dataset[i].energy for i in range(2)] == [3.0, 3.0]
    assert dataset[1].phase1_record_key.endswith(":2")
    assert Phase1ViewDataset(dataset, mode="both", level=1.0)[0].target_x.shape == dataset[0].x.shape


def test_identity_overlap_fails_without_reassigning_existing_split(tmp_path):
    path = tmp_path / "samples.lmdb"
    write_lmdb(path, {0: sample("CCO"), 1: sample("OCC")})
    train = StrictManifestDataset(manifest(tmp_path, path.name, [(0, 0)]))
    validation = StrictManifestDataset(manifest(tmp_path, path.name, [(1, 1)], kind="validation"))
    with pytest.raises(SplitOverlapError, match="preserve the split"):
        audit_manifest_identities(train, validation)
    assert train.record_ref(0)[1] == 0 and validation.record_ref(0)[1] == 1


def test_statistics_ignore_validation_labels_and_track_exact_training_view(tmp_path):
    path = tmp_path / "samples.lmdb"
    write_lmdb(path, {0: sample("CCO", energy=2.0), 1: sample("CCN", energy=4.0), 2: sample("CCCC", energy=999999.0)})
    train = StrictManifestDataset(manifest(tmp_path, path.name, [(0, 1)]))
    validation = StrictManifestDataset(manifest(tmp_path, path.name, [(2, 2)], kind="validation"))
    stats, provenance = fit_train_statistics(train, cap=2, seed=0, validation=validation)
    assert stats["muE"] == 3.0 and stats["stdE"] == 1.0
    assert provenance["train_only"]
    assert provenance["train_view_hash"] == train.view_hash
    assert provenance["valid_label_counts"]["energy"] == 2
    assert provenance["split_identity_audit"]["overlap_count"] == 0
    with pytest.raises(ValueError, match="declared training"):
        fit_train_statistics(validation)


def test_manifest_content_hash_and_duplicate_selection_are_rejected(tmp_path):
    path = tmp_path / "samples.lmdb"
    write_lmdb(path, {0: sample()})
    payload = manifest(tmp_path, path.name, [(0, 0)])
    payload["kind"] = "validation"
    with pytest.raises(ValueError, match="content hash"):
        StrictManifestDataset(payload)
    with pytest.raises(ValueError, match="duplicate"):
        StrictManifestDataset(manifest(tmp_path, path.name, [(0, 0), (0, 0)]))


def test_full_pool_plan_requires_frozen_test_list_and_preserves_overlap_evidence(tmp_path):
    import hashlib
    import json

    with pytest.raises(ValueError, match="explicitly frozen"):
        frozen_test_identities({"frozen": False, "test_files": []})
    path = tmp_path / "samples.lmdb"
    write_lmdb(path, {0: sample("CCO"), 1: sample("OCC")})
    train = StrictManifestDataset(manifest(tmp_path, path.name, [(0, 0)]))
    validation = StrictManifestDataset(manifest(tmp_path, path.name, [(1, 1)], kind="validation"))
    tests = tmp_path / "tests.csv"
    tests.write_text("smiles,unused_target\nCCN,99999\n", encoding="utf-8")
    specification = {"frozen": True, "test_files": [{
        "path": str(tests), "sha256": hashlib.sha256(tests.read_bytes()).hexdigest(),
        "role": "test", "smiles_column": "smiles",
    }]}
    output = tmp_path / "plan"
    with pytest.raises(SplitOverlapError, match="overlapping"):
        build_identity_decontamination_plan(
            train, validation, frozen_downstream_specification=specification, output_directory=output,
        )
    evidence = json.loads((output / "decontamination_plan.json").read_text())
    assert evidence["train_validation_overlap_count"] == 1
    assert evidence["split_unchanged"]
    assert train.record_ref(0)[1] == 0 and validation.record_ref(0)[1] == 1
