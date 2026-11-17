import contextlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from phychem_mfm.phase1.v31_loader import normalize_values,record_key,V31Target
from phychem_mfm.phase1.p_f64_sidecar import PFloat64Sidecar

class F64SidecarChecks(unittest.TestCase):
    def test_float64_reference_cancellation_precedes_final_f32_cast(self):
        spec=dict(fit_role='TRAIN',center=0.,scale=2.,element_reference=dict(basis=[6],coefficients=[1e9],intercept=0.))
        raw=np.array([[1e9+.125]],dtype=np.float64)
        result=normalize_values(raw,spec,Z=np.array([6]))
        self.assertEqual(result.dtype,np.float32);self.assertEqual(result[0,0],.0625)
        self.assertEqual(normalize_values(raw.astype(np.float32),spec,Z=np.array([6]))[0,0],0.)
    def test_f32_default_normalization_is_bit_identical(self):
        spec=dict(fit_role='TRAIN',center=1.37,scale=2.19,element_reference=dict(basis=[6],coefficients=[.083],intercept=.127))
        raw=np.array([[2.1],[np.nan],[-1.3]],dtype=np.float32);Z=np.array([6,6])
        reference=(raw-np.float32(.127+2*.083)-np.float32(1.37))/np.float32(2.19)
        np.testing.assert_array_equal(normalize_values(raw,spec,Z=Z).view('u4'),reference.view('u4'))
    def test_lookup_handles_and_nan_fallback(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as resources:
            p=Path(directory);data=np.zeros(3,dtype=[('molecule_index','<u4'),('conformer_index','<u2'),('record_handle','S7'),('energy','<f8')])
            data['molecule_index']=[0,0,1];data['conformer_index']=[0,0,2]
            data['record_handle']=[record_key('P',0,0),record_key('U',0,0),record_key('P',1,2)];data['energy']=[1e9+.125,np.nan,2.5]
            np.save(p/'values.npy',data);np.save(p/'offsets.npy',np.array([0,2,3]))
            (p/'manifest.json').write_text(json.dumps(dict(status='SUBSET_TEST',enabled_fields=['energy'],splits=dict(TRAIN=dict(D6_directory=directory,values='values.npy',molecule_offsets='offsets.npy')))))
            side=PFloat64Sidecar(p/'manifest.json','TRAIN',p)
            cleanup.callback(side.close)
            resources.callback(side.close)
            self.assertEqual(side.lookup(0,0,'P')['energy'],1e9+.125)
            self.assertTrue(np.isnan(side.lookup(0,0,'U')['energy']));self.assertEqual(side.lookup(0,2,'P'),{})
            spec=dict(fit_role='TRAIN',center=0.,scale=1.)
            target=V31Target(np.array([[5.]],np.float32),np.array([[5.]],np.float32),np.array([[True]]),'P','energy','molecule','scalar',True)
            view=SimpleNamespace(fields=[dict(name='energy',normalization=spec)],normalizations={})
            self.assertIs(side.apply(dict(energy=target),0,0,'U',view,np.array([6]))['energy'],target)
            self.assertEqual(side.apply(dict(energy=target),0,0,'P',view,np.array([6]))['energy'].raw.dtype,np.float64)
            with self.assertRaisesRegex(ValueError,'split location'):
                PFloat64Sidecar(p/'manifest.json','TRAIN',p/'wrong')
if __name__=='__main__':unittest.main()