"""Three synthetic boundaries; Root runs them before existing DATA or monitors."""
import copy,importlib,pathlib,sys,unittest
from . import contract as C,reduce as D,tensor as T,native as N

class Boundaries(unittest.TestCase):
    def test_full_defined_mass_empty_tasks_and_scf_are_separate(self):
        groups=[];own=[];pairs=[]
        for i in range(20):
            rows=[];checks=[]
            for j,name in enumerate(C.P.E.P.TASKS):
                for k,arm in enumerate(C.P.E.P.ARMS):
                    row={'qa_id':'qa20-%02d-%02d'%(i,j*5+k),'molecule_id':'synthetic_%02d'%i,'condition':name,'arm':arm,
                        'checks':{'synthetic_technical_flag':True},'defined_QC_pass':True,'interpretation_UNKNOWN':['SYNTHETIC_UNADOPTED_DOMAIN'],
                        'SCF_converged_original_metadata':None}
                    rows.append(row)
                for a,b in D.A.PAIRS:
                    values={f:{'pass':True,'within_numeric_allowance':True,'sufficient_signal':True,'max_abs_residual':0.,'max_allowance':1e-8}
                        for f in D.A.FIELDS.get(name,set())}
                    checks.append({'molecule_id':'synthetic_%02d'%i,'condition':name,'arms':[a,b],
                        'defined_vector_checks':values,'defined_QC_pass':True,'unsupported_axes_basis_tensors_certified':False})
            groups.append({'schema':'STRICT20_READBACK_EXACT_GROUP_EVIDENCE_V1','group_index':i,'original_own_call_checks':rows,'original_pair_checks':checks})
            own.extend(rows);pairs.extend(checks)
        config={k:{} for k in ('coordinate_atol_A','vector_tolerances','rendered_coordinate_atol_A','same_geometry_dipole_atol_au')}
        analysis={'schema':'PPRIME_NEW20_DEFINED_QA_CHECKS_V1','own_call_checks':own,'pair_checks':pairs,'old15FAIL_preserved':True,
            'scientific_PASS':False,'full_or2000_release':'HOLD','original_predeclared_tolerances':config}
        result,_=D.collect(analysis,groups,config,self.assertEqual)
        self.assertEqual((result['own_rows'],result['pair_rows'],result['vector_checks'],result['empty_vector_pair_rows']),(1200,1200,500,900))
        self.assertEqual(result['SCF_original_converged_counts'],{'NULL_UNKNOWN':1200});self.assertFalse(result['scientific_PASS'])
        with self.assertRaises(Exception):D.collect(analysis,groups[:-1],config,self.assertEqual)
        with self.assertRaises(Exception):D.scf_state(1)

    def test_original_tensor_signal_and_coordinate_tolerance(self):
        import numpy as np
        path=C.REPO/'workflows/data_v1_final/pprime/vector_audit'
        if str(path) not in sys.path:sys.path.insert(0,str(path))
        m=importlib.import_module('math_v1');self.assertEqual(pathlib.Path(m.__file__),path/'math_v1.py')
        q=[1.,.2,-.3,.4,-.5,-.7];r=np.asarray([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
        rotated=r@m.tensor_matrix(q)@r.T;qr=[rotated[0,0],rotated[0,1],rotated[1,1],rotated[0,2],rotated[1,2],rotated[2,2]]
        tol={'atol':1e-10,'rtol':0.,'minimum_tensor_norm':1e-8}
        self.assertEqual(T.state(m.tensor_covariance(q,qr,[0.]*6,[0.]*6,tol,rotation=r)),'PASS')
        wrong=list(qr);wrong[1]+=1e-3
        self.assertEqual(T.state(m.tensor_covariance(q,wrong,[0.]*6,[0.]*6,tol,rotation=r)),'FAIL_NUMERIC_ALLOWANCE')
        self.assertEqual(T.state(m.tensor_covariance([0.]*6,[0.]*6,[0.]*6,[0.]*6,tol,rotation=r)),'UNDEFINED_INSUFFICIENT_SIGNAL')
        xyz=[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]];out=copy.deepcopy(xyz);out[1][0]+=5e-12
        value={'key':{'calc_type':'pm7_B'},'input_binding':{'program_coordinates_A':xyz,'symbols':['C','H','H']},
            'geometry':{'state':'DESCRIPTIVE_NOT_SIGNED','float64_coordinates_exactly_equal':False,'original_reader_output':{
                'ATOM_X_OPT:ANGSTROMS':{'values':out},'ATOM_EL':{'values':['C','H','H']}}}}
        got=N.frame(value,{'coordinate_atol_A':{'mopac':1e-9,'xtb':1e-9}},m)
        self.assertEqual(got['state'],'PASS_ORIGINAL_COORDINATE_AND_ATOM_ORDER_GATE')
        self.assertFalse(got['printed_float64_exact_is_not_the_tolerance_gate'])
        self.assertEqual(N.frame({'key':{'calc_type':'xtb_singlepoint'},'input_binding':{},'geometry':{'state':'NO_COORD_BLOCK'}},{},m)['state'],
            'UNKNOWN_NO_INDEPENDENT_NATIVE_COORDINATE_BLOCK')

    def test_exact_detail_domain_large_data_and_unknown_not_promoted(self):
        index=C.P.E.P.TASKS.index('xtb_singlepoint');grad=C.P.E.P.TASKS.index('xtb_perturbed_gradient')
        refs=[{'path':str(C.P.ACTUAL/('qa20-00-%02d'%(index*5+k))/'all_output_raw.sqlite'),'bytes':25<<20,'sha256':'a'*64} for k in range(5)]
        refs.extend({'path':str(C.P.ACTUAL/('qa20-00-%02d'%(grad*5+k))/'result.DATA.json'),'bytes':3<<20,'sha256':'b'*64} for k in range(5))
        self.assertEqual(sum(C.is_detail_reference(r) for r in refs),10)
        prepare=C.ROOT/'artifacts/synthetic_no_body_prepare'
        ep={'candidate_protocol_reference':{'path':str(C.ROOT/'control/synthetic_protocol.json'),'bytes':1,'sha256':'c'*64},
            'prepared20_reference':{'path':str(prepare/'prepared20.json'),'bytes':1,'sha256':'d'*64}}
        qas=['qa20-00-%02d'%(j*5+k) for j in (index,grad) for k in range(5)]
        task_refs=[{'path':str(prepare/'tasks'/(qa+'.DATA.json')),'bytes':32,'sha256':'e'*64} for qa in qas]
        claim_refs=[{'path':str(C.P.E.LEDGER/(C.P.E.once_key(ep,qa)+'.json')),'bytes':64,'sha256':'f'*64} for qa in qas]
        selected,proof=C.select_detail_references([*refs,*task_refs,*claim_refs],0,prepare,ep)
        self.assertEqual(len(selected),30);self.assertTrue(proof['task_claim_triples_in_original_group_inventory'])
        self.assertTrue(all(C.is_detail_reference(r) for r in task_refs));self.assertFalse(any(C.is_detail_reference(r) for r in claim_refs))
        for missing in (task_refs[0],claim_refs[0]):
            with self.assertRaises(Exception):C.select_detail_references([r for r in [*refs,*task_refs,*claim_refs] if r!=missing],0,prepare,ep)
        self.assertEqual(C.P.triple(refs[0])['bytes'],25<<20)
        for patch in ({'bytes':True},{'bytes':-1},{'sha256':'a'*65}):
            with self.assertRaises(Exception):C.P.triple({**refs[0],**patch})
        other=next(i for i,n in enumerate(C.P.E.P.TASKS) if n not in ('xtb_singlepoint','xtb_perturbed_gradient'))
        self.assertFalse(C.is_detail_reference({'path':str(C.P.ACTUAL/('qa20-00-%02d'%(other*5))/'result.DATA.json')}))
        self.assertEqual(T.state({'pass':False}),'UNKNOWN_UNAVAILABLE_OR_INVALID')
        old=T.old_controls({'contradictions':[{'reason':'ORIGINAL_FAIL'}],'rotation_comparisons':[],
            'quadrupole_origin_controls':[],'same_geometry_SP_gradient_controls':[]})
        self.assertEqual(old['missing_origin_controls'],'UNKNOWN_NO_RETAINED_CONTROL')
        self.assertEqual(old['finite_difference_energy_gradient_control'],'NOT_MEASURED')
