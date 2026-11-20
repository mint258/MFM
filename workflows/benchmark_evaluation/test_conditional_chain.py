"""Protect seed policy and prevent partial native submissions from launching duplicate fits."""
import copy
from pathlib import Path
import unittest
from .conditional_chain import wire,validated_groups

class ChainTests(unittest.TestCase):
    root=Path("/owned")
    def prep(self,count=2,same_card=True):
        tasks=[]
        for index in range(count):
            tasks.append(dict(primary_job=str(100+index),learner="TabPFN",feature_group="D",
                program="/owned/group.py",script="/owned/group.sbatch",python="/owned/env/bin/python",
                node="compute-0-5",uuid="GPU-one" if same_card else "GPU-"+str(index),array=index==1,
                declaration=dict(model_seed=20261026,split_and_statistics_seed=20261025,
                    original_labels_or_masks_changed=False,task_roster_reselection=False,original_model_budget_unchanged=True),
                required_tasks=[dict(endpoint_key="endpoint"+str(index),feature_group="D",learner="TabPFN",
                    reason="FINAL_SIGNIFICANT_IMPROVEMENT",frozen_B1_role="RETAIN",confirmation_seed=20261026,primary_seed=20261025)]))
        return dict(stage="C1",status="CONDITIONAL_NEURAL_SOURCE_PREPARATION_CLOSED",failures=[],
            prepared_native_groups=tasks,required_configuration_rows=count)
    def run_chain(self,prep,fail_at=None):
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
            dict(report=script,combine=script,final=script),submit,release,write)
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
    def test_incomplete_or_duplicate_required_plan_rejected(self):
        prep=self.prep(1);prep["required_configuration_rows"]=2
        with self.assertRaises(ValueError):validated_groups(prep,self.root)
        prep=self.prep();prep["prepared_native_groups"][1]=copy.deepcopy(prep["prepared_native_groups"][0])
        with self.assertRaises(ValueError):validated_groups(prep,self.root)

if __name__=="__main__":unittest.main()
