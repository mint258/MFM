"""Eight synthetic input-boundary checks; no real source or chemistry package."""
import json,unittest
from .formats import CSVProjection,UnknownFormat,inventory_summary,sdf_metadata,mol2_metadata,mat_metadata

class InputFormatFixtures(unittest.TestCase):
    def test_CSV_RFC4180_projection_never_decodes_assay(self):
        p=CSVProjection('muv')
        raw=b'smiles,mol_id,assay\r\n"C,C","id\r\nA",\xff\r\n"C""N",0,1\r\n'
        for i in range(0,len(raw),3):p.feed(raw[i:i+3])
        out=p.finish();self.assertEqual(out['record_counts']['physical_data_records'],2)
        self.assertEqual(out['selected_column_observations']['1']['nonblank_fields'],2)
        self.assertFalse(out['assay_values_text_decoded']);self.assertNotIn('id\r\nA',json.dumps(out))

    def test_CSV_blank_zero_duplicate_and_short_records_survive(self):
        p=CSVProjection('tox21');p.feed(b'smiles,mol_id,smiles,assay\n,0,C,1\n\nN,id\n')
        out=p.finish();self.assertEqual(out['record_counts']['physical_data_records'],3)
        self.assertEqual(out['duplicate_literal_header_names'],{'smiles':2})
        self.assertEqual(out['smiles_schema_state'],'MISSING_OR_AMBIGUOUS_UNKNOWN')
        self.assertEqual(out['record_counts']['field_count_below_header'],2)

    def test_CSV_truncation_and_non_RFC_quote_are_unknown(self):
        p=CSVProjection('hiv');p.feed(b'smiles,assay\nC,0\n"N')
        with self.assertRaises(UnknownFormat):p.finish()
        self.assertEqual(p.summary()['record_counts']['physical_data_records'],1)
        self.assertFalse(p.summary()['CSV_EOF_complete'])
        with self.assertRaises(UnknownFormat):CSVProjection('hiv').feed(b'smiles\nC"N\n')

    def test_all_inventory_members_classified_with_duplicates_unknown_links(self):
        rows=[]
        for i,name in enumerate(('a/1abc_ligand.sdf','a/1abc_ligand.sdf','a/1abc_ligand.mol2','a/1abc_protein.pdb','odd.bin','link')):
            rows.append({'ordinal':i,'name':name,'type_hex':'32' if i==5 else '30','declared_bytes':7,
              'regular_member_sha256':None if i==5 else 'a'*64})
        out=inventory_summary('pdbbind_general',iter(rows))
        self.assertEqual(sum(out['category_counts'].values()),6);self.assertEqual(out['duplicate_name_extra_occurrences'],1)
        self.assertEqual(out['first_candidate_members_in_physical_order']['SDF']['ordinal'],0)
        self.assertEqual(out['category_counts']['other_or_unknown'],1)

    def test_SDF_V2000_counts_markers_and_property_names_only(self):
        raw=(b'SECRET_TITLE\nprogram 3D\n\n  2  1  0  0  0  0            999 V2000\n'
          b'    1.2345    2.0000    3.0000 C   0  0  0  0  0\n'
          b'    0.0000    0.0000    0.0000 O   0  0  0  0  0\n'
          b'  1  2  1  0\nM  CHG  1   1   1\nM  END\n>  <native_ID>\nSECRET_VALUE\n\n$$$$\n')
        out=sdf_metadata(raw);self.assertTrue(out['count_match']);self.assertEqual(out['native_property_names'],['native_ID'])
        self.assertTrue(out['native_marker_presence']['M_CHG']);self.assertNotIn('SECRET',json.dumps(out))

    def test_SDF_V3000_native_markers_without_graph_perception(self):
        raw=(b't\np\n\n  0  0  0     0  0            999 V3000\nM  V30 BEGIN CTAB\nM  V30 COUNTS 1 0 0 0 0\n'
          b'M  V30 BEGIN ATOM\nM  V30 1 C 0 0 0 0 CHG=1 MASS=13 CFG=1\nM  V30 END ATOM\nM  V30 BEGIN BOND\n'
          b'M  V30 END BOND\nM  V30 END CTAB\nM  END\n$$$$\n')
        out=sdf_metadata(raw);self.assertTrue(out['count_match']);self.assertTrue(out['native_marker_presence']['V3000_CFG'])
        self.assertFalse(out['native_graph_identity_accepted'])

    def test_MOL2_charge_stereo_stay_unknown_without_RDKit(self):
        raw=(b'@<TRIPOS>MOLECULE\nSECRET\n2 1 0 0 0\nSMALL\nUSER_CHARGES\n@<TRIPOS>ATOM\n'
          b'1 C 1 2 3 C.3 1 LIG -0.1\n2 O 2 3 4 O.2 1 LIG -0.2\n@<TRIPOS>BOND\n1 1 2 1\n'
          b'@<TRIPOS>UNITY_ATOM_ATTR\n1 1\ncharge 1\n')
        out=mol2_metadata(raw,True);self.assertTrue(out['count_match']);self.assertTrue(out['UNITY_ATOM_ATTR_marker_present'])
        self.assertEqual(out['native_formal_charge_assignment'],'UNKNOWN_NOT_INFERRED')
        self.assertFalse(out['RDKit_MOL2_parser_called']);self.assertNotIn('SECRET',json.dumps(out))
        with self.assertRaises(UnknownFormat):mol2_metadata(raw,False)

    def test_QM7b_metadata_is_not_QM7_graph_or_alignment(self):
        out=mat_metadata([('X',(7211,23,23),'double'),('T',(7211,14),'double'),('names',(1,14),'cell')])
        self.assertEqual(out['matrix_row_universe_from_actual_X_shape'],7211)
        self.assertEqual(out['direct_source_graph_identity'],'NO_DIRECT_SOURCE_GRAPH_IDENTITY')
        self.assertFalse(out['loadmat_called']);self.assertFalse(out['QM7_Z7165_adapter_called'])
        self.assertEqual(mat_metadata([('Z',(1,2),'double')])['direct_source_graph_identity'],'CANDIDATE_VARIABLE_NAMES_UNVERIFIED')
        self.assertEqual(mat_metadata([('mystery',(1,2),'cell')])['direct_source_graph_identity'],'UNKNOWN_ADDITIONAL_VARIABLE_SEMANTICS')
if __name__=='__main__':unittest.main()
