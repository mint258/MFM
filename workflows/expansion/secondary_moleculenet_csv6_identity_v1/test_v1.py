"""Four finite seam/identity-evidence fixtures; unchanged B supplies three key fixtures."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from secondary_missing11_identity_format_probe_v1 import formats as original
from . import projection,journal
TEST_ROOT=None
class Budget:
    def check(self,extra=0,drain=False):pass

class CallbackBoundaries(unittest.TestCase):
    def test_CRLF_chunk_split_quoted_comma_newline_quote_and_binary_assay(self):
        raw=b'mol_id,smiles,assay\r\n"id,1","C\nC",\xff\r\n"id""2",CC,7\r\n'
        expected=original.CSVProjection('tox21');expected.feed(raw);summary=expected.finish()
        for width in (1,2,7,len(raw)):
            rows=[];parser=projection.CallbackCSV('tox21',rows.append)
            for start in range(0,len(raw),width):parser.feed(raw[start:start+width])
            actual=parser.finish();self.assertEqual(actual,summary);self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]['identity_fields']['0']['text'],'id,1');self.assertEqual(rows[0]['identity_fields']['1']['text'],'C\nC')
            self.assertEqual(rows[1]['identity_fields']['0']['text'],'id"2')
            cursor=parser.header_record['source_record_bytes']
            for row in rows:
                self.assertEqual(row['source_offset'],cursor);piece=raw[cursor:cursor+row['source_record_bytes']]
                self.assertEqual(hashlib.sha256(piece).hexdigest(),row['source_record_sha256']);cursor+=len(piece)
                self.assertEqual(set(row['identity_fields']),{'0','1'})
            self.assertEqual(cursor,len(raw));self.assertNotIn('assay',[v['literal_column_name'] for v in rows[0]['identity_fields'].values()])
    def test_blank_short_duplicate_zero_ID_invalid_UTF8_and_last_line_preserved(self):
        raw=b'mol_id,smiles,label\n0,C,1\n0,C,0\n\nonly_id\n4,\xff,2\n5,,3'
        rows=[];parser=projection.CallbackCSV('tox21',rows.append);parser.feed(raw);summary=parser.finish()
        self.assertEqual(len(rows),6);self.assertEqual([r['source_row_ordinal'] for r in rows],list(range(1,7)))
        self.assertEqual(rows[0]['identity_fields']['0']['text'],rows[1]['identity_fields']['0']['text']);self.assertEqual(rows[0]['identity_fields']['0']['text'],'0')
        self.assertEqual(rows[2]['identity_fields']['0']['state'],'EMPTY');self.assertEqual(rows[2]['identity_fields']['1']['state'],'MISSING')
        self.assertEqual(rows[4]['identity_fields']['1']['state'],'INVALID_UTF8');self.assertEqual(rows[4]['identity_fields']['1']['invalid_UTF8_original_bytes_base64'],'/w==')
        self.assertEqual(rows[-1]['identity_fields']['1']['state'],'EMPTY');self.assertEqual(summary['record_counts']['physical_data_records'],6)
        self.assertTrue(all(r['role']=='ALLSPLITS' for r in rows))
    def test_unknown_truncated_quotes_and_software_cap_never_drop_a_success_row(self):
        for raw in (b'smiles,label\n"CC',b'smiles,label\nC"C,1',b'smiles,label\n"CC"x,1'):
            rows=[];parser=projection.CallbackCSV('hiv',rows.append)
            with self.assertRaises(original.UnknownFormat):parser.feed(raw);parser.finish()
        rows=[];parser=projection.CallbackCSV('hiv',rows.append);parser.feed(b'smiles,label\r');parser.feed(b'\nCC,1\r');parser.finish()
        self.assertEqual(rows[0]['source_record_bytes'],5);self.assertEqual(rows[0]['source_record_sha256'],hashlib.sha256(b'CC,1\r').hexdigest())
        with self.assertRaises(original.UnknownFormat):
            parser=projection.CallbackCSV('hiv',lambda row:None);parser.feed(b'smiles\n'+b'C'*(original.IDENTITY_FIELD_CAP+1))
    def test_complete_identity_journal_is_durable_before_nullable_parquet(self):
        import pyarrow.parquet as pq
        rows=[];parser=projection.CallbackCSV('hiv',rows.append);parser.feed(b'smiles,label\n,\xff\n');parser.finish();row=rows[0]
        value={'observation':{'source':row,'physical_identity':'hiv:1','SMILES_derived_full_keys':[],'WP5_keys':[],
            'key_state':'EMPTY','missing_full_key':True,'identity_errors':[]},'worker_pid':None,'worker_wall_seconds':None,'worker_CPU_seconds':None}
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            writer=journal.Writer(Path(folder),Budget());writer.dispatch(row);writer.complete(value)
            events=[json.loads(line) for line in writer.path.read_text().splitlines()]
            self.assertEqual([r['event'] for r in events],['ROW_DURABLE_BEFORE_SUBMIT','RESULT_DURABLE_BEFORE_PARQUET_OR_AGGREGATION'])
            self.assertEqual(events[1]['value']['observation']['source'],row);writer.close()
            saved=pq.read_table(writer.parquet).to_pylist()[0];self.assertEqual(saved['source_row_ordinal'],1)
            self.assertEqual(saved['full_keys'],[]);self.assertIsNone(saved['worker_pid']);self.assertEqual(json.loads(saved['source_identity_json']),row)
