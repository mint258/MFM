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
from .v31_segment_timing import timed

_as_tensor = timed('h2d')(torch.as_tensor)


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
    def __init__(self, encoder, view, *, forms='H1', pooling='registry',
                 output_parameterization='raw', head_hidden_dim=64, p_recipe=None):
        super().__init__()
        if output_parameterization not in ('raw', 'normalized'):
            raise ValueError('Explicit raw or normalized head output required')
        self.output_parameterization = output_parameterization
        self.grouped_fields = False
        recipe = p_recipe or {}
        self.shared_projector = None
        if recipe.get('shared_projector',False):
            with torch.random.fork_rng(devices=[]):
                self.shared_projector = nn.Sequential(nn.Linear(512,512),nn.SiLU(),nn.Linear(512,512))
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
        self.heads = V3HeadBank(self.head_registry, dim=encoder.latent_dim, forms=forms, hidden_dim=head_hidden_dim,
            pooling_overrides=overrides, allow_onsite_fields=onsite,
            pair_distance=not recipe.get('pair_without_distance',False))
        self.p_recipe_pma = None
        if recipe.get('pma_pooling',False):
            from ..model.v3_latent import MolecularLatent, LatentSpec
            self.p_recipe_pma = MolecularLatent(LatentSpec(kind='pma',n_ref=53.64145,
                write_back=False,reconstruction=False))
            self.heads.enable_p_recipe_pma(self.p_recipe_pma.representation_dim)
        # Unit transform is used ONLY after applying the actual D4 transform to
        # both sides; it is not a replacement for missing data-line statistics.
        self.unit_normalizations = {f.name: TrainNormalization((0.,), (1.,), inherited,
            'D4_ALREADY_APPLIED') for f in head_fields}

    def encode_atoms(self, batch):
        return self.encoder.encode_atoms(batch)

    def configure_step_overhead(self, options):
        from ..model.perf_sync import configure
        configure(self, options)
        self.grouped_fields = options.get('grouped_fields', False)
        from ..model.heads import EquivariantDenoisingHead
        for module in self.heads.modules():
            if isinstance(module, EquivariantDenoisingHead):
                module.activation_checkpointing = options.get('head_checkpointing', True)
        import sys
        tiled = sys.modules.get('model_v3_architecture_s_memory_170a7752bad1812d')
        for module in list(self.encoder.modules()):
            original = getattr(module, 'dist_mlp', None)
            if not isinstance(original, nn.Sequential):
                continue
            if options.get('distance_tiling', True):
                if tiled is not None and type(original) is nn.Sequential:
                    module.dist_mlp = tiled.TiledDistanceMLP(original)
            elif type(original).__name__ == 'TiledDistanceMLP':
                module.dist_mlp = nn.Sequential(*list(original.children()))

    def encode_graph(self, batch, pooling='mean'):
        return self.encoder.encode_graph(batch, pooling=pooling)

    @timed('forward')
    def predict(self, samples, *, groups=('D', 'P'), fields=None, clean_features=None, clean_batch=None,
                clean_z=None):
        active = {f.name for f in self.registry.enabled(groups, fields)}
        physical = {self.selections[name][0] for name in active}
        device = next(self.parameters()).device
        predictions = {}
        prepared = getattr(samples, 'prepared', {})
        for route in sorted({self.routes[name] for name in physical}):
            selected = tuple(name for name in physical if self.routes[name] == route)
            route_fields = [name for name in active if self.selections[name][0] in selected]
            sample_indices = list(range(len(samples)))
            if route == 22:
                sample_indices = []
                for i, sample in enumerate(samples) if not prepared else ():
                    observed = any(sample['targets'][name].valid.any() for name in route_fields)
                    if not observed:
                        continue
                    pos = sample['pos_perturbed']
                    if pos is None or not np.isfinite(pos).all():
                        raise ValueError('Observed perturbed label lacks its actual source geometry')
                    sample_indices.append(i)
                if prepared:
                    sample_indices = prepared['route_indices'].get(route, [])
                if not sample_indices:
                    for name in route_fields:
                        shape = prepared['shapes'][name] if prepared else np.concatenate([s['targets'][name].raw for s in samples]).shape
                        predictions[name] = next(self.parameters()).new_full(shape, float('nan'))
                    continue
            working_samples = [samples[i] for i in sample_indices]
            if route == 21 and clean_features is not None:
                batch, h0 = clean_batch, clean_features
                z = clean_z
            else:
                if prepared and route == 22:
                    batch = prepared['perturbed_batch'].to(device)
                    h0 = self.encoder.encode_atoms(batch)
                else:
                    source = working_samples
                    if route == 22:
                        source = [{**s, 'pos': s['pos_perturbed']} for s in working_samples]
                    batch, h0 = encode_samples(source, self.encoder, device=device)
                module = getattr(self.encoder, 'latent_module', None)
                z = None if module is None else module.last_z
                if batch.pos is None:
                    # A coordinate-free encoder never receives coordinates;
                    # invariant pair heads may still use the supplied distances.
                    batch.pos = _as_tensor(np.concatenate([s['pos'] for s in source]),
                                                dtype=torch.float32, device=device)
            pairs, pair_rows = {}, {}
            if self.shared_projector is not None:
                h0 = self.shared_projector(h0)
            if self.p_recipe_pma is not None:
                from ..model.perf_sync import dense_batch, batch_layout
                with batch_layout(batch):
                    dense, mask = dense_batch(h0,batch.batch)
                z = self.p_recipe_pma.finish(dense,mask)
            for name in active:
                head_name, _ = self.selections[name]
                field = self.by_name[name]
                if head_name not in selected or field.level != 'pair':
                    continue
                if prepared:
                    pairs[head_name] = prepared['pairs'][head_name].to(device)
                    rows, total = prepared['pair_rows'][head_name]
                    pair_rows[head_name] = (rows.to(device), total)
                    continue
                masks = [s['targets'][name].valid.any(-1) for s in working_samples]
                indices = [_as_tensor(s['targets'][name].pair_index[mask].T.copy(), device=device,
                           dtype=torch.long) + batch.ptr[i] for i, (s, mask) in enumerate(zip(working_samples, masks))]
                pairs[head_name] = torch.cat(indices, dim=1)
                mask = np.concatenate(masks)
                pair_rows[head_name] = (_as_tensor(np.flatnonzero(mask), device=device), len(mask))
            latent = (dict(graph_latent=z) if hasattr(self.heads,'latent_scalar_dim')
                      or self.p_recipe_pma is not None else {})
            if self.grouped_fields:
                observed = prepared['observed'].get(route, set()) if prepared else set()
                for head_name in selected if not prepared else ():
                    names = [name for name in route_fields if self.selections[name][0] == head_name]
                    if any(np.concatenate([sample['targets'][name].valid for name in names], axis=-1).all(-1).any()
                           for sample in working_samples):
                        observed.add(head_name)
                latent['observed_fields'] = observed
            self.heads.grouped_fields = self.grouped_fields
            from ..model.perf_sync import batch_layout
            with batch_layout(batch):
                values = self.heads(h0, batch.batch, batch.pos, enabled_groups=groups,
                    enabled_fields=selected, pair_indices=pairs, **latent)
            for name, (rows, total) in pair_rows.items():
                value = values[name]
                values[name] = value.new_full((total, value.shape[-1]), float('nan')).index_copy(0, rows, value)
            for name in active:
                head_name, component = self.selections[name]
                if head_name in values:
                    value = values[head_name] if component is None else values[head_name][:, component:component+1]
                    if len(sample_indices) != len(samples):
                        if prepared:
                            rows = prepared['scatter_rows'][name].to(device)
                            total = prepared['shapes'][name][0]
                        else:
                            lengths = [len(s['targets'][name].raw) for s in samples]
                            offsets = np.r_[0, np.cumsum(lengths)]
                            rows = _as_tensor(np.concatenate([np.arange(offsets[i], offsets[i+1]) for i in sample_indices]), device=device)
                            total = int(offsets[-1])
                        value = value.new_full((total, value.shape[-1]), float('nan')).index_copy(0, rows, value)
                    predictions[name] = value
        return predictions

    @timed('loss')
    def loss(self, predictions, samples, *, groups=('D', 'P'), fields=None,
             fixed_full_condition=False):
        if self.grouped_fields and not fixed_full_condition:
            from .v31_grouped_loss import grouped_v31_loss
            return grouped_v31_loss(self, predictions, samples, groups, fields)
        active = self.registry.enabled(groups, fields)
        targets, normalized_predictions, members = {}, {}, {}
        for field in active:
            name = field.name
            specification = self.definitions[name]
            specification = specification.get('normalization', self.view.normalizations.get(name))
            if specification is None:
                raise ValueError('Missing D4 normalization for ' + name)
            prediction = predictions[name]
            values = _as_tensor(np.concatenate([s['targets'][name].values for s in samples]),
                                     dtype=torch.float32, device=prediction.device)
            valid = _as_tensor(np.concatenate([s['targets'][name].valid for s in samples]),
                                    dtype=torch.bool, device=prediction.device)
            head_name, component = self.selections[name]
            normalized = prediction if self.output_parameterization == 'normalized' else torch_affine(prediction, specification)
            members.setdefault(head_name, []).append((component, normalized,
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
        loss_function = compute_v3_loss
        if self.grouped_fields:
            from .v31_grouped_loss import grouped_regression_loss
            loss_function = grouped_regression_loss
        result = loss_function(normalized_predictions, targets, self.head_registry, self.unit_normalizations,
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
            if self.output_parameterization == 'normalized':
                value = torch_affine(value, specification, inverse=True)
            if specification.get('element_reference') is not None:
                if field.level != 'graph':
                    raise ValueError('Element reference is only valid for molecular energy fields')
                value = value + value.new_tensor([element_offset(s['Z'], specification) for s in samples])[:, None]
            output[name] = value
        return output

