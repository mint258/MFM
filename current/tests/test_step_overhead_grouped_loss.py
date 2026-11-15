"""The taskbook's one added synthetic test: masks, missing NaNs and empty fields."""
import torch

from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
from phychem_mfm.phase1.v3_losses import compute_v3_loss
from phychem_mfm.phase1.v31_grouped_loss import grouped_regression_loss


def test_grouped_field_losses_match_original_with_masks_nans_and_empty_fields():
    generator = torch.Generator().manual_seed(0)
    fields = tuple(FieldSpec(name, 'P', 'fixture', level, representation=representation)
                   for name, level, representation in (
                       ('g0','graph','scalar'), ('g1','graph','scalar'), ('empty','graph','scalar'),
                       ('gv0','graph','vector'), ('gv1','graph','vector'),
                       ('a0','atom','scalar'), ('a1','atom','scalar'),
                       ('av0','atom','vector'), ('av1','atom','vector'),
                       ('pair0','pair','scalar'), ('pair1','pair','scalar')))
    registry = LabelRegistry(fields, 'synthetic', 'a'*64, 'data_line')
    predictions, targets, norms = {}, {}, {}
    for index, field in enumerate(fields):
        size = {'graph':5,'atom':13,'pair':17}[field.level]
        predictions[field.name] = torch.randn(size,field.prediction_width,generator=generator,requires_grad=True)
        values = torch.randn(size,field.target_width,generator=generator)
        valid = torch.arange(size)%3 != index%3
        if field.name == 'empty':valid[:] = False
        values[~valid] = float('nan')
        targets[field.name] = FieldTarget(values, valid)
        center = 0. if field.representation == 'vector' else .2
        components = field.target_width if index%2 else 1
        norms[field.name] = TrainNormalization((center,)*components, (1.3,)*components, 'b'*64, 'fixture')
    original = compute_v3_loss(predictions,targets,registry,norms,enabled_groups=('P',))
    grouped = grouped_regression_loss(predictions,targets,registry,norms,enabled_groups=('P',))
    assert grouped.counts == original.counts
    for name in original.fields:
        torch.testing.assert_close(grouped.fields[name],original.fields[name],atol=1e-7,rtol=1e-6)
