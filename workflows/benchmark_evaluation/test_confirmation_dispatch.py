"""Conditional dispatch uses invented task metadata and never executes a neural fit."""
import unittest
from workflows.benchmark_evaluation.confirmation_dispatch import planned_jobs,prepare_job_source
from workflows.benchmark_evaluation.selection import IncompleteComparison
class DispatchTests(unittest.TestCase):
    def row(self,task="keep",dataset="DATA"):
        return dict(endpoint_key=dataset+"::"+task,dataset=dataset,producer_task=task,learner="TabPFN",
            feature_group="D",reason="FINAL_SIGNIFICANT_IMPROVEMENT",primary_seed=20261025,confirmation_seed=20261026)
    def binding(self,task="keep",job=12,dataset="DATA"):
        return dict(dataset=dataset,producer_task=task,learner="TabPFN",feature_group="D",
            primary_job=job,template_id="original_"+str(job))
    def test_only_required_tasks_group_by_actual_original_producer(self):
        groups,reused=planned_jobs([self.row(),self.row("other")],
            [self.binding(),self.binding("other"),self.binding("irrelevant",44)])
        self.assertEqual(len(groups),1);self.assertEqual(len(groups[0]["required_tasks"]),2)
        self.assertEqual(groups[0]["primary_job"],"12");self.assertEqual(reused,[])
    def test_source_task_name_alone_cannot_mix_datasets_or_features(self):
        with self.assertRaises(IncompleteComparison):
            planned_jobs([self.row()],[self.binding(dataset="OTHER")])
        wrong=self.binding();wrong["feature_group"]="Pprime"
        with self.assertRaises(IncompleteComparison):planned_jobs([self.row()],[wrong])
    def test_ambiguous_producer_binding_or_duplicate_plan_is_rejected(self):
        with self.assertRaises(IncompleteComparison):
            planned_jobs([self.row()],[self.binding(),self.binding(job=13)])
        with self.assertRaises(IncompleteComparison):
            planned_jobs([self.row(),self.row()],[self.binding()])
    def test_completed_mandatory_NMR_exception_is_reused_without_dispatch(self):
        row=dict(self.row(),model="Chemprop-v2",confirmation_native_job=4537338,
            reason="SOURCE_BINDING_ERROR_REQUIRED_REDO_OF_TRAINED_1H_SAMPLES")
        groups,reused=planned_jobs([row],[],baseline=True)
        self.assertEqual(groups,[]);self.assertEqual(reused[0]["confirmation_native_job"],4537338)
    def test_source_adapter_keeps_held_out_task_untrained_and_original_statistics_seed(self):
        group=planned_jobs([self.row()],[self.binding()])[0][0]
        source="""SEED=20261025
group='DATA'
calls=[]
class Model:
    def __init__(self,random_state):self.seed=random_state
    def fit(self):calls.append((task,population,self.seed,SEED))
for task in ('keep','held_out'):
    for population in ('retained','full'):
        model=Model(random_state=SEED);model.fit()
report=dict(seed=SEED)
"""
        program,declaration=prepare_job_source(group,source,default_dataset="DATA")
        namespace={};exec(program,namespace)
        self.assertEqual(namespace["calls"],[("keep","retained",20261026,20261025)])
        self.assertTrue(declaration["original_model_budget_unchanged"])
    def test_traditional_ML_cannot_be_dispatched(self):
        row=self.row();row["learner"]="LightGBM"
        with self.assertRaises(IncompleteComparison):planned_jobs([row],[])

    def test_environment_download_must_be_bound_on_CPU_before_GPU_confirmation(self):
        group=planned_jobs([self.row()],[self.binding()])[0][0]
        with self.assertRaises(IncompleteComparison):
            prepare_job_source(group,"import urllib.request\nurllib.request.urlopen('https://example.invalid/official_weights')\n",default_dataset='DATA')

    def test_bound_original_job_disambiguates_repeated_task_metadata(self):
        row=dict(self.row(),primary_source_job="12")
        groups,_=planned_jobs([row],[self.binding(),self.binding(job=13)])
        self.assertEqual(groups[0]["primary_job"],"12")
