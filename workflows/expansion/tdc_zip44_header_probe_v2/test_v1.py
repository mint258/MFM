"""Three synthetic boundaries; Root CPU execution is required before actual ZIP."""
import io,unittest,zipfile
from .projection import HeaderOnly,method_proof,checked_inventory,F


class Boundaries(unittest.TestCase):
    def test_original_grammar_CRLF_quoted_newline_and_opaque_assays(self):
        method_proof();p=HeaderOnly('real_endpoint/train_val.csv')
        raw=b'\xef\xbb\xbfUnassigned,Other\r\n"x\r\ny",\xff\r\n\r\nz\n'
        for i in range(0,len(raw),2):p.feed(raw[i:i+2])
        s=p.finish();self.assertEqual(s['literal_header'],['Unassigned','Other'])
        self.assertEqual(s['record_counts']['physical_data_records'],3)
        self.assertEqual(s['record_counts']['field_count_below_header'],2)
        self.assertEqual(s['selected_data_columns'],0);self.assertFalse(s['data_fields_text_decoded'])
    def test_duplicate_or_invalid_header_is_not_an_identity_mapping(self):
        p=HeaderOnly('endpoint/test.csv');p.feed(b'X,X\n1,2\n');s=p.finish()
        self.assertEqual(s['duplicate_literal_header_names'],{'X':2});self.assertEqual(p.selected,{})
        p=HeaderOnly('endpoint/test.csv')
        with self.assertRaises(UnicodeDecodeError):p.feed(b'\xff\n')
        p=HeaderOnly('endpoint/test.csv');p.feed(b'X\n"unfinished')
        with self.assertRaises(F.UnknownFormat):p.finish()
    def test_unsafe_duplicate_and_bad_CRC_never_become_complete_zip(self):
        info=zipfile.ZipInfo('../bad.csv');info.compress_type=0;info.CRC=0;info.compress_size=0;info.file_size=0
        expected={'name':info.filename,'directory':False,'CRC32':0,'compressed_bytes':0,'uncompressed_bytes':0}
        with self.assertRaises(F.UnknownFormat):checked_inventory([info]*68,[expected]*68)
        info=zipfile.ZipInfo('safe.csv');info.compress_type=0;info.CRC=0;info.compress_size=0;info.file_size=0;expected=dict(expected,name='safe.csv')
        with self.assertRaises(F.UnknownFormat):checked_inventory([info]*68,[expected]*68)
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w',compression=zipfile.ZIP_STORED) as z:z.writestr('a.csv',b'A\n1\n')
        broken=bytearray(b.getvalue());start=broken.index(b'A\n1\n');broken[start+2]^=1
        with zipfile.ZipFile(io.BytesIO(broken)) as z:
            with self.assertRaises(zipfile.BadZipFile):z.read('a.csv')
