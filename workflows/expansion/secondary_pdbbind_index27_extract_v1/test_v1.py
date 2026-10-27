"""Exactly three synthetic methods; Root runs them on CPU, no original DATA IO."""
import copy,gzip,hashlib,io,json,tarfile,unittest
from . import contracts as C,projection as P
Q=C.Q


def relation(ordinal,raw,missing):
    return {'source_id':'pdbbind_general','original_index_ordinal':ordinal,'original_ID':P.token(raw[:4]),
        'original_details':{'official_rule':'NON_COMMENT_LINE_FIRST4_BYTES','line_bytes':len(raw),'line_sha256':hashlib.sha256(raw).hexdigest()},
        'matching_existing_native_entities':[] if missing else [['PDB_ID_ALL_COMPONENTS','native']],
        'no_native_context_in_all_components':missing,'graph_charge_stereo_if_no_native':'UNKNOWN','same_ID_implies_same_graph':False,
        'original_index_row_not_dropped':True,'full_or_pool_release':False,'relation_basis':'ORIGINAL_ORDINAL_OR_EXACT_LITERAL_PDB_ID_ONLY_NOT_GRAPH_EQUIVALENCE'}


class Boundaries(unittest.TestCase):
    def test_relation_projection_exact_mass_and_missing_axis(self):
        raw=[b'0001 target\n',b'AbC2 target\n',b'zzz3 target\n'];rows=[relation(i,r,i!=1) for i,r in enumerate(raw)]
        r=P.Relations({'pdbbind_general':3},{'pdbbind_general':2})
        for row in rows:r.feed(row,{'offset':row['original_index_ordinal']})
        selected=r.finish();self.assertEqual(set(selected),{0,2})
        p=P.Projection(selected,{'pdbbind_general':3})
        for row in rows:p.feed({'event':'ORIGINAL_INDEX_ID_DURABLE_BEFORE_INDEX','source_id':row['source_id'],'ordinal':row['original_index_ordinal'],'ID':row['original_ID'],'details':row['original_details']},{'offset':0})
        self.assertEqual(len(p.finish()),2);self.assertEqual(p.bound[0]['projection']['ID']['text'],'0001')
        with self.assertRaises(ValueError):r.feed(rows[0],{})
        with self.assertRaises(ValueError):P.Relations({'pdbbind_general':3},{'pdbbind_general':2}).finish()
        altered=copy.deepcopy(rows[0]);altered['matching_existing_native_entities']=[['x']]
        with self.assertRaises(ValueError):P.Relations({'pdbbind_general':3},{'pdbbind_general':2}).feed(altered,{})
        altered=copy.deepcopy(rows[0]);altered['original_ID']=P.token(b'000X')
        with self.assertRaises(ValueError):P.Projection(selected,{'pdbbind_general':3}).feed({'event':'ORIGINAL_INDEX_ID_DURABLE_BEFORE_INDEX','source_id':'pdbbind_general','ordinal':0,'ID':altered['original_ID'],'details':rows[0]['original_details']},{})

    def test_opaque_first4_original_noncomment_ordinal_no_label_decode(self):
        raw=b'000A affinity=\xff\r\n';row=relation(0,raw,True);bound={0:{'projection':{'ID':row['original_ID'],'details':row['original_details']}}};emitted=[];comments=[]
        lines=P.IndexLines(bound,2,lambda *x:emitted.append(x),lambda *x:comments.append(x))
        lines.feed(b'# literal header\r\n');lines.feed(raw);lines.feed(b'\n');v=lines.finish()
        self.assertEqual(v['noncomment_rows'],2);self.assertEqual(emitted[0][0],raw);self.assertEqual(emitted[0][1],0);self.assertEqual(len(comments),1)
        self.assertEqual(row['original_ID']['text'],'000A');self.assertEqual(P.token(b'abc\xff')['state'],'INVALID_UTF8_UNKNOWN')
        for bad in (raw[:-1],raw.replace(b'000A',b'000a'),b'  '+raw):
            with self.assertRaises(ValueError):P.IndexLines(bound,1,lambda *x:None,lambda *x:None).feed(bad)
        with self.assertRaises(ValueError):P.IndexLines(bound,1,lambda *x:None,lambda *x:None).finish()

    def test_large_data_locator_and_complete_tar_gzip_inventory(self):
        ref={'path':str(C.ROOT/'artifacts/synthetic_only/not_opened.bin'),'bytes':1759178739,'sha256':'a'*64}
        self.assertEqual(C.data_locator(ref),ref)
        with self.assertRaises(ValueError):Q.normalized(ref)
        for change in ({'bytes':True},{'bytes':-1},{'bytes':2.0},{'sha256':'a'*65},{'path':str(C.ROOT/'code/not_DATA.bin')},{'extra':1}):
            bad={**ref,**change}
            with self.assertRaises(ValueError):C.data_locator(bad)
        raw=b'# evidence\n0001 value\n';r=relation(0,b'0001 value\n',True);bound={0:{'projection':{'ID':r['original_ID'],'details':r['original_details']}}}
        output=io.BytesIO()
        with tarfile.open(fileobj=output,mode='w',format=tarfile.USTAR_FORMAT) as t:
            info=tarfile.TarInfo('index');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
        decoded=output.getvalue();compressed=gzip.compress(decoded)
        old={'ordinal':0,'name':'index','type_hex':'30','declared_bytes':len(raw),'regular_member_bytes_read':len(raw),'regular_member_sha256':hashlib.sha256(raw).hexdigest(),
            'linkname':None,'extracted':False,'identity_or_target_rows_decoded':False}
        expected={'members':1,'regular_bytes':len(raw),'decoded_bytes':len(decoded),'decoded_sha256':hashlib.sha256(decoded).hexdigest()}
        def run(data,inventory):return P.scan_tar(io.BytesIO(data),iter(inventory),expected,'index',P.IndexLines(bound,1,lambda *x:None,lambda *x:None),lambda:None,{})
        self.assertTrue(run(compressed,[old])['gzip_EOF_CRC_verified'])
        bad={**old,'regular_member_sha256':'f'*64}
        with self.assertRaises(ValueError):run(compressed,[bad])
        with self.assertRaises((EOFError,OSError,ValueError,tarfile.ReadError)):run(compressed[:-5],[old])
