"""MFM4 wiring to existing head forms and loss, with explicit D4 parameters.

Physical vector heads stay vectors when the data registry exposes separate
component field_keys. Perturbed labels use array22, never S's random noise.
"""
from __future__ import annotations

from dataclasses import replace
import numpy as np
import torch
from torch import nn

from .v31_loader import encode_samples, enabled_encoder_fields
from .v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
from .v3_losses import compute_v3_loss


LEVELS = {'molecule': 'graph', 'molecule_vector': 'graph',
          'atom_vector': 'atom', 'atom': 'atom', 'sparse_atom_pair': 'pair',
          'graph': 'graph', 'pair': 'pair'}
PERTURBED_REGISTRY_IDS = {623, 624, 625}


def head_layout(view, selected_fields=None):
    """Resolve existing physical heads and independent training-view fields."""
    metadata = {c['field_key']: c for cs in view.schema['columns'].values() for c in cs}
    heads, fields, routes, selections, onsite = {}, [], {}, {}, []
    for field in view.fields if selected_fields is None else selected_fields:
        if field.get('loss_enabled', True) is False:
            continue
        name = field['name']
        meta = metadata.get(field.get('source_field', name), {})
        level = LEVELS[field['level']]
        representation = field.get('representation', 'scalar')
        layout = view.schema.get('target_layout', {}).get(field.get('target_id'), {})
        physical_vector = level == 'graph' and (representation == 'vector' or layout.get('kind') == 'vector')
        head_name = field['target_id'] if physical_vector else name
        component = None
        if physical_vector:
            column = field['selectors'][0][1]
            component = layout['column_indices'].index(column)
            if len(field['selectors']) != 1 or not 0 <= component < 3:
                raise ValueError('Molecular vector component selector differs')
        physical_representation = 'vector' if physical_vector else representation
        pooling = ('sum' if meta.get('extensive') in ('extensive', 'mass_and_geometry_moment') else 'mean')
        heads.setdefault(head_name, FieldSpec(head_name, field['group'], field['family'], level,
            representation=physical_representation, pooling=pooling, unit=field.get('unit', 'source_registry_unit')))
        # Keep source columns for selection/metrics. The original physical
        # vector remains one radial-Huber field in head_registry/loss.
        fields.append(FieldSpec(name, field['group'], field['family'], level,
            representation='scalar' if physical_vector else representation,
            pooling=pooling, unit=field.get('unit', 'source_registry_unit')))
        routes[head_name] = 22 if field.get('registry_id') in PERTURBED_REGISTRY_IDS else 21
        selections[name] = (head_name, component)
        if level == 'pair':
            # MFM4 carries native directed pair rows, including onsite rows.
            # Head math is unchanged; generic callers retain strict defaults.
            onsite.append(head_name)
    return tuple(heads.values()), tuple(fields), routes, selections, tuple(onsite)


def torch_affine(value, specification, *, inverse=False):
    """D4 transform for predictions in residual units; no fit or clipping."""
    center = value.new_tensor(specification['center'])
    scale = value.new_tensor(specification['scale'])
    return value * scale + center if inverse else (value - center) / scale


def element_offset(Z, specification):
    reference = specification.get('element_reference')
    if reference is None:
        return 0.
    return reference.get('intercept', 0.) + sum(
        int(np.count_nonzero(Z == z)) * coefficient
        for z, coefficient in zip(reference['basis'], reference['coefficients']))


class V31PDModel(nn.Module):
    """Adapter only: existing backbone, V3HeadBank and compute_v3_loss."""
    def __init__(self, encoder, view, *, forms='H1', pooling='registry'):
        super().__init__()
        from ..model.v3_heads import V3HeadBank
        head_fields, loss_fields, self.routes, self.selections, onsite = head_layout(
            view, enabled_encoder_fields(view.fields, encoder))
        inherited = view.schema['source_D3_reference']['sha256']
        self.head_registry = LabelRegistry(head_fields, 'MFM4_v31_physical_heads', inherited, 'data_line')
        self.head_by_name = self.head_registry.by_name()
        self.registry = LabelRegistry(loss_fields, 'training_view_v1', inherited, 'data_line')
        self.by_name = self.registry.by_name()
        self.definitions = {f['name']: f for f in view.fields}
        self.encoder, self.view = encoder, view
        overrides = {f.name: pooling for f in head_fields if f.level == 'graph' and f.representation == 'scalar'}
        self.heads = V3HeadBank(self.head_registry, dim=encoder.latent_dim, forms=forms,
            pooling_overrides=overrides, allow_onsite_fields=onsite)
        # Unit transform is used ONLY after applying the actual D4 transform to
        # both sides; it is not a replacement for missing data-line statistics.
        self.unit_normalizations = {f.name: TrainNormalization((0.,), (1.,), inherited,
            'D4_ALREADY_APPLIED') for f in head_fields}

    def encode_atoms(self, batch):
        return self.encoder.encode_atoms(batch)

    def encode_graph(self, batch, pooling='mean'):
        return self.encoder.encode_graph(batch, pooling=pooling)

    def predict(self, samples, *, groups=('D', 'P'), fields=None, clean_features=None, clean_batch=None):
        active = {f.name for f in self.registry.enabled(groups, fields)}
        physical = {self.selections[name][0] for name in active}
        device = next(self.parameters()).device
        predictions = {}
        for route in sorted({self.routes[name] for name in physical}):
            selected = tuple(name for name in physical if self.routes[name] == route)
            route_fields = [name for name in active if self.selections[name][0] in selected]
            sample_indices = list(range(len(samples)))
            if route == 22:
                sample_indices = []
                for i, sample in enumerate(samples):
                    observed = any(sample['targets'][name].valid.any() for name in route_fields)
                    if not observed:
                        continue
                    pos = sample['pos_perturbed']
                    if pos is None or not np.isfinite(pos).all():
                        raise ValueError('Observed perturbed label lacks its actual source geometry')
                    sample_indices.append(i)
                if not sample_indices:
                    for name in route_fields:
                        shape = np.concatenate([s['targets'][name].raw for s in samples]).shape
                        predictions[name] = next(self.parameters()).new_full(shape, float('nan'))
                    continue
            working_samples = [samples[i] for i in sample_indices]
            if route == 21 and clean_features is not None:
                batch, h0 = clean_batch, clean_features
            else:
                source = working_samples
                if route == 22:
                    source = [{**s, 'pos': s['pos_perturbed']} for s in working_samples]
                batch, h0 = encode_samples(source, self.encoder, device=device)
                if batch.pos is None:
                    # A coordinate-free encoder never receives coordinates;
                    # invariant pair heads may still use the supplied distances.
                    batch.pos = torch.as_tensor(np.concatenate([s['pos'] for s in source]),
                                                dtype=torch.float32, device=device)
            pairs, pair_rows = {}, {}
            for name in active:
                head_name, _ = self.selections[name]
                field = self.by_name[name]
                if head_name not in selected or field.level != 'pair':
                    continue
                masks = [s['targets'][name].valid.any(-1) for s in working_samples]
                indices = [torch.as_tensor(s['targets'][name].pair_index[mask].T.copy(), device=device,
                           dtype=torch.long) + batch.ptr[i] for i, (s, mask) in enumerate(zip(working_samples, masks))]
                pairs[head_name] = torch.cat(indices, dim=1)
                mask = np.concatenate(masks)
                pair_rows[head_name] = (torch.as_tensor(np.flatnonzero(mask), device=device), len(mask))
            values = self.heads(h0, batch.batch, batch.pos, enabled_groups=groups,
                enabled_fields=selected, pair_indices=pairs)
            for name, (rows, total) in pair_rows.items():
                value = values[name]
                values[name] = value.new_full((total, value.shape[-1]), float('nan')).index_copy(0, rows, value)
            for name in active:
                head_name, component = self.selections[name]
                if head_name in values:
                    value = values[head_name] if component is None else values[head_name][:, component:component+1]
                    if len(sample_indices) != len(samples):
                        lengths = [len(s['targets'][name].raw) for s in samples]
                        offsets = np.r_[0, np.cumsum(lengths)]
                        rows = np.concatenate([np.arange(offsets[i], offsets[i+1]) for i in sample_indices])
                        value = value.new_full((int(offsets[-1]), value.shape[-1]), float('nan')).index_copy(
                            0, torch.as_tensor(rows, device=device), value)
                    predictions[name] = value
        return predictions

    def loss(self, predictions, samples, *, groups=('D', 'P'), fields=None,
             fixed_full_condition=False):
        active = self.registry.enabled(groups, fields)
        targets, normalized_predictions, members = {}, {}, {}
        for field in active:
            name = field.name
            specification = self.definitions[name]
            specification = specification.get('normalization', self.view.normalizations.get(name))
            if specification is None:
                raise ValueError('Missing D4 normalization for ' + name)
            prediction = predictions[name]
            values = torch.as_tensor(np.concatenate([s['targets'][name].values for s in samples]),
                                     dtype=torch.float32, device=prediction.device)
            valid = torch.as_tensor(np.concatenate([s['targets'][name].valid for s in samples]),
                                    dtype=torch.bool, device=prediction.device)
            head_name, component = self.selections[name]
            members.setdefault(head_name, []).append((component, torch_affine(prediction, specification),
                                                       values, valid, specification))
        for name, columns in members.items():
            field = self.head_by_name[name]
            if columns[0][0] is None:
                _, prediction, value, valid, specification = columns[0]
                if field.representation == 'vector':
                    self._require_vector_normalization([specification])
            else:
                columns.sort(key=lambda item: item[0])
                if [item[0] for item in columns] != [0, 1, 2]:
                    raise ValueError('The original physical vector loss requires all three selected components')
                self._require_vector_normalization([item[4] for item in columns])
                prediction = torch.cat([item[1] for item in columns], dim=-1)
                value = torch.cat([item[2] for item in columns], dim=-1)
                valid = torch.cat([item[3] for item in columns], dim=-1)
            normalized_predictions[name] = prediction
            targets[name] = FieldTarget(value, valid.all(-1))
        result = compute_v3_loss(normalized_predictions, targets, self.head_registry, self.unit_normalizations,
            enabled_groups=groups, enabled_fields=tuple(members))
        if fixed_full_condition:
            denominators = {g: sum(f.group == g for f in self.head_registry.fields) for g in groups}
            total = sum((value / (len(groups) * denominators[self.head_by_name[name].group])
                         for name, value in result.fields.items()), result.total.new_zeros(()))
            result = replace(result, total=total)
        return result

    @staticmethod
    def _require_vector_normalization(specifications):
        scales = []
        for specification in specifications:
            center = np.asarray(specification['center'])
            scale = np.asarray(specification['scale']).reshape(-1)
            if np.any(center != 0.) or np.any(scale != scale[0]):
                raise ValueError('Original equivariant vector normalization requires zero center and one scale')
            scales.append(float(scale[0]))
        if any(scale != scales[0] for scale in scales):
            raise ValueError('All components of the same physical vector need the same D4 scale')

    def field_counts(self, samples, *, groups=('D','P'), fields=None):
        """Counts for original physical loss fields, preserving component masks."""
        members = {}
        for field in self.registry.enabled(groups, fields):
            head_name, component = self.selections[field.name]
            masks = np.concatenate([s['targets'][field.name].valid for s in samples])
            members.setdefault(head_name, []).append((component, masks))
        counts = {}
        for name, columns in members.items():
            if columns[0][0] is not None:
                columns.sort(key=lambda item: item[0])
                if [item[0] for item in columns] != [0,1,2]:
                    raise ValueError('The physical vector count requires all three components')
            counts[name] = int(np.concatenate([item[1] for item in columns], axis=-1).all(-1).sum())
        return counts

    def original_predictions(self, predictions, samples):
        """Add the supplied elemental energy reference for original-unit R²/MAE."""
        output = {}
        for name, value in predictions.items():
            field = self.by_name[name]
            definition = self.definitions[name]
            specification = definition.get('normalization', self.view.normalizations.get(name))
            if specification.get('element_reference') is not None:
                if field.level != 'graph':
                    raise ValueError('Element reference is only valid for molecular energy fields')
                value = value + value.new_tensor([element_offset(s['Z'], specification) for s in samples])[:, None]
            output[name] = value
        return output
