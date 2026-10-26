"""Three synthetic boundaries for honest timeout closure; no scientific input."""
import copy,unittest
from model import terminal_rows,descriptive_strata,validate_cost_decision


def fixture():
    tasks={f'm{i:03}':{'meta':{'molecule_id':f'm{i:03}','cohort':'retry_once','file_group':0,'expected_conformers':2,'Sprime_status':'EMBED_FAILED'}} for i in range(336)}
    missing={'m334':2,'m335':2};summaries={mid:{'status':'SUCCESS','elapsed_seconds':1.0} for mid in list(tasks)[:334]}
    refs={mid:{'path':'/synthetic/'+mid+'.json.gz','sha256':'fixture','bytes':1} for mid in summaries}
    return tasks,summaries,refs,missing


class TimeoutClosureBoundaries(unittest.TestCase):
    def test_union336_does_not_fabricate_two_packages_or_scientific_status(self):
        tasks,summaries,refs,missing=fixture()
        rows,failures=terminal_rows(tasks,summaries,refs,missing,{},lambda task:'task-sha',lambda task:7)
        self.assertEqual((len(rows),len(failures)),(336,2))
        self.assertTrue(all(row['package_reference'] is None and row['scientific_status'] is None and row['failure_stage']=='UNKNOWN' for row in failures))
        self.assertTrue(all(row['worker_pid'] is None and not row['new_attempt_ledger_created'] for row in failures))
        bad=copy.deepcopy(refs);bad['m334']={'path':'/fake'}
        with self.assertRaises(ValueError):terminal_rows(tasks,summaries,bad,missing,{},lambda task:'sha',lambda task:7)
    def test_control_or_unlisted_population_member_is_rejected(self):
        tasks,summaries,refs,missing=fixture();summaries['control']={'status':'SUCCESS','elapsed_seconds':1};refs['control']={'path':'/control'}
        with self.assertRaises(ValueError):terminal_rows(tasks,summaries,refs,missing,{},lambda task:'sha',lambda task:7)
    def test_censored_timing_has_no_finite_upper_forecast_or_invented_missing_duration(self):
        tasks,summaries,refs,missing=fixture();rows=descriptive_strata(tasks,summaries,missing)
        self.assertEqual(rows[0]['worker_seconds_sum_lower_bound'],334)
        self.assertIsNone(rows[0]['worker_seconds_sum_upper_bound']);self.assertEqual(rows[0]['execution_unresolved_molecules'],2)
        self.assertEqual(rows[0]['latent_scientific_success_fraction_bounds'],[334/336,1.])
        self.assertTrue(rows[0]['completed_package_max_is_not_reliable_full_forecast'])
        authority={'schema':'USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1','status':'USER_AUTHORIZED','on_overrun':'REPORT_AND_CONTINUE',
            'original_threshold_multiplier':1.5,'only_cost_stop_rule_changed':True,'scientific_quality_thresholds_unchanged':True,
            'retain_actual_accounting_including_failures_and_startup':True,'preserve_historical_requests_sources_and_results':True,
            'no_forced_termination':True,'max_single_job_wall_seconds':172800,'cpu_only':True,'quota_reserve_bytes':200000000000,
            'slurm_memory_policy':'SLURM_DEFAULT_UNSPECIFIED'}
        policy=validate_cost_decision(authority)
        self.assertFalse(policy['cost_alone_blocks_closure_or_full_planning']);self.assertFalse(policy['cost_below_threshold_is_scientific_PASS'])
        authority['scientific_quality_thresholds_unchanged']=False
        with self.assertRaisesRegex(ValueError,'PRESERVE_QUALITY'):validate_cost_decision(authority)
if __name__=='__main__':unittest.main()