"""Reject false full completion and changed same-pilot binding before planning."""
import copy
import unittest
from unittest.mock import patch
from . import completion as M


class CompletionTests(unittest.TestCase):
    def test_true_full_scope_keeps_all_statuses_and_actual_pilot_stage(self):
        ref={'path':'/actual/stage/receipt.json','bytes':1,'sha256':'r'}
        pr={'path':'plan','bytes':1,'sha256':'p'};sr={'path':'startup','bytes':1,'sha256':'s'}
        bindings=dict(quality_reference_review={'actual189':True},source_capsule_reference={'source':True},parent_transport_manifest={'transport':True})
        receipt=dict(schema='PUBCHEM_UFF3_ALLOCATION_RECEIPT_V1',mode='full',status='COMPLETE_CANDIDATE_SHARD_NOT_TRAINING_RELEASE',
            shard_count=1,shard_index=0,expected_molecules=2500000,closed_family_export_molecules=2500000,
            source_total_molecules=2500000,state_counts={'EXPORTED':2000000,'FAILED':300000,'UNKNOWN':200000},maximum_conformers=3,
            recipe_sha256=M.C.recipe_sha(),new_QM_calls=0,runtime={'job_id':'real-full'},source_manifest={'frozen':True},
            execution_metadata=dict(original_launcher_plan_reference=pr,original_startup_proof_reference=sr),**bindings)
        plan=dict(output_directory='/actual/stage',resume_output_directory='/actual/stage',pilot_completed={'actual':True},source_manifest=receipt['source_manifest'])
        def check(r=receipt,p=plan):
            with patch.object(M,'read',side_effect=lambda x:r if x==ref else p),patch.object(M,'parent')as terminal:
                value=M.generation(ref,{'actual-account':True},bindings);terminal.assert_called_once()
                return value
        self.assertEqual(check()[2]['generation_receipt_reference'],ref)
        for change in ({'closed_family_export_molecules':2000000},{'mode':'pilot'},{'maximum_conformers':4},{'new_QM_calls':1}):
            with self.assertRaises(ValueError):check({**receipt,**change})
        with self.assertRaisesRegex(ValueError,'identical output'):check(p={**plan,'resume_output_directory':'/another/stage'})
        with self.assertRaisesRegex(ValueError,'189'):check({**receipt,'quality_reference_review':{'provisional50k':True}})


if __name__=='__main__':unittest.main()