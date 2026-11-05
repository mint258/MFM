"""Three pure byte/record distinction fixtures, preceding every retained payload."""
import unittest
from secondary_missing11_identity_format_probe_v1.formats import CSVProjection
from .analysis import ByteCensus
class NewlineBoundaries(unittest.TestCase):
    def census(self,raw,width):
        value=ByteCensus()
        for i in range(0,len(raw),width):value.feed(raw[i:i+width])
        return value.finish()
    def test_plain_CRLF_is_one_physical_terminator_across_every_chunk(self):
        raw=b'smiles,x\r\nC,1\r\nN,0\r\n'
        expected=self.census(raw,len(raw))
        for width in (1,2,3,7):self.assertEqual(self.census(raw,width),expected)
        self.assertEqual(expected['byte_patterns'],{'CR':3,'LF':3,'CRLF':3,'CRCRLF':0})
        self.assertEqual(expected['quote_agnostic_physical_line_counts']['physical_lines_including_header'],3)
        self.assertEqual(expected['quote_agnostic_physical_line_counts']['literal_empty_lines'],0)
        p=CSVProjection('hiv')
        for byte in raw:p.feed(bytes([byte]))
        self.assertEqual(p.finish()['record_counts']['physical_data_records'],2)
    def test_CRCRLF_has_an_actual_empty_physical_line_in_synthetic_bytes(self):
        raw=b'smiles,x\r\r\nC,1\r\r\n';out=self.census(raw,1)
        self.assertEqual(out['byte_patterns'],{'CR':4,'LF':2,'CRLF':2,'CRCRLF':2})
        self.assertEqual(out['bare_CR_not_immediately_followed_by_LF'],2)
        self.assertEqual(out['quote_agnostic_physical_line_counts']['physical_lines_including_header'],4)
        self.assertEqual(out['quote_agnostic_physical_line_counts']['literal_empty_lines'],2)
        p=CSVProjection('hiv');p.feed(raw);summary=p.finish()
        self.assertEqual(summary['record_counts']['physical_data_records'],3);self.assertEqual(summary['record_counts']['field_count_below_header'],2)
        self.assertFalse(out['physical_lines_or_CSV_records_claimed_as_effective_molecules'])
    def test_quoted_newlines_are_not_more_CSV_samples_and_EOF_adds_no_blank(self):
        raw=b'smiles,x\r\n"C\r\nC",1\r\n';out=self.census(raw,2);p=CSVProjection('hiv');p.feed(raw)
        self.assertEqual(out['quote_agnostic_physical_line_counts']['physical_lines_including_header'],3)
        self.assertEqual(p.finish()['record_counts']['physical_data_records'],1)
        last=self.census(b'smiles,x\nC,1',1)
        self.assertEqual(last['quote_agnostic_physical_line_counts']['physical_lines_including_header'],2)
        self.assertEqual(last['quote_agnostic_physical_line_counts']['literal_empty_lines'],0)
        self.assertEqual(last['quote_agnostic_physical_line_counts']['terminator:NO_FINAL_TERMINATOR'],1)
        value=ByteCensus();value.feed(b'A\n');value.finish()
        with self.assertRaises(ValueError):value.feed(b'B')
