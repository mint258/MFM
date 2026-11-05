"""Synthetic checks of actual typed loss routing, group means and gradients."""
import pytest
import torch
from torch import nn

from model_v3_typed_fixture import ordered_target, tensor_target
from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
from phychem_mfm.phase1.v3_losses import V3LossResult, compute_v3_loss


def registry():
    return LabelRegistry((FieldSpec("q", "P", "r674", "graph", representation="symmetric_tensor6"),
        FieldSpec("p", "P", "ordinary", "graph"), FieldSpec("r", "D", "r73", "ordered_entry")),
        "synthetic-typed-loss", "a" * 64)


def normalizers():
    return {name: TrainNormalization((0.,), (scale,), "b" * 64, "synthetic-typed-loss")
            for name, scale in (("q", 2.), ("p", 1.), ("r", 1.))}


def plain():
    return FieldTarget(torch.zeros((1, 1)), torch.tensor([True]))


def test_tensor_is_one_target_and_ordered_entries_use_observed_entry_mean():
    q = torch.tensor([[3., 0., 0., 0., 0., 0.], [float("nan")] * 6, [float("nan")] * 6], requires_grad=True)
    r = torch.tensor([[1.], [2.], [3.], [float("nan")]], requires_grad=True)
    p = torch.tensor([[2.]], requires_grad=True)
    result = compute_v3_loss({"q": q, "r": r, "p": p}, {"q": tensor_target(), "r": ordered_target(), "p": plain()},
        registry(), normalizers(), enabled_groups=("S", "D", "P"))
    assert result.fields["q"].item() == pytest.approx(.125)  # .5*((3/2)^2/9)
    assert result.fields["r"].item() == pytest.approx(1.5)  # (.5 + 1.5 + 2.5)/3
    assert result.groups["P"].item() == pytest.approx((.125 + 1.5)/2)
    assert result.total.item() == pytest.approx((((.125 + 1.5)/2) + 1.5)/3)
    assert result.counts == {"q": 1, "p": 1, "r": 3}
    assert result.observed_fields == {"S": 0, "D": 1, "P": 2}
    result.total.backward()
    assert torch.isfinite(q.grad).all() and not q.grad[1:].any()
    assert torch.isfinite(r.grad).all() and r.grad[-1].item() == 0.
    metrics = result.metrics()
    assert metrics["domain_audit/q/source_valid_components"] == 17
    assert metrics["domain_audit/q/source_valid_xy"] == 2
    assert metrics["domain_audit/q/loss_excluded_tensors"] == 2
    assert metrics["domain_audit/r/retained_entries"] == 4
    assert metrics["domain_audit/r/onsite_entries"] == 2


def test_tensor_radial_huber_uses_frobenius_offdiagonal_weights_and_d9():
    q = torch.zeros((3, 6), requires_grad=True)
    with torch.no_grad(): q[0, 1] = 6.
    result = compute_v3_loss({"q": q}, {"q": tensor_target()}, registry(), normalizers(),
        enabled_groups=("P",), enabled_fields=("q",))
    assert result.total.item() == pytest.approx(2. ** .5 - .5)  # sqrt(2*(6/2)^2/9)-.5
    result.total.backward()
    assert q.grad[0, 1].item() == pytest.approx(2. ** .5 / 6.)
    assert not q.grad[1:].any()


def test_zero_eligible_typed_fields_leave_group_denominator_and_head_gradients_untouched():
    h0 = torch.ones((3, 4), requires_grad=True)
    q_head, p_head, r_head = nn.Linear(4, 6), nn.Linear(4, 1), nn.Linear(4, 1)
    q = q_head(h0)
    r = r_head(torch.cat((h0, h0[:1]), dim=0))
    p = p_head(h0[:1])
    result = compute_v3_loss({"q": q, "r": r, "p": p},
        {"q": tensor_target().masked(False), "r": ordered_target().masked(False), "p": plain()},
        registry(), normalizers(), enabled_groups=("D", "P"))
    assert result.counts == {"q": 0, "p": 1, "r": 0}
    assert result.observed_fields == {"D": 0, "P": 1}
    torch.testing.assert_close(result.total, result.fields["p"] / 2)
    result.total.backward()
    assert q_head.weight.grad is q_head.bias.grad is r_head.weight.grad is r_head.bias.grad is None
    assert p_head.weight.grad is not None and torch.isfinite(h0.grad).all()
    assert result.audit_counts["q"]["source_valid_components"] == 17
    assert result.audit_counts["q"]["loss_eligible_tensors"] == 0


def test_disabled_domain_prediction_does_not_need_targets_or_gain_gradient():
    q = torch.full((3, 6), float("nan"), requires_grad=True)
    p = torch.tensor([[1.]], requires_grad=True)
    result = compute_v3_loss({"q": q, "p": p}, {"p": plain()}, registry(), {"p": normalizers()["p"]},
        enabled_groups=("P",), enabled_fields=("p",))
    result.total.backward()
    assert q.grad is None and result.counts == {"p": 1} and result.audit_counts == {}


def test_no_eligible_tensor_does_not_require_fabricated_scale_or_connected_zero():
    q = torch.full((3, 6), float("nan"), requires_grad=True)
    result = compute_v3_loss({"q": q}, {"q": tensor_target().masked(False)}, registry(), {},
        enabled_groups=("P",), enabled_fields=("q",))
    assert result.total.item() == 0 and not result.total.requires_grad
    assert result.observed_fields == {"P": 0} and q.grad is None


def test_legacy_loss_result_positional_constructor_keeps_default_empty_audit():
    result = V3LossResult(torch.tensor(0.), {}, {}, {}, {}, ())
    assert result.audit_counts == {} and result.metrics() == {"loss/total": 0.}
