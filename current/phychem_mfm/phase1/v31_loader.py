"""MFM4 read-only data layer for model-line taskbook v2.

The data line owns field selection, channel aggregation and TRAIN statistics.
This module does not fit, infer or alter those scientific definitions.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import struct

import numpy as np
import torch


DTYPES = {1: 'u1', 2: '<i2', 3: '<u2', 4: '<u4', 5: '<i4', 6: '<f4'}
ARRAY_IDS = {'d20': 4, 'mol_labels': 23, 'atom_labels': 24,
             'atom_vectors': 25, 'pair_labels': 27}
ORDER_IDS = {'PM7': {'fixed_random': 7, 'energy': 9, 'diversity': 10},
             'UFF': {'fixed_random': 8, 'energy': 11, 'diversity': 12}}


def decode_mfm4(payload):
    """Decode numeric arrays without pickle, hashes or a second read."""
    data = memoryview(payload)
    if len(data) < 8:
        raise ValueError('Truncated MFM4 header')
    magic, version, count = struct.unpack_from('<4sHH', data)
    if magic != b'MFM4' or version != 1:
        raise ValueError('Expected MFM4 version 1')
    result, offset, previous = {}, 8, -1
    for _ in range(count):
        if offset + 4 > len(data):
            raise ValueError('Truncated array header')
        key, dtype, ndim = struct.unpack_from('<HBB', data, offset)
        offset += 4
        if key <= previous or dtype not in DTYPES or offset + 4 * ndim > len(data):
            raise ValueError('Invalid MFM4 array descriptor')
        previous = key
        shape = struct.unpack_from('<' + 'I' * ndim, data, offset)
        offset += 4 * ndim
        size = math.prod(shape)
        nbytes = size * np.dtype(DTYPES[dtype]).itemsize
        end = offset + nbytes
        padded = (end + 3) // 4 * 4
        if padded > len(data) or any(data[end:padded]):
            raise ValueError('Truncated MFM4 data or nonzero padding')
        result[key] = np.frombuffer(data, dtype=DTYPES[dtype], count=size,
                                    offset=offset).reshape(shape).copy()
        offset = padded
    if offset != len(data):
        raise ValueError('Trailing MFM4 bytes')
    return result


def record_key(kind, molecule, conformer=None):
    if kind == 'M':
        return b'M' + struct.pack('>I', molecule)
    if kind not in ('P', 'U'):
        raise ValueError('Unknown record kind')
    return kind.encode() + struct.pack('>IH', molecule, conformer)


def allowed_conformers(molecule, *, source='PM7', order='fixed_random',
                       k=None, diagnostic=False):
    """Exclude D5 before first-k selection; never invent an unavailable order."""
    if source not in ORDER_IDS or order not in ORDER_IDS[source]:
        raise ValueError('Unknown geometry source or ordering')
    if k is not None and (type(k) is not int or k <= 0):
        raise ValueError('k must be a positive integer or None (all)')
    array_id = ORDER_IDS[source][order]
    if array_id not in molecule:
        raise ValueError('Requested conformation order is not published')
    values = molecule[array_id].astype(np.int64)
    holdout = molecule[13 if source == 'PM7' else 14].astype(bool)
    values = values[holdout[values] if diagnostic else ~holdout[values]]
    return values if k is None else values[:k]


def aggregate_r73(arrays, codebook, rule):
    """Sum explicit channel groups per directed pair, retaining missingness.

    rule supplies the data-line channel mapping, classification code column,
    and missing-component/empty-sum policies. No orbital code is guessed.
    """
    if rule.get('reduction') != 'sum':
        raise ValueError('r73 requires the published sum reduction')
    axis = rule.get('code_column')
    if axis not in (0, 1, 2):
        raise ValueError('r73 needs an explicit classification code column')
    groups = rule.get('channels')
    if not isinstance(groups, dict) or set(groups) != {'sigma', 'pi'}:
        raise ValueError('Data-line sigma/pi channel mapping is required')
    if set(groups['sigma']) & set(groups['pi']):
        raise ValueError('r73 sigma/pi channel groups overlap')
    missing = rule.get('missing_components')
    empty = rule.get('empty_sum')
    if missing not in ('propagate', 'ignore') or empty not in ('nan', 'zero'):
        raise ValueError('Explicit r73 missing/empty policies are required')
    rows, codes, values = arrays[31], arrays[32][:, axis], arrays[34]
    output = np.full((len(arrays[26]), 2), np.nan, dtype=np.float32)
    for column, name in enumerate(('sigma', 'pi')):
        selected_codes = []
        for code in groups[name]:
            selected_codes.append(codebook.index(code) if isinstance(code, str) else code)
        selected = np.isin(codes, selected_codes)
        observed = selected & ~np.isnan(values)
        sums = np.zeros(len(output), dtype=np.float32)
        counts = np.zeros(len(output), dtype=np.int64)
        np.add.at(sums, rows[observed], values[observed])
        np.add.at(counts, rows[observed], 1)
        if empty == 'zero':
            output[:, column] = sums
        else:
            output[counts > 0, column] = sums[counts > 0]
        if missing == 'propagate':
            output[rows[selected & np.isnan(values)], column] = np.nan
    return output


@dataclass
class V31Target:
    raw: np.ndarray
    values: np.ndarray
    valid: np.ndarray
    group: str
    family: str
    level: str
    representation: str
    loss_enabled: bool
    pair_index: np.ndarray | None = None


def normalize_values(raw, specification, *, Z):
    """Apply explicit D4 affine/element-reference parameters, never fit them."""
    if specification.get('fit_role') != 'TRAIN':
        raise ValueError('Normalization must come from TRAIN')
    values = np.asarray(raw, dtype=np.float32).copy()
    reference = specification.get('element_reference')
    if reference is not None:
        counts = {int(z): int((Z == z).sum()) for z in np.unique(Z)}
        offset = reference.get('intercept', 0.) + sum(
            counts.get(int(z), 0) * coefficient
            for z, coefficient in zip(reference['basis'], reference['coefficients']))
        values -= np.float32(offset)
    if 'lower' in specification or 'upper' in specification:
        values = np.clip(values, specification.get('lower', -np.inf),
                         specification.get('upper', np.inf))
    center = np.asarray(specification['center'], dtype=np.float32)
    scale = np.asarray(specification['scale'], dtype=np.float32)
    if not np.all(np.isfinite(scale) & (scale > 0)):
        raise ValueError('D4 scale must be finite and positive')
    return (values - center) / scale


class TrainingView:
    """Select fields and parameters from the data-line training-view manifest.

    Each field names an existing schema field_key (or r73 sigma/pi output),
    with an explicit D4 normalization. A path to that mapping may be supplied
    instead of embedding it. This simple public JSON interface carries no SHA
    or acceptance receipts.
    """
    def __init__(self, schema, manifest):
        self.schema, self.manifest = schema, manifest
        fields = manifest.get('fields')
        if not isinstance(fields, list) or not fields:
            raise ValueError('A nonempty data-line training field list is required')
        self.fields = [field for field in fields if field.get('enabled', True)]
        self.normalizations = manifest.get('normalizations', {})
        if isinstance(self.normalizations, str):
            self.normalizations = json.loads(Path(self.normalizations).read_text())
        self.locations = {}
        for name, columns in schema['columns'].items():
            for column in columns:
                self.locations.setdefault(column['field_key'], []).append(
                    (name, column['column_index']))
        names = [f['name'] for f in self.fields]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate training fields')
        for field in self.fields:
            key = field.get('field_key', field['name'])
            if field.get('registry_id') == 674 or '.r674.' in key:
                raise ValueError('r674 cannot be enabled for training')
            if not field.get('r73_component') and key not in self.locations:
                raise ValueError('Training field is absent from schema: ' + key)

    def extract(self, molecule, conformer):
        output, r73 = {}, None
        for field in self.fields:
            name = field['name']
            if field.get('r73_component'):
                if 34 not in conformer:
                    continue  # U geometry-only records have no P-prime labels.
                if r73 is None:
                    r73 = aggregate_r73(conformer, self.schema['r73_channel_codebook'],
                                        self.manifest['r73'])
                raw = r73[:, ['sigma', 'pi'].index(field['r73_component'])][:, None]
                array_name = 'pair_labels'
            else:
                key = field.get('field_key', name)
                locations = self.locations[key]
                array_name = locations[0][0]
                source = molecule if array_name == 'd20' else conformer
                array_id = ARRAY_IDS[array_name]
                if array_id not in source:
                    continue
                cols = [c for _, c in locations]
                array = source[array_id]
                if array_name == 'atom_vectors':
                    raw = array[:, cols[0], :]
                else:
                    raw = array[..., cols]
                    if raw.ndim == 1:
                        raw = raw[None, :]
            raw = np.asarray(raw, dtype=np.float32)
            valid = ~np.isnan(raw)
            spec = field.get('normalization', self.normalizations.get(name))
            if spec is None:
                raise ValueError('Missing D4 normalization for ' + name)
            values = normalize_values(raw, spec, Z=molecule[1])
            output[name] = V31Target(raw, values, valid, field['group'], field['family'],
                field['level'], field.get('representation', 'scalar'), True,
                conformer.get(26) if array_name == 'pair_labels' else None)
        return output


class MFM4Dataset:
    """Per-process LMDB handles, molecule-first sampling and explicit geometry."""
    def __init__(self, root, *, split='TRAIN', training_view=None, source='PM7',
                 order='fixed_random', k=None, diagnostic=False, molecule_indices=None):
        self.root = Path(root)
        self.directory = self.root / ('v31_pilot_' + split)
        if not self.directory.exists():
            self.directory = self.root / split
        self.schema = json.loads((self.root / 'schema.json').read_text())
        self.manifest = json.loads((self.directory / 'manifest.json').read_text())
        self.source, self.order, self.k, self.diagnostic = source, order, k, diagnostic
        if source not in ('PM7', 'UFF'):
            raise ValueError('Geometry source must be PM7 or UFF')
        if isinstance(training_view, (str, Path)):
            training_view = json.loads(Path(training_view).read_text())
        self.view = None if training_view is None else TrainingView(self.schema, training_view)
        self.indices = (np.arange(self.manifest['molecule_count']) if molecule_indices is None
                        else np.asarray(molecule_indices, dtype=np.int64))
        self._env = self._pid = self._ids = None

    def __len__(self):
        return len(self.indices)

    def __getstate__(self):
        state = dict(self.__dict__)
        state['_env'] = state['_pid'] = None
        return state

    def _open(self):
        if self._pid != os.getpid():
            self.close()
            import lmdb
            self._env = lmdb.open(str(self.directory), readonly=True, lock=False,
                                  readahead=False, max_readers=512)
            self._pid = os.getpid()

    def record(self, kind, molecule, conformer=None):
        self._open()
        with self._env.begin() as txn:
            payload = txn.get(record_key(kind, molecule, conformer))
        if payload is None:
            raise KeyError((kind, molecule, conformer))
        return decode_mfm4(payload)

    def choices(self, molecule):
        return allowed_conformers(self.record('M', molecule), source=self.source,
                                  order=self.order, k=self.k, diagnostic=self.diagnostic)

    def sample(self, rng):
        # Conditional uniform draws are independent of conformation counts.
        molecule = int(rng.choice(self.indices))
        choices = self.choices(molecule)
        if not len(choices):
            raise ValueError('Selected molecule has no allowed conformations')
        return self.read(molecule, int(rng.choice(choices)))

    def read(self, molecule, conformer):
        m = self.record('M', molecule)
        if conformer not in allowed_conformers(m, source=self.source, order=self.order,
                                               k=self.k, diagnostic=self.diagnostic):
            raise ValueError('Conformer is excluded by the training/diagnostic manifest')
        c = self.record('P' if self.source == 'PM7' else 'U', molecule, conformer)
        return {'molecule_index': molecule, 'conformer_index': conformer,
                'geometry_source': self.source, 'Z': m[1], 'pos': c[21],
                'pos_perturbed': c.get(22), 'bonds': m[2], 'bond_order': m[3],
                'targets': {} if self.view is None else self.view.extract(m, c)}

    def molecule_mean(self, molecule):
        """Mean allowed-conformer labels, aligning directed pair endpoints."""
        samples = [self.read(molecule, int(c)) for c in self.choices(molecule)]
        if not samples:
            raise ValueError('No conformations available for averaging')
        output = {}
        for name in set.intersection(*(set(s['targets']) for s in samples)):
            targets = [s['targets'][name] for s in samples]
            template = targets[0]
            if template.pair_index is not None:
                pairs = sorted(set(tuple(p) for t in targets for p in t.pair_index.tolist()))
                index = {p: i for i, p in enumerate(pairs)}
                raw = np.full((len(targets), len(pairs), template.raw.shape[-1]), np.nan,
                              dtype=np.float32)
                for i, target in enumerate(targets):
                    for j, pair in enumerate(target.pair_index.tolist()):
                        raw[i, index[tuple(pair)]] = target.raw[j]
                pair_index = np.asarray(pairs, dtype=np.int64).reshape(-1, 2)
            else:
                raw = np.stack([t.raw for t in targets])
                pair_index = None
            count = (~np.isnan(raw)).sum(0)
            mean = np.divide(np.nansum(raw, axis=0), count,
                             out=np.full(raw.shape[1:], np.nan), where=count > 0).astype(np.float32)
            field = next(f for f in self.view.fields if f['name'] == name)
            spec = field.get('normalization', self.view.normalizations.get(name))
            output[name] = V31Target(mean, normalize_values(mean, spec, Z=samples[0]['Z']),
                ~np.isnan(mean), template.group, template.family, template.level,
                template.representation, template.loss_enabled, pair_index)
        return output

    def identities(self):
        """Read the external reversible ID map when identities are needed."""
        if self._ids is None:
            import pyarrow.parquet as pq
            self._ids = pq.read_table(self.directory / 'id_map.parquet')
        return self._ids

    def close(self):
        if self._env is not None:
            self._env.close()
        self._env = self._pid = None


def enabled_encoder_fields(fields, encoder):
    """Coordinate-free encoders automatically omit coordinate/vector heads."""
    if getattr(encoder, 'accepts_coordinates', True):
        return tuple(fields)
    return tuple(f for f in fields if f.get('representation', 'scalar') != 'vector'
                 and f.get('kind') != 'denoise_eps_mse')


def field_weights(fields, *, groups, families=None, fixed_full_condition=False):
    """Equal groups/fields, with optional frozen full-condition field weights."""
    full = [f for f in fields if f.get('enabled', True) and f['group'] in groups]
    selected = [f for f in full if families is None or f['family'] in families]
    denominator = full if fixed_full_condition else selected
    counts = {g: sum(f['group'] == g for f in denominator) for g in groups}
    return {f['name']: 1. / (len(groups) * counts[f['group']]) for f in selected}


class SampleMilestones:
    def __init__(self, consumed=0):
        self.consumed = consumed

    def advance(self, count):
        before, self.consumed = self.consumed, self.consumed + count
        return tuple(n for n in (1_000_000 * 2 ** i for i in range(7))
                     if before < n <= self.consumed)
