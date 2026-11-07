"""Synthetic D7 tests: no source LMDB, no UFF, no QM, no original data scans."""
from __future__ import annotations
import copy
from pathlib import Path
import tempfile
import unittest

from profile_common import IO, SELECTION, decode_hof, read_hof_file, scalar_columns
from run_profile import geometry_orders, unique_representatives


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"conformer_id":i,"energy":e,"x":x} for i,e,x in ((0,2,0),(1,-3,1),(2,1,4))]
        self.distance = lambda left,right: abs(left["x"]-right["x"])

    def test_random_order_is_exact_frozen_pprime_seed_rule(self):
        expected = sorted(range(3),key=lambda key:SELECTION.stable_key(20261025,"m","uff_sprime",key))
        orders = geometry_orders(self.rows,self.distance,"m","uff_sprime")
        self.assertEqual(orders["fixed_random"],expected)
        self.assertEqual(orders,geometry_orders(list(reversed(self.rows)),self.distance,"m","uff_sprime"))

    def test_diversity_starts_at_canonical_minimum_energy(self):
        orders = geometry_orders(self.rows,self.distance,"m","pm7")
        self.assertEqual(orders["energy"],[1,2,0])
        self.assertEqual(orders["diversity"],[1,2,0])

    def test_missing_hof_does_not_delete_geometry_or_invent_energy_order(self):
        rows = copy.deepcopy(self.rows)
        rows[1]["energy"] = None
        orders = geometry_orders(rows,self.distance,"m","pm7")
        self.assertEqual(len(orders["fixed_random"]),3)
        self.assertIsNone(orders["energy"])
        self.assertIsNone(orders["diversity"])
        self.assertEqual(len(unique_representatives(rows,orders["fixed_random"],self.distance)),3)

    def test_half_angstrom_boundary_and_duplicate_count(self):
        rows=[{"conformer_id":i,"x":x} for i,x in enumerate((0,.499,.5))]
        self.assertEqual(unique_representatives(rows,[0,1,2],self.distance),[0,2])

    def test_duplicate_id_or_nonpermutation_rejected(self):
        with self.assertRaisesRegex(ValueError,"PERMUTATION"):
            unique_representatives(self.rows,[0,1,1],self.distance)


class HofTests(unittest.TestCase):
    def row(self):
        return {"calc_type":"pm7_B","status":"SUCCESS","values":[{"registry_id":60,"kind":1,"f64":-3.25}],
                "numeric_issues":[],"converged":True}

    def test_finite_canonical_hof_and_null_convergence_review(self):
        row=self.row()
        self.assertEqual(decode_hof(row)["value_kcal_mol"],-3.25)
        row["converged"]=None
        value=decode_hof(row)
        self.assertTrue(value["valid"])
        self.assertTrue(value["convergence_null_review"])

    def test_other_property_failure_does_not_mask_valid_hof(self):
        row=self.row();row["status"]="PROPERTY_FAILED";row["numeric_issues"]=[68]
        self.assertTrue(decode_hof(row)["valid"])

    def test_hof_specific_invalid_states_remain_explicit(self):
        for field,value,reason in (("converged",False,"SCF_NOT_CONVERGED"),
                                   ("numeric_issues",[60],"HOF_NUMERIC_ISSUE"),
                                   ("values",[],"HOF_CELL_ABSENT")):
            row=self.row();row[field]=value
            with self.subTest(reason=reason):
                self.assertEqual(decode_hof(row)["reason"],reason)
        row=self.row();row["values"][0]["f64"]=float("inf")
        self.assertEqual(decode_hof(row)["reason"],"HOF_NONFINITE")


class ArrowProjectionTests(unittest.TestCase):
    def setUp(self):
        import pyarrow as pa
        self.pa=pa
        self.temp=tempfile.TemporaryDirectory(prefix="d7_scalar_leaf_fixture_")
        self.path=Path(self.temp.name)/"fixture.parquet"
        cell=pa.struct([("registry_id",pa.int16()),("kind",pa.int8()),("f64",pa.float64()),
                        ("array_f64",pa.large_list(pa.float64())),("text",pa.large_string())])
        self.schema=pa.schema([("record_id",pa.string()),("molecule_id",pa.string()),("attempt_id",pa.int8()),
            ("job_id",pa.int64()),("task_id",pa.string()),("lane",pa.int16()),("total_atoms",pa.int32()),
            ("calc_type",pa.string()),("status",pa.string()),("numeric_issues",pa.list_(pa.int16())),
            ("converged",pa.bool_()),("values",pa.large_list(cell))])
        self.row={"record_id":"r","molecule_id":"m","attempt_id":1,"job_id":22,"task_id":"t","lane":2,"total_atoms":2,
            "calc_type":"pm7_B","status":"SUCCESS","numeric_issues":[],"converged":True,
            "values":[{"registry_id":60,"kind":1,"f64":-3.25,"array_f64":None,"text":None},
                      {"registry_id":68,"kind":5,"f64":None,"array_f64":[.1]*1000,"text":"not a scalar target"}]}
        self.owner={key:self.row[key] for key in ("record_id","molecule_id","attempt_id","job_id","task_id","lane","total_atoms")}

    def tearDown(self):
        self.temp.cleanup()

    def write(self,rows):
        import pyarrow.parquet as pq
        pq.write_table(self.pa.Table.from_pylist(rows,schema=self.schema),self.path)
        return {"path":str(self.path),"bytes":self.path.stat().st_size,"sha256":"fixture",
                "family":"pm7_neutral","source_job_id":22,"inherited_full_readback_verified":True}

    def test_projection_excludes_array_and_text_leafs(self):
        import pyarrow.parquet as pq
        self.write([self.row])
        pf=pq.ParquetFile(self.path)
        columns=scalar_columns(pf)
        batch=next(pf.iter_batches(columns=columns))
        keys=set(batch.to_pylist()[0]["values"][0])
        self.assertEqual(keys,{"registry_id","kind","f64"})
        self.assertFalse(any("array" in name or "text" in name for name in columns))

    def test_full_owner_tuple_filters_historical_row(self):
        historical=copy.deepcopy(self.row);historical["attempt_id"]=0
        ref=self.write([historical,self.row])
        result=read_hof_file({"ref":ref,"owners":{"r":self.owner}})
        self.assertEqual(result["hof"]["r"]["value_kcal_mol"],-3.25)

    def test_wrong_lane_is_not_silently_matched_by_record_id(self):
        ref=self.write([self.row])
        owner=dict(self.owner,lane=3)
        with self.assertRaisesRegex(ValueError,"LANE_ATOMS"):
            read_hof_file({"ref":ref,"owners":{"r":owner}})

    def test_duplicate_current_owner_row_is_rejected(self):
        ref=self.write([self.row,self.row])
        with self.assertRaisesRegex(ValueError,"DUPLICATE_CANONICAL"):
            read_hof_file({"ref":ref,"owners":{"r":self.owner}})


class RmsdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from rdkit import Chem
        cls.science=IO.load_science({"science_source_pins":[
            {"path":"/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/scripts/sprime_v6.py",
             "bytes":20644,"sha256":"d6f1d29a6de673a1faf186e095c4fef7534a81022a09a4840ec65e5d8fa424d3"},
            {"path":"/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/scripts/prepare.py",
             "bytes":6040,"sha256":"4b10dc5c0c2c1f3c42250ca1c8541c43661ada301484f92a6ce7bfce512f4a10"}]})
        cls.mol=Chem.RWMol()
        for _ in range(4):cls.mol.AddAtom(Chem.Atom(6))

    def test_proper_rotation_translation_invariant(self):
        import numpy as np
        xyz=np.asarray([[0,0,0],[1,0,0],[0,2,0],[0,0,3]],dtype=float)
        rotation=np.asarray([[0,-1,0],[1,0,0],[0,0,1]])
        self.assertLess(self.science.rmsd(self.mol,xyz,xyz@rotation+np.asarray([3,-4,5])),1e-12)

    def test_reflection_is_not_accepted_as_proper_rotation(self):
        import numpy as np
        xyz=np.asarray([[0,0,0],[1,0,0],[0,2,0],[0,0,3]],dtype=float)
        mirror=xyz.copy();mirror[:,0]*=-1
        self.assertGreater(self.science.rmsd(self.mol,xyz,mirror),.1)

    def test_atom_permutation_is_not_silently_optimized(self):
        import numpy as np
        xyz=np.asarray([[0,0,0],[1,0,0],[0,2,0],[0,0,3]],dtype=float)
        self.assertGreater(self.science.rmsd(self.mol,xyz,xyz[[1,0,2,3]]),.1)


if __name__=="__main__":
    unittest.main()
