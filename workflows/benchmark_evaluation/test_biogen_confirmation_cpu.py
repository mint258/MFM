"""Synthetic seed26 CPU source, runtime and protected-queue handover contracts."""
import ast
import copy
import unittest
from .biogen_confirmation_cpu import (
    prepare_biogen_confirmation_cpu_source,validate_biogen_group,validate_cpu_runtime,
    remaining_gpu_dependencies,rebind_confirmation_runs)

class BiogenConfirmationCpuTests(unittest.TestCase):
    def group(self):
        return dict(primary_job=4537679,feature_group="Pprime",learner="TabPFN",array=False,
            required_tasks=[dict(dataset="Biogen_ADME",feature_group="Pprime",learner="TabPFN",
                primary_source_job="4537679",confirmation_seed="20261026",primary_seed="20261025",
                fold_and_statistics_seed="20261025",reason="FINAL_SIGNIFICANT_IMPROVEMENT",frozen_B1_role="APPENDIX",
                task_roster_reselection="False",original_labels_or_masks_changed="False",producer_task="kept")])
    def source(self):
        declaration=dict(model_seed=20261026,split_and_statistics_seed=20261025,reason="FINAL_SIGNIFICANT_IMPROVEMENT",
            selected_original_tasks=[("Biogen_ADME","kept")],task_roster_reselection=False,
            primary_fit_population_only=True,original_model_budget_unchanged=True)
        return ("MODEL_SEED=20261026\nSEED=20261025\n__confirmation_default_dataset='Biogen_ADME'\n"
            "__confirmation_selected=frozenset([('Biogen_ADME','kept')])\n__confirmation_declaration="+repr(declaration)+"\n"
            "torch.set_num_threads(2)\ncheckpoint='smoke100/job_4536865/model_cache/tabpfn-v2-regressor.ckpt'\n"
            "classifier=False\nmodel=(TabPFNClassifier if classifier else TabPFNRegressor).create_default_for_version("
            "ModelVersion.V2,device='cuda',model_path=checkpoint,random_state=MODEL_SEED,n_preprocessing_jobs=2,"
            "inference_config={'SUBSAMPLE_SAMPLES':10000},ignore_pretraining_limits=False)\n"
            "model.fit(TRAIN_FEATURES,TRAIN_LABELS)\nanswer=model.predict(TEST_FEATURES)\n")
    def test_only_device_and_execution_threads_change_in_the_complete_AST(self):
        original=self.source();prepared=prepare_biogen_confirmation_cpu_source(original,self.group())
        tree=ast.parse(prepared)
        constructor=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                         and n.func.attr=="create_default_for_version")
        device=next(k for k in constructor.keywords if k.arg=="device")
        self.assertEqual(device.value.value,"cpu");device.value.value="cuda"
        thread=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="set_num_threads")
        self.assertEqual(thread.args[0].value,16);thread.args[0].value=2
        self.assertEqual(ast.dump(tree,include_attributes=False),ast.dump(ast.parse(original),include_attributes=False))
    def test_functional_model_arguments_data_objects_and_prediction_population_are_preserved(self):
        records={};marker=object()
        class Torch:
            def set_num_threads(self,value):records["threads"]=value
        class FakeModel:
            def fit(self,x,y):records["fit"]=(x,y)
            def predict(self,x):records["test"]=x;return marker
        class Factory:
            @classmethod
            def create_default_for_version(cls,version,**kwargs):
                records["version"]=version;records["kwargs"]=kwargs;return FakeModel()
        train=object();labels=object();test=object();version=object()
        ns=dict(torch=Torch(),TabPFNRegressor=Factory,TabPFNClassifier=Factory,
                ModelVersion=type("Version",(),dict(V2=version)),TRAIN_FEATURES=train,TRAIN_LABELS=labels,TEST_FEATURES=test)
        exec(prepare_biogen_confirmation_cpu_source(self.source(),self.group()),ns)
        self.assertEqual(records["threads"],16);self.assertIs(records["version"],version)
        self.assertEqual(records["kwargs"]["device"],"cpu")
        self.assertEqual(records["kwargs"]["random_state"],20261026)
        self.assertEqual(records["kwargs"]["n_preprocessing_jobs"],2)
        self.assertEqual(records["kwargs"]["inference_config"],{"SUBSAMPLE_SAMPLES":10000})
        self.assertEqual(ns["SEED"],20261025);self.assertEqual(ns["__confirmation_selected"],{("Biogen_ADME","kept")})
        self.assertIs(records["fit"][0],train);self.assertIs(records["fit"][1],labels)
        self.assertIs(records["test"],test);self.assertIs(ns["answer"],marker)
    def test_wrong_seeds_version_or_already_cpu_source_are_rejected(self):
        for old,new in (("MODEL_SEED=20261026","MODEL_SEED=20261027"),("SEED=20261025","SEED=17"),
                        ("ModelVersion.V2","ModelVersion.V3"),("device='cuda'","device='cpu'")):
            with self.assertRaises(ValueError):prepare_biogen_confirmation_cpu_source(self.source().replace(old,new),self.group())
    def test_selected_tasks_population_and_budget_declaration_cannot_be_changed(self):
        for old,new in (("('Biogen_ADME', 'kept')","('Biogen_ADME', 'unplanned')"),
                        ("'primary_fit_population_only': True","'primary_fit_population_only': False"),
                        ("'original_model_budget_unchanged': True","'original_model_budget_unchanged': False")):
            with self.assertRaises(ValueError):prepare_biogen_confirmation_cpu_source(self.source().replace(old,new),self.group())
    def test_group_scope_does_not_add_other_datasets_roles_tasks_or_arrays(self):
        for field,value in (("primary_job",123),("feature_group","Other"),("learner","LightGBM"),("array",True)):
            group=self.group();group[field]=value
            with self.assertRaises(ValueError):validate_biogen_group(group)
        for field,value in (("dataset","Other"),("confirmation_seed","20261027"),("frozen_B1_role","EXCLUDE"),
                            ("task_roster_reselection","True"),("original_labels_or_masks_changed","True")):
            group=self.group();group["required_tasks"][0][field]=value
            with self.assertRaises(ValueError):validate_biogen_group(group)
    def test_original_preprocessing_and_thread_selector_are_required(self):
        for source in (self.source().replace("n_preprocessing_jobs=2","n_preprocessing_jobs=3"),
                       self.source().replace("torch.set_num_threads(2)","torch.set_num_threads(4)"),
                       self.source().replace("torch.set_num_threads(2)","pass")):
            with self.assertRaises(ValueError):prepare_biogen_confirmation_cpu_source(source,self.group())
        with self.assertRaises(ValueError):prepare_biogen_confirmation_cpu_source(self.source(),self.group(),cpus=32)
    def test_runtime_rejects_wrong_node_allocation_or_visible_GPU(self):
        validate_cpu_runtime("compute-0-12",16,"compute-0-12","")
        for args in (("sonmi",16,"sonmi",""),("compute-0-21",16,"compute-0-21",""),
                     ("compute-0-13",16,"compute-0-12",""),("compute-0-12",2,"compute-0-12",""),
                     ("compute-0-12",16,"compute-0-12","0")):
            with self.assertRaises(ValueError):validate_cpu_runtime(*args)
    def test_removed_middle_jobs_cannot_bypass_protected_GPU_head(self):
        order=[dict(job=101,uuid="A"),dict(job=102,uuid="A"),dict(job=103,uuid="A"),dict(job=104,uuid="A")]
        actual=remaining_gpu_dependencies(order,{102,103},{"A":[7]})
        self.assertEqual(actual,{"101":"afterany:7","104":"afterany:101"})
    def test_each_remaining_GPU_queue_keeps_original_order_and_own_protected_barriers(self):
        order=[dict(job=101,uuid="A"),dict(job=201,uuid="B"),dict(job=102,uuid="A"),
               dict(job=202,uuid="B"),dict(job=103,uuid="A")]
        actual=remaining_gpu_dependencies(order,{101,202},{"A":[7,8],"B":[9]})
        self.assertEqual(actual,{"201":"afterany:9","102":"afterany:7:8","103":"afterany:102"})
    def test_dependency_rewrite_rejects_unknown_or_duplicate_native_jobs(self):
        order=[dict(job=101,uuid="A"),dict(job=102,uuid="A")]
        for rows,removed,barriers in ((order,{999},{}),(order+order[:1],{101},{}),(order,{101},{"A":[101]})):
            with self.assertRaises(ValueError):remaining_gpu_dependencies(rows,removed,barriers)
    def test_rebinding_preserves_all_primary_identities_order_and_unselected_runs(self):
        original=dict(stage="C1",preparation_manifest="/owned/prep",groups=[
            dict(primary_job="11",runs=[dict(job=101,array=False)]),
            dict(primary_job="12",runs=[dict(job=102,array=False)])],unresolved_cells=[])
        before=copy.deepcopy(original);actual=rebind_confirmation_runs(original,{102:202})
        self.assertEqual(original,before);self.assertEqual(actual["groups"][0],original["groups"][0])
        self.assertEqual([g["primary_job"] for g in actual["groups"]],["11","12"])
        self.assertEqual(actual["groups"][1]["runs"][0]["job"],202)
        self.assertEqual(actual["groups"][1]["runs"][0]["zero_start_GPU_job"],102)
    def test_rebinding_rejects_unknown_array_or_colliding_native_IDs(self):
        b=dict(groups=[dict(primary_job="11",runs=[dict(job=101,array=False)]),
                       dict(primary_job="12",runs=[dict(job=102,array=False)])])
        for mapping in ({999:201},{101:102},{101:201,102:201}):
            with self.assertRaises(ValueError):rebind_confirmation_runs(b,mapping)
        b["groups"][0]["runs"][0]["array"]=True
        with self.assertRaises(ValueError):rebind_confirmation_runs(b,{101:201})
