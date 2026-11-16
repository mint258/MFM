"""E1: the same normalized output gives the same original physical loss."""
import numpy as np
import torch

from phychem_mfm.phase1.v31_loader import TrainingView
from phychem_mfm.phase1.v31_training import V31PDModel, torch_affine


def test_e1_normalized_output_preserves_loss_units_energy_reference_and_vector():
    class Encoder(torch.nn.Module):
        latent_dim = 8
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.ones(()))
    schema = dict(columns={
        'mol_labels': [dict(field_key='energy', column_index=0, family='energy', level='molecule', kind='scalar')],
        'atom_vectors': [dict(field_key='force', column_index=0, family='gradient', level='atom_vector', kind='vector')]},
        source_D3_reference={'sha256': 'a' * 64})
    energy = dict(fit_role='TRAIN', center=64., scale=.125,
                  element_reference=dict(basis=[6], coefficients=[100.]))
    vector = dict(fit_role='TRAIN', center=0., scale=.25)
    fields = [dict(name='energy', group='P', family='energy', level='molecule', normalization=energy),
              dict(name='force', group='P', family='gradient', level='atom_vector',
                   representation='vector', normalization=vector)]
    view = TrainingView(schema, dict(fields=fields))
    from phychem_mfm.phase1.v31_loader import V31Target
    sample = dict(Z=np.array([6], dtype=np.uint8), targets={
        'energy': V31Target(np.array([[164.25]],dtype=np.float32), np.array([[2.]],dtype=np.float32),
                           np.ones((1,1),dtype=bool),'P','energy','molecule','scalar',True),
        'force': V31Target(np.zeros((1,3),dtype=np.float32), np.zeros((1,3),dtype=np.float32),
                          np.ones((1,3),dtype=bool),'P','gradient','atom_vector','vector',True)})
    old = V31PDModel(Encoder(), view)
    new = V31PDModel(Encoder(), view, output_parameterization='normalized')
    normalized = {'energy': torch.tensor([[3.]],requires_grad=True),
                  'force': torch.tensor([[1.,2.,3.]],requires_grad=True)}
    raw = {name: torch_affine(value, energy if name=='energy' else vector,inverse=True)
           for name,value in normalized.items()}
    old_loss, new_loss = old.loss(raw,[sample],groups=('P',)), new.loss(normalized,[sample],groups=('P',))
    torch.testing.assert_close(new_loss.total, old_loss.total, atol=1e-6,rtol=1e-5)
    for name in old_loss.fields:
        torch.testing.assert_close(new_loss.fields[name],old_loss.fields[name],atol=1e-6,rtol=1e-5)
    expected = old.original_predictions(raw,[sample])
    actual = new.original_predictions(normalized,[sample])
    for name in expected:
        torch.testing.assert_close(actual[name],expected[name],atol=1e-6,rtol=1e-5)
