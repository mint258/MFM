import json,os,unittest
from pathlib import Path
import numpy as np,torch
from chemprop import data,nn,models
from workflows.benchmark_data.admission import protect
torch.set_num_threads(1);torch.set_num_interop_threads(1)
def components(rows):
    return data.MulticomponentDataset([data.MoleculeDataset([data.MoleculeDatapoint.from_smi(r[key],[r['y']],x_d=np.asarray([float(r.get('is_gas',False))]) if key=='feature_smiles' else None) for r in rows]) for key in ('feature_smiles','solvent_smiles')])
class OpticalRoleInterfaceTests(unittest.TestCase):
    def test_two_component_graph_preserves_ordered_chromophore_and_solvent_roles(self):
        rows=[dict(feature_smiles='CCC',solvent_smiles='O',y=1.),dict(feature_smiles='CCC',solvent_smiles='CCO',y=2.)]
        dataset=components(rows);batch=next(iter(data.build_dataloader(dataset,batch_size=2,shuffle=False,drop_last=False)))
        mp=nn.MulticomponentMessagePassing([nn.BondMessagePassing(),nn.BondMessagePassing()],n_components=2,shared=False)
        model=models.MulticomponentMPNN(mp,nn.MeanAggregation(),nn.RegressionFFN(input_dim=mp.output_dim+1));model.eval()
        with torch.inference_mode():fingerprint=model.fingerprint(batch.bmgs,batch.V_ds,batch.X_d);prediction=model(batch.bmgs,batch.V_ds,batch.X_d)
        self.assertEqual(tuple(fingerprint.shape),(2,601));self.assertEqual(tuple(prediction.shape),(2,1))
        torch.testing.assert_close(fingerprint[0,:300],fingerprint[1,:300])
        self.assertFalse(torch.allclose(fingerprint[0,300:600],fingerprint[1,300:600]))
    def test_target_scaler_is_fitted_only_on_training_observations(self):
        training=components([dict(feature_smiles='CCC',solvent_smiles='O',y=2.),dict(feature_smiles='CCC',solvent_smiles='CCO',y=4.)])
        scaler=training.normalize_targets();self.assertAlmostEqual(float(scaler.mean_[0]),3.)
        testing=components([dict(feature_smiles='CCCC',solvent_smiles='O',y=10000.)])
        self.assertAlmostEqual(float(scaler.mean_[0]),3.)
    def test_declared_gas_condition_uses_native_empty_graph_and_explicit_phase_flag(self):
        rows=[dict(feature_smiles='CCC',solvent_smiles='',is_gas=True,y=1.),dict(feature_smiles='CCC',solvent_smiles='O',is_gas=False,y=2.)]
        dataset=components(rows)
        self.assertEqual(dataset.datasets[1].data[0].mol.GetNumAtoms(),0)
        batch=next(iter(data.build_dataloader(dataset,batch_size=2,shuffle=False,drop_last=False)))
        mp=nn.MulticomponentMessagePassing([nn.BondMessagePassing(),nn.BondMessagePassing()],n_components=2,shared=False)
        model=models.MulticomponentMPNN(mp,nn.MeanAggregation(),nn.RegressionFFN(input_dim=mp.output_dim+1));model.eval()
        with torch.inference_mode():prediction=model(batch.bmgs,batch.V_ds,batch.X_d)
        self.assertEqual(tuple(prediction.shape),(2,1))
        np.testing.assert_array_equal(batch.X_d.cpu().numpy().ravel(),[1.,0.])

tests=unittest.defaultTestLoader.loadTestsFromTestCase(OpticalRoleInterfaceTests)
if not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful():raise SystemExit(1)
print('OPTICAL_GAS_CONTEXT_INTERFACE_PASS',tests.countTestCases(),flush=True)
