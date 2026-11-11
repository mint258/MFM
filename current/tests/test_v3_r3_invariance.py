"""The single additional taskbook-v3 R3 permutation/padding unit test."""
import torch

from phychem_mfm.phase1.v3_dev_readouts import FrozenFeatureProbe


def test_r3_atom_permutation_and_padding_do_not_change_prediction():
    torch.manual_seed(20261025)
    model = FrozenFeatureProbe(512,readout='R3',output_level='graph',n_ref=4.,
        mean=torch.randn(512),scale=torch.rand(512)+.5).eval()
    x = torch.randn(2,5,512,dtype=torch.float32)
    mask = torch.tensor([[True,True,True,False,False],[True]*5])
    with torch.no_grad():
        reference = model(x,mask)
        permutation = torch.tensor([4,2,0,3,1])
        permuted = model(x[:,permutation],mask[:,permutation])
        padding = torch.full((2,4,512),float('nan'),dtype=torch.float32)
        padded = model(torch.cat((x,padding),dim=1),
                       torch.cat((mask,torch.zeros(2,4,dtype=torch.bool)),dim=1))
    for actual in (permuted,padded):
        tolerance = torch.maximum(torch.full_like(reference,1e-6),1e-5*reference.abs())
        assert bool(((actual-reference).abs()<=tolerance).all())
