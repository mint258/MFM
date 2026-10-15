"""Source-order structure readers; no targets, split selection or conformer work.

These interfaces encode verified source conventions, not a completed mapping
audit. Full source bytes may be hashed; XYZ annotations are never interpreted.
An identity string is metadata and never replaces the source atom sequence.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import io
import math
from numbers import Integral
from pathlib import Path
import re

from rdkit import Chem, rdBase

from .identity import IDENTITY_POLICY, IdentityResult, canonical_hash


BOHR_TO_ANGSTROM = 0.529177210903
SOURCE_CONTRACT = "source_atom_order_v1"
ATTNSOM_COMMIT = "0faa38bbd1665262efb3642a2a3ae0f83c928a49"
IDENTITY_CONSTRUCTION = "rdkit_graph_no_conformers_v1"
READER_IDENTITY_VERSION = 2
MAX_ATOMS = 4096
MAX_STRUCTURE_BYTES = 8 * 1024 * 1024
MAX_LINE_BYTES = 65536
_KEY = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
_DECIMAL = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
_COORDINATE = re.compile(_DECIMAL + r"(?:(?:[EeDd]|\*\^)[+-]?[0-9]+)?$")


class DownstreamStructureError(ValueError):
    """Source structure or its declared numbering convention is invalid."""


@dataclass(frozen=True)
class SourceStructure:
    atomic_numbers: tuple[int, ...]
    x: tuple[int, ...]
    source_atom_map: tuple[int, ...]
    pos_angstrom: tuple[tuple[float, float, float], ...] | None
    identity: IdentityResult | None
    mol: Chem.Mol | None
    provenance: dict

    @property
    def n_atoms(self) -> int:
        return len(self.atomic_numbers)


def _positive_count(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise DownstreamStructureError(f"{name} must be an explicit positive integer")
    return int(value)


def _atom_numbers(mol) -> tuple[int, ...]:
    numbers = tuple(atom.GetAtomicNum() for atom in mol.GetAtoms())
    if not 0 < len(numbers) <= MAX_ATOMS or any(not 1 <= z <= 118 for z in numbers):
        raise DownstreamStructureError("Invalid source atom count or atomic number")
    return numbers


def _identity_from_mol(mol, source_field: str) -> IdentityResult:
    # Match the existing SMILES-graph identity input, independently of source
    # conformers. Keep original graph/stereo/H/order/coords untouched. The
    # source parser's stereo interpretation remains part of its provenance.
    copied = Chem.Mol(mol)
    copied.RemoveAllConformers()
    with rdBase.BlockLogs():
        try:
            key = Chem.MolToInchiKey(copied)
            canonical = Chem.MolToSmiles(copied, canonical=True, isomericSmiles=True)
        except Exception as exc:
            raise DownstreamStructureError("Source full InChIKey generation failed") from exc
    if not _KEY.fullmatch(key or ""):
        raise DownstreamStructureError("Source lacks a valid standard full InChIKey")
    return IdentityResult(key, canonical, source_field=source_field)


def _provenance(source_kind: str, source_bytes: bytes, numbers: tuple, **metadata) -> dict:
    result = {
        "source_contract": SOURCE_CONTRACT, "source_kind": source_kind,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_bytes": len(source_bytes), "rdkit_version": rdBase.rdkitVersion,
        "source_atomic_number_order_hash": canonical_hash(numbers),
        "source_atom_map_policy": "source index i -> encoder source atom i; no permutation",
        "atom_encoding": "zero_based", "permutation_applied": False,
        "identity_policy": IDENTITY_POLICY,
        "mapping_audit_complete": False,
    }
    result.update(metadata)
    return result


def _coordinate(token: bytes) -> float:
    try:
        text = token.decode("ascii")
        if not _COORDINATE.fullmatch(text):
            raise ValueError
        value = float(text.replace("*^", "e").replace("D", "E").replace("d", "e"))
    except (UnicodeDecodeError, ValueError):
        raise DownstreamStructureError("Invalid XYZ coordinate") from None
    if not math.isfinite(value):
        raise DownstreamStructureError("Non-finite XYZ coordinate")
    return value


def _element(token: bytes) -> int:
    try:
        text = token.decode("ascii")
        if re.fullmatch(r"[0-9]+", text):
            number = int(text)
        elif re.fullmatch(r"[A-Z][a-z]?", text):
            with rdBase.BlockLogs():
                number = Chem.GetPeriodicTable().GetAtomicNumber(text)
        else:
            raise ValueError
    except (UnicodeDecodeError, RuntimeError, ValueError):
        raise DownstreamStructureError("Invalid XYZ element") from None
    if not 1 <= number <= 118:
        raise DownstreamStructureError("XYZ atomic number outside 1..118")
    return number


def read_xyz_structure(path: str | Path, *, units: str, max_atoms: int = MAX_ATOMS) -> SourceStructure:
    """Read exactly N structural rows in their original order, in explicit units.

    Hash the entire original bytes, but decode only N and columns 1..4 of N
    atom rows. Comment, fifth/extra columns and trailing annotations are opaque
    bytes. No bonds or full molecular identity are inferred from XYZ alone.
    """
    if units not in {"bohr", "angstrom"}:
        raise DownstreamStructureError("XYZ units must be explicitly bohr or angstrom")
    limit = _positive_count(max_atoms, "max_atoms")
    if limit > MAX_ATOMS:
        raise DownstreamStructureError("max_atoms exceeds bounded reader limit")
    path = Path(path)
    before = path.stat()
    if before.st_size > MAX_STRUCTURE_BYTES:
        raise DownstreamStructureError("XYZ exceeds bounded source size")
    with path.open("rb") as handle:
        source = handle.read(MAX_STRUCTURE_BYTES + 1)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise DownstreamStructureError("XYZ source changed during read")
    if len(source) > MAX_STRUCTURE_BYTES or len(source) != after.st_size:
        raise DownstreamStructureError("XYZ source exceeds limit or is truncated")
    stream = io.BytesIO(source)
    declaration = stream.readline(MAX_LINE_BYTES + 1)
    if (len(declaration) > MAX_LINE_BYTES or len(declaration.strip()) > 16
            or not re.fullmatch(rb"[0-9]+", declaration.strip())):
        raise DownstreamStructureError("Invalid XYZ atom-count declaration")
    count = int(declaration.strip())
    if not 0 < count <= limit:
        raise DownstreamStructureError("XYZ declared atom count outside bounded range")
    comment = stream.readline(MAX_LINE_BYTES + 1)
    if not comment or len(comment) > MAX_LINE_BYTES:
        raise DownstreamStructureError("XYZ comment line missing or exceeds bounded size")
    scale = BOHR_TO_ANGSTROM if units == "bohr" else 1.0
    numbers, positions = [], []
    for _ in range(count):
        line = stream.readline(MAX_LINE_BYTES + 1)
        if not line or len(line) > MAX_LINE_BYTES:
            raise DownstreamStructureError("XYZ atom row truncated or exceeds bounded size")
        fields = line.split(maxsplit=4)
        if len(fields) < 4:
            raise DownstreamStructureError("XYZ atom row lacks element and three coordinates")
        numbers.append(_element(fields[0]))
        xyz = tuple(_coordinate(token) * scale for token in fields[1:4])
        if not all(math.isfinite(value) for value in xyz):
            raise DownstreamStructureError("Converted XYZ coordinates are not finite")
        positions.append(xyz)
    numbers = tuple(numbers)
    metadata = _provenance(
        "xyz", source, numbers, source_path=str(path.resolve()), source_units=units,
        output_units="angstrom", coordinate_scale=scale, hydrogen_policy="retain source XYZ rows",
        source_scope="complete XYZ bytes", coordinate_rows_read=count,
        annotations="comment, extra atom columns and tail not interpreted",
        geometry_ready_for_encoder=True, identity_status="not inferred from coordinates",
    )
    return SourceStructure(numbers, tuple(z - 1 for z in numbers), tuple(range(count)),
                           tuple(positions), None, None, metadata)


def read_qm7_xyz(path: str | Path) -> SourceStructure:
    """The audited QM7 MAT exporter preserves Bohr coordinates, not angstrom."""
    return read_xyz_structure(path, units="bohr")


def _text_source(value: str, kind: str) -> bytes:
    if not isinstance(value, str) or not value.strip():
        raise DownstreamStructureError(f"Missing source {kind}")
    try:
        source = value.encode("utf-8")
    except UnicodeEncodeError:
        raise DownstreamStructureError(f"Invalid source {kind} encoding") from None
    if len(source) > 2 * 1024 * 1024:
        raise DownstreamStructureError(f"Source {kind} exceeds bounded size")
    return source


def _graph_structure(mol, source: bytes, kind: str, **metadata) -> SourceStructure:
    numbers = _atom_numbers(mol)
    identity = _identity_from_mol(mol, kind)
    # A conformer-bearing default key has a different input contract. Retain it
    # only for diagnosis; it cannot select or invalidate the graph grouping key.
    diagnostic_key, diagnostic_error = None, None
    with rdBase.BlockLogs():
        try:
            candidate = Chem.MolToInchiKey(Chem.Mol(mol))
            if _KEY.fullmatch(candidate or ""):
                diagnostic_key = candidate
            else:
                diagnostic_error = "InvalidDefaultSourceKey"
        except Exception as exc:
            diagnostic_error = type(exc).__name__
    for index, atom in enumerate(mol.GetAtoms()):
        atom.SetIntProp("_phase1_source_atom_index", index)
    provenance = _provenance(
        kind, source, numbers, source_scope=f"provided {kind} text only",
        attnsom_source_commit=ATTNSOM_COMMIT, geometry_ready_for_encoder=False,
        reader_identity_version=READER_IDENTITY_VERSION,
        identity_construction=IDENTITY_CONSTRUCTION,
        conformer_identity_input="ignored_on_copy",
        graph_identity_inchikey=identity.inchikey,
        source_mol_default_inchikey=diagnostic_key,
        source_mol_default_inchikey_scope="diagnostic only; never a grouping selector",
        source_mol_default_inchikey_error=diagnostic_error,
        source_mol_default_inchikey_differs_from_graph=(diagnostic_key != identity.inchikey
                                                      if diagnostic_key is not None else None),
        source_mol_default_inchikey_conformer_dimensions=["3D" if conf.Is3D() else "2D"
                                                        for conf in mol.GetConformers()],
        **metadata,
    )
    # Bind source/parser/identity method/version, including diagnostic context.
    # No self reference: this digest covers the complete preceding provenance.
    provenance["identity_provenance_hash"] = canonical_hash(provenance)
    # A source graph is not an approved 3D H0 input, even if the mol has coords.
    return SourceStructure(numbers, tuple(z - 1 for z in numbers), tuple(range(len(numbers))),
                           None, identity, mol, provenance)


def read_cyp_mol_block(block: str, *, expected_n_atoms: int | None = None) -> SourceStructure:
    """Preserve supplied SDF mol block atom order and all explicit hydrogens."""
    source = _text_source(block, "mol_block")
    with rdBase.BlockLogs():
        try:
            mol = Chem.MolFromMolBlock(block, sanitize=True, removeHs=False, strictParsing=True)
        except Exception as exc:
            raise DownstreamStructureError("CYP source mol block parsing failed") from exc
    if mol is None:
        raise DownstreamStructureError("CYP source mol block parsing failed")
    _atom_numbers(mol)  # Check the bounded graph before inspecting conformers.
    if expected_n_atoms is not None and _positive_count(expected_n_atoms, "expected_n_atoms") != mol.GetNumAtoms():
        raise DownstreamStructureError("CYP source n_atoms does not match mol block")
    dimensions = []
    for conformer in mol.GetConformers():
        dimensions.append("3D" if conformer.Is3D() else "2D")
        for i in range(mol.GetNumAtoms()):
            point = conformer.GetAtomPosition(i)
            if not all(math.isfinite(value) for value in (point.x, point.y, point.z)):
                raise DownstreamStructureError("CYP source mol block has non-finite coordinates")
    return _graph_structure(
        mol, source, "mol_block", parser="Chem.MolFromMolBlock",
        parser_options={"sanitize": True, "removeHs": False, "strictParsing": True},
        hydrogen_policy="retain source explicit hydrogens; do not AddHs or RemoveHs",
        source_conformer_dimensions=dimensions, coordinate_units="unverified",
        geometry_status="source dimension flags only; 3D suitability not audited",
        som_numbering="PRIMARY 1-based; other levels require independent contract",
    )


def read_az_raw_smiles(raw_smiles: str) -> SourceStructure:
    """Use author's default MolFromSmiles parser on the unmodified raw string.

    RDKit's default sanitize=True/removeHs=True/parseName=True is intentional;
    isotope hydrogens may survive. No extra RemoveHs, AddHs or SMILES roundtrip
    is applied. This function neither reads CSV files nor receives targets.
    """
    source = _text_source(raw_smiles, "raw_smiles")
    if len(source) > MAX_LINE_BYTES:
        raise DownstreamStructureError("AZ raw SMILES exceeds bounded size")
    with rdBase.BlockLogs():
        try:
            mol = Chem.MolFromSmiles(raw_smiles)
        except Exception as exc:
            raise DownstreamStructureError("AZ raw SMILES parsing failed") from exc
    if mol is None:
        raise DownstreamStructureError("AZ raw SMILES parsing failed")
    return _graph_structure(
        mol, source, "raw_smiles", parser="Chem.MolFromSmiles",
        parser_options={"sanitize": True, "removeHs": True, "parseName": True},
        hydrogen_policy="RDKit default SMILES parser; no subsequent H modification",
        source_conformer_dimensions=[], coordinate_units="no coordinates",
        som_numbering="0-based on atoms returned by default raw SMILES parser",
    )


def convert_som_indices(indices: Sequence[int] | str, *, index_base: int,
                        n_source_atoms: int) -> tuple[int, ...]:
    """Convert explicitly declared numbering once, preserving the supplied order.

    Accept integer sequences, or integers separated solely by whitespace or
    commas. Reject duplicates, mixed separators, floats, JSON wrappers and
    unordered containers. The caller supplies labels under its own protocol;
    this helper has no source-file or benchmark selection access.
    """
    if isinstance(index_base, bool) or not isinstance(index_base, Integral) or index_base not in (0, 1):
        raise DownstreamStructureError("index_base must be explicitly 0 or 1")
    count = _positive_count(n_source_atoms, "n_source_atoms")
    if isinstance(indices, str):
        text = indices.strip()
        if not text:
            values = []
        elif re.fullmatch(r"[0-9]+(?:\s*,\s*[0-9]+)*", text):
            values = [int(token) for token in text.split(",")]
        elif re.fullmatch(r"[0-9]+(?:\s+[0-9]+)*", text):
            values = [int(token) for token in text.split()]
        else:
            raise DownstreamStructureError("Ambiguous or invalid SoM index format")
    elif isinstance(indices, Sequence) and not isinstance(indices, (bytes, bytearray)):
        values = list(indices)
    else:
        raise DownstreamStructureError("SoM indices require an ordered integer sequence or strict text")
    if any(isinstance(value, bool) or not isinstance(value, Integral) for value in values):
        raise DownstreamStructureError("SoM indices must be integers, without coercion")
    result = tuple(int(value) - int(index_base) for value in values)
    if any(not 0 <= value < count for value in result):
        raise DownstreamStructureError("SoM index outside source atom range")
    if len(set(result)) != len(result):
        raise DownstreamStructureError("Duplicate SoM source atom indices")
    return result
