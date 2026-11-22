"""Synthetic scheduler metadata only; never reload scientific results."""
import copy,json,unittest
from .infrastructure_handover import *

class HandoverTests(unittest.TestCase):
    def spec(self):
        return [dict(dataset="test",feature_group="Pprime_plus_D",learner="LightGBM",
            job=101,folder="C1/job_101",original_CPU_job=101,seed=20261025),
            dict(dataset="unchanged",feature_group="D",learner="LightGBM",job=99,folder="D/job_99",seed=20261025)]
    def test_owned_pending_boundary_required(self):
        text="JobId=101 UserId=zixiao(1278) JobState=PENDING RunTime=00:00:00"
        self.assertEqual(require_owned_pending(text)["JobId"],"101")
        for old,new in (("1278","1"),("PENDING","RUNNING"),("00:00:00","00:00:01")):
            with self.assertRaises(ValueError):require_owned_pending(text.replace(old,new))
    def test_dependency_structure_and_unrelated_parents_preserved(self):
        dep="afterok:101(unfulfilled),afterany:302:303(unfulfilled)?aftercorr:404(satisfied)"
        self.assertEqual(remap_dependency(dep,{101:201}),"afterok:201,afterany:302:303?aftercorr:404")
        self.assertIsNone(remap_dependency("(null)",{101:201}))
        self.assertEqual(remap_dependency("afterany:302:101",{101:201}),"afterany:302:201")
        with self.assertRaises(ValueError):remap_dependency("unknown:101",{101:201})
    def test_actual_source_binding_changes_only_native_identity(self):
        source=self.spec();snapshot=copy.deepcopy(source);result=remap_c1_specs(source,{101:201})
        self.assertEqual(source,snapshot);self.assertEqual(result[1],source[1])
        self.assertEqual(result[0]["job"],201);self.assertEqual(result[0]["folder"],"C1/job_201")
        self.assertEqual(result[0]["original_CPU_job"],101);self.assertEqual(result[0]["seed"],20261025)
    def test_missing_duplicated_or_unregistered_sources_refused(self):
        for mapping in ({102:202},{101:101},{101:201,99:201}):
            with self.assertRaises(ValueError):remap_c1_specs(self.spec(),mapping)
        duplicated=self.spec()+[self.spec()[0]]
        with self.assertRaises(ValueError):remap_c1_specs(duplicated,{101:201})
        changed=self.spec();changed[0]["learner"]="TabPFN"
        with self.assertRaises(ValueError):remap_c1_specs(changed,{101:201})
    def test_primary_literal_rebound_without_touching_scientific_body(self):
        script='#!/bin/bash\nc1_specs=json.loads("[]")\nseed=20261025\n'
        rewritten=replace_primary_specs(script,self.spec())
        self.assertTrue(rewritten.endswith("seed=20261025\n"))
        ns=dict(json=json);exec(rewritten.split("\n",1)[1],ns)
        self.assertEqual(ns["c1_specs"],self.spec())
        with self.assertRaises(ValueError):replace_primary_specs("no original binding\n",self.spec())
    def test_zero_native_proof_requires_all_daemons_and_no_children_or_models(self):
        proof="PROC 10 Dl slurmstepd\nPROC 11 Dl slurmstepd\nCHILDREN 10:\nCHILDREN 11:\n"
        self.assertTrue(zero_model_processes(proof,{10,11}))
        for bad in (proof+"PROC 12 R python\n",proof.replace("CHILDREN 10:","CHILDREN 10: 12"),proof.replace("10 Dl","10 Sl")):
            with self.assertRaises(ValueError):zero_model_processes(bad,{10,11})
    def atomic(self):
        return dict(job="4537644",status="APPROVED_PKA_ATOMIC_SUPPLEMENT_CLOSED",
            B1_task_screen_modified=False,all_required_neural_confirmations_closed=True,predeclared_result_role="APPENDIX")
    def test_long_closed_atomic_source_uses_actual_fulfilled_precondition(self):
        result=closed_atomic_prerequisite(self.atomic(),"Welcome\n4537644|COMPLETED|0:0\n")
        self.assertEqual(result["job"],4537644);self.assertFalse(result["native_future_dependency_required"])
    def test_atomic_gate_rejects_pending_failed_changed_or_duplicate_evidence(self):
        for accounting in ("4537644|RUNNING|0:0\n","4537644|FAILED|1:0\n","4537644|COMPLETED|0:0\n"*2,""):
            with self.assertRaises(ValueError):closed_atomic_prerequisite(self.atomic(),accounting)
        changed=self.atomic();changed["B1_task_screen_modified"]=True
        with self.assertRaises(ValueError):closed_atomic_prerequisite(changed,"4537644|COMPLETED|0:0\n")

if __name__=="__main__":unittest.main()
