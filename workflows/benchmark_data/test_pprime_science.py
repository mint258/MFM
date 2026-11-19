"""Only the new downstream input/I/O boundary; no quantum executable is invoked."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import numpy as np
from rdkit import Chem
from workflows.benchmark_data.pprime_science import native_input,Adapter


def fixture_source():
    mol=Chem.AddHs(Chem.MolFromSmiles('CCO'))
    source={'model_smiles':'CCO','atomic_numbers':[a.GetAtomicNum() for a in mol.GetAtoms()]}
    conformer={'conformer_id':2,'converged':True,'geometry_source':'UFF_Sprime',
        'coordinates_A':[[i*10.,0.,0.] for i in range(mol.GetNumAtoms())]}
    return source,conformer


class DownstreamBoundaryTests(unittest.TestCase):
    def test_atom_order_and_existing_coordinates_are_bound_without_generation(self):
        source,conformer=fixture_source();native=native_input(source,conformer)
        self.assertTrue(np.array_equal(native['coords'],conformer['coordinates_A']))
        self.assertIn((1,0),native['pairs'])  # source bond survives beyond 4 A
        self.assertNotIn((2,0),native['pairs'])
        self.assertIsNone(native['energy'])
        source['atomic_numbers'][0]=8
        with self.assertRaises(ValueError):native_input(source,conformer)

    def test_one_failed_task_preserves_all_twelve_requests_and_raw_policy(self):
        source,conformer=fixture_source();names=['pm7_B','pm7_water','pm7_octanol','pm7_cation','pm7_anion',
            'xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol','xtb_fod','xtb_perturbed_gradient']
        tasks=[{'name':n,'family':'mopac' if i<5 else 'xtb','keywords':'fixture'} for i,n in enumerate(names)]
        cleanup=Mock(return_value=0);native=SimpleNamespace(cleanup_scratch=cleanup,DEADLINE=float('inf'),UNFINISHED=())
        engine=SimpleNamespace(NATIVE=native,CONFIG={'tasks':tasks,'pair_cutoff_A':4.,'expected_versions':{'mopac':'fixture1','xtb':'fixture2'},
            'registry':{'path':'synthetic-registry'},'units':{'energy':'fixture'}},
            PARSER=SimpleNamespace(context=lambda:{}),validate_atomic_arrays=lambda *args:[],canonical_status=lambda s:s,
            extract_scf=lambda *args:{'scf_iterations':1,'converged':True,'iteration_definition':'fixture','missing_reason':None},
            PACKAGE={'software_versions':{'mopac':{'software_version_id':1},'xtb':{'software_version_id':2}}},
            REGISTRY=[],WIRE=SimpleNamespace(wanted=lambda e:True),derived_quantities=Mock())
        with tempfile.TemporaryDirectory() as tmp:
            adapter=Adapter(engine,Path(tmp),{'path':'synthetic-original-package'})
            called=[];retained=[]
            def invoke(task,data,row,work):
                called.append(task['name']);self.assertTrue(np.array_equal(data['coords'],conformer['coordinates_A']))
                path=Path(tmp)/task['name'];path.mkdir();(path/'input.out').write_text('synthetic output')
                (path/'input.xyz').write_text('input must never be archived')
                paths=[path/'input.out'];native.output_archive(paths,None,None);native.cleanup_scratch(path)
                return {'task':task['name'],'status':'PROPERTY_FAILED' if task['name']=='pm7_octanol' else 'SUCCESS',
                    'values':{},'Q02_delta_HOF_kcal_mol':None}
            native.invoke=invoke
            def sink(meta,files,keep,admit):
                if keep:retained.append((meta['calc_type'],[f['name'] for f in files]))
                return {'output_retained':keep}
            result=adapter.compute(source,conformer,{'record_id':'synthetic','molecule_id':'synthetic',
                'record_payload_sha256':None,'audit_selected':False},sink,lambda needed:None)
            self.assertEqual(called,names)
            self.assertEqual(retained,[('pm7_octanol',['input.out'])])
            self.assertEqual(cleanup.call_count,12)
            self.assertFalse(result['all_twelve_tasks_success']);self.assertFalse(result['P_ready'])
            engine.derived_quantities.assert_called_once()

if __name__=='__main__':unittest.main()
