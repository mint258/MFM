import torch

from loss import structural_total


def test_deletion_keeps_absolute_component_gradients():
    fields = {name: torch.tensor(value, requires_grad=True) for name, value in
              [('s_noise', 2.), ('s_element', 3.), ('s_bond', 5.)]}
    counts = dict(s_noise=30, s_element=4, s_bond=12)
    baseline = structural_total(fields, counts)
    expected = torch.stack(list(fields.values())).mean()
    assert torch.equal(baseline, expected)
    baseline_grads = torch.autograd.grad(baseline, list(fields.values()))
    for disabled in ('s_element', 's_bond'):
        remaining = [name for name in fields if name != disabled]
        deleted = structural_total(fields, counts, disabled=(disabled,))
        assert torch.allclose(deleted, baseline - fields[disabled]/3)
        grads = torch.autograd.grad(deleted, [fields[name] for name in remaining])
        assert all(torch.equal(grad, baseline_grads[list(fields).index(name)])
                   for name, grad in zip(remaining, grads))


def test_missing_role_uses_original_valid_role_denominator():
    fields = dict(s_noise=torch.tensor(2.), s_element=torch.tensor(0.), s_bond=torch.tensor(5.))
    counts = dict(s_noise=30, s_element=0, s_bond=12)
    assert structural_total(fields, counts).item() == 3.5
    assert structural_total(fields, counts, disabled=('s_bond',)).item() == 1.
