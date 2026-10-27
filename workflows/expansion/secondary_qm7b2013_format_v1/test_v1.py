"""Exactly three synthetic boundaries; original DATA and native/graph APIs absent."""
import copy,hashlib,io,json,struct,unittest,zipfile
from . import contracts as C,formats as F
Q=C.Q


def ref(name):return {'path':str(C.ROOT/'control'/('SYNTHETIC_FORMAT_'+name)), 'bytes':1,'sha256':'0'*64}


def closed_fixture():
    p={k:None for k in C.AQ.REVIEW_FIELDS};p.update(schema=C.AQ.PLAN,scope_key=C.AQ.KEY,
        scope_parameters=C.AQ.PARAMETERS,source_references=[],root_review_reference=ref('review'))
    review={k:p[k] for k in C.AQ.REVIEW_FIELDS};review.update(status='APPROVED_FOR_EXACT_STAGE',reviewer='root',approved_source_references=[])
    r={'schema':'SECONDARY_QM7B_OFFICIAL2013_ARCHIVE_RECEIPT_V1',
        'status':'OFFICIAL_ARCHIVE_SHA_ALL_MEMBER_EOF_CRC_INVENTORY_COMPLETE_GRAPH_AND_ROW_MAPPING_UNKNOWN',
        'job_id':'1884892','uid':1264,'endpoint':Q.ENDPOINT,'node':'sonmi1','scope_parameters':C.AQ.PARAMETERS,
        'all_member_observation':{'physical_members':4,'total_uncompressed_bytes':C.EXPANDED,'directory_flags':0,
            'duplicate_literal_filenames_preserved':0,'every_member_EOF_CRC_SHA_verified':True,
            'original_compressed_and_uncompressed_bytes_preserved':True},
        'graph_SMILES_MAT_mapping_accepted':False,'global_pool_decontamination_release':False,
        'new_graph_parse_key_UFF_QM_calls':0,'fixtures':{'tests_run':3,'failures':0,'errors':0,'skips':0,'expected_failures':0,'unexpected_successes':0},
        'plan_reference':ref('plan'),'startup_proof_reference':ref('proof'),
        'original_archive_reference':{'path':str(C.ZIP_PATH),'bytes':C.ZIP_BYTES,'sha256':C.ZIP_SHA},
        'all_uncompressed_original_bytes_reference':{'path':str(C.ROOT/'artifacts/SYNTHETIC_FORMAT.raw'),'bytes':C.EXPANDED,'sha256':'0'*64}}
    a={'actual_parent':{'JobIDRaw':'1884892','State':'COMPLETED','ExitCode':'0:0','UID':'1264','AllocCPUS':'16','Partition':'cpu','NodeList':'sonmi1'},
        'query_returncode':0,'uid':1264,'endpoint':Q.ENDPOINT,'queue_request_reference':ref('request')}
    s={'schema':C.AQ.PROOF,'job_id':'1884892','endpoint':Q.ENDPOINT,'uid':1264,'node':'sonmi1',
        'plan_reference':r['plan_reference'],'root_review_reference':p['root_review_reference'],
        'controller_evidence':{'queue_request_reference':a['queue_request_reference']}}
    request={'adapter':{'producer_plan_reference':r['plan_reference'],'startup_proof_path':r['startup_proof_reference']['path']},'scope_key':C.AQ.KEY}
    submission={'job_id':'1884892','sbatch_returncode':0,'queue_request_reference':a['queue_request_reference']}
    return [r,a,p,s,review,request,submission]


class Boundaries(unittest.TestCase):
    def test_actual_C0_parent_shape_and_large_locator_never_small_source(self):
        values=closed_fixture();self.assertEqual(C.validate_closed(*values)[0]['bytes'],2671083)
        for field,value in (('State','TIMEOUT'),('ExitCode','1:0'),('UID','1278')):
            bad=copy.deepcopy(values);bad[1]['actual_parent'][field]=value
            with self.assertRaises(ValueError):C.validate_closed(*bad)
        bad=copy.deepcopy(values);bad[3]['job_id']='1884893'
        with self.assertRaises(ValueError):C.validate_closed(*bad)
        locator={'path':str(C.ROOT/'artifacts/SYNTHETIC_FORMAT.zip'),'bytes':3<<20,'sha256':'a'*64}
        self.assertEqual(C.data_locator(locator)['bytes'],3<<20)
        for field,value in (('bytes',True),('bytes',0),('sha256','a'*65)):
            bad=dict(locator);bad[field]=value
            with self.assertRaises(ValueError):C.data_locator(bad)

    def test_original_inventory_all_members_EOF_CRC_and_no_alias_sink(self):
        files=[('README.txt',b'opaque source documentation\n'),('tiny.xyz',b'2\nopaque-id CCO\nC 1.234567 0 0\nH 0 0 0\n'),('unknown.bin',b'\xff\x01')]
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
            for name,raw in files:z.writestr(name,raw)
        total=sum(len(raw) for _,raw in files);sink=F.MemberSink(total);found=[]
        def emit(value):
            raw=sink.take();self.assertEqual(hashlib.sha256(raw).hexdigest(),value['whole_member_SHA256']);found.append(value)
        result=F.inventory(io.BytesIO(archive.getvalue()),sink,emit,lambda n=0:None,total,3)
        self.assertEqual(result['physical_members'],3);self.assertEqual(result['total_uncompressed_bytes'],total)
        self.assertTrue(result['every_member_EOF_CRC_SHA_verified']);self.assertEqual(len(found),3)
        self.assertEqual(sink.concat.hexdigest(),hashlib.sha256(b''.join(raw for _,raw in files)).hexdigest())
        corrupt=bytearray(archive.getvalue());corrupt[30+len(files[0][0])]^=1
        with self.assertRaises((zipfile.BadZipFile,ValueError)):
            F.inventory(io.BytesIO(corrupt),F.MemberSink(total),lambda value:None,lambda n=0:None,total,3)

    def test_passive_MAT_XYZ_opaque_lines_and_original_scope_source_bindings(self):
        synthetic_mat=struct.pack('<5i',0,1,1,0,2)+b'X\0'+b'\0'*8
        mat=F.mat_metadata(synthetic_mat)
        self.assertEqual(mat['fields'],[{'field_name':'X','shape':[1,1],'MATLAB_class':'double'}])
        self.assertFalse(mat['array_values_loaded']);self.assertEqual(mat['MAT_row_mapping'],'UNKNOWN')
        xyz=b'2\nopaque-id CCO\nC 1.234567 0 0\nH 0 0 0\n';lines=[]
        result=F.inspect_member('tiny.xyz',xyz,lines.append)
        self.assertEqual(result['records'],1);self.assertEqual(result['atomic_rows'],2)
        self.assertFalse(result['coordinate_floats_parsed']);self.assertEqual(sum(v['bytes'] for v in lines),len(xyz))
        text=json.dumps(result);self.assertNotIn('opaque-id',text);self.assertNotIn('CCO',text);self.assertNotIn('1.234567',text)
        bad=F.inspect_member('tiny.xyz',xyz.replace(b'1.234567',b'NaN'),lambda value:None)
        self.assertIn('UNKNOWN',bad['format']);self.assertEqual(bad['MAT_row_mapping'],'UNKNOWN')
        from secondary_qm7b_official2013_acquisition_v1.archive import inventory
        self.assertIs(F.inventory,inventory)
        proof=C.guard_derivation();self.assertTrue(proof['body_guard_bytes_unchanged_except_declared_scope_literals'])
        old=Q.ref(C.ROOT/'code/secondary_cpu_readonly_queue_v13/controller.py')
        new=Q.ref(C.ROOT/'code/secondary_cpu_readonly_qm7b2013_format_v1/controller.py')
        self.assertEqual((old['bytes'],old['sha256']),(new['bytes'],new['sha256']))


if __name__=='__main__':unittest.main()
