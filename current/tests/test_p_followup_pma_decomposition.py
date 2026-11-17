"""User-directive D-prime combination checks; no repeated head overfit."""
from types import SimpleNamespace

import numpy as np
import torch

from phychem_mfm.phase1.v31_loader import TrainingView, V31Target
from phychem_mfm.phase1.v31_training import V31PDModel


class Encoder(torch.nn.Module):
    latent_dim = 512

    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.ones(()))


def view():
    names = ('energy', 'retained')
    columns = [dict(field_key=n, column_index=i, family='energy', level='molecule', kind='scalar')
               for i, n in enumerate(names)]
    schema = dict(columns=dict(mol_labels=columns), source_D3_reference=dict(sha256='a' * 64))
    fields = [dict(name=n, group='P', family='energy', level='molecule',
                   normalization=dict(fit_role='TRAIN', center=0., scale=1.)) for n in names]
    return TrainingView(schema, dict(fields=fields))


def model(**options):
    torch.manual_seed(17)
    return V31PDModel(Encoder(), view(), p_recipe=dict(pma_pooling=True, anti_collapse=True), **options)


def inputs():
    h = torch.arange(3 * 512, dtype=torch.float32).reshape(3, 512) / 1000
    batch = SimpleNamespace(batch=torch.tensor([0, 0, 1]), pos=torch.zeros(3, 3))
    samples = []
    for atoms in (2, 1):
        target = V31Target(np.zeros((1, 1)), np.zeros((1, 1), np.float32),
                           np.ones((1, 1), bool), 'P', 'energy', 'molecule', 'scalar', True)
        samples.append(dict(Z=np.full(atoms, 6), pos=np.zeros((atoms, 3), np.float32),
                            targets=dict(energy=target, retained=target)))
    return samples, batch, h


def predict(candidate):
    samples, batch, h = inputs()
    return candidate.predict(samples, groups=('P',), clean_features=h, clean_batch=batch)


def test_pma_decomposition_has_two_actual_outputs_and_preserves_other_heads():
    baseline = model()
    decomposed = model(conformer_decomposition=dict(selected_fields=['energy']))
    outputs = predict(decomposed)
    assert outputs['energy'].shape == (2, 2)
    assert outputs['retained'].shape == (2, 1)
    key = decomposed.heads.keys['energy']
    assert decomposed.heads.field_heads[key].in_features == decomposed.p_recipe_pma.representation_dim
    assert decomposed.heads.field_heads[key].out_features == 2
    baseline_state = baseline.state_dict()
    for name, value in decomposed.state_dict().items():
        if not isinstance(value, torch.Tensor):
            assert value == baseline_state[name]
        elif name in ('heads.field_heads.' + key + '.weight', 'heads.field_heads.' + key + '.bias'):
            assert torch.equal(value[:1], baseline_state[name])
        else:
            assert torch.equal(value, baseline_state[name]), name
    assert torch.equal(outputs['retained'], predict(baseline)['retained'])


def test_pma_decomposition_explicitly_off_is_bitwise_identical():
    baseline = model()
    disabled = model(conformer_decomposition=None)
    for name, value in baseline.state_dict().items():
        other = disabled.state_dict()[name]
        assert torch.equal(value, other) if isinstance(value, torch.Tensor) else value == other
    actual, expected = predict(disabled), predict(baseline)
    assert actual.keys() == expected.keys()
    assert all(torch.equal(actual[name], expected[name]) for name in actual)
