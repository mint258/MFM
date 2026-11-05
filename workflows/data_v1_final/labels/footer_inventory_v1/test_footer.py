"""Three synthetic footer-only boundaries, never real scientific sources."""
import io,struct,unittest
from .footer import footer_only,parse_metadata,records,pack_records


class Tracking(io.BytesIO):
    def __init__(self,value):super().__init__(value);self.reads=[]
    def read(self,n=-1):
        start=self.tell();value=super().read(n);self.reads.append([start,start+len(value)]);return value


class FooterBoundaries(unittest.TestCase):
    def test_exact_envelope_never_reads_body(self):
        body=b'NEVER_READ_THIS_BODY';footer=b'only-metadata'
        raw=b'PAR1'+body+footer+struct.pack('<I',len(footer))+b'PAR1';stream=Tracking(raw)
        found=footer_only(stream,len(raw))
        self.assertEqual(stream.reads,[[0,4],[len(raw)-8,len(raw)],[4+len(body),len(raw)-8]])
        self.assertNotIn(body,found['metadata_file']);self.assertFalse(found['current_wholebody_SHA_verified'])
        self.assertEqual(found['metadata_file'],b'PAR1'+footer+struct.pack('<I',len(footer))+b'PAR1')

    def test_real_synthetic_arrow_metadata_ranges_and_chunks(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        pa.set_cpu_count(1);pa.set_io_thread_count(1)
        sink=pa.BufferOutputStream();pq.write_table(pa.table({'id':[1,2,3,4,5],'x':[.1,.2,.3,.4,.5]}),sink,row_group_size=2)
        raw=sink.getvalue().to_pybytes();stream=Tracking(raw);found=footer_only(stream,len(raw))
        meta=parse_metadata(found);items=list(records(meta,5));groups=[r for r in items if r['type']=='row_group']
        self.assertEqual([(r['physical_row_lo'],r['physical_row_hi']) for r in groups],[(0,2),(2,4),(4,5)])
        self.assertEqual(items[-1]['column_chunks'],6);self.assertEqual(items[-1]['physical_rows'],5)
        self.assertTrue(all(r[0]>=found['footer_start'] or r==[0,4] for r in stream.reads))
        self.assertEqual(len(stream.reads),3)
        with self.assertRaisesRegex(ValueError,'PHYSICAL_ROWS'):list(records(meta,6))

    def test_corrupt_length_wrong_rows_and_output_bounds_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'FOOTER_LENGTH'):
            footer_only(io.BytesIO(b'PAR1'+b'x'+struct.pack('<I',100)+b'PAR1'),13)
        with self.assertRaisesRegex(ValueError,'MAGIC'):
            footer_only(io.BytesIO(b'PAR1'+b'x'+struct.pack('<I',1)+b'PARE'),13)
        with self.assertRaisesRegex(ValueError,'BUFFER_CAP'):
            pack_records([{'type':'source','padding':'x'*200},{'type':'file_end'}],raw_cap=32)
        with self.assertRaisesRegex(ValueError,'COMPLETE_SOURCE'):
            pack_records([{'type':'row_group','rows':1}])

if __name__=='__main__':unittest.main()
