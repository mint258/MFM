"""Synthetic contracts for the remaining mandatory confirmation CPU execution."""
import ast,copy,unittest
from .confirmation_cpu_pool import prepare_required_cpu_source,validate_required_group,validate_cpu_runtime,assign_slots,CPU_SLOTS,resolve_confirmation_environment

class RequiredConfirmationCpuTests(unittest.TestCase):
    def group(self):
        return dict(primary_job=123,feature_group="Pprime",learner="TabPFN",array=False,
            required_tasks=[dict(dataset="MoleculeACE",feature_group="Pprime",learner="TabPFN",
                primary_source_job="123",confirmation_seed="20261026",primary_seed="20261025",
                fold_and_statistics_seed="20261025",reason="FINAL_SIGNIFICANT_IMPROVEMENT",frozen_B1_role="RETAIN",
                task_roster_reselection="False",original_labels_or_masks_changed="False",producer_task="kept")])
    def source(self):
        declaration=dict(model_seed=20261026,split_and_statistics_seed=20261025,reason="FINAL_SIGNIFICANT_IMPROVEMENT",
            selected_original_tasks=[("MoleculeACE","kept")],task_roster_reselection=False,
            primary_fit_population_only=True,original_model_budget_unchanged=True)
        return ("MODEL_SEED=20261026\nSEED=20261025\n__confirmation_default_dataset='MoleculeACE'\n"
            "__confirmation_selected=frozenset([('MoleculeACE','kept')])\n__confirmation_declaration="+repr(declaration)+"\n"
            "torch.set_num_threads(2)\ncheckpoint='smoke100/job_4536865/model_cache/tabpfn-v2-regressor.ckpt'\n"
            "classifier=False\nmodel=(TabPFNClassifier if classifier else TabPFNRegressor).create_default_for_version("
            "ModelVersion.V2,device='cuda',model_path=checkpoint,random_state=MODEL_SEED,n_preprocessing_jobs=2,"
            "inference_config={'SUBSAMPLE_SAMPLES':10000},ignore_pretraining_limits=False)\n"
            "model.fit(TRAIN_FEATURES,TRAIN_LABELS)\nanswer=model.predict(TEST_FEATURES)\n")

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
        exec(prepare_required_cpu_source(self.source(),self.group(),16),ns)
        self.assertEqual(records["threads"],16);self.assertIs(records["version"],version)
        self.assertEqual(records["kwargs"]["device"],"cpu")
        self.assertEqual(records["kwargs"]["random_state"],20261026)
        self.assertEqual(records["kwargs"]["n_preprocessing_jobs"],2)
        self.assertEqual(records["kwargs"]["inference_config"],{"SUBSAMPLE_SAMPLES":10000})
        self.assertEqual(ns["SEED"],20261025);self.assertEqual(ns["__confirmation_selected"],{("MoleculeACE","kept")})
        self.assertIs(records["fit"][0],train);self.assertIs(records["fit"][1],labels)
        self.assertIs(records["test"],test);self.assertIs(ns["answer"],marker)

    def test_variable_execution_threads_keep_original_two_preprocessing_jobs(self):
        source=self.source().replace("torch.set_num_threads(2)","cpus=int(os.environ['SLURM_CPUS_PER_TASK'])\ntorch.set_num_threads(cpus)").replace("n_preprocessing_jobs=2","n_preprocessing_jobs=cpus")
        result=prepare_required_cpu_source(source,self.group(),32);tree=ast.parse(result)
        self.assertIn("torch.set_num_threads(cpus)",result)
        self.assertIn("n_preprocessing_jobs=2",result)
        restored=ast.parse(result.replace("device='cpu'","device='cuda'").replace("n_preprocessing_jobs=2","n_preprocessing_jobs=cpus"))
        self.assertEqual(ast.dump(restored),ast.dump(ast.parse(source)))
    def test_plain_regressor_and_absent_original_thread_selector_are_supported(self):
        source=self.source().replace("(TabPFNClassifier if classifier else TabPFNRegressor)","TabPFNRegressor").replace("torch.set_num_threads(2)\n","")
        result=prepare_required_cpu_source(source,self.group(),32)
        self.assertIn("device='cpu'",result);self.assertNotIn("set_num_threads",result)
        self.assertEqual(ast.dump(ast.parse(result.replace("device='cpu'","device='cuda'"))),ast.dump(ast.parse(source)))
    def test_original_declared_budget_population_and_task_filter_are_mandatory(self):
        for old,new in (("'original_model_budget_unchanged': True","'original_model_budget_unchanged': False"),
            ("'primary_fit_population_only': True","'primary_fit_population_only': False"),
            ("frozenset([('MoleculeACE','kept')])","frozenset([('MoleculeACE','another')])")):
            with self.subTest(change=old),self.assertRaises(ValueError):prepare_required_cpu_source(self.source().replace(old,new),self.group(),16)
    def test_seed_weight_version_backend_and_preprocessing_drift_are_rejected(self):
        for old,new in (("MODEL_SEED=20261026","MODEL_SEED=20261027"),("SEED=20261025","SEED=20261026"),
            ("ModelVersion.V2","ModelVersion.V2_5"),("device='cuda'","device='cpu'"),
            ("n_preprocessing_jobs=2","n_preprocessing_jobs=32"),("job_4536865","job_9999999")):
            with self.subTest(change=old),self.assertRaises(ValueError):prepare_required_cpu_source(self.source().replace(old,new),self.group(),16)
    def test_both_final_roles_allowed_excluded_and_closed_biogen_rejected(self):
        for role in ("RETAIN","APPENDIX"):
            group=self.group();group["required_tasks"][0]["frozen_B1_role"]=role
            self.assertEqual(validate_required_group(group),(("MoleculeACE","kept"),))
        for key,value in (("frozen_B1_role","EXCLUDE"),("confirmation_seed","20261025"),("original_labels_or_masks_changed","True")):
            group=self.group();group["required_tasks"][0][key]=value
            with self.assertRaises(ValueError):validate_required_group(group)
        group=self.group();group["primary_job"]=4537679
        with self.assertRaises(ValueError):validate_required_group(group)
    def test_duplicate_tasks_arrays_or_unbound_primary_are_rejected(self):
        group=self.group();group["required_tasks"]*=2
        with self.assertRaises(ValueError):validate_required_group(group)
        group=self.group();group["array"]=True
        with self.assertRaises(ValueError):validate_required_group(group)
        group=self.group();group["required_tasks"][0]["primary_source_job"]="124"
        with self.assertRaises(ValueError):validate_required_group(group)
    def test_runtime_exact_allocation_node_and_disabled_cuda(self):
        validate_cpu_runtime("compute-0-12",32,"compute-0-12",32,"")
        for args in (("compute-0-21",32,"compute-0-21",32,""),("compute-0-12",16,"compute-0-12",32,""),
            ("compute-0-12",32,"compute-0-13",32,""),("compute-0-12",32,"compute-0-12",32,"GPU-x")):
            with self.assertRaises(ValueError):validate_cpu_runtime(*args)
    def test_slot_round_robin_is_bounded_and_preserves_every_input(self):
        rows=[dict(original_GPU_job=100+i,group=self.group()) for i in range(40)];before=copy.deepcopy(rows)
        assigned=assign_slots(rows);self.assertEqual(rows,before)
        self.assertEqual(len(assigned),40);self.assertEqual({r["CPU_slot"] for r in assigned},set(range(8)))
        self.assertEqual([r["original_GPU_job"] for r in assigned],[r["original_GPU_job"] for r in rows])
        self.assertTrue(all(r["node"]==CPU_SLOTS[r["CPU_slot"]] and r["allocated_CPUs"]==16 for r in assigned))
        self.assertTrue(all(sum(r["CPU_slot"]==i for r in assigned)==5 for i in range(8)))
    def test_large_context_uses_demand_allocation_without_changing_group(self):
        group=self.group();group["required_tasks"][0]["dataset"]="Joung2020"
        rows=[dict(original_GPU_job=100,group=group)]
        self.assertEqual(assign_slots(rows)[0]["allocated_CPUs"],32)
        self.assertEqual(assign_slots(rows)[0]["group"],group)
        with self.assertRaises(ValueError):assign_slots(rows*2)
    def test_unregistered_cpu_selector_or_thread_count_is_rejected(self):
        for source in (self.source().replace("torch.set_num_threads(2)","torch.set_num_threads(4)"),
            self.source().replace("n_preprocessing_jobs=2","n_preprocessing_jobs=cpus")):
            with self.assertRaises(ValueError):prepare_required_cpu_source(source,self.group(),32)

    def environment(self,feature="Pprime"):
        return dict(BENCHMARK_MODEL="C1-TabPFN-"+feature,TABPFN_ALLOW_CPU_LARGE_DATASET="1",LOKY_MAX_CPU_COUNT="2")
    def test_joung_original_task_index_is_preserved(self):
        group=self.group();group["required_tasks"][0]["dataset"]="Joung2020"
        env=self.environment();env["BENCHMARK_TASK_INDEX"]="8"
        self.assertEqual(resolve_confirmation_environment(group,self.source(),env),env)
    def test_expansion_actual_dispatch_uses_tabpfn_instead_of_lightgbm_default(self):
        group=self.group();group["required_tasks"][0]["dataset"]="ExpansionRx"
        source=self.source()+"\nmodel_name=os.environ.get('C1_MODEL','LightGBM')\nactual_learner='LightGBM' if model_name=='LightGBM' else 'TabPFN'\n"
        env=resolve_confirmation_environment(group,source,self.environment())
        class Env:
            def get(self,key,default):return env.get(key,default)
        namespace={"os":type("OS",(),{"environ":Env()})}
        exec("\n".join(source.splitlines()[-2:]),namespace)
        self.assertEqual(namespace["model_name"],"TabPFN-V2");self.assertEqual(namespace["actual_learner"],"TabPFN")
        self.assertEqual(env["C1_MODEL"],"TabPFN-V2")
    def test_expansion_wrong_explicit_learner_or_missing_selector_is_rejected(self):
        group=self.group();group["required_tasks"][0]["dataset"]="ExpansionRx"
        source=self.source()+"\nmodel_name=os.environ.get('C1_MODEL','LightGBM')\n"
        env=self.environment();env["C1_MODEL"]="LightGBM"
        with self.assertRaises(ValueError):resolve_confirmation_environment(group,source,env)
        with self.assertRaises(ValueError):resolve_confirmation_environment(group,self.source(),self.environment())
    def test_unknown_environment_model_and_context_drift_fail_before_source_execution(self):
        for key,value in (("UNREGISTERED","x"),("BENCHMARK_MODEL","C1-LightGBM-Pprime"),("LOKY_MAX_CPU_COUNT","32")):
            env=self.environment();env[key]=value
            with self.assertRaises(ValueError):resolve_confirmation_environment(self.group(),self.source(),env)
    def test_ppe_original_binding_and_data_selector_are_preserved(self):
        group=self.group();group["required_tasks"][0]["dataset"]="PPE1694"
        env=self.environment();env["REFERENCE_BINDING_JOB"]="4536997"
        self.assertEqual(resolve_confirmation_environment(group,self.source(),env),env)
        env["REFERENCE_BINDING_JOB"]="4536995"
        with self.assertRaises(ValueError):resolve_confirmation_environment(group,self.source(),env)
    def test_environment_resolution_never_changes_input_and_non_expansion_inheritance_rejected(self):
        env=self.environment();before=copy.deepcopy(env)
        self.assertEqual(resolve_confirmation_environment(self.group(),self.source(),env),before);self.assertEqual(env,before)
        env["C1_MODEL"]="TabPFN-V2"
        with self.assertRaises(ValueError):resolve_confirmation_environment(self.group(),self.source(),env)
    def test_source_actual_benchmark_model_selection_remains_registered(self):
        source=self.source()+"\nmodel_name=os.environ.get('BENCHMARK_MODEL','RF-ECFP4')\n"
        self.assertEqual(resolve_confirmation_environment(self.group(),source,self.environment())["BENCHMARK_MODEL"],"C1-TabPFN-Pprime")
        with self.assertRaises(ValueError):resolve_confirmation_environment(self.group(),source.replace("'BENCHMARK_MODEL'","'UNREGISTERED'"),self.environment())
