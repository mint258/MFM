"""Three synthetic execution boundaries,no DATA,native initialize or invoke."""
import copy,pathlib,sys,tempfile,unittest
from . import contract as C,resources as B,io as W,metadata as M,analysis as A
def synthetic_plan():
    ref={'path':'/synthetic/protocol.json','bytes':1,'sha256':'0'*64};prepared={'path':'/synthetic/prepared20.json','bytes':1,'sha256':'1'*64}
    return {'original_protocol_reference':ref,'candidate_protocol_reference':{**ref,'sha256':'2'*64},'prepared20_reference':prepared,'wall_seconds':86400}
def synthetic_matrix():return [{'qa_id':'qa20-%02d-%02d'%(i,j),'molecule_id':'SYNTHETIC-MID-%02d'%i,'condition':C.P.TASKS[j//5],'arm':C.P.ARMS[j%5]} for i in range(20) for j in range(60)]
class Boundaries(unittest.TestCase):
    def test_exact_new20_user_authority_before_any_body_not_old15_or_template(self):
        for plan in ({},{'user_decision_reference':None}):
            with self.assertRaises(ValueError):C.require_user(plan)
        plan=synthetic_plan();value=M.decision_template(plan)
        with self.assertRaises(ValueError):C.user_fields(value,plan)
        value.update(status='USER_AUTHORIZED',actual_user_statement='SYNTHETIC_UNIT_VALUE_ONLY_NO_REAL_APPROVAL',not_authorized_by_this_template=False)
        C.user_fields(value,plan)
        for key,replacement in (('schema','USER_AUTHORIZED_PPRIME_STRICT_NUMERICS15_QA_V1'),('maximum_new_QM_calls',1201),('maximum_wall_seconds',7200),
            ('automatic_retry',True),('maximum_simultaneous_native_calls',17),('production_or2000_full_release','RELEASE'),('not_authorized_by_this_template',True)):
            bad=copy.deepcopy(value);bad[key]=replacement
            with self.assertRaises(ValueError):C.user_fields(bad,plan)
        changed={**plan,'prepared20_reference':{**plan['prepared20_reference'],'sha256':'3'*64}}
        with self.assertRaises(ValueError):C.user_fields(value,changed)
    def test_exclusive_once_and_closed25M_unknown112M_natural_drain_roles(self):
        plan=synthetic_plan();key=C.once_key(plan,'qa20-00-00');self.assertNotEqual(key,C.once_key(plan,'qa20-00-01'))
        self.assertNotEqual(key,C.once_key({**plan,'candidate_protocol_reference':{**plan['candidate_protocol_reference'],'sha256':'4'*64}},'qa20-00-00'))
        with tempfile.TemporaryDirectory(prefix='new20_pure_claim_') as d:
            p=pathlib.Path(d);store=W.Store(p,3<<20);claim=p/(key+'.json');W.claim_create(claim,{'synthetic':True},store)
            with self.assertRaises(FileExistsError):W.claim_create(claim,{'synthetic':True},store)
        roles=B.Roles()
        for i in range(1184):roles.start('closed-'+str(i));roles.settle('closed-'+str(i),C.CLOSED_CAP,True)
        for i in range(16):roles.start('active-'+str(i))
        self.assertEqual(C.P.PREP_CAP+roles.bound(),32672<<20)
        with self.assertRaises(ValueError):roles.start('seventeenth')
        roles.settle('active-0',26<<20,True);self.assertIn('active-0',roles.unknown);self.assertTrue(roles.stop)
        with self.assertRaises(ValueError):roles.start('replacement')
        for i in range(1,16):roles.settle('active-'+str(i),1<<20,True)
        self.assertEqual(roles.active,set());self.assertIn('active-0',roles.unknown)
    def test_exact12_fivearm_matrix_and_shared_semantic_UNKNOWN_not_fake_axis_PASS(self):
        rows=synthetic_matrix();self.assertEqual(len(C.matrix(rows)),1200)
        for change in ('MID','ARM','MISSING'):
            bad=copy.deepcopy(rows)
            if change=='MID':
                for row in bad:
                    if row['molecule_id']=='SYNTHETIC-MID-19':row['molecule_id']='SYNTHETIC-MID-00'
            elif change=='ARM':bad[0]['arm']='P1'
            else:bad.pop()
            with self.assertRaises(ValueError):C.matrix(bad)
        record={'qa_id':'SYNTHETIC','molecule_id':'SYNTHETIC-MID','condition':'pm7_water','arm':'B1',
            'native_invoke_function_return_observed':True,'parsed_wp5_result':{'scope_status':'SUCCESS','atomic_array_validation':[]},
            'actual_postcall_input_references':[{'matches_prepared_bytes':True}],'closed_raw_container_reference':{'synthetic':True},
            'raw_readback_source':'CLOSED_SQLITE_GZIP_EOF_CRC_WHOLE_AND_MEMBER_SHA_ORIGINAL_UNBUNDLE'}
        check,_=A.own(record,{});self.assertTrue(check['defined_QC_pass']);self.assertTrue(check['interpretation_UNKNOWN'])
        bad=copy.deepcopy(record);bad['parsed_wp5_result']['scope_status']='CALCULATION_FAILED';self.assertFalse(A.own(bad,{})[0]['defined_QC_pass'])
        saved=list(sys.path);sys.path[:0]=[str(C.O.PPRIME),str(C.O.PPRIME/'vector_audit')]
        try:
            dip=[2.541746473,5.083492946,7.625239419];sp=copy.deepcopy(record);sp.update(condition='xtb_singlepoint',case={'case_id':'SYNTHETIC','calc_type':'xtb_singlepoint'},
                independent_raw_readback={'xtb_dipole':{'dipole_Debye':dip,'raw_atomic_units':[1.,2.,3.],'rounding_halfwidth_Debye':[1e-9]*3}})
            sp['parsed_wp5_result']['values']={'dipole_Debye':dip};check,measured=A.own(sp,{})
            self.assertTrue(check['defined_QC_pass']);self.assertFalse(measured['coordinates']['supports_input_axes'])
            self.assertTrue(any('NO_INDEPENDENT_OUTPUT_COORDINATE_BLOCK' in x for x in check['interpretation_UNKNOWN']))
            sp['independent_raw_readback']={};self.assertFalse(A.own(sp,{})[0]['defined_QC_pass'])
        finally:sys.path[:]=saved
if __name__=='__main__':unittest.main()
