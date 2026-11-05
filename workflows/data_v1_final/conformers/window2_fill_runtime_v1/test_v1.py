"""One pure original-state equivalence test; no real data, Native or benchmark."""
import json
import unittest
from unittest.mock import Mock, patch
from .run import part_values, original


class FillInputElisionTests(unittest.TestCase):
    def test_fast_stub_matches_full_original_state_and_only_slow_materializes(self):
        metas=[
            {'molecule_id':'already2','S_conformers':2,'Sprime_status':'SUCCESS','fill_status':'old-fill','effective_role':'TRAIN'},
            {'molecule_id':'notclosed','S_conformers':2,'Sprime_status':'SUCCESS','fill_status':None,'effective_role':'TRAIN'},
            {'molecule_id':'already1','S_conformers':1,'Sprime_status':'SUCCESS','fill_status':'old-complete','effective_role':'VAL'},
            {'molecule_id':'short','S_conformers':2,'Sprime_status':'UFF_UNSUPPORTED','fill_status':None,'effective_role':'TRAIN'},
            {'molecule_id':'unsupported','S_conformers':1,'Sprime_status':'UFF_UNSUPPORTED','fill_status':'retained','effective_role':'FULL'}]
        ids={'already2':[9,3],'notclosed':[8,2],'already1':[4],'short':[7],'unsupported':[6]}
        statistics=[{'molecule_id':m['molecule_id'],'status':('SOURCE_OR_COMPUTATION_FAILED' if m['molecule_id']=='notclosed' else 'COMPLETE'),
            'sprime_unique_ids_json':json.dumps(ids[m['molecule_id']]),'error':'original-source-error'} for m in metas]
        byid={r['molecule_id']:r for r in statistics};bounds={m['molecule_id']:20+i for i,m in enumerate(metas)}
        full={m['molecule_id']:{'meta':m,'d7':byid[m['molecule_id']],
            'records':[{'record_id':'must-not-read','source_path':'no-real-file'}],
            'uff':[{'coordinates':'must-not-materialize-for-fast'}],'prior_packet':'unused',
            'max_original_attempt_idx':bounds[m['molecule_id']]} for m in metas}
        real_safe_fill=original.safe_fill
        with patch.object(original.d7,'SCIENCE',None),patch.object(original.d7,'native',side_effect=AssertionError('NO_NATIVE')) as native:
            expected=[real_safe_fill(full[m['molecule_id']]) for m in metas]
            pool=Mock()
            pool.map.side_effect=lambda function,jobs,chunksize:[function(job) for job in jobs]
            db=object()
            with patch.object(original.d7,'tasks',side_effect=lambda connection,selected:[dict(full[m['molecule_id']]) for m in selected]) as tasks, \
                 patch.object(original,'safe_fill',wraps=real_safe_fill) as safe:
                first=part_values(db,[metas[0]],statistics,bounds,pool)
                self.assertEqual(first,[expected[0]])
                tasks.assert_not_called();pool.map.assert_not_called()
                stub=safe.call_args.args[0]
                self.assertEqual(stub['records'],[]);self.assertEqual(stub['uff'],[])
                self.assertIs(stub['meta'],metas[0]);self.assertIs(stub['d7'],byid['already2'])
                self.assertEqual(stub['max_original_attempt_idx'],bounds['already2'])
                safe.reset_mock()
                actual=part_values(db,metas,statistics,bounds,pool)
                self.assertEqual(actual,expected)
                self.assertEqual([v['molecule_id'] for v in actual],[m['molecule_id'] for m in metas])
                tasks.assert_called_once_with(db,[metas[1],metas[3]])
                self.assertIs(pool.map.call_args.args[0],safe)
                self.assertEqual([j['meta']['molecule_id'] for j in pool.map.call_args.args[1]],['notclosed','short'])
                self.assertEqual(pool.map.call_args.kwargs,{'chunksize':4})
                self.assertEqual(safe.call_count,len(metas))
                self.assertEqual(actual[0]['kept_original_sprime_ids'],[9,3])
                self.assertEqual(actual[1]['status'],'EXECUTION_UNRESOLVED')
                self.assertEqual(actual[-1]['status'],'UFF_UNSUPPORTED')
            native.assert_not_called()


if __name__=='__main__':unittest.main()