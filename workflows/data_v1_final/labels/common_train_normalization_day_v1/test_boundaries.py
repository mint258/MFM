"""Three synthetic Main CPU boundaries; no production DATA or native engine."""
import copy,hashlib,json,struct,tempfile,unittest
from pathlib import Path
from . import contract as C,io as I,authority as A,bindings as B,audit as U
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K

class Boundaries(unittest.TestCase):
    def setUp(self):self.saved=(I.ALLOWED,I.ORIGINS,I.ROOT,I.CAP)
    def tearDown(self):I.ALLOWED,I.ORIGINS,I.ROOT,I.CAP=self.saved

    def test_real_authority_predicate_source_identity_and_child_antijoin(self):
        keys=[('opaqueM','pm7','nativeOpaque'),('opaqueM','uff_sprime','0')]
        parent=keys[0];child=('opaqueM','pm7','actualChildOpaque')
        self.assertEqual(A.eligible('TRAIN',True,child,parent,{parent}),(False,'HELDOUT_GEOMETRY_OR_ITS_PERTURBED_VIEW'))
        self.assertTrue(A.eligible('TRAIN',True,keys[1],None,{parent})[0])
        for role in ('VAL','FULL','EMBARGO'):self.assertFalse(A.eligible(role,True,keys[1],None,set())[0])
        self.assertFalse(A.eligible('TRAIN',False,keys[1],None,set())[0])
        with self.assertRaises(ValueError):A.physical_key({'molecule_id':'opaqueM','geometry_source':'uff_sprime','sprime_conf_idx':False})
        with self.assertRaises(ValueError):A.physical_key({'molecule_id':'opaqueM','geometry_source':'pm7','native_record_id':'opaque','sprime_conf_idx':0})
        geom=[];diag=[]
        for m in ('m1','m2'):
            for source in ('pm7','uff_sprime'):
                row={'molecule_id':m,'geometry_source':source,'geometry_id':m+'@'+source,'parent_geometry_id':None}
                geom.append(row);diag.append(row)
        self.assertEqual(len(A.check_diagnostic_rows(diag,geom,{'m1':True,'m2':True},{'m1':'TRAIN','m2':'TRAIN'},expected=2)),4)
        with self.assertRaises(ValueError):A.check_diagnostic_rows(diag[:-1],geom,{'m1':True,'m2':True},{'m1':'TRAIN','m2':'TRAIN'},expected=2)

    def test_original_typed_IO_None_negative_zero_mask_and_large_DATA_guard(self):
        e={'field_id':0,'field_key':'synthetic','source_path':'synthetic','values_float64':[-0.0,None],
          'atom_indices':[0,1],'source_value_mask':[True,False],'value_mask':[True,False],
          'source_reasons':[],'new_reasons':[],'review_reasons':[]}
        owner={'record_ordinal':0,'record_id':'opaque','new_role':'TRAIN'};task=next(iter(B.TASKS.values()))
        row={'row_kind':'task','record_ordinal':0,'task_code':task,'record_id':'opaque','role_code':B.ROLES['TRAIN'],
          'file_id':1,'physical_row':0,'row_group':0,'row_within_group':0,'owner_sha256':K.owner_signature(owner),**K.pack_entries([e]),
          'compact_mask_json':K.binary_json_dumps(B.compact.encode(0,task,[e])),'base_json':'','base_f64':b''}
        row['view_sha256']=K.row_signature(row)
        with tempfile.TemporaryDirectory(prefix='dv1_common_train_source3_') as name:
            root=Path(name);part=K.TypedPart('task',task,4<<20,1<<20);part.add(row);ref=part.finish(root/'part.parquet')['reference']
            I.configure({'source_references':[],'data_references':[ref],'cache_transitive_output_origins':[],
              'output_directory':str(root/'output'),'whole_output_cap_bytes':128<<20})
            p=I.require(ref);import pyarrow.parquet as pq
            h=pq.ParquetFile(p)
            try:got=h.read().to_pylist()[0]
            finally:h.close()
            e2=K.unpack_entries(got,{0:{'field_id':0,'field_key':'synthetic','source_path':'synthetic'}})
            self.assertEqual(U.exact_cache_parity([e],e2),U.exact_cache_parity(e2,[e]))
            changed=copy.deepcopy(e2);changed[0]['values_float64'][0]=0.0
            with self.assertRaises(ValueError):U.exact_cache_parity([e],changed)
            changed=copy.deepcopy(e2);changed[0]['atom_indices'][1]=0
            with self.assertRaises(ValueError):U.exact_cache_parity([e],changed)
            big=root/'large.data';big.write_bytes(b'x'*(3<<20));br=I.pin(big);I.ALLOWED[br['path']]=br
            self.assertEqual(I.require(br),big)
            with self.assertRaises(ValueError):C.reference(dict(br,bytes=True))
            with self.assertRaises(ValueError):I.require(dict(br,sha256='0'*64))

    def test_original_256_TSQR_logical_fold_and_one_percent_stop_boundary(self):
        a=B.TSQR([1,6]);b=B.TSQR([1,6]);rows=[([1]*(i%5+1)+[6]*(i%3+1),float(i%17-8)) for i in range(513)]
        for numbers,value in rows:a.add(numbers,value)
        for lo,hi in ((0,17),(17,256),(256,300),(300,513)):
            for numbers,value in rows[lo:hi]:b.add(numbers,value)
        self.assertEqual(a.state(),b.state());self.assertEqual(B.merge_qr([a.state()]),B.merge_qr([b.state()]))
        self.assertEqual(B.verify()['TSQR_chunk'],256)
        groups=[{'group_index':i,'source_job_id':'opaque'+str(i)} for i in range(171)];C.logical(groups)
        with self.assertRaises(ValueError):C.logical(groups[::-1])
        with self.assertRaises(ValueError):C.logical(groups+[{'group_index':171,'source_job_id':'opaque0'}])
        self.assertEqual(B.quality_stop_fields({'0':{'newly_masked_records':1}},100,.01),[])
        self.assertEqual(B.quality_stop_fields({'0':{'newly_masked_records':2}},100,.01),['0'])
        self.assertEqual(U.quality_fields({'0':{'newly_masked_records':0,'final_valid_records':99}},100),[])
        self.assertEqual(U.quality_fields({'0':{'newly_masked_records':0,'final_valid_records':98}},100),['0'])
        self.assertEqual(U.quality_fields({'0':{'newly_masked_records':0,'final_valid_records':100,'masked_records_any_leaf':2}},100),['0'])
        self.assertEqual(U.quality_fields({'0':{'records':100,'newly_masked_records':0,'final_valid_records':0}},active_field_ids=[1]),[])
        item={'field_id':0,'values_float64':[2.0],'value_mask':[True],'review_reasons':[]}
        self.assertEqual(B.reference_review(item,{'0':{'median':1.0,'MAD':0.0}}),1.0)
        self.assertIn('ZERO_MAD_UNEQUAL_VALUE_REVIEW_ONLY',item['review_reasons'])

if __name__=='__main__':unittest.main()
