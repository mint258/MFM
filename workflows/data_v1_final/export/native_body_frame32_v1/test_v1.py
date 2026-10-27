"""Three new meaningful pure boundaries; original three are run separately."""
import hashlib,sqlite3,unittest
from . import contract as C,reader as D,observe as O


class Boundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        for path in (C.WP5,C.VECTOR):
            if str(path) not in sys.path:sys.path.insert(0,str(path))
        cls.original=O.originals('fixture')
        cls.archive=O.module('_native32_fixture_original_archive',C.A.ARCHIVE)

    def test_raw_caps_explicit_key_and_original_member_integrity_before_body_acceptance(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        db.execute('CREATE TABLE records(record_id,calc_type,execution_id,raw_frame)')
        db.execute('INSERT INTO records VALUES(?,?,?,?)',('r','pm7_B','e',b'DO_NOT_FETCH'))
        observed=[];db.set_trace_callback(observed.append)
        try:
            item={'record_id':'r','calc_type':'pm7_B','execution_id':'e'}
            row={'raw_bytes':C.RAW_CAP+1,'raw_frame_bytes':1,'raw_sha256':'0'*64}
            with self.assertRaisesRegex(ValueError,'CAP_BEFORE_BLOB'):D.raw(db,item,row,{},b'',None,None)
            self.assertEqual(observed,[])
            for value in (True,0,-1):
                with self.assertRaises(ValueError):C.triple({'path':'/original/data','bytes':value,'sha256':'0'*64})
            body,manifest=self.archive.bundle([{'name':'process.out','data':b'native output\n'}])
            class Identity:
                def decompress(self,data,dictionary,size):return data
            row={'raw_bytes':len(body),'raw_frame_bytes':len(body),'raw_sha256':hashlib.sha256(body).hexdigest()}
            decoded,files,m=D.decode_raw(body,row,b'',Identity(),self.archive.unbundle)
            self.assertEqual(decoded,body);self.assertEqual(m,manifest);self.assertEqual(files[0]['data'],b'native output\n')
            with self.assertRaisesRegex(ValueError,'RAW_BUNDLE_SHA'):D.decode_raw(body[:-1]+b'x',row,b'',Identity(),self.archive.unbundle)
        finally:db.close()

    def test_original_r73_dual_end_onsite_duplicates_and_r674_exact_six_header(self):
        parser,engine,native,legacy,read=self.original
        text='SIGMA-PI BOND-ORDER MATRIX\n S-SIGMA P-SIGMA\n S-SIGMA C 1 1.00\n P-SIGMA C 1 2.00 3.00\n P-SIGMA C 1 2.00 3.00\nTOTAL ENERGY PARTITIONING\n'
        evidence=O.sigma_evidence(text,1,parser,native,legacy)
        self.assertEqual(evidence['same_atom_entries'],5);self.assertEqual(evidence['duplicate_keys_preserved'],2)
        self.assertEqual([r['entry_ordinal'] for r in evidence['entries']],list(range(5)))
        self.assertEqual(evidence['entries'][1]['src_channel'],'P-SIGMA');self.assertEqual(evidence['entries'][1]['dst_channel'],'S-SIGMA')
        self.assertFalse(evidence['AO_ATOMINDEX_used_as_basis_map'])
        q='molecular quadrupole (traceless):\n xx xy yy xz yz zz\n full: 1.00 2.00 3.00 4.00 5.00 6.00\n'
        e=O.quadrupole_evidence(q,{'molecular_quadrupole_traceless_au':[1.,2.,3.,4.,5.,6.]},parser,read)
        self.assertEqual(e['component_order'],['xx','xy','yy','xz','yz','zz']);self.assertEqual(e['tensor_axes'],'UNKNOWN_NOT_ACCEPTED_FROM_GEOMETRY_MATCH_ALONE')
        for invalid in (q.replace('xx xy yy xz yz zz','xx yy zz'),q+'full: 1 2 3 4 5 6\n'):
            self.assertEqual(O.quadrupole_evidence(invalid,{},parser,read)['status'],'UNKNOWN')

    def test_original_renderer_filename_bundle_hash_atom_order_and_lossless_f64_evidence(self):
        parser,engine,_,_,_=self.original
        protocol={'seed':20261010,'perturb_sigma_A':0.1}
        task={'name':'xtb_singlepoint','family':'xtb'}
        files=engine.render_inputs(task,{'symbols':['C','H'],'coords':[[0.,0.,0.],[1.,0.,0.]]},{'record_id':'synthetic'},protocol)
        per=[{'name':n,'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(files.items())]
        body,_=self.archive.bundle([{'name':n,'data':b,'role':'input'} for n,b in sorted(files.items())])
        self.assertEqual(O.input_binding(files,per,hashlib.sha256(body).hexdigest(),self.archive.bundle),per)
        with self.assertRaisesRegex(ValueError,'BUNDLE_SHA'):O.input_binding(files,per,'0'*64,self.archive.bundle)
        with self.assertRaisesRegex(ValueError,'ATOM_ORDER'):O.input_coordinates(files['input.xyz'],'input.xyz',['H','C'],parser.f)
        self.assertEqual(O.input_coordinates(files['input.xyz'],'input.xyz',['C','H'],parser.f),[[0.,0.,0.],[1.,0.,0.]])
        data=D.scientific_bytes({'native_token':'-0.000D+00','value':-0.0,'nonfinite_original_parser_output':float('nan')})
        self.assertIn(b'0000000000000080',data)
