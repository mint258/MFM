"""Explicit analytic engineering fixture, never a D release or scientific proxy."""
from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import random

import numpy as np
import torch
from torch_geometric.data import Batch, Data

from .v3_architecture_views import build_two_structural_views
from .v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization, canonical_hash
from .v3_sampling import ConformerRef, InMemorySamplingIndex, MoleculeEntry, UniformMoleculeSampler
from .v3_structural import StructuralFieldBinding, build_structural_views, eligibility_from_choices
from .v3_trainer import PreparedV3Batch

VERSION = 'engineering_fixture_not_D3_D5_v1'


def fixture_source():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class SyntheticProxyProvider:
    read_only, node_local = True, True
    data_version = VERSION

    def __init__(self, index, registry, structural_binding, *, views):
        self.index, self.registry, self.binding, self.views = index, registry, structural_binding, views
        self.source_sha256 = fixture_source()
        self.calls, self.closed = 0, False
        self.generator = torch.Generator().manual_seed(31337)

    def state_dict(self):
        return {'calls': self.calls, 'generator': self.generator.get_state().clone()}

    def load_state_dict(self, state):
        self.calls = state['calls']; self.generator.set_state(state['generator'])

    def prepare(self, choices, *, role, view_config, enabled_groups, enabled_fields):
        if self.closed: raise RuntimeError('Engineering provider already closed')
        self.calls += 1
        records = []
        for choice in choices:
            n = choice.native_atoms; axis = torch.arange(n, dtype=torch.float32)
            jitter = .001*(float(torch.rand((), generator=self.generator))+float(torch.rand(()))
                + float(np.random.random())+random.random())
            phase = .2*choice.molecule_index + (.3 if role == 'VAL' else .1 if role != 'TRAIN' else 0.)
            pos = torch.stack((axis*.6, (axis+phase).sin()*.2, (axis*.4+phase).cos()*.2), -1)+jitter
            records.append(Data(x=(axis.long()%3+5)[:, None], pos=pos,
                rdkit_bond_index=torch.stack((torch.arange(n-1), torch.arange(1, n))),
                rdkit_bond_order=(torch.arange(n-1)%5+1).long(), rdkit_bond_status='ok'))
        clean = Batch.from_data_list(records)
        masks = eligibility_from_choices(choices, self.registry, self.binding, enabled_fields=enabled_fields)
        builder = build_two_structural_views if self.views == 'two' else build_structural_views
        views = builder(clean, ordinals=tuple(c.ordinal for c in choices), config=view_config,
            include_structural='S' in enabled_groups, graph_eligibility=masks)
        targets = {
            'fixture_P_graph': FieldTarget(torch.tensor([[.1*c.molecule_index+.01*c.ordinal] for c in choices]), torch.ones(len(choices), dtype=torch.bool)),
            'fixture_D_atom': FieldTarget(torch.cat([torch.arange(c.native_atoms, dtype=torch.float32)[:, None]/10 for c in choices]),
                torch.ones(sum(c.native_atoms for c in choices), dtype=torch.bool))}
        enabled = {f.name for f in self.registry.enabled(enabled_groups, enabled_fields)}
        return PreparedV3Batch(tuple(choices), views, {k:v for k,v in targets.items() if k in enabled},
            self.source_sha256, VERSION, role)

    def validation_batches(self, *, role, view_config, enabled_groups, enabled_fields):
        # The outer trainer preserves committed provider state. Validation must
        # not depend on how many training prepares have preceded this call.
        self.generator.manual_seed(view_config.seed + (101 if role == 'VAL' else 211))
        sampler = UniformMoleculeSampler(self.index, seed=7919, sample_budget=2)
        choices = tuple(sampler.choice(i) for i in range(2))
        choices = tuple(replace(c, ordinal=(100 if role == 'VAL' else 200)+i,
            molecule_id='engineering_unseen_'+str(i) if role == 'VAL' else c.molecule_id,
            conformer_id='engineering_unseen_conformer_'+str(i)) for i,c in enumerate(choices))
        value = self.prepare(choices, role=role, view_config=view_config,
            enabled_groups=enabled_groups, enabled_fields=enabled_fields)
        return 1, iter((value,))

    def close(self): self.closed = True


def synthetic_proxy_inputs(*, views='three'):
    from .v3_proxy_run import ProxyInputs
    source = fixture_source()
    fields = (
        FieldSpec('fixture_S_element', 'S', 'structure', 'atom', kind='classification', classes=119, unit='element_class'),
        FieldSpec('fixture_S_noise', 'S', 'structure', 'atom', kind='denoise_eps_mse', representation='vector', unit='angstrom'),
        FieldSpec('fixture_S_bond', 'S', 'structure', 'pair', kind='classification', classes=5, unit='source_bond_class'),
        FieldSpec('fixture_P_graph', 'P', 'fixture_physics', 'graph', pooling='sum', unit='engineering_unit'),
        FieldSpec('fixture_D_atom', 'D', 'fixture_descriptor', 'atom', unit='engineering_unit'))
    registry = LabelRegistry(fields, VERSION, source)
    binding = StructuralFieldBinding(*(f.name for f in fields[:3]))
    index = InMemorySamplingIndex(tuple(MoleculeEntry('engineering_m'+str(i),
        tuple(ConformerRef(f'engineering_c{i}_{j}', j, 4+i, (('PM7',f'engineering:{i}:{j}'),)) for j in range(2)),
        (('S',True),('D',True),('P',True)),
        (('structure',True),('fixture_physics',True),('fixture_descriptor',True))) for i in range(3)), VERSION)
    norms = {f.name: TrainNormalization((0.,),(1.,),source,VERSION) for f in fields if f.group != 'S'}
    populations = {role: canonical_hash({'role':role,'fixture_source':source,'members':2})
        for role in ('VAL','TRAIN_UNSEEN_CONFORMATION')}
    return ProxyInputs(index, SyntheticProxyProvider(index,registry,binding,views=views), registry,binding,norms,
        {'scope':'ENGINEERING_SYNTHETIC_ONLY','provides_D_authority':False},populations,
        authority_kind='synthetic_engineering', release_accepted=False)
