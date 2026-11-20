"""Pure section-5 source adapters; no fitting, geometry or file reads.

Descriptor values are already produced. Composition alone uses the original
member's source SMILES graph and graph-level implicit H, never native geometry
atom counts (ExpansionRx geometries may omit hydrogens).
"""
from dataclasses import replace

import torch

try:
    from .descriptor_features import append_member_d3
    from .dev_descriptor_readouts import composition_features
except ImportError:
    from descriptor_features import append_member_d3
    from dev_descriptor_readouts import composition_features


def _source_uids(rows, dataset):
    if not isinstance(dataset, str) or not dataset:
        raise ValueError("Explicit original development dataset ID is required")
    result = []
    for row in rows:
        uid = row.source_member_uid
        if not isinstance(uid, str) or not uid:
            raise ValueError("Original source_member_uid is required; molecule_uid is not a member substitute")
        result.append(uid)
    return tuple(result)


def task_descriptors(rows, dataset, descriptor_store, d3_members, *, standardized, normalization):
    """Return the same-order 2D+six-D3 batch using original member namespaces.

    Development manifests declare member_key='member_uid', not the benchmark's
    'record_id'. The declared key is passed explicitly to the D3 join; no ID is
    renamed, split, concatenated, hashed, or substituted by molecule identity.
    """
    rows = tuple(rows)
    uids = _source_uids(rows, dataset)
    reference = descriptor_store.membership_reference
    member_key = reference["member_key"]
    requests = tuple((dataset, uid) for uid in uids) if reference.get("dataset_key") else uids
    batch = descriptor_store.get_members(requests, standardized=standardized)
    if tuple(batch.member_uids) != requests:
        raise ValueError("Published descriptor member identities differ from the native development rows")
    if tuple(batch.molecule_ids) != tuple(row.molecule_uid for row in rows):
        raise ValueError("Published descriptor molecule IDs differ from native development molecule identity")
    for row, source_split in zip(rows, batch.source_splits):
        if hasattr(row, "source_split") and row.source_split != source_split:
            raise ValueError("Published descriptor split differs from the native development row")
    return append_member_d3(batch, d3_members, standardized=standardized,
                            normalization=normalization, tuple_member_key=member_key)


def composition_rows(rows, dataset, d3_members):
    """Attach complete source-graph composition without changing native rows.

    Existing member metadata must provide source_smiles. Chem.AddHs only makes
    the hydrogens already represented implicitly in that source graph explicit;
    it creates no coordinates/conformers and selects no geometry-H policy.
    """
    from rdkit import Chem

    rows = tuple(rows)
    uids = _source_uids(rows, dataset)
    requested = {(dataset, uid) for uid in uids}
    members = {}
    for member in d3_members:
        # This is specifically the development source namespace; no fallback
        # to benchmark record_id or to molecule-level representative graphs.
        if "dataset" not in member or "member_uid" not in member:
            continue
        key = (member["dataset"], member["member_uid"])
        if key not in requested:
            continue
        identity = (member["molecule_id"], member.get("source_split"), member.get("source_smiles"))
        if key in members and members[key] != identity:
            raise ValueError("Conflicting original development member graph binding")
        members[key] = identity
    output = []
    for row, uid in zip(rows, uids):
        key = (dataset, uid)
        if key not in members:
            raise ValueError("UNRESOLVED: original member source graph metadata is missing: " + repr(key))
        molecule, source_split, smiles = members[key]
        if molecule != row.molecule_uid:
            raise ValueError("Original composition member/molecule identity differs from native development row")
        if hasattr(row, "source_split") and row.source_split != source_split:
            raise ValueError("Original composition source split differs from native development row")
        if not isinstance(smiles, str) or not smiles.strip():
            raise ValueError("UNRESOLVED: original member source_smiles is unavailable: " + repr(key))
        graph = Chem.MolFromSmiles(smiles)
        if graph is None or not graph.GetNumAtoms():
            raise ValueError("UNRESOLVED: original member source_smiles cannot form its source graph: " + repr(key))
        explicit_graph = Chem.AddHs(graph)
        atomic_numbers = [atom.GetAtomicNum() for atom in explicit_graph.GetAtoms()]
        features = composition_features(atomic_numbers)
        output.append(replace(row, graph_features=torch.as_tensor(features, dtype=torch.float64)))
    return tuple(output)
