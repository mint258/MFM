"""Tests for new C1 binding and reporting policy, using invented fixture records only."""
import unittest
from workflows.benchmark_evaluation.c1_reporting import expected_cells,native_primary_row,native_population,make_primary_report
from workflows.benchmark_evaluation.selection import IncompleteComparison

class C1ReportTests(unittest.TestCase):
    def endpoint(self,dataset="ExpansionRx",target="p",level="molecule",key="expansionrx::p"):
        return dict(endpoint_key=key,dataset=dataset,target=target,level=level,split_policy="original")
    def rows(self,factor=0.0):
        return [dict(task='p',record_id=str(i),evaluation_id=str(i),full_inchikey="KEY-"+str(i),
                     y_true=float(i+1),prediction=float(i+1)*factor,training_mean=0.0,primary_source_job="701",native_producer_job="701",native_source_folder="/original/job_701") for i in range(3)]
    def test_native_missingness_keeps_original_coverage_and_labels(self):
        source=self.rows()
        candidate=self.rows(.9)[:2];candidate[1]["prediction"]=None
        values,coverage=native_population(source,candidate)
        self.assertEqual(len(values),1)
        self.assertEqual(coverage["original_primary_TEST_rows"],3)
        self.assertEqual(coverage["missing_native_TEST_rows"],2)
        self.assertFalse(coverage["missing_native_features_imputed"])
    def test_candidate_cannot_introduce_new_test_ids_or_changed_labels(self):
        candidate=self.rows(.9);candidate[0]["record_id"]="OTHER";candidate[0]["evaluation_id"]="OTHER"
        with self.assertRaises(IncompleteComparison):native_population(self.rows(),candidate)
        candidate=self.rows(.9);candidate[0]["y_true"]=999.
        with self.assertRaises(IncompleteComparison):native_population(self.rows(),candidate)
    def test_atomic_scope_does_not_invent_atomic_D_or_TabPFN(self):
        molecule=self.endpoint()
        nmr=self.endpoint("NMRShiftDB2","1H","atom","nmrshiftdb2::1H")
        mechanism=self.endpoint("pKahub","single_site_mechanism","atom","pkahub::single_site_mechanism")
        cells=expected_cells([molecule,nmr,mechanism])
        self.assertEqual(len(cells),8)
        self.assertEqual([c[1:] for c in cells if c[0]==nmr["endpoint_key"]],
                         [("Pprime_plus_RDKit_atom","LightGBM")])
    def test_blind_outside_domain_uses_actual_fit_TRAIN_mean(self):
        catalog=[self.endpoint()]
        raw=dict(self.rows()[0],task="p",retained=False,domain_eligible=False,prediction=0.)
        spec=dict(learner="TabPFN",feature_group="D",dataset="ExpansionRx")
        self.assertIsNotNone(native_primary_row(raw,catalog,spec))
        raw["prediction"]=1.
        with self.assertRaises(IncompleteComparison):native_primary_row(raw,catalog,spec)
    def test_existing_primary_filter_is_preserved_for_nonblind_tasks(self):
        catalog=[self.endpoint("Biogen_ADME","p",key="biogen_adme::p")]
        raw=dict(self.rows()[0],task="p",retained=False,domain_eligible=False)
        spec=dict(learner="LightGBM",feature_group="D",dataset="Biogen_ADME")
        self.assertIsNone(native_primary_row(raw,catalog,spec))
    def test_missing_native_scaffold_fold_cannot_be_discarded(self):
        original=[dict(r,repetition=0,fold=0) for r in self.rows()]
        candidate=[dict(r,repetition=0,fold=0) for r in self.rows(.9)]
        with self.assertRaises(IncompleteComparison):native_population(original,candidate,True)
    def report_inputs(self,role="RETAIN"):
        endpoint=self.endpoint()
        screen=[dict(endpoint,decision=role,status="SCREENED")]
        base={endpoint["endpoint_key"]:{"LightGBM-RDKit2D":self.rows()}}
        c1={(endpoint["endpoint_key"],f,l):self.rows(.9 if l=="TabPFN" else .2)
            for f in ("D","Pprime","Pprime_plus_D") for l in ("LightGBM","TabPFN")}
        return [endpoint],screen,base,c1
    def test_only_final_significant_TabPFN_cells_require_confirmation(self):
        table,contrasts,plan=make_primary_report(*self.report_inputs())
        self.assertEqual(len(table),6)
        self.assertEqual(len(plan),3)
        self.assertTrue(all(r["producer_task"]=="p" for r in plan))
        self.assertTrue(all(r["learner"]=="TabPFN" and r["confirmation_seed"]==20261026 for r in plan))
        self.assertTrue(all(not r["task_roster_reselection"] for r in table))
        self.assertTrue(all(r["bootstrap_draws"]==1000 for r in table))
    def test_excluded_tasks_do_not_acquire_second_seeds(self):
        _,_,plan=make_primary_report(*self.report_inputs("EXCLUDE"))
        self.assertEqual(plan,[])
    def test_absent_producer_is_not_silently_declared_unresolved(self):
        catalog,screen,base,c1=self.report_inputs()
        c1.pop(next(iter(c1)))
        with self.assertRaises(IncompleteComparison):make_primary_report(catalog,screen,base,c1)

if __name__=="__main__":unittest.main()

"""Actual fit-count and feature-layout reporting contracts, using invented records."""
import unittest
from workflows.benchmark_evaluation.c1_reporting import fit_metadata_summary
from workflows.benchmark_evaluation.selection import IncompleteComparison
class FitMetadataTests(unittest.TestCase):
    def test_native_available_TRAIN_count_is_not_replaced_by_another_models_population(self):
        records=[dict(n_train='31',feature_count='67',subsampling_ensemble='False'),
                 dict(n_train='99',feature_count='67',fit_population='full',evaluation_population='full')]
        summary=fit_metadata_summary(records)
        self.assertEqual(summary['actual_TRAIN_rows'],31)
        self.assertEqual(summary['input_feature_count'],67)
        self.assertFalse(summary['official_TabPFN_subsampling_ensemble'])
    def test_fold_sizes_may_differ_but_native_feature_layout_may_not(self):
        records=[dict(n_train=str(20+i),feature_count='75') for i in range(25)]
        summary=fit_metadata_summary(records,True)
        self.assertEqual((summary['actual_TRAIN_rows_min'],summary['actual_TRAIN_rows_max']),(20,44))
        records[-1]['feature_count']='76'
        with self.assertRaises(IncompleteComparison):fit_metadata_summary(records,True)
    def test_absent_fit_count_stays_unknown_instead_of_becoming_zero(self):
        self.assertIn('UNKNOWN',fit_metadata_summary([])['actual_TRAIN_size'])
        with self.assertRaises(IncompleteComparison):fit_metadata_summary([dict(n_train='0')])
if __name__=='__main__':unittest.main()

"""Final consumers reuse existing score metadata instead of independently replaying it."""
import unittest
from unittest.mock import patch
from workflows.benchmark_evaluation.c1_reporting import primary_statistics
from workflows.benchmark_evaluation.selection import IncompleteComparison
class ExistingScoreReuseTests(unittest.TestCase):
    def rows(self):return [dict(full_inchikey='ORIGINAL-KEY',y_true=2.,prediction=1.,training_mean=0.)]
    def record(self):return dict(n_test_rows='1',bootstrap_draws='1000',MAE='1.0',RAE='0.5',
             RAE_CI95_low='0.5',RAE_CI95_high='0.5',metric_status='OK')
    def test_closed_CPU_score_is_exported_without_a_second_bootstrap(self):
        with patch('workflows.benchmark_evaluation.c1_reporting.single_model_statistics',side_effect=RuntimeError('must not replay')):
            score=primary_statistics(self.rows(),[self.record()])
        self.assertEqual(score['RAE'],.5)
        self.assertEqual(score['statistics_source'],'REUSED_CLOSED_CPU_PRODUCER_STATISTICS')
    def test_deferred_GPU_statistics_are_computed_only_in_the_CPU_consumer(self):
        expected=dict(MAE=1.,RAE=.5)
        with patch('workflows.benchmark_evaluation.c1_reporting.single_model_statistics',return_value=expected) as compute:
            score=primary_statistics(self.rows(),[dict(bootstrap_draws='0',metric_status='PENDING_CPU_STATISTICS')])
        compute.assert_called_once()
        self.assertIn('NEW_CPU_REPORT',score['statistics_source'])
    def test_closed_metadata_cannot_silently_refer_to_another_test_population(self):
        record=dict(self.record(),n_test_rows='2')
        with self.assertRaises(IncompleteComparison):primary_statistics(self.rows(),[record])
if __name__=='__main__':unittest.main()
