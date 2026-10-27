"""Two metadata-only boundaries, in addition to the original three tests."""
import unittest
from .resume import partition,data_cap


def source(i):
    return {'file_id':i,'path':'/unused/source_'+str(i),'bytes':100+i,'sha256':str(i)*64,
      'source_kind':'label' if i<2 else 'base','family':'D20' if i<2 else 'base_geometry','rows':10}


def layer_report(done,pending,job='old'):
    rows=[]
    for n,i in enumerate(done):
        s=source(i);rows.append({'file_id':i,'producer_reference':{k:s[k] for k in ('path','bytes','sha256')},
          'source_kind':s['source_kind'],'family':s['family'],'physical_rows':10,'gzip_member_byte_lo':n*4,'gzip_member_byte_hi':(n+1)*4})
    return {'schema':'WP5_FOOTER_SHARD_V1','actual_wholebody_SHA_computed':False,'source_values_or_data_pages_read':False,
      'completed':rows,'pending_file_ids':pending,'errors':[],'expected_files':len(done)+len(pending),
      'inventory':{'path':'/unused/metadata_'+job,'bytes':4*len(done),'sha256':'a'*64},'runtime':{'job_id':job}}


class ResumeBoundaries(unittest.TestCase):
    def test_pending_reassigned_but_completed_never_reopened_or_duplicated(self):
        book={'files':[source(i) for i in range(3)]}
        first={'report':{'path':'first'},'assigned_file_ids':[0,1,2]};second={'report':{'path':'second'},'assigned_file_ids':[1,2]}
        reports={'first':layer_report([0],[1,2]),'second':layer_report([1],[2],'new')}
        done,pending,streams,jobs=partition(book,[first,second],reports)
        self.assertEqual(set(done),{0,1});self.assertEqual(pending,[2]);self.assertEqual(len(streams),2)
        duplicate={'report':{'path':'duplicate'},'assigned_file_ids':[0]}
        with self.assertRaisesRegex(ValueError,'REASSIGNED_COMPLETED'):
            partition(book,[first,duplicate],dict(reports,duplicate=layer_report([0],[],'duplicate')))
        self.assertEqual(jobs,['new','old'])

    def test_cumulative_cap_charges_prior_streams_once_and_never_increases_parser_limits(self):
        stream={'path':'/unused/stream','bytes':450000000,'sha256':'b'*64}
        report={'path':'/unused/report','bytes':200000,'sha256':'c'*64}
        cap,charge=data_cap(8<<30,[stream,stream],[report,report],['old'])
        self.assertEqual(charge,450200000+(80<<20));self.assertEqual(cap+charge+(80<<20),8<<30)
        with self.assertRaisesRegex(ValueError,'NOT_A_FULL_GUARANTEE'):
            data_cap(8<<30,[dict(stream,bytes=8<<30)],[report],['old'])

if __name__=='__main__':unittest.main()
