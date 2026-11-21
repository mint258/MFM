"""Synthetic challenge-qualified pKa alignment; raw IDs and experimental fields remain intact."""
import unittest
from .c1_reporting import native_evaluation_id,native_primary_row,native_population
from .selection import IncompleteComparison

class PkaChallengeIdentityTests(unittest.TestCase):
    def raw(self,challenge="SAMPL6",record="pKahub:combined.tsv:7",task="acid"):
        return dict(dataset="pKahub",task=task,challenge=challenge,record_id=record,
                    rawdataID="7",challenge_compound_id="SM1",full_inchikey="FULL-KEY",
                    y_true=2.,prediction=1.,training_mean=0.)
    def test_same_raw_id_in_different_challenges_has_distinct_comparison_identity(self):
        for challenge in ("SAMPL6","SAMPL7"):
            raw=self.raw(challenge);before=dict(raw)
            self.assertEqual(native_evaluation_id(raw,"pKahub"),challenge+":pKahub:combined.tsv:7")
            self.assertEqual(raw,before)
        self.assertNotEqual(native_evaluation_id(self.raw("SAMPL6"),"pKahub"),
                            native_evaluation_id(self.raw("SAMPL7"),"pKahub"))
    def test_already_qualified_TabPFN_identity_is_kept_and_conflicts_rejected(self):
        for challenge in ("SAMPL6","SAMPL7"):
            identity=challenge+":pKahub:combined.tsv:7"
            raw=self.raw(challenge,identity,"macro_acid")
            self.assertEqual(native_evaluation_id(raw,"pKahub"),identity)
            raw.pop("challenge")
            self.assertEqual(native_evaluation_id(raw,"pKahub"),identity)
            raw["challenge"]="SAMPL7" if challenge=="SAMPL6" else "SAMPL6"
            with self.assertRaises(IncompleteComparison):native_evaluation_id(raw,"pKahub")
    def test_missing_unknown_or_misqualified_challenges_cannot_be_guessed(self):
        for challenge in (None,"","SAMPL8","sampl6"):
            with self.assertRaises(IncompleteComparison):native_evaluation_id(self.raw(challenge),"pKahub")
        for record in (None,"","SAMPL8:pKahub:combined.tsv:7","SAMPL7:pKahub:combined.tsv:7"):
            with self.assertRaises(IncompleteComparison):native_evaluation_id(self.raw("SAMPL6",record),"pKahub")
    def test_non_pKa_and_atomic_task_identities_do_not_acquire_a_challenge_prefix(self):
        raw=self.raw()
        self.assertEqual(native_evaluation_id(raw,"Other"),raw["record_id"])
        raw["task"]="single_site_mechanism"
        self.assertEqual(native_evaluation_id(raw,"pKahub"),raw["record_id"])
    def test_six_LightGBM_macro_cells_align_without_changing_native_fields_or_coverage(self):
        for feature in ("D","Pprime","Pprime_plus_D"):
            for task in ("acid","base"):
                key="pkahub::macro_"+task
                catalog=[dict(dataset="pKahub",target="macro_"+task,endpoint_key=key)]
                spec=dict(dataset="pKahub",feature_group=feature,learner="LightGBM")
                originals=[self.raw(challenge,task=task) for challenge in ("SAMPL6","SAMPL7")]
                candidate=[native_primary_row(raw,catalog,spec) for raw in originals]
                frozen=[dict(row,record_id=row["evaluation_id"]) for row in candidate]
                extra=dict(frozen[0],record_id="SAMPL6:pKahub:extra",evaluation_id="SAMPL6:pKahub:extra")
                available,coverage=native_population(frozen+[extra],candidate)
                self.assertEqual(len(available),2)
                self.assertEqual(coverage["missing_native_TEST_rows"],1)
                self.assertFalse(coverage["missing_native_features_imputed"])
                for raw,bound in zip(originals,candidate):
                    for field,value in raw.items():self.assertEqual(bound[field],value)
                    self.assertEqual(bound["task"],task)
                    self.assertEqual(bound["record_id"],"pKahub:combined.tsv:7")
    def test_identity_binding_does_not_relax_foreign_TEST_label_or_molecule_guards(self):
        catalog=[dict(dataset="pKahub",target="macro_acid",endpoint_key="pkahub::macro_acid")]
        spec=dict(dataset="pKahub",feature_group="D",learner="LightGBM")
        row=native_primary_row(self.raw(),catalog,spec);reference=[dict(row)]
        for field,value in (("evaluation_id","SAMPL6:pKahub:foreign"),("y_true",99.),("full_inchikey","FOREIGN")):
            changed=dict(row,**{field:value})
            with self.assertRaises(IncompleteComparison):native_population(reference,[changed])
