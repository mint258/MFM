"""Three pure native-composition / locator / opaque-coordinate boundaries."""
import copy,io,unittest
from . import projection as P


class Boundaries(unittest.TestCase):
    def test_native_nonH_frozen_function_and_empty_keys_preserved(self):
        source={'physical_frame_ordinal':0,'native_author_ID':None,'atoms':5,'native_symbol_counts':{'H':2,'Cl':1,'C':2},
            'source_offset':0,'frame_bytes':100,'frame_sha256':'0'*64}
        row=P.project(source,{'synthetic':True});self.assertEqual(row['non_h_composition'],[[6,2],[17,1]])
        self.assertEqual(row['inchikeys'],[]);self.assertEqual(row['WP5_keys'],[]);self.assertTrue(row['missing_full_key'])
        self.assertFalse(row['missing_identity_or_composition']);self.assertTrue(row['unresolved_source_variant'])
    def test_no_unknown_hydrogen_only_zero_count_or_fake_nativeID(self):
        source={'physical_frame_ordinal':0,'native_author_ID':None,'atoms':1,'native_symbol_counts':{'H':1},
            'source_offset':0,'frame_bytes':1,'frame_sha256':'0'*64}
        for changed in (source,dict(source,native_symbol_counts={'X':1}),dict(source,native_symbol_counts={'C':0}),dict(source,native_author_ID='MAT-1')):
            with self.assertRaises(ValueError):P.project(changed,{'synthetic':True})
    def test_full_native_frame_boundaries_no_comment_or_float_decoding_and_no_dedup(self):
        raw=b'2\nProperties=species:S:1:pos:R:3 ccsd_pol=OPAQUE\nC 1e999 0 0\nH 0 0 -2D-99\n'
        stream=io.BytesIO(raw+raw);a=P.read_frame(stream,0,lambda:None);b=P.read_frame(stream,1,lambda:None)
        self.assertEqual(a['native_symbol_counts'],{'C':1,'H':1});self.assertEqual(a['frame_sha256'],b['frame_sha256'])
        self.assertEqual(b['source_offset'],len(raw));self.assertIsNone(P.read_frame(stream,2,lambda:None))
        ra=P.project(a,{'synthetic':True});rb=P.project(b,{'synthetic':True})
        self.assertEqual(ra['non_h_composition'],rb['non_h_composition']);self.assertNotEqual(ra['source_id'],rb['source_id'])
        with self.assertRaises(ValueError):P.read_frame(io.BytesIO(raw[:-1]),0,lambda:None)
