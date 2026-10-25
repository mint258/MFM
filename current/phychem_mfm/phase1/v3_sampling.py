"""Uniform molecules, then uniform allowed conformations, with committed cursors.

The in-memory index is a synthetic/model-side projection, not a physical D-1
format. Real data adapters can implement SamplingIndex using a node-local
memory map without replicating a corpus-sized Python manifest in each worker.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Iterator, Protocol


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, name, *, minimum=0):
    _require(type(value) is int and value >= minimum, f"Invalid {name}")
    return value


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _flags(values, name):
    values = tuple(tuple(value) for value in values)
    _require(all(len(item) == 2 and type(item[0]) is str and bool(item[0])
                 and type(item[1]) is bool for item in values)
             and len({item[0] for item in values}) == len(values), f"Invalid {name}")
    return values


@dataclass(frozen=True)
class ConformerRef:
    conformer_id: str
    fixed_order: int
    native_atoms: int
    geometry_locators: tuple[tuple[str, str], ...]
    diversity_order: int | None = None

    def __post_init__(self):
        _require(type(self.conformer_id) is str and bool(self.conformer_id), "Conformer ID required")
        _integer(self.fixed_order, "fixed conformer order")
        _integer(self.native_atoms, "native atom count", minimum=1)
        pairs = tuple(tuple(pair) for pair in self.geometry_locators)
        _require(bool(pairs) and all(len(pair) == 2 and pair[0] in ("PM7", "Sprime_UFF")
                 and type(pair[1]) is str and bool(pair[1]) for pair in pairs)
                 and len({pair[0] for pair in pairs}) == len(pairs), "Explicit geometry locators required")
        object.__setattr__(self, "geometry_locators", pairs)
        if self.diversity_order is not None:
            _integer(self.diversity_order, "diversity order")

    def locator(self, source):
        _require(source in dict(self.geometry_locators), "Requested geometry is not exported")
        return dict(self.geometry_locators)[source]


@dataclass(frozen=True)
class MoleculeEntry:
    molecule_id: str
    conformers: tuple[ConformerRef, ...]
    group_mask: tuple[tuple[str, bool], ...]
    family_mask: tuple[tuple[str, bool], ...]
    mixed_geometry_source: str | None = None
    minimum_energy_conformer_id: str | None = None

    def __post_init__(self):
        _require(type(self.molecule_id) is str and bool(self.molecule_id), "Molecule ID required")
        values = tuple(self.conformers)
        _require(bool(values) and all(isinstance(value, ConformerRef) for value in values)
                 and len({value.conformer_id for value in values}) == len(values)
                 and len({value.fixed_order for value in values}) == len(values),
                 "Unique conformer IDs and fixed orders required")
        object.__setattr__(self, "conformers", tuple(sorted(values, key=lambda value: value.fixed_order)))
        object.__setattr__(self, "group_mask", _flags(self.group_mask, "group masks"))
        object.__setattr__(self, "family_mask", _flags(self.family_mask, "family masks"))
        _require(set(dict(self.group_mask)) == {"S", "D", "P"}, "All S/D/P molecule masks required")
        _require(self.mixed_geometry_source in (None, "PM7", "Sprime_UFF"), "Invalid per-molecule geometry")
        if self.minimum_energy_conformer_id is not None:
            _require(self.minimum_energy_conformer_id in {value.conformer_id for value in values},
                     "Minimum-energy selection must reference an exported conformer")


@dataclass(frozen=True)
class ConformationSelection:
    mode: str = "all"
    k: int | None = None

    def __post_init__(self):
        _require(self.mode in ("all", "first_k", "minimum_energy", "diversity_first_k"),
                 "Unknown conformation selection")
        if self.mode in ("first_k", "diversity_first_k"):
            _integer(self.k, "conformation k", minimum=1)
        else:
            _require(self.k is None, "k is only valid for a first-k selection")

    def allowed(self, molecule: MoleculeEntry) -> tuple[ConformerRef, ...]:
        values = molecule.conformers
        if self.mode == "all":
            return values
        if self.mode == "first_k":
            return values[:self.k]
        if self.mode == "minimum_energy":
            _require(molecule.minimum_energy_conformer_id is not None,
                     "Minimum-energy conformer must be supplied by the data line")
            return tuple(value for value in values if value.conformer_id == molecule.minimum_energy_conformer_id)
        _require(all(value.diversity_order is not None for value in values)
                 and len({value.diversity_order for value in values}) == len(values),
                 "Unique data-line diversity order required")
        return tuple(sorted(values, key=lambda value: value.diversity_order)[:self.k])


class SamplingIndex(Protocol):
    content_sha256: str
    version: str
    role: str
    authority: str

    def __len__(self) -> int: ...
    def molecule_at(self, index: int) -> MoleculeEntry: ...


@dataclass(frozen=True)
class InMemorySamplingIndex:
    """Fixture/small-pilot index; use an adapter-backed index for full data."""
    molecules: tuple[MoleculeEntry, ...]
    version: str
    role: str = "TRAIN"
    authority: str = "synthetic_fixture"

    def __post_init__(self):
        values = tuple(self.molecules)
        _require(bool(values) and all(isinstance(value, MoleculeEntry) for value in values)
                 and len({value.molecule_id for value in values}) == len(values), "Unique molecules required")
        _require(self.role in ("TRAIN", "VAL", "TRAIN_UNSEEN_CONFORMATION") and bool(self.version),
                 "Explicit data version and allowed role required")
        _require(self.authority in ("synthetic_fixture", "data_line"), "Unknown index authority")
        object.__setattr__(self, "molecules", values)

    def __len__(self):
        return len(self.molecules)

    def molecule_at(self, index):
        return self.molecules[index]

    @property
    def content_sha256(self):
        return _hash(asdict(self))


@dataclass(frozen=True)
class SampleChoice:
    ordinal: int
    molecule_index: int
    molecule_id: str
    conformer_id: str
    geometry_source: str
    locator: str
    native_atoms: int
    group_mask: tuple[tuple[str, bool], ...]
    family_mask: tuple[tuple[str, bool], ...]
    index_sha256: str
    sampler_sha256: str


def _uniform(seed: int, ordinal: int, stream: str, bound: int):
    # Exact rejection sampling avoids modulo bias. The independent hash streams
    # make the draw reproducible without consuming Python/Torch global RNG.
    threshold = (1 << 256) - (1 << 256) % bound
    attempt = 0
    while True:
        raw = f"model_v3:{seed}:{ordinal}:{stream}:{attempt}".encode("ascii")
        value = int.from_bytes(hashlib.sha256(raw).digest(), "big")
        if value < threshold:
            return value % bound
        attempt += 1


class UniformMoleculeSampler:
    """Sample with replacement, independent of each molecule's conformer count.

    Iteration/prefetch is speculative. Only commit_batch changes the persisted
    cursor. A restarted iterator deterministically reproduces unconsumed draws.
    """
    def __init__(self, index: SamplingIndex, *, seed: int, sample_budget: int,
                 selection=ConformationSelection(), geometry_source="PM7"):
        _require(index.role == "TRAIN" and len(index) > 0, "Training sampler requires a nonempty TRAIN index")
        _require(type(index.content_sha256) is str and len(index.content_sha256) == 64,
                 "Bound index SHA256 required")
        _integer(seed, "seed")
        _integer(sample_budget, "sample budget", minimum=1)
        _require(isinstance(selection, ConformationSelection), "Typed conformation selection required")
        _require(geometry_source in ("PM7", "Sprime_UFF", "mixed"), "Unknown geometry source")
        self.index, self.seed, self.sample_budget = index, seed, sample_budget
        self.selection, self.geometry_source = selection, geometry_source
        self.index_sha256 = index.content_sha256
        self.contract = {"schema": "model_v3_uniform_molecule_sampler_v1", "index_sha256": self.index_sha256,
                         "data_version": index.version, "seed": seed, "sample_budget": sample_budget,
                         "selection": asdict(selection), "geometry_source": geometry_source,
                         "sampling": "uniform_molecule_then_uniform_allowed_conformer_with_replacement"}
        self.content_sha256 = _hash(self.contract)
        self.samples_consumed = 0

    def choice(self, ordinal: int) -> SampleChoice:
        _integer(ordinal, "sample ordinal")
        _require(ordinal < self.sample_budget, "Sample budget exhausted")
        molecule_index = _uniform(self.seed, ordinal, "molecule", len(self.index))
        molecule = self.index.molecule_at(molecule_index)
        allowed = self.selection.allowed(molecule)
        conformer = allowed[_uniform(self.seed, ordinal, "conformer", len(allowed))]
        geometry = molecule.mixed_geometry_source if self.geometry_source == "mixed" else self.geometry_source
        _require(geometry in ("PM7", "Sprime_UFF"), "Mixed manifest requires every molecule's explicit source")
        return SampleChoice(ordinal, molecule_index, molecule.molecule_id, conformer.conformer_id,
                            geometry, conformer.locator(geometry), conformer.native_atoms,
                            molecule.group_mask, molecule.family_mask, self.index_sha256, self.content_sha256)

    def __iter__(self) -> Iterator[SampleChoice]:
        start = self.samples_consumed
        for ordinal in range(start, self.sample_budget):
            yield self.choice(ordinal)

    def __len__(self):
        return self.sample_budget - self.samples_consumed

    def commit_batch(self, choices):
        choices = tuple(choices)
        _require(bool(choices), "Cannot commit an empty batch")
        expected = tuple(self.choice(self.samples_consumed + i) for i in range(len(choices)))
        _require(choices == expected, "Committed samples differ from the next deterministic draws")
        self.samples_consumed += len(choices)

    def state_dict(self):
        return {"schema": self.contract["schema"], "contract_sha256": self.content_sha256,
                "samples_consumed": self.samples_consumed}

    def load_state_dict(self, state):
        _require(type(state) is dict and set(state) == {"schema", "contract_sha256", "samples_consumed"}
                 and state["schema"] == self.contract["schema"]
                 and state["contract_sha256"] == self.content_sha256, "Sampler contract changed")
        cursor = _integer(state["samples_consumed"], "committed sample cursor")
        _require(cursor <= self.sample_budget, "Sampler cursor exceeds budget")
        self.samples_consumed = cursor
