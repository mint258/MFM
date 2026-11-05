import pytest
import torch

from phychem_mfm.phase1.v31_experiments import accumulated_backward
from phychem_mfm.phase1.v3_losses import V3LossResult


@pytest.mark.parametrize('fixed', [None, {'D': 3, 'P': 2}])
def test_mixed_group_microbatches_match_full_observation_means_and_fixed_family_weights(fixed):
    chunks = [{'a': torch.tensor([1., 2.]), 'b': torch.tensor([]), 'c': torch.tensor([3.]), 'd': torch.tensor([])},
              {'a': torch.tensor([4.]), 'b': torch.tensor([2., 5.]), 'c': torch.tensor([]), 'd': torch.tensor([])}]
    field_groups = dict(a='D', b='D', c='P', d='D')
    parameter = torch.tensor(.7, requires_grad=True)
    def step(chunk):
        values = {name: .5 * (x * parameter).square().mean() if len(x) else parameter * 0.
                  for name, x in chunk.items()}
        return V3LossResult(parameter * 0., values, {}, {k: len(v) for k, v in chunk.items()}, {}, ('D','P'))
    full = {name: torch.cat([chunk[name] for chunk in chunks]) for name in chunks[0]}
    expected = step(full)
    d = (expected.fields['a'] + expected.fields['b']) / (2 if fixed is None else 3)
    p = expected.fields['c'] / (1 if fixed is None else 2)
    total = (d + p) / 2
    total.backward()
    gradient = parameter.grad.clone()
    parameter.grad = None
    actual = accumulated_backward(chunks, step, lambda chunk: {k: len(v) for k,v in chunk.items()},
        field_groups, ('D','P'), fixed_denominators=fixed, device='cpu')
    torch.testing.assert_close(actual.total, total.detach(), atol=1e-6, rtol=1e-6)
    torch.testing.assert_close(parameter.grad, gradient, atol=1e-6, rtol=1e-6)
    assert actual.counts == {'a': 3, 'b': 2, 'c': 1, 'd': 0}
    assert actual.observed_fields == {'D': 2, 'P': 1}
