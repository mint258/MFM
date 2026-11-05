"""Synthetic resource boundaries only, never science or actual scheduler evidence."""
import copy
from pathlib import Path
import sys,types,unittest
from unittest import mock
from . import resource_runtime as R


def fixture():
    def pin(name):return {'path':'/synthetic/recovery_auto/'+name,'bytes':1,'sha256':'a'*64}
    refs={k:pin(k+'.json') for k in ('plan','approval','authority','replacement','owned','evidence')}
    plan={'schema':'SPRIME_MISSING_RECOVERY_PLAN_V1','status':'ROOT_APPROVED_RECOVERY_EXECUTION','original_job_id':'4520364',
        'expected_original_molecules':336,'expected_missing_molecules':{'principal_01112964':7,'principal_00509656':10},
        'workers':16,'cpus':16,'memory_gib':64,'replay_control_count':14,'replay_control_ids':['synthetic_%02d'%i for i in range(14)],
        'new_logical_retry_count':0,'scientific_recipe_changed':False,'formal_generation_authorized':False,
        'wall_seconds':6900,'additional_allocated_core_seconds_cap':110400,'runtime_forecast':'RIGHT_CENSORED_NO_DEFENSIBLE_POINT_ESTIMATE'}
    approval={'schema':'SPRIME_MISSING_RECOVERY_USER_AND_ROOT_DECISION_V1','status':'APPROVED_FOR_THIS_RECOVERY_ONLY',
        'plan_reference':refs['plan'],'cost_ceiling_not_forecast':110400,'original_336_approval_reused':False}
    replacement={'schema':'SPRIME_PENDING_ONLY_RESOURCE_REPLACEMENT_ROOT_REVIEW_V1','status':'APPROVED_NO_PRIOR_PHYSICAL_EXECUTION',
        'reviewer':'root','historical_plan_reference':refs['plan'],'historical_approval_reference':refs['approval'],
        'no_prior_worker_execution_verified':True,'no_recovery_output_directory_verified':True,
        'replaced_parent_job_ids':['999960'],'evidence_references':[refs['evidence']]}
    rows=[{'job_id':jid,'state':state,'exit_code':'0:0','elapsed_raw_seconds':seconds,'alloc_cpus':16,'allocated_core_seconds':16*seconds}
        for jid,state,seconds in (('4520335','COMPLETED',606),('4520364','TIMEOUT',14425),('4520527','COMPLETED',1),('999960','CANCELLED',0))]
    selection={'related_parent_ids':[r['job_id'] for r in rows],'selected_parent_rows':rows,'unclassified_scope_parent_ids_for_root_review':[]}
    binding={'schema':'SPRIME_AUTO_MEMORY_RECOVERY_RESOURCE_BINDING_V1','status':'ROOT_APPROVED_FOR_EXACT_RECOVERY_RESOURCE_REPLACEMENT',
        'reviewer':'root','memory_policy':R.POLICY,'slurm_memory_requested':False,'historical64GiB_is_not_new_request':True,
        'cpus':16,'allowed_nodes':[f'compute-0-{n}' for n in range(11,20)],'scope_key':R.SCOPE_KEY,'scope_parameters':R.PARAMETERS,
        'historical_plan_reference':refs['plan'],'historical_approval_reference':refs['approval'],'new_authority_reference':refs['authority'],
        'pending_only_replacement_review_reference':refs['replacement'],'whole_owned_accounting_reference':refs['owned'],
        'wall_seconds':6200,'historical_plan_wall_seconds':6900,
        'followup_requested_allocation_reserves':[
            {'stage':'read_only_recovered_closure','cpus':16,'wall_seconds':180,'requested_core_seconds':2880},
            {'stage':'readback_validation','cpus':16,'wall_seconds':120,'requested_core_seconds':1920}],
        'followup_requested_allocation_reserve_core_seconds':4800,'future_allocation_reserves_are_not_actual_cost_or_runtime_forecasts':True,
        'prior_related_actual_parent_ids':selection['related_parent_ids'],'prior_related_actual_parent_rows':rows,
        'prior_related_actual_core_seconds':sum(r['allocated_core_seconds'] for r in rows),
        'formal_generation_authorized':False,'new_seeds':0,'new_logical_retries':0,'original_32GiB_exception_reused':False,
        'soft_owned_rss_stop_bytes':24<<30,'soft_min_mem_available_bytes':2<<30}
    docs={refs[k]['path']:v for k,v in (('plan',plan),('approval',approval),('replacement',replacement),
        ('authority',{'schema':'USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1','status':'USER_AUTHORIZED'}))}
    return binding,selection,docs


def check(binding,selection,docs):
    with mock.patch.object(R,'load_pin',side_effect=lambda p:docs[p['path']]), \
         mock.patch.object(R,'verify',side_effect=lambda p:Path(p['path'])), \
         mock.patch.object(R,'owned_related_selection',return_value=selection):
        return R.binding_metadata(binding)


class ResourceBindingBoundaries(unittest.TestCase):
    def test_smaller_new_wall_preserves_historical_plan_and_followup_reserve(self):
        b,s,d=fixture();result=check(b,s,d)
        self.assertEqual(result['plan']['wall_seconds'],6900)
        self.assertEqual(result['plan']['memory_gib'],64)
        self.assertEqual(b['wall_seconds'],6200)
        self.assertNotIn('memory_gib',b)
        self.assertLessEqual(result['prior_actual_core_seconds']+16*b['wall_seconds']+4800,345600)

    def test_historical_wall_and_invalid_followup_reserve_cannot_hide_cost(self):
        for case in ('old_wall','missing_followup','zero_followup','false_actual_label'):
            with self.subTest(case=case):
                b,s,d=fixture()
                if case=='old_wall':b['wall_seconds']=6900
                elif case=='missing_followup':b['followup_requested_allocation_reserves'].pop()
                elif case=='zero_followup':b['followup_requested_allocation_reserves'][0]['wall_seconds']=0
                else:b['future_allocation_reserves_are_not_actual_cost_or_runtime_forecasts']=False
                with self.assertRaises(ValueError):check(b,s,d)

    def test_prepare_cost_unknown_scope_or_executed_replacement_is_rejected(self):
        for case,error in (('missing_prepare','ACTUAL_ORIGINAL_SPRIME_PREPARATION_COST_MUST_BE_INCLUDED'),
                           ('unknown','ALL_CURRENT_OWNED_SCOPES_MUST_BE_EXPLICIT'),
                           ('already_executed','REPLACED_RECOVERY_MUST_BE_REAL_CANCELLED_ZERO_ELAPSED_PARENT_NOT_EXECUTED_RETRY')):
            with self.subTest(case=case):
                b,s,d=fixture()
                if case=='missing_prepare':
                    s['selected_parent_rows']=[r for r in s['selected_parent_rows'] if r['job_id']!='4520335']
                    s['related_parent_ids']=[r['job_id'] for r in s['selected_parent_rows']]
                    b['prior_related_actual_parent_ids']=s['related_parent_ids'];b['prior_related_actual_parent_rows']=s['selected_parent_rows']
                    b['prior_related_actual_core_seconds']=sum(r['allocated_core_seconds'] for r in s['selected_parent_rows'])
                elif case=='unknown':s['unclassified_scope_parent_ids_for_root_review']=['90001']
                else:s['selected_parent_rows'][-1].update(elapsed_raw_seconds=1,allocated_core_seconds=16)
                with self.assertRaisesRegex(ValueError,error):check(b,s,d)

    def test_sampler_discards_old_admission_flags_and_uses_only_actual_soft_metrics(self):
        b,_,_=fixture();proof={'job_id':'999999'}
        metrics={'node_used_bytes':90<<30,'mem_total_bytes':100<<30,'mem_available_bytes':10<<30,'capacity_bytes':100<<30,
            'owned_rss_bytes':1<<30,'observed_epoch':1,'observed_monotonic':1,'sample_seconds':0,'processes':[],
            'dispatch_allowed':False,'reserved_bytes':32<<30,'memory_basis':'OLD_32G85_POLICY'}
        legacy=types.ModuleType('live_memory_policy_32g_v1')
        legacy.ProcSampler=mock.Mock(return_value=lambda:copy.deepcopy(metrics))
        legacy.parse_meminfo=lambda _:{'MemTotal':100<<30,'MemAvailable':10<<30}
        with mock.patch.object(R,'CACHE',{'proof':proof,'binding':b}), \
             mock.patch.dict(sys.modules,{'live_memory_policy_32g_v1':legacy}), \
             mock.patch.object(Path,'read_text',return_value='synthetic meminfo'):
            sampler=R.RecoverySampler('999999',proof)
            accepted=sampler()
            self.assertTrue(accepted['dispatch_allowed'])
            self.assertFalse(accepted['slurm_memory_requested'])
            self.assertTrue(accepted['legacy_sampler_admission_flags_discarded'])
            self.assertNotIn('reserved_bytes',accepted)
            metrics['mem_available_bytes']=1<<30
            self.assertFalse(sampler()['dispatch_allowed'])
            metrics['mem_available_bytes']=10<<30;metrics['owned_rss_bytes']=24<<30
            self.assertFalse(sampler()['dispatch_allowed'])


if __name__=='__main__':unittest.main()
