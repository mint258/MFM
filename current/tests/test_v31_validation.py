import numpy as np
import pytest
import torch

from phychem_mfm.phase1.v31_loader import TrainingView
from phychem_mfm.phase1.v31_training import V31PDModel
from phychem_mfm.phase1.v31_validation import validate_v31


def test_unseen_and_seen_molecule_diagnostic_metrics_never_mix(tmp_path):
    pa = pytest.importorskip('pyarrow')
    import pyarrow.parquet as pq
    class Encoder(torch.nn.Module):
        latent_dim = 8
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.ones(()))
        def encode_atoms(self, batch):
            return batch.x.float().repeat(1, 8) * self.weight
    schema = dict(columns={'mol_labels': [dict(field_key='label', column_index=0,
        family='shape', level='molecule', kind='scalar')]}, source_D3_reference={'sha256':'a'*64})
    view = TrainingView(schema, dict(fields=[dict(name='label', group='D', family='shape',
        level='molecule', normalization=dict(fit_role='TRAIN',center=0.,scale=1.))]))
    model = V31PDModel(Encoder(), view)
    for parameter in model.parameters():
        torch.nn.init.zeros_(parameter)
    class Dataset:
        source = 'PM7'
        _index_set = {0}
        def __init__(self, directory, diagnostic):
            self.directory, self.diagnostic = directory, diagnostic
        def read(self, molecule, conformer):
            value = 9. if self.diagnostic else 1. + 2*conformer
            m = {1:np.array([6,1],dtype=np.uint8)}
            return dict(Z=m[1], pos=np.zeros((2,3),dtype=np.float32),pos_perturbed=None,
                bonds=np.array([[0,1]]),bond_order=np.array([1]),
                targets=view.extract(m,{23:np.array([value],dtype=np.float32)}))
    populations = {}
    for role, diagnostic in [('FULL',False), ('TRAIN_UNSEEN_CONFORMATION',True)]:
        directory = tmp_path/role
        directory.mkdir()
        pq.write_table(pa.table(dict(record_kind=['M','P','P'], molecule_index=[0,0,0],
            conformer_index=[None,0,1], holdout=[False,False,diagnostic])), directory/'id_map.parquet')
        populations[role] = Dataset(directory, diagnostic)
    result = validate_v31(populations, pd_model=model, groups=('D',), batch_size=1)
    full, diagnostic = result['FULL'], result['TRAIN_UNSEEN_CONFORMATION']
    assert full['records'] == 2 and diagnostic['records'] == 1
    assert full['source_column_metrics']['label']['MAE'] == pytest.approx(2., abs=1e-6, rel=1e-6)
    assert diagnostic['source_column_metrics']['label']['MAE'] == pytest.approx(9., abs=1e-6, rel=1e-6)
    assert full['source_column_metrics']['label']['R2'] == pytest.approx(-4., abs=1e-6, rel=1e-6)
    assert diagnostic['source_column_metrics']['label']['R2'] is None
    assert not full['selection_use'] and not diagnostic['selection_use'] and model.training
