"""Three synthetic in-Parent methods; never initialize/invoke a native program."""
import copy,hashlib,json,pathlib,sys,unittest
from . import contract as C,prepare as P
WORKSPACE=None
class Boundaries(unittest.TestCase):
    def test_exact_original1000x2_has_no_QA80_atom_filter(self):
        pairs=[{'record_id':'synthetic:%d:%d'%(i,j),'molecule_id':'m%d'%i,'geometry_source':'uff_sprime','random_order_rank':j,
          'source':{'total_atoms':120},'conformer':{'sprime_conf_idx':j+7}} for i in range(1000) for j in range(2)]
        self.assertEqual(len(C.pairs_matrix(pairs)),1000)
        bad=copy.deepcopy(pairs);bad[1]['conformer']['sprime_conf_idx']=7
        with self.assertRaises(ValueError):C.pairs_matrix(bad)
        bad=copy.deepcopy(pairs);bad[1]['random_order_rank']=True
        with self.assertRaises(ValueError):C.pairs_matrix(bad)
        bad=copy.deepcopy(pairs);bad[1]['record_id']=bad[0]['record_id']
        with self.assertRaises(ValueError):C.pairs_matrix(bad)
        for node in C.NODES:self.assertEqual(C.parameters(node)['node'],node)
        for name in ('record','charge','check'):self.assertIs(getattr(P.Budget,name),getattr(C.ResourceOrigin.Budget,name))

    def test_large_DATA_locator_and_input_coordinate_hash_seam(self):
        ref={'path':'/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/synthetic/pairs.jsonl','bytes':19385976,'sha256':'a'*64}
        self.assertEqual(C.triple(ref),ref)
        C.distinct_geometry('a'*64,'b'*64)
        with self.assertRaises(ValueError):C.distinct_geometry('a'*64,'a'*64)
        for key,value in (('bytes',True),('bytes',0),('sha256','a'*65)):
            bad=dict(ref);bad[key]=value
            with self.assertRaises(ValueError):C.triple(bad)
        tasks=[{'name':n,'tag':'original'} for n in C.O.TASKS];new=copy.deepcopy(tasks)
        for task in new:
            if task['name'] in ('pm7_B','xtb_singlepoint','xtb_perturbed_gradient'):task['tag']='candidate'
        class Engine:
            @staticmethod
            def render_inputs(task,native,row,protocol):
                if task['name'].startswith('pm7'):
                    return {'input.xyz':b'1\n\nC 0 0 0\n','input.mop':task['tag'].encode()+b'\n\n\nC 0 1 0 1 0 1\n'}
                return {'input.xyz':b'1\n\nC 0 0 0\n','native.inp':task['tag'].encode()}
        pair={'source':{},'record_id':'synthetic','molecule_id':'m0'}
        result=P.input_hashes(Engine,None,pair,{'tasks':tasks},{'tasks':new});self.assertEqual(len(result),12)
        differences={r['task'] for r in result if r['original_input_file_sha256']!=r['candidate_input_file_sha256']}
        self.assertEqual(differences,{'pm7_B','xtb_singlepoint','xtb_perturbed_gradient'})
        class Wrong:
            @staticmethod
            def render_inputs(task,native,row,protocol):return {'input.xyz':b'1\n\nC '+task['tag'].encode()+b' 0 0\n'}
        with self.assertRaises(ValueError):P.input_hashes(Wrong,None,pair,{'tasks':tasks},{'tasks':new})

    def test_original_parent_cost_and_success_gates_are_not_diag_PERMISSION(self):
        sys.path.insert(0,str(C.Q.REPO/'workflows/data_v1_final/pprime'))
        from close_pilot import assess
        result={'runtime':{'job_id':'123','node':'compute-0-14'},'completed_records':2000,'status':'PPRIME_PILOT_COMPUTE_CLOSED_AWAITING_PARENT_ACCOUNTING',
          'failures':[],'all_workers_joined':True,'record_success_rate':.995}
        row={'JobIDRaw':'123','User':'zixiao','ElapsedRaw':'1462','AllocCPUS':'16','NodeList':'compute-0-14','State':'COMPLETED','ExitCode':'0:0'}
        config={'minimum_success_rate':.995,'maximum_allocated_core_seconds_per_conformer':11.7}
        self.assertTrue(all(assess(result,[row],config)['gates'].values()))
        row['ElapsedRaw']='1463';self.assertFalse(assess(result,[row],config)['gates']['allocated_seconds_within_1_5x_wp5'])
        result['record_success_rate']=.9945;self.assertFalse(assess(result,[row],config)['gates']['record_success_at_least_99_5_percent'])
        proposal=C.proposal();self.assertEqual(proposal['maximum_native_calls'],24000);self.assertEqual(proposal['arms_per_geometry'],1)
        self.assertIn('NEW_EXPLICIT_USER_AUTHORIZED',proposal['tighter_option']);self.assertTrue(proposal['full_release_not_authorized'])
