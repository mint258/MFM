"""Create only fresh pytest-owned candidate MFM3 stores, never source LMDBs."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np

from phychem_mfm.phase1.v3_contract import FieldSpec, LabelRegistry, canonical_hash
from phychem_mfm.phase1.v3_sampling import ConformerRef, InMemorySamplingIndex, MoleculeEntry, UniformMoleculeSampler
from phychem_mfm.phase1.v3_structural import StructuralFieldBinding
from phychem_mfm.phase1.v3_wire_audit import identity_sha256
from phychem_mfm.phase1.v3_wire_provider import (CandidateWireFactory, SCOPE, array_sha256, data_runtime, file_ref)

VERSION = "synthetic_MFM3_candidate_not_D3_v1"


def json_file(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    return file_ref(path)


def fixture(root, *, mutation=None, with_bond_mapping=True):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    runtime = data_runtime(); store = runtime["wire_v1.store"]; granular = runtime["pipeline_v1.granular_store"]
    fields = (
        FieldSpec("s_element", "S", "structural", "atom", kind="classification", classes=119),
        FieldSpec("s_noise", "S", "structural", "atom", kind="denoise_eps_mse", representation="vector"),
        FieldSpec("s_bond", "S", "structural", "pair", kind="classification", classes=5),
        FieldSpec("energy", "P", "physics", "graph", unit="fixture_energy"),
        FieldSpec("dipole", "P", "physics", "graph", representation="vector", unit="fixture_vector"),
        FieldSpec("atom", "D", "descriptor", "atom", unit="fixture_atom"),
        FieldSpec("pair", "P", "physics", "pair", unit="fixture_pair"))
    registry = LabelRegistry(fields, VERSION, "a" * 64)
    groups = (("S", True), ("D", True), ("P", True))
    families = (("structural", True), ("physics", True), ("descriptor", True))
    entries = tuple(MoleculeEntry("mol" + str(i), (ConformerRef("geom" + str(i), 0, n, (("PM7", "geom" + str(i)),)),), groups, families)
                    for i, n in enumerate((12, 9)))
    index = InMemorySamplingIndex(entries, VERSION)
    book = json_file(root / "reason_book.json", {"scope": SCOPE, "unresolved_leaf_code": 65535,
        "codes": {"7": "FIXTURE_SOURCE_PARTIAL_FIELD", "9": "FIXTURE_GENERIC_LEAF_MISSING", "11": "FIXTURE_REVIEW_ONLY"}})
    native_descriptor = Path(__file__).parents[1] / "phychem_mfm/data/descriptor_schema.py"
    bond = json_file(root / "bond_book.json", {"scope": SCOPE, "real_wire_authority": False, "native_status": "ok",
        "native_descriptor_sha256": hashlib.sha256(native_descriptor.read_bytes()).hexdigest(),
        "wire_to_native": {"0": 1, "1": 3, "2": 2, "3": 5, "4": 4}}) if with_bond_mapping else None
    physical = {}
    for field in fields[3:]:
        members = [{"field_key": "fixture_" + field.name + suffix} for suffix in (("_x", "_y", "_z") if field.representation == "vector" else ("",))]
        physical[field.name] = {"group": field.group, "family": field.family, "unit": field.unit,
            "level": "molecule" if field.level == "graph" else field.level, "kind": field.representation,
            "geometry_source": "pm7", "members": members, "pair_index_policy": {"directed": False, "allow_self": False}}
    schemas = {"geometry": {"kind": "geometry"}, **{family: {"kind": "labels", "family": family,
        "mask_encoding": "field-set+sparse-leaf-v1", "compiled": {"physical_targets": {key: value for key, value in physical.items() if value["family"] == family}}}
        for family in ("physics", "descriptor")}}
    records, payloads = [], {name: [] for name in schemas}
    for i, n in enumerate((12, 9)):
        gid, mid = "geom" + str(i), "mol" + str(i)
        axes = np.arange(n, dtype="<f4")
        z = np.full(n, 6, dtype="<i2")
        pos = np.stack((axes * .6, np.sin(axes) * .2, np.cos(axes) * .1), axis=-1).astype("<f4")
        pairs = np.stack((np.arange(n - 1), np.arange(1, n)), axis=-1).astype("<i4")
        arrays = {"atomic_numbers": z, "positions_A": pos, "bond_pairs": pairs,
                  "bond_order_codes": (np.arange(n - 1) % 5).astype("|u1")}
        atom_ids = list(range(n))
        order = canonical_hash({"source_atom_ids": atom_ids, "atomic_numbers_sha256": array_sha256(z), "positions_A_sha256": array_sha256(pos)})
        meta = {"molecule_id": mid, "export_record_id": gid, "geometry_source": "pm7", "effective_role": "TRAIN",
                "source_role": "TRAIN", "n_atoms": n, "parent_geometry_id": None, "view_id": None,
                "model_fixture_atom_order_sha256": order}
        payloads["geometry"].append((meta, arrays))
        records.append({"geometry_id": gid, "export_record_id": gid, "molecule_id": mid, "model_geometry_source": "PM7",
            "n_atoms": n, "geometry_store": "geometry", "source_atom_ids": atom_ids, "atom_order_sha256": order,
            "identity_sha256": identity_sha256(meta), "native_identity": {"geometry_id": gid, "molecule_id": mid,
                "geometry_source": "pm7", "native_record_id": "native-record-" + str(i), "sprime_conf_idx": None}})
        for family in ("physics", "descriptor"):
            label_meta = {**meta, "group_exposure_mask": dict(groups), "family_exposure_mask": dict(families),
                "reason_codebook_sha256": book["sha256"], "reason_granularity": {}}
            labels = {}
            for name, target in schemas[family]["compiled"]["physical_targets"].items():
                if name == "energy": value = np.array(1. + i, dtype="<f4")
                elif name == "dipole": value = np.array([.2, np.nan, .4], dtype="<f4")
                elif name == "atom": value = np.arange(n, dtype="<f4") / 10
                else: value = np.linspace(.2, .8, n - 1, dtype="<f4")
                valid = np.isfinite(value).astype("|u1")
                labels["values/" + name], labels["valid/" + name] = value, valid
                if name == "pair": labels["pairs/" + name] = pairs.copy()
                notes = {}
                for j, member in enumerate(target["members"]):
                    key = member["field_key"]
                    component = valid[..., j] if len(target["members"]) > 1 else valid
                    invalid = np.flatnonzero(component.reshape(-1) == 0).astype("<i4")
                    notes[key] = {"leaf_shape": list(component.shape)}
                    labels["reason_fields_source/" + key] = np.array([7] if name == "dipole" else [], dtype="<u2")
                    labels["reason_fields_new/" + key] = np.array([], dtype="<u2")
                    labels["reason_fields_review/" + key] = np.array([11], dtype="<u2")
                    labels["reason_leaf_index/" + key] = invalid
                    labels["reason_leaf_code/" + key] = np.full(len(invalid), 9, dtype="<u2")
                label_meta["reason_granularity"][name] = {"mode": "field_set_and_sparse_generic_leaf_v1", "members": notes}
            payloads[family].append((label_meta, labels))
    if mutation is not None: mutation(schemas, payloads, records)
    stores = []
    for name, schema in schemas.items():
        writer = store.FamilyWriter(root / name, schema, map_bytes=8 << 20) if name == "geometry" else granular.GranularFamilyWriter(root / name, schema, map_bytes=8 << 20)
        try:
            writer.write_batch(payloads[name]); receipt = writer.finish()
        finally: writer.close()
        stores.append({"name": name, "kind": schema["kind"], "path": str(root / name),
            "schema_sha256": receipt["schema_sha256"], "data": receipt["data"]})
    manifest = {"scope": SCOPE, "data_version": VERSION, "records": records, "stores": stores,
        "reason_codebook": book, "synthetic_bond_mapping": bond,
        "targets": [{"target_id": field.name, "model_field": field.name, "store": field.family,
            "condition": "PM7", "geometry_context": "base", "basis_indexed": False} for field in fields[3:]]}
    factory = CandidateWireFactory(index, registry, manifest, node_local_root=root, allow_candidate=True,
                                   handle_events=root / "handles.jsonl")
    sampler = UniformMoleculeSampler(index, seed=3, sample_budget=8)
    return factory, sampler, registry, StructuralFieldBinding("s_element", "s_noise", "s_bond")
