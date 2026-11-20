"""New approved-target binding, atom masks and immutable-roster supplement interface."""
import copy
import unittest
import numpy as np
from .approved_pka_atomic import (DEFINITION,validate_definition,target_row,validate_populations,
    atom37,p_site_vector,atom_target_array,prediction_rows,apply_to_c1)

class ApprovedPkaTests(unittest.TestCase):
    def manifest(self):
        return dict(status="ATOMIC_SINGLE_SITE_TARGETS_READY",
            user_definition_authority=dict(approved=True,definition_id=DEFINITION,
                authority_kind="explicit_user_message_question_reply",question_item_id="recorded reply",
                user_reply="approved original source catalogue",proposal_job=4536942,catalog_patterns=37),
            microscopic_experimental_records=0,predicted_microspecies_used_as_experimental=False,
            multi_site_microscopic_assignment=False)
    def raw(self,blind=False):
        return dict(definition_approved=True,single_site_definition_id=DEFINITION,
            eligibility_status="APPROVED_SINGLE_SITE_ATOMIC_TARGET",
            experimental_macro_reused_under_single_site_definition=True,
            experimental_microscopic_annotation=False,microscopic_assignment_performed=False,
            benchmark_role="EXTERNAL_BLIND" if blind else "TRAIN_POOL",endpoint="atomic_pKa_acid",
            full_InChIKey=("BBBBBBBBBBBBBB-BBBBBBBBBB-B" if blind else "AAAAAAAAAAAAAA-AAAAAAAAAA-A"),
            model_atom_index=3,source_atom_index=7,model_smiles="CC(=O)O",target_value=4.25,
            record_id=("pKahub_atomic_single_site_v1:EXTERNAL_BLIND:SAMPL6:SM01:acid" if blind else "pKahub_atomic_single_site_v1:TRAIN:one"),
            macro_record_id="original macro ID",geometry_dataset="pKahub",geometry_record_id="source ID",
            source_challenge="SAMPL6" if blind else None,challenge_compound_id="SM01" if blind else None)
    def domain(self):return dict(model_atom_to_source=[4,5,6,7],retained=True,domain_eligible=True)
    def test_exact_approval_and_micro_caveat_required(self):
        self.assertEqual(validate_definition(self.manifest())["definition_id"],DEFINITION)
        for field,value in (("microscopic_experimental_records",1),("multi_site_microscopic_assignment",True)):
            m=self.manifest();m[field]=value
            with self.assertRaises(ValueError):validate_definition(m)
        m=self.manifest();m["user_definition_authority"]["approved"]=False
        with self.assertRaises(ValueError):validate_definition(m)
    def test_original_label_and_both_atom_indices_preserved(self):
        r=target_row(self.raw(),self.domain())
        self.assertEqual((r["y"],r["model_atom_index"],r["source_atom_index"]),(4.25,3,7))
        self.assertEqual(r["record_id"],self.raw()["record_id"])
        self.assertEqual(r["macro_record_id"],"original macro ID")
    def test_unapproved_multisite_or_bad_mapping_refused(self):
        for field,value in (("definition_approved",False),("microscopic_assignment_performed",True),
                            ("experimental_microscopic_annotation",True),("model_atom_index",99)):
            r=self.raw();r[field]=value
            with self.assertRaises(ValueError):target_row(r,self.domain())
        d=self.domain();d["model_atom_to_source"][3]=2
        with self.assertRaises(ValueError):target_row(self.raw(),d)
    def test_original_domain_cannot_be_relaxed(self):
        d=self.domain();d["domain_eligible"]=False
        with self.assertRaises(ValueError):target_row(self.raw(),d)
    def test_complete_key_blind_exclusion_and_challenge_namespace(self):
        tr=target_row(self.raw(),self.domain());te=target_row(self.raw(True),self.domain())
        self.assertEqual(validate_populations([tr,te]),(1,1))
        bad=dict(te,full_inchikey=tr["full_inchikey"])
        with self.assertRaises(ValueError):validate_populations([tr,bad])
        with self.assertRaises(ValueError):validate_populations([tr,dict(te,source_challenge=None)])
        with self.assertRaises(ValueError):validate_populations([tr,te,te])
    def test_atom_mask_labels_only_approved_model_site(self):
        r=target_row(self.raw(),self.domain());mol,y=atom_target_array(r)
        self.assertEqual(mol.GetAtomWithIdx(3).GetAtomicNum(),8)
        self.assertEqual(y.shape,(4,1));self.assertEqual(y[3,0],4.25)
        self.assertEqual(np.isfinite(y).sum(),1)
        self.assertEqual(len(atom37(mol.GetAtomWithIdx(3))),37)
    def test_native_p_values_remap_once_without_filling(self):
        array=np.asarray([[1.,float("nan")],[2.,3.]])
        self.assertEqual(p_site_vector(array,[7,4],7)[0],1.)
        self.assertTrue(np.isnan(p_site_vector(array,[7,4],7)[1]))
        self.assertIsNone(p_site_vector(None,[7,4],7))
        self.assertIsNone(p_site_vector([[float("nan")]], [7],7))
        with self.assertRaises(ValueError):p_site_vector(array,[7,7],7)
        with self.assertRaises(ValueError):p_site_vector(array,[7],7)
    def test_prediction_binding_keeps_original_test_and_training_reference(self):
        r=target_row(self.raw(True),self.domain())
        p=prediction_rows([r],np.array([4.]),5.5,"LightGBM")
        self.assertEqual((p[0]["record_id"],p[0]["y_true"],p[0]["training_mean"]),(r["record_id"],4.25,5.5))
        self.assertEqual(p[0]["source_challenge"],"SAMPL6")
        with self.assertRaises(ValueError):prediction_rows([r],np.array([]),5.5,"LightGBM")
    def supplement(self):
        cell=dict(endpoint_key="existing::single_site_mechanism",dataset="pKahub",target="single_site_mechanism",
            level="atom",feature_group="Pprime_plus_RDKit_atom",learner="LightGBM",frozen_B1_role="UNRESOLVED",
            task_roster_reselection=False,status="UNRESOLVED")
        s=dict(status="APPROVED_PKA_ATOMIC_SUPPLEMENT_CLOSED",B1_task_screen_modified=False,
            predeclared_result_role="APPENDIX",all_required_neural_confirmations_closed=True,
            source_definition_manifest=self.manifest(),C1_result=dict(cell,status="FINAL_APPROVED_SINGLE_SITE_APPENDIX",RAE=.5))
        return cell,s
    def test_only_registered_unresolved_cell_replaced_without_replaying_other_results(self):
        cell,s=self.supplement();other=dict(dataset="unchanged",RAE=.123,metadata="same original source")
        original=[other,cell];snapshot=copy.deepcopy(original)
        result=apply_to_c1(original,s)
        self.assertEqual(original,snapshot);self.assertEqual(result[0],other)
        self.assertEqual(result[1]["RAE"],.5)
        self.assertEqual(result[1]["frozen_B1_role"],"UNRESOLVED")
    def test_final_metadata_reuses_closed_train_reference_and_preserves_old_placeholder_history(self):
        cell,s=self.supplement();cell["reason"]="ORIGINAL_EXPERIMENTAL_SINGLE_SITE_ATOM_ANNOTATIONS_ABSENT"
        s["C1_result"]["status"]="FINAL_APPROVED_SINGLE_SITE_APPENDIX"
        aggregate=[dict(model="C1_Pprime_plus_RDKit_atom_LightGBM",task="single_site_mechanism",
            definition_id="AUTHOR_TABLE_S2_37_CATALOG_V1",training_mean="6.1147480427053",n_train="4347")]
        row=apply_to_c1([cell],s,aggregate)[0]
        self.assertEqual(row["training_mean"],aggregate[0]["training_mean"])
        self.assertEqual(row["n_train"],"4347")
        self.assertEqual(row["historical_primary_placeholder_reason"],cell["reason"])
        self.assertEqual(row["reason"],"APPROVED_POST_FREEZE_SINGLE_SITE_APPENDIX")
        with self.assertRaises(ValueError):apply_to_c1([cell],s,[])
    def test_changed_role_or_definition_or_incomplete_confirmation_refused(self):
        cell,s=self.supplement()
        for field,value in (("B1_task_screen_modified",True),("all_required_neural_confirmations_closed",False)):
            changed=copy.deepcopy(s);changed[field]=value
            with self.assertRaises(ValueError):apply_to_c1([cell],changed)
        changed=copy.deepcopy(s);changed["C1_result"]["frozen_B1_role"]="RETAIN"
        with self.assertRaises(ValueError):apply_to_c1([cell],changed)

if __name__=="__main__":unittest.main()
