"""Opt-in synthetic consumption of DataB's per-source D5 candidate projection.

This is model-side engineering, not a release schema or final D5 authority.
Original projection inputs are required because the projection alone omits
the energy orders and diagnostic tables needed to check its minimum ID.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import ClassVar, Mapping

from . import v3_sampling
from .v3_sampling import ConformationSelection, ConformerRef, MoleculeEntry, UniformMoleculeSampler

PROJECTION_SCHEMA = "D5_PER_SOURCE_TRAINING_SAMPLING_PROJECTION_V1"
PROJECTION_SOURCE_SHA256 = "50aceee73de4718b7f35dbd2a37a207a7739d57f8ed53f39a36da16bfbc0e2dd"
SOURCES = {"pm7": "PM7", "uff_sprime": "Sprime_UFF"}
ORDER_TYPES = ("fixed_random", "energy", "diversity")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    _require(type(value) is str and bool(value) and "\0" not in value, "Explicit nonempty literal ID/version required")
    return value


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _snapshot(value):
    encoded = _canonical(value)
    _require(len(encoded.encode("utf-8")) <= 16 * 1024 ** 2, "Candidate metadata snapshot exceeds declared 16 MiB boundary")
    return json.loads(encoded)


def _file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _mask(value, *, groups=False):
    _require(isinstance(value, dict) and bool(value)
             and all(type(k) is str and bool(k) and type(v) is bool for k, v in value.items()),
             "Explicit boolean exposure masks required")
    _require(not groups or set(value) == {"S", "D", "P"}, "All S/D/P exposure flags required")
    return tuple(sorted(value.items()))


@dataclass(frozen=True)
class CandidateProjectionInput:
    molecule_id: str
    projection: Mapping
    training_arguments: Mapping
    projection_source_sha256: str


@dataclass(frozen=True)
class NativeConformerIdentity:
    geometry_id: str
    molecule_id: str
    geometry_source: str
    native_record_id: str | None
    sprime_conf_idx: int | None

    def __post_init__(self):
        _text(self.geometry_id)
        _text(self.molecule_id)
        _require(self.geometry_source in SOURCES, "Unknown native geometry source")
        if self.geometry_source == "pm7":
            _text(self.native_record_id)
            _require(self.sprime_conf_idx is None, "PM7 identity cannot use a UFF index")
        else:
            _require(type(self.sprime_conf_idx) is int and self.sprime_conf_idx >= 0
                     and (self.native_record_id is None or type(self.native_record_id) is str), "UFF native identity differs")

    @property
    def model_geometry_source(self):
        return SOURCES[self.geometry_source]

    def as_dict(self):
        return asdict(self)

    @property
    def content_sha256(self):
        return _hash(self.as_dict())


@dataclass(frozen=True)
class CandidateMoleculeProjection:
    molecule_id: str
    source_entries: tuple[tuple[str, MoleculeEntry], ...]
    native_identities: tuple[NativeConformerIdentity, ...]
    training_geometry_ids: tuple[str, ...]
    diagnostic_geometry_ids: tuple[str, ...]
    binding_json: str

    def entry_for(self, model_geometry_source):
        _require(model_geometry_source in dict(self.source_entries), "Unknown projected geometry source")
        return dict(self.source_entries)[model_geometry_source]

    @property
    def bindings(self):
        return json.loads(self.binding_json)

    @property
    def content_sha256(self):
        return hashlib.sha256(self.binding_json.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CandidateSamplingIndex:
    molecules: tuple[MoleculeEntry, ...]
    projections: tuple[CandidateMoleculeProjection, ...]
    native_identities: tuple[NativeConformerIdentity, ...]
    native_geometry_ids: tuple[str, ...]
    version: str
    geometry_source: str
    selection: ConformationSelection
    binding_json: str
    role: ClassVar[str] = "TRAIN"
    authority: ClassVar[str] = "synthetic_fixture"
    status: ClassVar[str] = "CANDIDATE_MODEL_SAMPLING_NOT_RELEASE"
    contract_finalized: ClassVar[bool] = False
    real_data_export_accepted: ClassVar[bool] = False

    def __len__(self):
        return len(self.molecules)

    def molecule_at(self, index):
        return self.molecules[index]

    @property
    def bindings(self):
        # A caller cannot mutate the digest by changing a returned dictionary.
        return json.loads(self.binding_json)

    @property
    def content_sha256(self):
        return hashlib.sha256(self.binding_json.encode("utf-8")).hexdigest()

    def native_identity_for(self, geometry_id):
        i = bisect_left(self.native_geometry_ids, geometry_id)
        if i == len(self.native_geometry_ids) or self.native_geometry_ids[i] != geometry_id:
            raise KeyError(geometry_id)
        return self.native_identities[i]

    def make_sampler(self, *, seed, sample_budget):
        """Use the checked source/selection with the unchanged model sampler."""
        return UniformMoleculeSampler(self, seed=seed, sample_budget=sample_budget,
                                       selection=self.selection, geometry_source=self.geometry_source)


def _project_one(item, *, max_rows):
    _require(isinstance(item, CandidateProjectionInput), "Typed candidate projection input required")
    molecule_id = _text(item.molecule_id)
    _require(item.projection_source_sha256 == PROJECTION_SOURCE_SHA256,
             "DataB projection source SHA differs from the explicitly reviewed implementation")
    _require(isinstance(item.training_arguments, Mapping) and isinstance(item.projection, Mapping),
             "Candidate projection and original arguments must be mappings")
    required = {"effective_role", "training_geometries", "training_orders", "diagnostic_targets",
                "native_atom_counts", "group_mask", "family_mask"}
    _require(required <= set(item.training_arguments) <= required | {"max_rows"}, "Original projection arguments differ")
    for name, cap in (("training_geometries", max_rows), ("training_orders", 3 * max_rows), ("diagnostic_targets", max_rows)):
        rows = item.training_arguments[name]
        _require(isinstance(rows, (tuple, list)) and len(rows) <= cap, "Explicit bounded projection row sequences required")
    args, projected = _snapshot(dict(item.training_arguments)), _snapshot(dict(item.projection))
    _require(args["effective_role"] == "TRAIN", "Candidate sampling requires original TRAIN arguments")
    upstream_cap = args.get("max_rows", 4096)
    _require(type(upstream_cap) is int and upstream_cap > 0, "Invalid upstream per-molecule row cap")
    _require(len(args["training_geometries"]) <= upstream_cap
             and len(args["training_orders"]) <= 3 * upstream_cap
             and len(args["diagnostic_targets"]) <= upstream_cap, "Upstream row cap would reject these inputs")
    _require(projected.get("schema") == PROJECTION_SCHEMA
             and projected.get("status") == "CANDIDATE_PROJECTION_NOT_RELEASE"
             and projected.get("contract_finalized") is False and projected.get("real_data_export_accepted") is False,
             "Only the reviewed candidate projection is accepted; no authority upgrade")
    _require(projected.get("projected_conformer_id_semantics") == "opaque D5 geometry_id; no cross-source alignment"
             and projected.get("minimum_energy_rule") == "retained energy training_rank=0 after diagnostic anti-join",
             "Projection ID/minimum semantics differ")
    _require(set(projected) == {"schema", "status", "source_entries", "native_conformer_identity",
                "projected_conformer_id_semantics", "minimum_energy_rule", "contract_finalized", "real_data_export_accepted"},
             "Unreviewed projection schema fields")
    group_mask, family_mask = _mask(args["group_mask"], groups=True), _mask(args["family_mask"])
    diagnostic = set()
    for row in args["diagnostic_targets"]:
        _require(row["molecule_id"] == molecule_id and row["geometry_source"] in SOURCES,
                 "Diagnostic molecule/source differs")
        gid = _text(row["geometry_id"])
        _require(gid not in diagnostic, "Duplicate diagnostic geometry ID")
        diagnostic.add(gid)
    geometries = {}
    for row in args["training_geometries"]:
        gid = _text(row["geometry_id"])
        _require(row["molecule_id"] == molecule_id and row["geometry_source"] in SOURCES,
                 "Training geometry molecule/source differs")
        _require(gid not in geometries, "Duplicate or cross-source geometry ID collision")
        _require(gid not in diagnostic and row["parent_geometry_id"] not in diagnostic,
                 "Diagnostic geometry/child leaked into training")
        _require((row["parent_geometry_id"] is None) == (row["view_id"] is None), "View/parent facts differ")
        if row["geometry_source"] == "pm7":
            _text(row["native_record_id"])
            _require(row["sprime_conf_idx"] is None, "PM7 cannot use a UFF conformer index")
        else:
            _require(type(row["sprime_conf_idx"]) is int and row["sprime_conf_idx"] >= 0,
                     "UFF physical conformer index required")
            _require(row["native_record_id"] is None or type(row["native_record_id"]) is str,
                     "UFF native record provenance must be preserved literally")
        geometries[gid] = row
    base = {gid: row for gid, row in geometries.items() if row["view_id"] is None}
    for row in geometries.values():
        if row["parent_geometry_id"] is not None:
            parent = base.get(row["parent_geometry_id"])
            _require(parent is not None and parent["geometry_source"] == row["geometry_source"], "View parent not retained in own source")
    atoms = args["native_atom_counts"]
    _require(isinstance(atoms, dict) and set(atoms) == set(base)
             and all(type(n) is int and n > 0 for n in atoms.values()), "Exact positive canonical base atom counts required")
    identities, physical = [], set()
    for gid, row in base.items():
        native = NativeConformerIdentity(gid, molecule_id, row["geometry_source"], row["native_record_id"], row["sprime_conf_idx"])
        key = (native.geometry_source, native.native_record_id if native.geometry_source == "pm7" else native.sprime_conf_idx)
        _require(key not in physical, "Duplicate base physical identity")
        physical.add(key)
        identities.append(native)
    identity_map = {row.geometry_id: row.as_dict() for row in identities}
    _require(_canonical(projected.get("native_conformer_identity")) == _canonical(identity_map),
             "Native identity sidecar differs from original source rows")
    entries = projected.get("source_entries")
    _require(isinstance(entries, dict) and set(entries) == set(SOURCES), "Two independent PM7/UFF source entries required")
    order_rows = {(source, kind): [] for source in SOURCES for kind in ORDER_TYPES}
    seen = set()
    for row in args["training_orders"]:
        gid, source, kind = row["geometry_id"], row["geometry_source"], row["order_type"]
        _require(row["molecule_id"] == molecule_id and (source, kind) in order_rows
                 and gid in base and base[gid]["geometry_source"] == source,
                 "Orders must reference retained base geometry in their own source")
        _require((gid, kind) not in seen, "Duplicate geometry/order entry")
        seen.add((gid, kind))
        _require(type(row["rank"]) is int and row["rank"] >= 0 and type(row["training_rank"]) is int
                 and row["training_rank"] >= 0, "Explicit original and training ranks required")
        order_rows[source, kind].append(row)
    typed_entries = []
    for source, model_source in SOURCES.items():
        members = {gid for gid, row in base.items() if row["geometry_source"] == source}
        _require(bool(members), "Both source projections require nonempty retained bases")
        ordered = {}
        for kind in ORDER_TYPES:
            rows = sorted(order_rows[source, kind], key=lambda row: row["training_rank"])
            _require(len(rows) == len(members) and {row["geometry_id"] for row in rows} == members,
                     "Three complete independent source orders required")
            _require([row["training_rank"] for row in rows] == list(range(len(members))), "Training ranks must be contiguous from zero")
            original = [row["rank"] for row in rows]
            _require(original == sorted(set(original)), "Training ranks must preserve original rank order")
            ordered[kind] = [row["geometry_id"] for row in rows]
        entry = entries[source]
        _require(set(entry) == {"molecule_id", "conformers", "group_mask", "family_mask", "mixed_geometry_source", "minimum_energy_conformer_id"}
                 and entry["molecule_id"] == molecule_id and entry["mixed_geometry_source"] == model_source,
                 "Projected source entry identity differs")
        _require(_canonical(entry["group_mask"]) == _canonical([list(value) for value in group_mask])
                 and _canonical(entry["family_mask"]) == _canonical([list(value) for value in family_mask]),
                 "Projected exposure differs from source boolean masks")
        refs = entry["conformers"]
        _require(isinstance(refs, list) and len(refs) == len(members)
                 and [ref["conformer_id"] for ref in refs] == ordered["fixed_random"], "Projected fixed order differs from retained training order")
        diversity = {gid: rank for rank, gid in enumerate(ordered["diversity"])}
        for rank, ref in enumerate(refs):
            gid = ref["conformer_id"]
            _require(set(ref) == {"conformer_id", "fixed_order", "native_atoms", "geometry_locators", "diversity_order"}
                     and type(ref["fixed_order"]) is int and ref["fixed_order"] == rank
                     and type(ref["native_atoms"]) is int and ref["native_atoms"] == atoms[gid]
                     and type(ref["diversity_order"]) is int and ref["diversity_order"] == diversity[gid]
                     and ref["geometry_locators"] == [[model_source, gid]], "Projected rank/atom count/source locator differs")
        minimum = ordered["energy"][0]
        _require(entry["minimum_energy_conformer_id"] == minimum, "Minimum must be retained energy training_rank=0, not original rank zero")
        typed_entries.append((model_source, MoleculeEntry(molecule_id,
            tuple(ConformerRef(**ref) for ref in refs), group_mask, family_mask, model_source, minimum)))
    bindings = {"molecule_id": molecule_id, "projection_schema": PROJECTION_SCHEMA,
        "projection_source_sha256": item.projection_source_sha256, "projection_sha256": _hash(projected),
        "training_geometry_sha256": _hash(args["training_geometries"]), "training_orders_sha256": _hash(args["training_orders"]),
        "diagnostic_sha256": _hash(args["diagnostic_targets"]), "native_atom_counts_sha256": _hash(atoms),
        "native_identity_sha256": _hash(identity_map), "original_arguments_sha256": _hash(args),
        "source_entry_sha256": {source: _hash(entry) for source, entry in entries.items()}}
    return CandidateMoleculeProjection(molecule_id, tuple(typed_entries), tuple(sorted(identities, key=lambda row: row.geometry_id)),
        tuple(geometries), tuple(sorted(diagnostic)), _canonical(bindings))


def build_candidate_sampling_index(inputs, *, data_version, geometry_source, selected_molecule_ids,
                                   selection=ConformationSelection(), mixed_sources=None, allow_candidate=False,
                                   max_molecules=4096, max_rows_per_molecule=4096, max_total_conformers=65536,
                                   max_total_geometry_rows=131072, max_total_diagnostic_rows=131072):
    """Bind candidate facts without granting data_line/release authority.

    Insufficient k is rejected here; that conservative candidate boundary does
    not settle the final scientific policy for molecules with fewer than k.
    """
    _require(allow_candidate is True, "Explicit allow_candidate=True is required; final D5 is not delivered")
    _text(data_version)
    _require(geometry_source in ("PM7", "Sprime_UFF", "mixed"), "Explicit model geometry source required")
    _require(isinstance(selection, ConformationSelection), "Typed conformation selection required")
    _require(all(type(value) is int and value > 0 for value in (max_molecules, max_rows_per_molecule, max_total_conformers,
                                                             max_total_geometry_rows, max_total_diagnostic_rows)),
             "Positive bounded candidate metadata limits required")
    values, molecule_ids, all_geometries, diagnostics, total = [], set(), set(), set(), 0
    for item in inputs:
        _require(len(values) < max_molecules, "Candidate molecule memory boundary exceeded")
        projected = _project_one(item, max_rows=max_rows_per_molecule)
        _require(projected.molecule_id not in molecule_ids, "Duplicate molecule projection")
        _require(not all_geometries.intersection(projected.training_geometry_ids), "Global geometry ID collision across molecules/sources")
        _require(not diagnostics.intersection(projected.diagnostic_geometry_ids), "Global duplicate diagnostic geometry ID")
        _require(len(all_geometries) + len(projected.training_geometry_ids) <= max_total_geometry_rows
                 and len(diagnostics) + len(projected.diagnostic_geometry_ids) <= max_total_diagnostic_rows,
                 "Candidate global geometry/diagnostic memory boundary exceeded")
        molecule_ids.add(projected.molecule_id)
        all_geometries.update(projected.training_geometry_ids)
        diagnostics.update(projected.diagnostic_geometry_ids)
        total += len(projected.native_identities)
        _require(total <= max_total_conformers, "Candidate conformer memory boundary exceeded")
        values.append(projected)
    _require(bool(values) and not all_geometries.intersection(diagnostics), "Empty input or diagnostic geometry ID returned to training")
    _require(isinstance(selected_molecule_ids, (tuple, list)) and bool(selected_molecule_ids), "Explicit ordered molecule selection required")
    selected = tuple(_text(value) for value in selected_molecule_ids)
    _require(len(set(selected)) == len(selected) and set(selected) <= molecule_ids, "Unknown or duplicate selected molecule ID")
    if geometry_source == "mixed":
        _require(isinstance(mixed_sources, Mapping) and set(mixed_sources) == set(selected)
                 and all(value in SOURCES.values() for value in mixed_sources.values()), "Mixed selection requires exactly one explicit source per molecule")
        chosen_sources = tuple((mid, mixed_sources[mid]) for mid in selected)
    else:
        _require(mixed_sources is None, "Single-source index must not receive a mixed source mapping")
        chosen_sources = tuple((mid, geometry_source) for mid in selected)
    by_id = {value.molecule_id: value for value in values}
    molecules = tuple(by_id[mid].entry_for(source) for mid, source in chosen_sources)
    if selection.mode in ("first_k", "diversity_first_k"):
        _require(all(selection.k <= len(molecule.conformers) for molecule in molecules), "Insufficient retained conformers for declared k; candidate policy rejects")
    chosen_projections = tuple(by_id[mid] for mid in selected)
    native = tuple(sorted((row for projected in chosen_projections for row in projected.native_identities), key=lambda row: row.geometry_id))
    bindings = {"schema": "MODEL_CANDIDATE_D5_PROJECTION_BINDINGS_V1", "authority": "synthetic_fixture",
        "status": CandidateSamplingIndex.status, "contract_finalized": False, "real_data_export_accepted": False,
        "data_version": data_version, "geometry_source": geometry_source, "selected_molecule_ids": list(selected),
        "selected_sources": [list(value) for value in chosen_sources], "selection": asdict(selection),
        "insufficient_k_policy": "reject_insufficient_candidate_only", "projection_schema": PROJECTION_SCHEMA,
        "input_projections": [value.bindings for value in values],
        "native_identity_sha256": _hash({row.geometry_id: row.as_dict() for row in native}),
        "selected_molecules_sha256": _hash([asdict(value) for value in molecules]),
        "source_sha256": {"data_projection": PROJECTION_SOURCE_SHA256, "model_bridge": _file_hash(__file__),
                           "model_sampler": _file_hash(v3_sampling.__file__)},
        "metadata_limits": {"max_molecules": max_molecules, "max_rows_per_molecule": max_rows_per_molecule,
                            "max_total_conformers": max_total_conformers, "max_total_geometry_rows": max_total_geometry_rows,
                            "max_total_diagnostic_rows": max_total_diagnostic_rows}}
    return CandidateSamplingIndex(molecules, chosen_projections, native, tuple(row.geometry_id for row in native),
                                  data_version, geometry_source, selection, _canonical(bindings))
