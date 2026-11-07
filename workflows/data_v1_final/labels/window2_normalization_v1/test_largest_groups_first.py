"""One pure synthetic whole-group scheduling regression; no scientific source."""
import copy,unittest
from unittest.mock import patch
from . import run as R

class LargestGroupsFirst(unittest.TestCase):
    def test_default_largest_stable_closed_and_original_reduction_order(self):
        def group(index,base,label):
            return {'group_index':index,'source_job_id':'job'+str(index),
                'base_files':[{'path':'unread-base-'+str(i),'bytes':size} for i,size in enumerate(base)],
                'label_files':[{'path':'unread-label-'+str(i),'bytes':size} for i,size in enumerate(label)]}
        groups=[group(5,[2],[2]),group(1,[10],[3,17]),group(9,[15,5],[10]),group(3,[999],[1]),group(8,[],[7])]
        closed={'3':'already-closed-report'};before=copy.deepcopy(groups);closed_before=copy.deepcopy(closed)
        cfg={'workers':2,'science_reference':{'path':'frozen','bytes':42}};cfg_before=copy.deepcopy(cfg)
        stage={'queries':{'fixed':True}};stage_before=copy.deepcopy(stage)
        with patch.object(R.P,'stat',side_effect=AssertionError('SOURCE_STAT_FORBIDDEN')),patch('builtins.open',side_effect=AssertionError('SOURCE_READ_FORBIDDEN')):
            original=R.pending_groups(groups,closed)
            self.assertEqual([g['group_index'] for g in original],[5,1,9,8])
            self.assertEqual(R.pending_groups(groups,closed,False),original)
            largest=R.pending_groups(groups,closed,True)
            self.assertEqual([g['group_index'] for g in largest],[1,9,8,5])
            self.assertTrue(all(any(g is source for source in groups) for g in largest))
            self.assertEqual([g['group_index'] for g in largest if g['group_index'] in (1,9)],[1,9])
            self.assertEqual(R.pending_groups(groups,{str(g['group_index']):'done' for g in groups},True),[])
            # A fake submit/finish harness changes only submission order. Reports
            # still reduce in the production driver's unchanged original order.
            submitted=[];reports=dict(closed)
            def submit(arguments):
                self.assertIs(arguments[0],cfg);self.assertIs(arguments[1],stage)
                self.assertEqual(arguments[2],'same-attempt-root')
                source=arguments[3];submitted.append(source['group_index'])
                reports[str(source['group_index'])]='report-'+str(source['group_index'])
            for source in largest:submit((cfg,stage,'same-attempt-root',source))
            self.assertEqual(submitted,[1,9,8,5])
            reduced=[reports[str(source['group_index'])] for source in groups]
            self.assertEqual(reduced,['report-5','report-1','report-9','already-closed-report','report-8'])
        self.assertEqual(groups,before);self.assertEqual(closed,closed_before)
        self.assertEqual(cfg,cfg_before);self.assertNotIn('largest_groups_first',cfg)
        self.assertEqual(stage,stage_before)