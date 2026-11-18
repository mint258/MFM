"""Registered threshold boundaries; no scores or training are generated here."""
import copy,json,pathlib,tempfile,unittest
from unittest import mock
import t_decide as d
from t_decide import single,both
class DecisionTests(unittest.TestCase):
    def test_two_seed_finish_reuses_seed0_cache_without_old_scores(self):
        # Synthetic I/O only. No experimental score/checkpoint is accessed.
        with tempfile.TemporaryDirectory(prefix='T_decision_cache_',dir=d.CONTROL) as directory:
            root=pathlib.Path(directory);repo=root/'repo';cfgdir=repo/'configs/p_heads/T'
            result=repo/'results/p_heads/T/T5_deltas.json';cfg=root/'candidate0.json';ref=root/'reference0.json'
            old_candidate=root/'forbidden_candidate0/readout/scores.json';old_reference=root/'forbidden_reference0/readout/scores.json'
            candidate1=root/'canonical_resumed_candidate1/readout/scores.json';reference1=root/'canonical_reference1/readout/scores.json'
            def write(path,value):
                path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
            write(cfg,dict(arm='T5',seed=0,run='synthetic_zero',output=str(old_candidate.parent.parent),
                p_heads_reference=dict(seed0_configuration=str(ref),reuse_external_seed1=False)))
            write(ref,dict(arm='B3',seed=0,output=str(old_reference.parent.parent)))
            write(cfgdir/'T5_seed1.json',dict(arm='T5',seed=1,output=str(candidate1.parent.parent)))
            write(cfgdir/'B3_seed1.json',dict(arm='B3',seed=1,output=str(reference1.parent.parent)))
            write(old_candidate,dict(forbidden_seed0=True));write(old_reference,dict(forbidden_seed0=True))
            zero={r:dict(delta=.02,ci95=[-.0123456789,.0523456789],candidate=.52,reference=.5) for r in ('R1','R3')}
            write(result,dict(arm='T5',reference_configuration=str(ref),results=copy.deepcopy(zero),status='SEED1_REQUIRED'))
            write(candidate1,{r:dict(synthetic='candidate1_'+r) for r in ('R1','R3')})
            write(reference1,{r:dict(synthetic='reference1_'+r) for r in ('R1','R3')})
            one={r:dict(delta=.01,ci95=[-.01,.03],candidate=.5,reference=.49) for r in ('R1','R3')}
            loads=[];pairs=[];second=[False]
            def load(path):
                path=pathlib.Path(path);loads.append(path)
                if path in (old_candidate,old_reference):raise AssertionError('Seed0 scores must never be reopened')
                if second[0] and path in (candidate1,reference1):raise AssertionError('Already saved seed1 must not be recalculated')
                return json.loads(path.read_text())
            def paired(candidate,reference):
                readout=candidate['synthetic'].removeprefix('candidate1_')
                self.assertIn(readout,('R1','R3'));self.assertEqual(reference['synthetic'],'reference1_'+readout)
                pairs.append(readout);return copy.deepcopy(one[readout])
            with mock.patch.object(d,'REPO',repo),mock.patch.object(d,'guard'),mock.patch.object(d,'load',side_effect=load),mock.patch.object(d,'save',side_effect=write),mock.patch.object(d,'paired',side_effect=paired),mock.patch.object(d,'seed1',side_effect=AssertionError('Use existing canonical seed1 configurations')),mock.patch('sys.argv',['t_decide','--configuration',str(cfg)]):
                d.main()
                saved=json.loads(result.read_text());self.assertEqual(saved['status'],'COMPLETE_TWO_SEEDS')
                self.assertEqual(pairs,['R1','R3'])
                for r in ('R1','R3'):
                    for key in ('delta','ci95','candidate','reference'):self.assertEqual(saved['results'][r][key],zero[r][key])
                    self.assertEqual(saved['results'][r]['seed1'],one[r])
                self.assertNotIn(old_candidate,loads);self.assertNotIn(old_reference,loads)
                # A later finish call reuses both published seeds, not new draws.
                second[0]=True;d.main();self.assertEqual(pairs,['R1','R3'])
    def test_single_seed_boundaries_and_sign(self):
        self.assertEqual(single(dict(delta=.06,ci95=[.001,.1])),'win')
        self.assertEqual(single(dict(delta=.059,ci95=[.001,.1])),'seed1_required')
        self.assertEqual(single(dict(delta=-.06,ci95=[-.1,-.001])),'loss')
        self.assertEqual(single(dict(delta=.07,ci95=[0,.1])),'seed1_required')
    def test_two_seed_effect_and_paired_direction(self):
        z=dict(delta=.04,ci95=[.01,.07],reference=.475)
        o=dict(delta=.04,ci95=[.01,.07],reference=.475)
        self.assertEqual(both(z,o),'win')
        o=dict(delta=.03,ci95=[.01,.05],reference=.475)
        self.assertEqual(both(z,o),'tie')
        z=dict(delta=-.01,ci95=[-.02,-.001],reference=.475)
        o=dict(delta=-.01,ci95=[-.02,-.001],reference=.475)
        self.assertEqual(both(z,o),'loss')
if __name__=='__main__':unittest.main()
