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

from .v31_normalization_routes import resolve_normalization_routes


DTYPES = {1: 'u1', 2: '<i2', 3: '<u2', 4: '<u4', 5: '<i4', 6: '<f4'}
ARRAY_IDS = {'d20': 4, 'mol_labels': 23, 'atom_labels': 24,
             'atom_vectors': 25, 'pair_labels': 27}
ORDER_IDS = {'PM7': {'fixed_random': 7, 'energy': 9, 'diversity': 10},
             'UFF': {'fixed_random': 8, 'energy': 11, 'diversity': 12}}


def decode_mfm4(payload, *, array_ids=None):
    """Decode selected numeric arrays, validating the entire framing once."""
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
        if array_ids is None or key in array_ids:
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
                       k=None, diagnostic=False, pprime=False, evaluation=False):
    """Exclude D5 before first-k selection; never invent an unavailable order."""
    if source not in ORDER_IDS or order not in ORDER_IDS[source]:
        raise ValueError('Unknown geometry source or ordering')
    if k is not None and (type(k) is not int or k <= 0):
        raise ValueError('k must be a positive integer or None (all)')
    holdout = molecule[13 if source == 'PM7' else 14].astype(bool)
    if diagnostic:
        # D6 retains actual D5 geometries outside ordinary source orders.
        values = np.flatnonzero(holdout)
        return values if k is None else values[:k]
    if pprime and source != 'UFF':
        raise ValueError('Pprime eligibility applies only to UFF')
    if pprime and evaluation:
        # M18 is TRAIN-only. FULL evaluates actual U labels with their masks.
        return np.flatnonzero(~holdout)
    array_id = ORDER_IDS[source][order]
    if array_id not in molecule:
        raise ValueError('Requested conformation order is not published')
    values = molecule[array_id].astype(np.int64)
    if source == 'UFF':
        if pprime:
            if 18 not in molecule:
                raise ValueError('Pprime training requires published M18 eligibility')
            eligible = molecule[18].astype(bool) & ~holdout
            if np.any(eligible & ~np.isin(np.arange(len(eligible)), values)):
                raise ValueError('Eligible Pprime geometry lacks the published source order')
        else:
            eligible = (molecule[17].astype(bool) if 17 in molecule
                        else np.ones(len(holdout), dtype=bool)) & ~holdout
        values = values[eligible[values]]
    else:
        values = values[~holdout[values]]
    return values if k is None else values[:k]


def aggregate_r73(arrays, codebook, rule):
    """Sum explicit channel groups per directed pair, retaining missingness.

    rule supplies the data-line channel mapping, classification code column,
    and missing-component/empty-sum policies. No orbital code is guessed.
    """
    published_blocks = rule.get('code_to_symmetry')
    if published_blocks is not None:
        # Frozen training_view_v1: BOTH basis axes must belong to the block.
        suffixes = rule.get('symmetry_by_label_suffix')
        if suffixes is not None:
            groups = {name: [i for i, label in enumerate(codebook) if any(
                block == name and suffix != 'other' and label.endswith(suffix)
                for suffix, block in suffixes.items())] for name in ('sigma', 'pi')}
        elif rule.get('codebook'):
            labels = rule['codebook']
            groups = {name: [i for i, label in enumerate(codebook) if label in {
                labels[int(code)] for code, block in published_blocks.items() if block == name}]
                for name in ('sigma', 'pi')}
        else:
            groups = {name: [int(code) for code, block in published_blocks.items()
                             if block == name] for name in ('sigma', 'pi')}
        axes, missing, empty = (0, 1), 'propagate', 'nan'
    elif rule.get('reduction') != 'sum':
        raise ValueError('r73 requires the published sum reduction')
    else:
        axis = rule.get('code_column')
        if axis not in (0, 1, 2):
            raise ValueError('r73 needs an explicit classification code column')
        axes = (axis,)
        groups = rule.get('channels')
        missing, empty = rule.get('missing_components'), rule.get('empty_sum')
    if not isinstance(groups, dict) or set(groups) != {'sigma', 'pi'}:
        raise ValueError('Data-line sigma/pi channel mapping is required')
    if set(groups['sigma']) & set(groups['pi']):
        raise ValueError('r73 sigma/pi channel groups overlap')
    if missing not in ('propagate', 'ignore') or empty not in ('nan', 'zero'):
        raise ValueError('Explicit r73 missing/empty policies are required')
    rows, codes, values = arrays[31], arrays[32], arrays[34]
    output = np.full((len(arrays[26]), 2), np.nan, dtype=np.float32)
    for column, name in enumerate(('sigma', 'pi')):
        selected_codes = []
        for code in groups[name]:
            selected_codes.append(codebook.index(code) if isinstance(code, str) else code)
        selected = np.isin(codes[:, axes], selected_codes).all(axis=1)
        observed = selected & np.isfinite(values)
        sums = np.zeros(len(output), dtype=np.float64)
        counts = np.zeros(len(output), dtype=np.int64)
        np.add.at(sums, rows[observed], values[observed])
        np.add.at(counts, rows[observed], 1)
        if empty == 'zero':
            output[:, column] = sums
        else:
            output[counts > 0, column] = sums[counts > 0]
        if missing == 'propagate':
            output[rows[selected & ~np.isfinite(values)], column] = np.nan
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
    fitted = specification.get('p_recipe_fitted', False)
    dtype = np.float64 if fitted or np.asarray(raw).dtype == np.float64 else np.float32
    values = np.asarray(raw, dtype=dtype).copy()
    reference = specification.get('element_reference')
    if reference is not None:
        counts = {int(z): int((Z == z).sum()) for z in np.unique(Z)}
        offset = reference.get('intercept', 0.) + sum(
            counts.get(int(z), 0) * coefficient
            for z, coefficient in zip(reference['basis'], reference['coefficients']))
        if not np.isfinite(offset):
            raise ValueError('D4 element reference must be finite')
        values -= dtype(offset)
    # D4 winsorizes the statistical fit, not the original training labels.
    # Quantile bounds may be present as provenance; never clip target values.
    center = np.asarray(specification['center'], dtype=dtype)
    scale = np.asarray(specification['scale'], dtype=dtype)
    if not np.all(np.isfinite(scale) & (scale > 0)):
        raise ValueError('D4 scale must be finite and positive')
    if not np.all(np.isfinite(center)):
        raise ValueError('D4 center must be finite')
    result = (values - center) / scale
    return result.astype(np.float32) if dtype == np.float64 else result


class TrainingView:
    """Select fields and parameters from the data-line training-view manifest.

    Each field names an existing schema field_key (or r73 sigma/pi output),
    with an explicit D4 normalization. A path to that mapping may be supplied
    instead of embedding it. This simple public JSON interface carries no SHA
    or acceptance receipts.
    """
    def __init__(self, schema, manifest, normalizations=None, *, normalization_dataset='P_D'):
        self.schema, self.manifest = schema, manifest
        self.normalization_dataset = normalization_dataset
        fields = manifest.get('fields')
        if not isinstance(fields, list) or not fields:
            raise ValueError('A nonempty data-line training field list is required')
        self.fields = []
        metadata = {field['field_key']: field for field in schema.get('fields', [])}
        metadata.update({column['field_key']: column
                         for columns in schema['columns'].values() for column in columns})
        for original in fields:
            if not original.get('enabled', True):
                continue
            field = dict(original)
            field.setdefault('name', field.get('field_key'))
            source = field.get('source_field', field.get('field_key', field['name']))
            meta = metadata.get(source, {})
            for key in ('family', 'level'):
                if key not in field:
                    field[key] = meta[key]
            field.setdefault('representation', meta.get('kind', 'scalar'))
            if field.get('registry_id') == 73 and field['name'].rsplit('.', 1)[-1] in ('sigma', 'pi'):
                field['r73_component'] = field['name'].rsplit('.', 1)[-1]
                preferred = field.get('preferred_schema_selector')
                if preferred:
                    derived = schema.get(preferred['mapping'], {}).get(preferred['target'])
                    if derived is not None:
                        field['_derived_r73_column'] = derived[preferred['column_key']]
            self.fields.append(field)
        self.normalizations = (manifest.get('normalizations', {})
                               if normalizations is None else normalizations)
        if isinstance(self.normalizations, str):
            self.normalizations = json.loads(Path(self.normalizations).read_text())
        from .v31_normalization_routes import inherit_source_loss_policy
        inherit_source_loss_policy(self.normalizations, self.fields, dataset=normalization_dataset)
        normalization_fields = [field for field in self.fields
                                if normalization_dataset != 'Pprime' or field['group'] == 'P']
        self.normalizations = resolve_normalization_routes(self.normalizations, normalization_fields,
            dataset=normalization_dataset)
        self.locations = {}
        for name, columns in schema['columns'].items():
            for ordinal, column in enumerate(columns):
                self.locations.setdefault(column['field_key'], []).append(
                    (name, column.get('column_index', ordinal)))
        for target_id, layout in schema.get('target_layout', {}).items():
            if layout['array_name'] in ARRAY_IDS:
                self.locations[target_id] = [(layout['array_name'], c)
                                             for c in layout['column_indices']]
        names = [f['name'] for f in self.fields]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate training fields')
        for field in self.fields:
            key = field.get('target_id', field.get('field_key', field['name']))
            if field.get('registry_id') == 674 or '.r674.' in key:
                raise ValueError('r674 cannot be enabled for training')
            selectors = field.get('selectors')
            if selectors and not field.get('r73_component'):
                self.locations[field['name']] = [(item[2], item[1]) for item in selectors]
                # Frozen view field_keys remain independent even if they share a native target.
                field['_location_key'] = field['name']
            if not field.get('r73_component') and field.get('_location_key', key) not in self.locations:
                raise ValueError('Training field is absent from schema: ' + key)

    def extract(self, molecule, conformer, *, mask_overrides=None):
        output, r73 = {}, None
        for field in self.fields:
            if self.normalization_dataset == 'Pprime' and field['group'] != 'P':
                continue
            name = field['name']
            if field.get('r73_component'):
                if '_derived_r73_column' in field:
                    if 27 not in conformer:
                        continue
                    raw = conformer[27][:, [field['_derived_r73_column']]]
                else:
                    if 34 not in conformer:
                        continue  # U geometry-only records have no P-prime labels.
                    if r73 is None:
                        r73 = aggregate_r73(conformer, self.schema['r73_channel_codebook'],
                                            self.manifest['r73'])
                    raw = r73[:, ['sigma', 'pi'].index(field['r73_component'])][:, None]
                array_name = 'pair_labels'
            else:
                key = field.get('_location_key', field.get('target_id', field.get('field_key', name)))
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
            if mask_overrides and field.get('field_key', name) in mask_overrides:
                from .v31_record_masks import apply_published_scalar_mask
                raw = apply_published_scalar_mask(raw, mask_overrides[field.get('field_key', name)])
            valid = ~np.isnan(raw)
            spec = field.get('normalization', self.normalizations.get(name))
            if spec is None:
                raise ValueError('Missing D4 normalization for ' + name)
            values = normalize_values(raw, spec, Z=molecule[1])
            output[name] = V31Target(raw, values, valid, field['group'], field['family'],
                field['level'], field.get('representation', 'scalar'), field.get('loss_enabled', True),
                conformer.get(26) if array_name == 'pair_labels' else None)
        return output


def split_metadata(root, split):
    """Follow released D6 locations while retaining the delivered pilot layout."""
    delivery_path = root / 'manifest.json'
    delivery = json.loads(delivery_path.read_text()) if delivery_path.is_file() else {}
    if 'split_roots' in delivery:
        roots = delivery['split_roots']
        if not isinstance(roots, dict) or split not in roots:
            raise ValueError(f'Split {split} is not delivered')
        location = roots[split]
        if not isinstance(location, str) or not location:
            raise ValueError('Invalid published split location')
        directory = Path(location)
        if not directory.is_absolute():
            directory = root / directory
    else:
        directory = root / ('v31_pilot_' + split)
        if not directory.exists():
            directory = root / split
    counts = delivery.get('molecules', {})
    declared = counts.get(split) if isinstance(counts, dict) else None
    metadata_path = directory / 'manifest.json'
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text())
    elif 'split_roots' in delivery and declared is not None:
        # Full D6 publishes its per-role counts once, in the schema root.
        metadata = {'molecule_count': declared}
    else:
        metadata = json.loads(metadata_path.read_text())
    count = metadata.get('molecule_count')
    if type(count) is not int or count < 0:
        raise ValueError('Invalid molecule_count in delivered metadata')
    if declared is not None and declared != count:
        raise ValueError('Delivered root and split molecule counts disagree')
    return directory, metadata


class MFM4Dataset:
    """Per-process LMDB handles, molecule-first sampling and explicit geometry."""
    def __init__(self, root, *, split='TRAIN', training_view=None, source='PM7',
                 order='fixed_random', k=None, diagnostic=False, molecule_indices=None,
                 normalizations=None, pprime=False, geometry_only=False, p_f64_sidecar=None):
        if geometry_only and training_view is not None:
            raise ValueError('Geometry-only reading cannot discard a requested training view')
        self.geometry_only = geometry_only
        self.root = Path(root)
        self.directory, self.manifest = split_metadata(self.root, split)
        self.schema = json.loads((self.root / 'schema.json').read_text())
        self._p_f64_sidecar = None
        if p_f64_sidecar is not None:
            from .p_f64_sidecar import PFloat64Sidecar
            self._p_f64_sidecar = PFloat64Sidecar(p_f64_sidecar, split, self.directory)
        self.source, self.order, self.k, self.diagnostic = source, order, k, diagnostic
        self.pprime, self.evaluation = pprime, split != 'TRAIN'
        if source not in ('PM7', 'UFF'):
            raise ValueError('Geometry source must be PM7 or UFF')
        if isinstance(training_view, (str, Path)):
            training_view = json.loads(Path(training_view).read_text())
        self.view = (None if training_view is None else
                     TrainingView(self.schema, training_view, normalizations,
                         normalization_dataset='Pprime' if pprime else 'P_D'))
        self.indices = (np.arange(self.manifest['molecule_count']) if molecule_indices is None
                        else np.asarray(molecule_indices, dtype=np.int64))
        self._index_set = set(map(int, self.indices))
        self._env = self._pid = self._ids = None
        self._molecules = {}
        from .v31_record_masks import published_record_masks
        self._record_masks = ({} if geometry_only or training_view is None else
            published_record_masks(normalizations or {}, self.directory,
                dataset='Pprime' if pprime else 'P_D'))

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
        if kind == 'M' and molecule in self._molecules:
            return self._molecules[molecule]
        self._open()
        with self._env.begin(buffers=True) as txn:
            payload = txn.get(record_key(kind, molecule, conformer))
            if payload is None:
                raise KeyError((kind, molecule, conformer))
            # Retained arrays own their memory before the LMDB transaction ends.
            selected = {21, 22} if self.geometry_only and kind != 'M' else None
            result = decode_mfm4(payload, array_ids=selected)
        if kind == 'M':
            self._molecules[molecule] = result
        return result

    def choices(self, molecule):
        return allowed_conformers(self.record('M', molecule), source=self.source,
                                  order=self.order, k=self.k, diagnostic=self.diagnostic,
                                  pprime=self.pprime, evaluation=self.evaluation)

    def sample(self, rng):
        # Conditional uniform draws are independent of conformation counts.
        molecule = int(rng.choice(self.indices))
        choices = self.choices(molecule)
        if not len(choices):
            raise ValueError('Selected molecule has no allowed conformations')
        return self.read(molecule, int(rng.choice(choices)))

    def read(self, molecule, conformer):
        if molecule not in self._index_set:
            raise ValueError('Molecule is outside the selected subset')
        m = self.record('M', molecule)
        if conformer not in self.choices(molecule):
            raise ValueError('Conformer is excluded by the training/diagnostic manifest')
        c = self.record('P' if self.source == 'PM7' else 'U', molecule, conformer)
        targets = {} if self.view is None else self.view.extract(m, c,
                    mask_overrides=self._record_masks.get((molecule, conformer)))
        if self._p_f64_sidecar is not None and self.view is not None:
            targets = self._p_f64_sidecar.apply(targets, molecule, conformer,
                'P' if self.source == 'PM7' else 'U', self.view, m[1])
        return {'molecule_index': molecule, 'conformer_index': conformer,
                'geometry_source': self.source, 'Z': m[1], 'pos': c[21],
                'pos_perturbed': c.get(22), 'bonds': m[2], 'bond_order': m[3],
                'targets': targets}

    def molecule_mean(self, molecule):
        """Mean allowed-conformer labels, aligning directed pair endpoints."""
        samples = [self.read(molecule, int(c)) for c in self.choices(molecule)]
        if not samples:
            raise ValueError('No conformations available for averaging')
        output = {}
        for name in set.intersection(*(set(s['targets']) for s in samples)):
            targets = [s['targets'][name] for s in samples]
            template = targets[0]
            field = next(f for f in self.view.fields if f['name'] == name)
            spec = field.get('normalization', self.view.normalizations.get(name))
            dtype = np.float64 if spec.get('p_recipe_fitted', False) else np.float32
            if template.pair_index is not None:
                pairs = sorted(set(tuple(p) for t in targets for p in t.pair_index.tolist()))
                index = {p: i for i, p in enumerate(pairs)}
                raw = np.full((len(targets), len(pairs), template.raw.shape[-1]), np.nan,
                              dtype=dtype)
                for i, target in enumerate(targets):
                    for j, pair in enumerate(target.pair_index.tolist()):
                        raw[i, index[tuple(pair)]] = target.raw[j]
                pair_index = np.asarray(pairs, dtype=np.int64).reshape(-1, 2)
            else:
                raw = np.stack([t.raw for t in targets])
                pair_index = None
            count = (~np.isnan(raw)).sum(0)
            mean = np.divide(np.nansum(raw, axis=0), count,
                             out=np.full(raw.shape[1:], np.nan), where=count > 0).astype(dtype)
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

    def indices_from_ids(self, molecule_ids):
        import pyarrow.parquet as pq
        table = pq.read_table(self.directory / 'id_map.parquet',
                              columns=['molecule_id', 'molecule_index'],
                              filters=[('record_kind', '=', 'M')])
        mapping = {row['molecule_id']: row['molecule_index'] for row in table.to_pylist()}
        return np.asarray([mapping[mid] for mid in molecule_ids], dtype=np.int64)

    def close(self):
        if self._env is not None:
            self._env.close()
        self._env = self._pid = None


def enabled_encoder_fields(fields, encoder):
    """Coordinate-free encoders automatically omit coordinate/vector heads."""
    if getattr(encoder, 'accepts_coordinates', True):
        return tuple(fields)
    return tuple(f for f in fields if f.get('representation', 'scalar') not in
                 ('vector', 'magnitude', 'symmetric_tensor6')
                 and f.get('kind') != 'denoise_eps_mse')


def encode_samples(samples, encoder, *, graph=False, pooling='mean', device=None):
    """Only the public encoder API sees model inputs; labels stay separate."""
    batch = collate_samples(samples, coordinates=getattr(encoder, 'accepts_coordinates', True), device=device)
    features = (encoder.encode_graph(batch, pooling=pooling) if graph
                else encoder.encode_atoms(batch))
    return batch, features


from .v31_segment_timing import phase, timed


@timed('collate')
def collate_samples(samples, *, coordinates=True, device=None):
    """Pack source model inputs without carrying any P/D targets into PyG."""
    prepared = getattr(samples, 'prepared', {})
    if coordinates and 'clean_batch' in prepared:
        batch = prepared['clean_batch']
        return batch if device is None else batch.to(device)
    from torch_geometric.data import Batch, Data
    from ..data.descriptor_schema import BOND_INDEX_FIELD, BOND_ORDER_FIELD, BOND_STATUS_FIELD
    records = []
    for sample in samples:
        record = Data(x=torch.as_tensor(sample['Z'].astype(np.int64) - 1).reshape(-1, 1))
        if coordinates:
            record.pos = torch.as_tensor(sample['pos'], dtype=torch.float32)
        setattr(record, BOND_INDEX_FIELD, torch.as_tensor(sample['bonds'].T.copy(), dtype=torch.long))
        setattr(record, BOND_ORDER_FIELD, torch.as_tensor(sample['bond_order'].astype(np.int64)))
        setattr(record, BOND_STATUS_FIELD, 'ok')
        records.append(record)
    batch = Batch.from_data_list(records)
    if device is not None:
        with phase('h2d'):
            batch = batch.to(device)
    return batch


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
