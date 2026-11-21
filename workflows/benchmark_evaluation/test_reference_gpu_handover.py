import unittest
from workflows.benchmark_evaluation.reference_gpu_handover import select_zero_start_cpu_successors,remap_zero_start_cpu_to_gpu_specs

class ZeroStartReferenceGPUHandoverTests(unittest.TestCase):
    def plan(self):
        return dict(schema="REGISTERED_REFERENCE_CPU_PRIMARY_PLAN_V1",maximum_parallel_CPU_models=8,
          declared_joint_benchmark_NFS_pool_bytes=40*1024**3,models=[
          dict(new_native_job=10,original_CPU_predecessor=None,dataset="Joung2020",feature_group="Pprime",original_model_fits_started=0),
          dict(new_native_job=11,original_CPU_predecessor=1,dataset="Joung2020",feature_group="Pprime_plus_D",original_model_fits_started=0)])
    def native(self,job=11,state="PENDING",runtime="00:00:00",restarts=0,user="zixiao(1278)"):
        return f"JobId={job} UserId={user} JobState={state} RunTime={runtime} Restarts={restarts} Reason=Dependency"
    def test_only_pending_successor_is_selected_and_plan_is_not_mutated(self):
        plan=self.plan();selected,skipped=select_zero_start_cpu_successors(plan,{10:self.native(10),11:self.native()})
        self.assertEqual([r["new_native_job"] for r in selected],[11]);self.assertEqual(skipped,[])
        selected[0]["dataset"]="changed";self.assertEqual(plan["models"][1]["dataset"],"Joung2020")
    def test_running_completing_or_closed_sources_are_never_replayed(self):
        for state in ("RUNNING","COMPLETING","CONFIGURING","COMPLETED","FAILED","TIMEOUT"):
            selected,skipped=select_zero_start_cpu_successors(self.plan(),{11:self.native(state=state)})
            with self.subTest(state=state):self.assertEqual(selected,[]);self.assertEqual(skipped[0]["state"],state)
        selected,skipped=select_zero_start_cpu_successors(self.plan(),{11:self.native().replace("Reason=Dependency","Reason=JobHeldUser")})
        self.assertEqual(selected,[]);self.assertEqual(skipped[0]["state"],"USER_HELD_NOT_REASSIGNED")
    def test_missing_observation_is_not_a_retry_authorization(self):
        selected,skipped=select_zero_start_cpu_successors(self.plan(),{})
        self.assertEqual(selected,[]);self.assertEqual(skipped[0]["state"],"NATIVE_HANDLE_MISSING_NO_REPLAY")
    def test_owner_source_or_unexpected_state_is_rejected(self):
        for raw in (self.native(job=12),self.native(user="other(1)"),self.native(state="UNKNOWN")):
            with self.subTest(raw=raw),self.assertRaises(ValueError):select_zero_start_cpu_successors(self.plan(),{11:raw})
    def test_nonzero_runtime_or_restart_cannot_be_called_zero_start(self):
        for raw in (self.native(runtime="00:00:01"),self.native(restarts=1)):
            with self.subTest(raw=raw),self.assertRaises(ValueError):select_zero_start_cpu_successors(self.plan(),{11:raw})
    def test_unsupported_task_or_capacity_plan_cannot_expand_scope(self):
        for key,value in (("maximum_parallel_CPU_models",15),("declared_joint_benchmark_NFS_pool_bytes",68*1024**3)):
            plan=self.plan();plan[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):select_zero_start_cpu_successors(plan,{11:self.native()})
        plan=self.plan();plan["models"][1]["dataset"]="NMRShiftDB2"
        with self.assertRaises(ValueError):select_zero_start_cpu_successors(plan,{11:self.native()})
    def test_mapping_preserves_original_GPU_provenance_and_other_sources(self):
        row=dict(job=11,folder="reference_cv_models/job_11",dataset="Joung2020",feature_group="Pprime_plus_D",learner="TabPFN",primary_execution_backend="CPU",zero_start_resource_reassignment_of_job=1)
        other=dict(job=20,folder="other/job_20",learner="LightGBM")
        result=remap_zero_start_cpu_to_gpu_specs([row,other],{11:30})
        self.assertEqual(result[0]["job"],30);self.assertEqual(result[0]["zero_start_resource_reassignment_of_job"],1)
        self.assertEqual(result[0]["zero_start_CPU_primary_reassignment_of_job"],11)
        self.assertEqual(result[1],other);self.assertEqual(row["job"],11)
    def test_mapping_rejects_non_CPU_or_wrong_source_or_duplicate(self):
        row=dict(job=11,folder="reference_cv_models/job_11",dataset="Joung2020",feature_group="Pprime",learner="TabPFN",primary_execution_backend="CPU")
        for specs,mapping in (([dict(row,primary_execution_backend="GPU")],{11:30}),([dict(row,folder="wrong")],{11:30}),
                              ([row,row],{11:30}),([row],{11:11}),([row],{99:30})):
            with self.subTest(specs=specs,mapping=mapping),self.assertRaises(ValueError):remap_zero_start_cpu_to_gpu_specs(specs,mapping)
if __name__=="__main__":unittest.main()
