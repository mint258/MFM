"""Three pure proposal boundaries; no real inputs, engine initialization or QM."""
import copy,unittest
from . import proposal as P


def baseline():
    tasks=[]
    for i,name in enumerate(P.NAMES):
        row={'name':name,'family':'mopac' if i<5 else 'xtb'}
        if i<5:row['keywords']=P.BASE_PM7 if name=='pm7_B' else 'PM7 1SCF CHARGE=0'
        else:row['args']=list(P.XTB_GRAD if name=='xtb_perturbed_gradient' else P.XTB_SP)
        if name=='xtb_perturbed_gradient':row['perturbed']=True
        tasks.append(row)
    return {'tasks':tasks,'seed':20261010,'perturb_sigma_A':.1,'timeout_seconds':900,'unchanged_synthetic_marker':{'nested':[1,2,3]}}


class Boundaries(unittest.TestCase):
    def test_only_three_fields_and_inverse_exact_original(self):
        old=baseline();saved=copy.deepcopy(old);new,diff=P.derive(old)
        self.assertEqual(old,saved);self.assertEqual(P.restore(new),old);self.assertEqual(len(diff),3)
        for index in (1,2,3,4,6,7,8,9,10):self.assertEqual(new['tasks'][index],old['tasks'][index])
    def test_existing_override_seed_timeout_or_geometry_flags_rejected(self):
        for change in ('SCFCRT','ACC','TIMEOUT','SEED'):
            b=baseline()
            if change=='SCFCRT':b['tasks'][0]['keywords']+=' SCFCRT=1.D-8'
            elif change=='ACC':b['tasks'][5]['args']+=['--acc','0.1']
            elif change=='TIMEOUT':b['timeout_seconds']=1800
            else:b['seed']+=1
            with self.assertRaises(ValueError):P.derive(b)
        b,_=P.derive(baseline());b['tasks'][5]['args']+=['--opt']
        with self.assertRaises(ValueError):P.restore(b)
    def test_new_once_key_protocol_and_case_binding(self):
        ref={'path':'/synthetic/candidate.json','bytes':1,'sha256':'0'*64};prep={'path':'/synthetic/old-prepared.json','bytes':1,'sha256':'2'*64}
        first=P.once_key(ref,prep,'qa-00');self.assertEqual(first,P.once_key(ref,prep,'qa-00'))
        self.assertNotEqual(first,P.once_key({**ref,'sha256':'1'*64},prep,'qa-00'));self.assertNotEqual(first,P.once_key(ref,prep,'qa-01'))
        with self.assertRaises(ValueError):P.once_key(ref,prep,'qa-15')
