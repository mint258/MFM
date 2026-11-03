"""Native source-only fixtures; Root executes these inside actual Alpha Slurm."""
import unittest
from . import evidence as F, bounds, kernel
from workflows.expansion.coconut_alpha_cached735_v1 import kernel as K


class Source(unittest.TestCase):
    def test_exact_product_HTML_fields_include_all_subscript_digits(self):
        p=F.ProductFields();p.feed('<span id="ContentSection_lbl_mFormula">C<sub>2</sub>H<sub>6</sub>O</span>'
            '<span id="ContentSection_lbl_SMILES">CCO</span>')
        self.assertEqual(p.complete(),dict(ContentSection_lbl_mFormula='C2H6O',ContentSection_lbl_SMILES='CCO'))

    def test_CSV_exact_ID_not_name_and_complete_multiline_record(self):
        raw=b'CyanoMetDB_Identifier,CompoundName,SMILES,Notes\nOTHER,same,CCO,no\nCyanoMetDB_0661,same,CCN,"line1\nline2"\n'
        result=F.csv_record(raw,'CyanoMetDB_0661')
        self.assertEqual(result['row']['SMILES'],'CCN')
        self.assertEqual(result['row']['Notes'],'line1\nline2')
        self.assertEqual(result['logical_data_record_1based'],2)

    def test_SDF_exact_property_retains_technical_grade_not_nearby_SKU(self):
        value=F.sdf_fields(b'header\nM  END\n>  <Catalog #>\n06-022\n\n>  <PURITY>\n\'20%\n\n')
        self.assertEqual(value['Catalog #'],'06-022');self.assertNotEqual(value['Catalog #'],'06-022N')
        self.assertEqual(value['PURITY'],"'20%")

    def test_unchanged_original_formula_object_observation_not_graph(self):
        value=K.STATE['original'].formula('C2H6O')
        self.assertEqual(value['composition'],[[6,2],[8,1]])
        self.assertEqual(value['state'],'SOURCE_FORMULA_NON_H_COUNTS_NOT_GRAPH_IDENTITY')
        self.assertIsNone(K.STATE['original'].formula('HX')['composition'])

    def test_antichain_OR_union_domain_disjoint_counts_not_dropped(self):
        def row(i,vector):return dict(source=dict(copy_block=1,source_row_ordinal=i,source_row_sha256='0'*64),
            original_id=str(i),original_UNKNOWN_unchanged=True,strict5_written=False,
            variants=[dict(variant_id='fixture',unsanitized_atom_observation=dict(
                positive_known_non_H_atom_lower_bound_observation=vector))])
        value=bounds.summarize([row(1,[[6,1]]),row(2,[[6,2],[8,1]]),row(3,[[8,1]]),row(4,[[6,1],[26,1]])])
        self.assertEqual([x['vector'] for x in value['global_union_minimal_antichain']],[((6,1),),((8,1),)])
        self.assertEqual(value['out_of_X_vectors'],1)
        self.assertEqual(value['production_candidates_read'],0);self.assertFalse(value['bounds_accepted'])

    def test_original_native_key_objects_and_explicit_MOL_seam(self):
        smiles='CCO';Chem=K.STATE['Chem'];mol=Chem.MolToMolBlock(Chem.MolFromSmiles(smiles))
        expected,errors=K.STATE['functions']['source_smiles_keys']({'whole':smiles})
        actual=K.keys(mol,'MOL')
        self.assertEqual(actual['keys'],expected);self.assertFalse(errors)
        self.assertFalse(actual['original_normalize_recipe'])
