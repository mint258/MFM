"""Explicit-H alignment, graph identity and inverse atomic-label mapping."""
import unittest
from unittest import mock
import numpy as np
from rdkit import Chem
from . import d3_source_alignment as module

class D3SourceAlignmentTests(unittest.TestCase):
    def source(self, smiles):
        p=Chem.SmilesParserParams();p.removeHs=False
        return Chem.AddHs(Chem.MolFromSmiles(smiles,p))

    def test_explicit_hydrogens_retain_source_identity_after_legacy_call(self):
        smiles="[H]OC([H])([H])C([H])([H])[H]"
        source=self.source(smiles);n=source.GetNumAtoms()
        xyz=np.arange(n*3,dtype=np.float64).reshape(n,3)
        z=[a.GetAtomicNum() for a in source.GetAtoms()]
        d20={"original_existing_values":"not recomputed"}
        expected,mapping=module.atom_permutation(smiles,source)
        self.assertNotEqual(tuple(range(n)),mapping)
        def legacy(s,mol,actual_z,coords,original_d20):
            self.assertIs(original_d20,d20)
            self.assertEqual(actual_z.tolist(),[a.GetAtomicNum() for a in expected.GetAtoms()])
            np.testing.assert_array_equal(coords,xyz[list(mapping)])
            return {"SASA_atom_A2":list(range(n)),"PMI1":123.0},[]
        with mock.patch.object(module,"legacy_geometry_descriptors",side_effect=legacy) as called:
            result,issues,actual_mapping=module.aligned_descriptors(smiles,source,z,xyz,d20)
        self.assertEqual(called.call_count,1)
        for legacy_id,source_id in enumerate(mapping):
            self.assertEqual(result["SASA_atom_A2"][source_id],legacy_id)
        self.assertEqual(actual_mapping,list(mapping));self.assertEqual(issues,[])

    def test_heavy_graph_connectivity_is_required_not_just_same_elements(self):
        with self.assertRaises(ValueError):
            module.atom_permutation("CCO",self.source("COC"))

    def test_isotopic_hydrogen_identity_and_stereo_are_preserved(self):
        smiles="[2H]OC(C)N"
        source=self.source(smiles);legacy,mapping=module.atom_permutation(smiles,source)
        for new,old in enumerate(mapping):
            self.assertEqual(legacy.GetAtomWithIdx(new).GetIsotope(),
                             source.GetAtomWithIdx(old).GetIsotope())
        with self.assertRaises(ValueError):
            module.atom_permutation("C[C@@H](O)N",self.source("C[C@H](O)N"))

    def test_successes_and_unrelated_property_failures_are_not_retried(self):
        failure="D3_SOURCE_MAPPING_OR_PROPERTY_FAILED:ValueError('"+module.ALIGNMENT_ERRORS[0]+"')"
        self.assertTrue(module.targeted_failure({"D3":None,"D3_issues":[failure]}))
        self.assertFalse(module.targeted_failure({"D3":{"PMI1":1.0},"D3_issues":[failure]}))
        self.assertFalse(module.targeted_failure({"D3":None,"D3_issues":["SASA:bad geometry"]}))
        self.assertFalse(module.targeted_failure({"D3":None,"D3_issues":[
            "D3_SOURCE_MAPPING_OR_PROPERTY_FAILED:ImportError('missing dependency')"]}))

class D3RepairJournalTests(unittest.TestCase):
    def test_only_failed_alignment_is_completed_once_and_geometry_is_unchanged(self):
        import json,sqlite3,zlib
        from . import d3_alignment_repair as repair
        db=sqlite3.connect(":memory:")
        db.execute("CREATE TABLE tasks(mid TEXT PRIMARY KEY,result BLOB,state TEXT)")
        smiles="[H]OC([H])([H])C([H])([H])[H]"
        p=Chem.SmilesParserParams();p.removeHs=False
        mol=Chem.AddHs(Chem.MolFromSmiles(smiles,p));n=mol.GetNumAtoms()
        xyz=np.arange(n*3,dtype=np.float64).reshape(n,3).tolist()
        failure="D3_SOURCE_MAPPING_OR_PROPERTY_FAILED:ValueError('"+module.ALIGNMENT_ERRORS[0]+"')"
        value=dict(model_smiles=smiles,atomic_numbers=[a.GetAtomicNum() for a in mol.GetAtoms()],
                   D20={"valid_mask":[True],"values":[9.0]},state="SPRIME_READY_D_PARTIAL",
                   conformers=[dict(conformer_id=0,coordinates_A=xyz,D3=None,D3_issues=[failure]),
                               dict(conformer_id=1,coordinates_A=xyz,D3={"kept":7.0},D3_issues=[])])
        db.execute("INSERT INTO tasks VALUES(?,?,?)",("fixture",repair.packed(value),value["state"]));db.commit()
        with mock.patch.object(repair,"aligned_descriptors",
                return_value=({"SASA_atom_A2":[1.0]*n},[],list(range(n)))) as call:
            first=repair.repair_rows(db,"SYNTHETIC",lambda:None)
            repair.repair_rows(db,"SYNTHETIC2",lambda:None)
        self.assertEqual(first,{"D3_REPAIRED":1});self.assertEqual(call.call_count,1)
        state,payload=db.execute("SELECT state,result FROM tasks").fetchone()
        result=json.loads(zlib.decompress(payload))
        self.assertEqual(state,"SPRIME_AND_D_READY")
        self.assertEqual(result["D20"],value["D20"])
        self.assertEqual(result["conformers"][0]["coordinates_A"],xyz)
        self.assertEqual(result["conformers"][1],value["conformers"][1])
        self.assertEqual(result["conformers"][0]["D3_original_alignment_failure"]["D3_issues"],[failure])

    def test_interrupted_or_failed_property_attempts_are_never_repeated(self):
        import sqlite3
        from . import d3_alignment_repair as repair
        db=sqlite3.connect(":memory:")
        db.execute("CREATE TABLE tasks(mid TEXT PRIMARY KEY,result BLOB,state TEXT)")
        repair.repair_rows(db,"SYNTHETIC",lambda:None)
        db.execute("INSERT INTO d3_alignment_once VALUES('old',0,'INTENT','OLD',0,NULL)")
        db.commit()
        with mock.patch.object(repair,"aligned_descriptors") as call:
            result=repair.repair_rows(db,"SYNTHETIC2",lambda:None)
        self.assertEqual(result,{"UNKNOWN_INTERRUPTED_NO_RETRY":1})
        call.assert_not_called()
