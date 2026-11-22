"""Protect seed policy and prevent partial native submissions from launching duplicate fits."""
import copy
from pathlib import Path
import unittest
from .conditional_chain import wire,validated_groups,protected_gpu_predecessors

class ChainTests(unittest.TestCase):
    root=Path("/owned")
    def prep(self,count=2,same_card=True):
        tasks=[]
        for index in range(count):
            tasks.append(dict(primary_job=str(100+index),learner="TabPFN",feature_group="D",
                program="/owned/group.py",script="/owned/group.sbatch",python="/owned/environments/env/bin/python",
                node="compute-0-5",uuid="GPU-one" if same_card else "GPU-"+str(index),array=index==1,
                declaration=dict(model_seed=20261026,split_and_statistics_seed=20261025,
                    original_labels_or_masks_changed=False,task_roster_reselection=False,original_model_budget_unchanged=True),
                required_tasks=[dict(endpoint_key="endpoint"+str(index),feature_group="D",learner="TabPFN",
                    reason="FINAL_SIGNIFICANT_IMPROVEMENT",frozen_B1_role="RETAIN",confirmation_seed=20261026,primary_seed=20261025)]))
        return dict(stage="C1",status="CONDITIONAL_NEURAL_SOURCE_PREPARATION_CLOSED",failures=[],
            prepared_native_groups=tasks,required_configuration_rows=count)
    def run_chain(self,prep,fail_at=None,scripts=None,final_prerequisite_jobs=(),initial_gpu_predecessors=None):
        self.writes={};self.submissions=[];self.releases=[]
        def write(path,value):self.writes[str(path)]=copy.deepcopy(value)
        def submit(path,dependency):
            if fail_at==len(self.submissions):raise RuntimeError("native admission/submission failure")
            self.submissions.append((str(path),dependency));return 200+len(self.submissions)
        def release(job):
            self.assertEqual(self.writes["/owned/out/dispatch_state.json"]["status"],"COMPLETE_CHAIN_RECORDED_BEFORE_RELEASE")
            self.assertEqual(len(self.submissions),len(prep["prepared_native_groups"])+3)
            self.releases.append(job)
        script="#!/bin/bash\n#SBATCH --partition=cpu\nset -euo pipefail\ntrue\n"
        return wire(prep,"/owned/prep/manifest.json",self.root,"/owned/out","/owned/cache.json",
            scripts if scripts is not None else dict(report=script,combine=script,final=script),submit,release,write,final_prerequisite_jobs=final_prerequisite_jobs,initial_gpu_predecessors=initial_gpu_predecessors)
    def test_same_uuid_serialized_and_all_exact_ids_recorded_before_release(self):
        result=self.run_chain(self.prep())
        self.assertEqual([dep for _,dep in self.submissions],[None,"afterany:201","afterany:201:202","afterok:203","afterok:204"])
        self.assertEqual(result["final_export_job"],205)
        self.assertTrue(result["bindings"]["groups"][1]["runs"][0]["array"])
        self.assertEqual(result["status"],"C1_CONDITIONAL_CHAIN_RELEASED")
    def test_different_cards_start_independently(self):
        self.run_chain(self.prep(same_card=False))
        self.assertEqual([dep for _,dep in self.submissions[:2]],[None,None])
    def test_empty_required_plan_launches_no_gpu(self):
        result=self.run_chain(self.prep(0))
        self.assertEqual(len(self.submissions),3)
        self.assertEqual(result["bindings"]["groups"],[])
    def test_partial_submission_never_releases_any_native_fit(self):
        with self.assertRaisesRegex(RuntimeError,"native admission"):self.run_chain(self.prep(),fail_at=1)
        self.assertEqual(self.releases,[])
        self.assertEqual(self.writes["/owned/out/dispatch_state.json"]["native_jobs"],["201"])
    def test_nonfinal_or_traditional_or_changed_seed_or_unowned_source_rejected(self):
        for name,value in (("frozen_B1_role","EXCLUDE"),("learner","LightGBM"),("confirmation_seed",20261027)):
            prep=self.prep(1);prep["prepared_native_groups"][0]["required_tasks"][0][name]=value
            with self.assertRaises(ValueError):validated_groups(prep,self.root)
        prep=self.prep(1);prep["prepared_native_groups"][0]["script"]="/other/group.sbatch"
        with self.assertRaises(ValueError):validated_groups(prep,self.root)
    def test_owned_venv_interpreter_symlink_to_shared_base_is_allowed(self):
        import tempfile
        from .conditional_chain import private_python_prefix
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);root=folder/"owned"
            private_bin=root/"environments"/"registered"/"bin";private_bin.mkdir(parents=True)
            shared_bin=folder/"shared_base"/"bin";shared_bin.mkdir(parents=True)
            base=shared_bin/"python";base.write_text("shared interpreter fixture")
            interpreter=private_bin/"python";interpreter.symlink_to(base)
            self.assertFalse(interpreter.resolve().is_relative_to(root.resolve()))
            self.assertEqual(private_python_prefix(interpreter,root),private_bin.parent.resolve())
            prep=self.prep(1);group=prep["prepared_native_groups"][0]
            group.update(program=str(root/"group.py"),script=str(root/"group.sbatch"),python=str(interpreter))
            self.assertEqual(len(validated_groups(prep,root)),1)
            with self.assertRaises(ValueError):private_python_prefix(base,root)
    def test_registered_submission_envelope_preserves_native_body_and_exports(self):
        from .conditional_chain import native_batch_script,script_with_exports
        body="#!/bin/bash\n#SBATCH --partition=cpu\nset -euo pipefail\nprintf '%s\\n' '$literal'\n"
        wrapped="sbatch <<'REGISTERED'\n"+body+"REGISTERED\n"
        self.assertEqual(native_batch_script(wrapped),body)
        rendered=script_with_exports(wrapped,{"BENCHMARK_SOURCE_CACHE":"/owned/path with spaces/cache.json"})
        self.assertTrue(rendered.startswith("#!/bin/bash\n#SBATCH --partition=cpu\n"))
        self.assertNotIn("sbatch <<",rendered)
        self.assertIn("export BENCHMARK_SOURCE_CACHE='/owned/path with spaces/cache.json'\n",rendered)
        self.assertTrue(rendered.endswith("printf '%s\\n' '$literal'\n"))
    def test_invalid_consumer_is_rejected_before_any_native_submission(self):
        good="#!/bin/bash\nset -euo pipefail\ntrue\n"
        with self.assertRaises(ValueError):
            self.run_chain(self.prep(1),scripts=dict(report=good,combine=good,final="sbatch unexpected-envelope"))
        self.assertEqual(self.submissions,[])
        self.assertEqual(self.releases,[])
    def test_final_waits_for_actual_atomic_producer_without_delaying_gpu_confirmations(self):
        result=self.run_chain(self.prep(),final_prerequisite_jobs=[4537644])
        self.assertEqual([dep for _,dep in self.submissions],
            [None,"afterany:201","afterany:201:202","afterok:203","afterok:204:4537644"])
        self.assertEqual(result["final_prerequisite_jobs"],["4537644"])
        self.assertIn("export BENCHMARK_SOURCE_CACHE=/owned/cache.json",self.writes["/owned/out/final_C1_results.sbatch"])
    def test_invalid_or_duplicate_final_prerequisite_rejected_before_any_submit(self):
        for bad in ([0],["pending"],["1:2"],[123,123]):
            with self.assertRaises(ValueError):self.run_chain(self.prep(),final_prerequisite_jobs=bad)
            self.assertEqual(self.submissions,[])
            self.assertEqual(self.releases,[])
    def test_incomplete_or_duplicate_required_plan_rejected(self):
        prep=self.prep(1);prep["required_configuration_rows"]=2
        with self.assertRaises(ValueError):validated_groups(prep,self.root)
        prep=self.prep();prep["prepared_native_groups"][1]=copy.deepcopy(prep["prepared_native_groups"][0])
        with self.assertRaises(ValueError):validated_groups(prep,self.root)


    def test_first_group_waits_for_active_allocations_then_serializes_its_own_successor(self):
        result=self.run_chain(self.prep(),initial_gpu_predecessors={"GPU-one":["301","302_4"]})
        self.assertEqual([dep for _,dep in self.submissions[:2]],["afterany:301:302_4","afterany:201"])
        self.assertEqual(result["initial_gpu_predecessors"],{"GPU-one":["301","302_4"]})
    def test_unknown_gpu_or_invalid_barriers_rejected_before_submission(self):
        for bad in ({"GPU-other":["301"]},{"GPU-one":["301","301"]},{"GPU-one":["pending"]},{"GPU-one":"301"}):
            with self.assertRaises(ValueError):self.run_chain(self.prep(),initial_gpu_predecessors=bad)
            self.assertEqual(self.submissions,[])

class ActiveGPUQueueTests(unittest.TestCase):
    def groups(self):
        return [dict(node="compute-0-"+str(n),uuid="GPU-"+str(n)) for n in (5,7,22)]
    def test_idle_required_cards_wait_for_every_active_owner_and_shared_card_only_own(self):
        raw="301|zixiao|RUNNING\n302_4|other|COMPLETING\n303|zixiao|SUSPENDED"
        result=protected_gpu_predecessors(self.groups(),{"compute-0-"+str(n):raw for n in (5,7,22)})
        self.assertEqual(result,{"GPU-5":["301","302_4","303"],"GPU-7":["301","302_4","303"],"GPU-22":["301","303"]})
    def test_explicit_empty_observation_and_no_required_groups_acquire_no_wait(self):
        self.assertEqual(protected_gpu_predecessors(self.groups()[:1],{"compute-0-5":""}),{"GPU-5":[]})
        self.assertEqual(protected_gpu_predecessors([],{}),{})
    def test_missing_observation_is_not_evidence_of_an_idle_gpu(self):
        with self.assertRaises(ValueError):protected_gpu_predecessors(self.groups(),{"compute-0-5":""})
    def test_pending_or_malformed_observations_never_create_reservations(self):
        for raw in ("301|zixiao|PENDING","0|zixiao|RUNNING","301||RUNNING","301|zixiao","301_2-4|zixiao|RUNNING",
                    "301|zixiao|RUNNING\n301|other|RUNNING"):
            with self.assertRaises(ValueError):protected_gpu_predecessors(self.groups()[:1],{"compute-0-5":raw})
    def test_duplicate_observation_is_one_wait_and_conflicting_gpu_mapping_is_rejected(self):
        self.assertEqual(protected_gpu_predecessors(self.groups()[:1],{"compute-0-5":"301|zixiao|RUNNING\n301|zixiao|RUNNING"}),{"GPU-5":["301"]})
        with self.assertRaises(ValueError):protected_gpu_predecessors(self.groups()[:1]+[dict(node="compute-0-5",uuid="GPU-other")],{"compute-0-5":""})

if __name__=="__main__":unittest.main()
