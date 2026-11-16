import pytest
import torch

from phychem_mfm.phase1.v31_experiments import accumulated_backward, segment_stop_samples
from phychem_mfm.phase1.v3_losses import V3LossResult


def test_segment_resume_preserves_budget_lr_and_sample_clock():
    from phychem_mfm.phase1.v3_training import SampleClock
    from phychem_mfm.phase1.v2_s_training import sample_lr_ratio
    configuration = dict(samples=64_000_000, run_until_samples=2_000_000)
    clock = SampleClock(configuration['samples'], samples_consumed=1_999_984)
    stop = segment_stop_samples(configuration, clock.samples_consumed)
    count = min(clock.max_next_samples(32), stop - clock.samples_consumed)
    assert count == 16
    clock.advance(count)
    assert clock.samples_consumed == 2_000_000 and clock.sample_budget == 64_000_000
    next_configuration = {**configuration, 'run_until_samples':4_000_000}
    assert segment_stop_samples(next_configuration, clock.samples_consumed) == 4_000_000
    for schedule in ('cosine','wsd'):
        before = sample_lr_ratio(clock.samples_consumed, configuration['samples'], schedule)
        after = sample_lr_ratio(clock.samples_consumed, next_configuration['samples'], schedule)
        assert before == pytest.approx(after, abs=1e-12, rel=1e-12)
    assert segment_stop_samples(dict(samples=6_000_000)) == 6_000_000


@pytest.mark.parametrize('stop,completed', [(1_500_000,0), (128_000_000,0),
    (2_000_000,2_000_000), (1_000_000,2_000_000), (True,0), (None,64_000_000)])
def test_segment_rejects_noncheckpoint_or_nonadvancing_execution(stop, completed):
    with pytest.raises(ValueError, match='later sample milestone'):
        segment_stop_samples(dict(samples=64_000_000, run_until_samples=stop), completed)


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
