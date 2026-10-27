"""Three pure metadata boundaries; no real tasks, ledger or scientific input."""
import copy,unittest
from . import contract as R


def ref(name):return {'path':'/synthetic/'+name,'bytes':1,'sha256':'0'*64}


def fixture():
    slot={'batch_id':R.BID,'job_name':'dv1_q_old96','output_root':str(R.F.BASE/'wave2'/R.BID/'generation_v1'),
      'cpus':16,'node':'compute-0-13','wall_seconds':28800,'whole_output_cap_bytes':R.F.CAP,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED'}
    review={'jobs':[dict(slot,job_name='dv1_q_root96_new',output_root=str(R.F.BASE/'wave2'/R.BID/'generation_root_v1'))],
      'maximum_concurrent_jobs':1}
    original={'schema':R.F.SCHEMAS['plan'],'status':'BOUNDED_WAVE_FROZEN_IMPORTS_CLOSED','imports320_durably_verified':True,
      'runtime':{'job_id':'4521486'},'jobs':[slot]+[{'batch_id':str(i)} for i in range(178)],'root_review':ref('oldreview'),
      'maximum_concurrent_jobs':2,'root_draft':ref('originaldraft'),'batches':[{'tasks':ref('unchanged')}]}
    prepared={'schema':R.F.SCHEMAS['prepared'],'status':'ORIGINAL_BATCH_INPUTS_READY_NOT_GENERATED','plan':ref('oldplan'),
      'runtime':{'job_id':R.PREPARE},'batch':{'batch_id':R.BID,'molecules':500},'molecules':500,'tasks':ref('tasks.jsonl'),
      'kernel_sha256':R.F.KERNEL_SHA,'baseline_metadata':{'signed_zero':-0.0,'none':None}}
    return slot,review,original,prepared


class Recovery96Metadata(unittest.TestCase):
    def test_only_fresh_single96_name_output_with_original_resources(self):
        slot,review,_,_=fixture();self.assertEqual(R.replacement_slot(slot,review),review['jobs'][0])
        for key,value in [('node','compute-0-17'),('wall_seconds',3600),('batch_id','batch-00095')]:
            bad=copy.deepcopy(review);bad['jobs'][0][key]=value
            with self.assertRaises(ValueError):R.replacement_slot(slot,bad)
        bad=copy.deepcopy(review);bad['jobs'].append(copy.deepcopy(bad['jobs'][0]))
        with self.assertRaises(ValueError):R.replacement_slot(slot,bad)

    def test_inverse_metadata_keeps_actual_runtime_all_tasks_and_original_unmodified(self):
        _,review,original,prepared=fixture();a=copy.deepcopy(original);b=copy.deepcopy(prepared)
        plan=R.derive_plan(original,ref('oldplan'),ref('newreview'),review,ref('decision'))
        header=R.derive_prepared(prepared,ref('oldheader'),ref('newplan'),ref('decision'))
        self.assertEqual((original,prepared),(a,b));self.assertEqual(plan['root_draft'],original['root_draft'])
        self.assertEqual(plan['batches'],original['batches']);self.assertEqual(header['tasks'],prepared['tasks'])
        self.assertEqual(header['runtime']['job_id'],R.PREPARE);self.assertFalse(header['recovery_metadata_derivation']['new_CPU_prepare_claimed'])
        with self.assertRaises(ValueError):R.derive_prepared(header,ref('other'),ref('another'),ref('decision'))

    def test_only_proven_all500_unstarted_zero_consumption_and_zero_unknown_can_proceed(self):
        _,_,_,prepared=fixture();closed={'schema':'SPRIME_FORMAL_CPU_CLOSED_BATCH_V3','status':'ACTUAL_TERMINAL_BATCH_CLASSIFIED',
          'batch_id':R.BID,'actual_parent_job_id':R.FAILED_RUN,'actual_parent':{'state':'FAILED','exit_code':'1:0'},
          'valid_packets':0,'consumed_outcomes':0,'execution_unresolved':0,'unstarted_count':500,'errors':[],
          'consumed_elsewhere':[],'plan':ref('oldplan'),'prepared':dict(ref('oldheader'),path='/synthetic/batch-00096/prepared_mapping_v1/prepared.json')}
        R.zero_consumption(closed,prepared,ref('oldplan'))
        for key,value in [('consumed_outcomes',1),('execution_unresolved',1),('unstarted_count',499),('errors',['unknown'])]:
            bad=copy.deepcopy(closed);bad[key]=value
            with self.assertRaises(ValueError):R.zero_consumption(bad,prepared,ref('oldplan'))


if __name__=='__main__':unittest.main()
