"""Expose the existing sealed geometry binding to an older source consumer.

The source reader returns MaterializedSourceSample(record, geometry, status,
provenance). The frozen materializer expects native_source_graph_binding as a
direct attribute, although the reader stores that exact field in provenance.
Original-source geometry also retains the FP64 hash but not a tensor field;
transport exposes the same existing conformer only after exact hash checks.
This adapter neither constructs a binding nor changes any source/target value.
"""
from __future__ import annotations

from copy import deepcopy
import math


class SourceSampleCompatibilityError(ValueError):
    pass


def require(value, message):
    if not value:
        raise SourceSampleCompatibilityError(message)


def checked_existing_binding(records, sample, *, expected_record=None):
    require(type(sample) is records.MaterializedSourceSample, 'Known source MaterializedSourceSample required')
    require(expected_record is None or sample.record is expected_record, 'Geometry sample changed its original source record')
    records._validate_record(sample.record)
    proof = sample.provenance
    records._sealed(proof, 'sample_provenance_sha256')
    require(proof.get('schema_version') == records.SAMPLE_SCHEMA
        and proof.get('record_binding_sha256') == sample.record.provenance['record_binding_sha256']
        and proof.get('status') == sample.status and proof.get('source_preserved') is True
        and proof.get('member_and_fold_preserved') is True and proof.get('annotation_values_decoded') is False,
        'Original geometry sample/source/member provenance differs')
    geometry_sha = None
    if sample.geometry is not None:
        records._validate_geometry_tensors(sample.geometry, sample.record.structure)
        geometry_sha = sample.geometry.provenance['geometry_provenance_sha256']
    require(proof.get('geometry_provenance_sha256') == geometry_sha, 'Original sample/geometry SHA association differs')
    require('native_source_graph_binding' in proof, 'Existing native source graph binding field is absent; no default is allowed')
    binding = proof['native_source_graph_binding']
    require(proof.get('native_source_graph_binding_scope') ==
        'ready cached geometry only; not applicable to original source or failed candidates',
        'Original native binding scope differs')
    if binding is None:
        require(proof['geometry_basis'] == 'ORIGINAL_SOURCE_3D' or sample.status == 'NOT_READY',
            'A ready cached sample cannot invent a missing native graph binding')
    else:
        require(proof['geometry_basis'] == 'SAVED_GENERATED_CANDIDATE' and sample.status == 'GEOMETRY_READY'
            and isinstance(binding, dict), 'Native graph binding is inconsistent with original geometry status')
        records._sealed(binding, 'native_source_graph_binding_sha256')
        require(binding.get('current_native_graph_sha256') == sample.record.provenance['native_graph_sha256'],
            'Existing native graph binding belongs to another structural record')
    if hasattr(sample, 'native_source_graph_binding'):
        require(sample.native_source_graph_binding == binding, 'Existing direct field and provenance disagree')
    return deepcopy(binding)


class CompatibleMaterializedSample:
    __slots__ = ('_records', '_sample', '_record', '_geometry')

    def __init__(self, records, sample, expected_record):
        checked_existing_binding(records, sample, expected_record=expected_record)
        self._records, self._sample, self._record = records, sample, expected_record
        self._geometry = (CompatibleSourceGeometry(records, sample)
            if sample.provenance['geometry_basis'] == 'ORIGINAL_SOURCE_3D' else sample.geometry)

    def __getattr__(self, name):
        return getattr(self._sample, name)

    @property
    def native_source_graph_binding(self):
        # Recheck the same sealed source on access; never mutate or reseal it.
        return checked_existing_binding(self._records, self._sample, expected_record=self._record)

    @property
    def geometry(self):
        return self._geometry


def checked_source_coordinates64(records, sample):
    """Copy the original same conformer, checking its pre-existing FP64 hash.

    The source reader discarded its FP64 tensor after recording the hash.
    Recover no values from FP32: read the unchanged original parsed conformer,
    validate its exact FP64 bytes and literal once-cast encoder bytes instead.
    """
    import torch
    checked_existing_binding(records, sample, expected_record=sample.record)
    require(sample.provenance['geometry_basis'] == 'ORIGINAL_SOURCE_3D'
        and sample.status == 'GEOMETRY_READY' and type(sample.geometry) is records.SourceEncoderGeometry,
        'Exact original-source ready geometry type required for coordinate transport')
    structure, geometry = sample.record.structure, sample.geometry
    proof, mol = geometry.provenance, structure.mol
    from rdkit import Chem
    before = mol.ToBinary(Chem.PropertyPickleOptions.AllProps)
    try:
        require(mol.GetNumConformers() == 1 and mol.GetConformer().Is3D() is True
            and mol.GetNumAtoms() == structure.n_atoms
            and tuple(atom.GetAtomicNum() for atom in mol.GetAtoms()) == structure.atomic_numbers
            and structure.source_atom_map == tuple(range(structure.n_atoms)),
            'Exactly one original 3D conformer in unchanged native atom order is required')
        require(all(atom.HasProp('_phase1_source_atom_index')
            and atom.GetIntProp('_phase1_source_atom_index') == i for i, atom in enumerate(mol.GetAtoms())),
            'Original source atom markers differ')
        require(proof.get('source_units') == proof.get('output_units') == 'angstrom'
            and proof.get('coordinate_scale') == 1.0
            and proof.get('source_block_sha256') == sample.record.provenance['structural_sha256'],
            'Original source coordinate units/block provenance differs')
        conformer = mol.GetConformer(); coordinates = []
        for i in range(structure.n_atoms):
            point = conformer.GetAtomPosition(i); xyz = (point.x, point.y, point.z)
            require(all(math.isfinite(value) for value in xyz), 'Nonfinite original conformer coordinate')
            coordinates.append(xyz)
        value = torch.tensor(coordinates, dtype=torch.float64, device='cpu')
        require(records.geometry_tensor_sha256(value) == proof.get('source_coordinates_float64_sha256'),
            'Original source FP64 coordinate bytes differ from the sealed geometry proof')
        positions = value.to(dtype=torch.float32)
        require(records.geometry_tensor_sha256(positions) == proof['encoder_tensor_hashes']['pos']
            and records.geometry_tensor_sha256(positions) == records.geometry_tensor_sha256(geometry.encoder_batch.pos),
            'Original source once-cast FP32 bytes differ from the sealed native encoder positions')
        return value.clone()
    finally:
        require(mol.ToBinary(Chem.PropertyPickleOptions.AllProps) == before,
            'Original conformer changed during coordinate field transport')


class CompatibleSourceGeometry:
    """Read-only field view over the existing source geometry and conformer."""
    __slots__ = ('_records', '_sample')

    def __init__(self, records, sample):
        checked_source_coordinates64(records, sample)
        self._records, self._sample = records, sample

    def __getattr__(self, name):
        return getattr(self._sample.geometry, name)

    @property
    def native_coordinates_float64(self):
        return checked_source_coordinates64(self._records, self._sample)


class CompatibleSourceRecords:
    """Delegate the source module with only the verified legacy field views."""
    def __init__(self, records):
        self._records = records

    def __getattr__(self, name):
        return getattr(self._records, name)

    def materialize_geometry(self, record, *, candidates, source_units):
        sample = self._records.materialize_geometry(record, candidates=candidates, source_units=source_units)
        return CompatibleMaterializedSample(self._records, sample, record)
