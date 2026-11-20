"""Tests cover only the new native P-prime feature/atom-map interface."""
import unittest
import numpy as np
from workflows.benchmark_evaluation.pprime_features import (
    NativePprimeLayout, first_actual_conformer, remap_to_original_atoms,
)
from workflows.data_v1_final.labels.common import MISSING

def lookup(detail, path):
    value = detail
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return MISSING
        value = value[key]
    return value

def column(key, path, level, component="value", rid=1):
    return dict(field_key=key,source_path=path,level=level,component=component,unit="native unit",registry_id=rid)

class NativePprimeTests(unittest.TestCase):
    def layout(self):
        return NativePprimeLayout({"columns":{
            "mol_labels":[column("P.pm7_B.r1.value","values.energy","molecule")],
            "atom_labels":[column("P.pm7_B.r2.value","values.net_charges_e","atom",rid=2)]}},lookup)
    def result(self):
        return {"Pprime_ready":True,"tasks":[dict(task="pm7_B",scope_status="SUCCESS",
                    values={"energy":4.25,"net_charges_e":[.2,None,-.2]})]}
    def test_unchanged_units_and_missing_native_atom(self):
        molecular,atomic,meta=self.layout().extract(self.result(),3)
        self.assertEqual(molecular.tolist(),[4.25])
        self.assertTrue(np.isnan(atomic[1,0]))
        self.assertAlmostEqual(atomic[2,0],-.2)
    def test_unavailable_quantum_record_is_not_filled_by_D(self):
        self.assertEqual(self.layout().extract({"Pprime_ready":False,"state":"FAILED"},3)[:2],(None,None))
    def test_native_failed_task_is_not_treated_as_a_numeric_value(self):
        result=self.result();result["tasks"][0]["scope_status"]="PROPERTY_FAILED"
        molecular,atomic,_=self.layout().extract(result,3)
        self.assertTrue(np.isnan(molecular).all() and np.isnan(atomic).all())
    def test_actual_conformer_id_is_not_assumed_to_be_zero(self):
        source={"result":{"conformers":[{"conformer_id":7,"converged":True,"geometry_source":"UFF_Sprime"},
                                         {"conformer_id":9,"converged":True,"geometry_source":"UFF_Sprime"}]}}
        self.assertEqual(first_actual_conformer(source),7)
    def test_no_accepted_geometry_remains_absent(self):
        self.assertIsNone(first_actual_conformer({"result":{"conformers":[]}}))
    def test_original_atom_map_scatter_preserves_missing_atoms(self):
        actual=remap_to_original_atoms(np.array([[1.],[2.],[3.]]),[2,None,0],4)
        self.assertEqual(actual[0,0],3.)
        self.assertEqual(actual[2,0],1.)
        self.assertTrue(np.isnan(actual[[1,3]]).all())
    def test_ambiguous_atom_mapping_is_not_silently_averaged(self):
        with self.assertRaises(ValueError):remap_to_original_atoms(np.array([[1.],[2.]]),[0,0],2)
    def test_native_fukui_component_order_uses_original_component_reader(self):
        schema={"columns":{"mol_labels":[column("P.pm7_B.r1.value","values.energy","molecule")],
             "atom_labels":[column("P.xtb_vfukui.r712.f_minus","values.fukui","atom","f_minus",712)]}}
        result={"Pprime_ready":True,"tasks":[dict(task="xtb_vfukui",scope_status="SUCCESS",
                  values={"fukui":[[1.,2.,3.],[4.,5.,6.]]})]}
        _,atomic,_=NativePprimeLayout(schema,lookup).extract(result,2)
        np.testing.assert_array_equal(atomic[:,0],[2.,5.])

if __name__=="__main__":
    unittest.main()
