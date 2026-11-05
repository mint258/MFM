"""Six new control boundaries only; no repeat of frozen science fixture suites."""
import copy,tempfile,unittest
from pathlib import Path
from .control import DispatchBook,partition_sources,review_contract
from .directory import select_groups
from .coverage import CappedOutput,metadata_only,sidecar_row
from workflows.data_v1_final.labels.streaming_v1 import compact


def r(path='fixture'):return {'path':path,'bytes':1,'sha256':'0'*64}


class FullProjectionBoundaries(unittest.TestCase):
    def test_fixed_source_partition_independent_input_order(self):
        files=[{'file_id':i,'rows':i+1} for i in range(65)]
        first=partition_sources(files);self.assertEqual(first,partition_sources(list(reversed(files))))
        ids=[i for p in first for i in p['file_ids']];self.assertEqual(sorted(ids),list(range(65)))
        self.assertEqual(len(ids),len(set(ids)));self.assertEqual(len(first),16)
        from .run import initialize,worker
        from workflows.data_v1_final.labels.bounded_projection_v1 import run as frozen
        self.assertIs(initialize,frozen.initialize);self.assertIs(worker,frozen.worker)

    def test_actual_rg_partial_cursor_and_gaps(self):
        groups=[{'row_group':0,'physical_row_lo':0,'physical_row_hi':7},
          {'row_group':1,'physical_row_lo':7,'physical_row_hi':20},{'row_group':2,'physical_row_lo':20,'physical_row_hi':21}]
        selected,hi=select_groups(groups,5,21,2);self.assertEqual([g['row_group'] for g in selected],[0,1]);self.assertEqual(hi,20)
        selected,hi=select_groups(groups,20,21,2);self.assertEqual(len(selected),1);self.assertEqual(hi,21)
        bad=copy.deepcopy(groups);bad[1]['physical_row_lo']=8
        with self.assertRaisesRegex(ValueError,'GAP_OR_OVERLAP'):select_groups(bad,7,21,2)

    def test_intent_and_unknown_are_never_redispatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=DispatchBook(Path(tmp)/'state.sqlite',True,files=[{'file_id':3,'rows':10},{'file_id':4,'rows':10}],
              cap=1000,inodes=100,master_reference=r(),review_reference=r('review'))
            try:
                one=[{'file_id':3,'physical_row_lo':0,'physical_row_hi':10}];db.claim('once',one,100,10,r('cfg'))
                db.assert_claim('once',r('cfg'),one);db.running('once')
                with self.assertRaisesRegex(ValueError,'ONCE_ONLY'):db.running('once')
                with self.assertRaisesRegex(ValueError,'ACTUAL_ACCEPT'):db.claim('other',[{'file_id':4,'physical_row_lo':0,'physical_row_hi':10}],100,10,r('other'))
                self.assertEqual(db.pending({'file_ids':[3]}),[]);self.assertEqual(db.snapshot()['sources'][0]['lease'],'once')
            finally:db.close()

    def test_actual_accept_only_monotone_closed_cursor_and_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=DispatchBook(Path(tmp)/'state.sqlite',True,files=[{'file_id':0,'rows':10}],
              cap=100,inodes=10,master_reference=r(),review_reference=r('review'))
            try:
                one=[{'file_id':0,'physical_row_lo':0,'physical_row_hi':10}];db.claim('a',one,100,10,r('a'));db.running('a')
                with self.assertRaisesRegex(ValueError,'MONOTONE'):db.accept('a',r('a'),[{'file_id':0,'next_physical_row':11}],r('out'),20,2)
                db.accept('a',r('a'),[{'file_id':0,'next_physical_row':4}],r('out'),20,2)
                nexts=db.pending({'file_ids':[0]});self.assertEqual(nexts,[{'file_id':0,'physical_row_lo':4,'physical_row_hi':10}])
                with self.assertRaisesRegex(ValueError,'CUMULATIVE_CAP'):db.claim('over',nexts,81,2,r('b'))
                db.claim('b',nexts,80,8,r('b'));self.assertEqual(db.snapshot()['batches'][0]['charged_bytes'],20)
            finally:db.close()

    def test_full_review_needs_actual_storage_and_no_final_norm_authority(self):
        master={'schema':'FULL_LABEL_PROJECTION_MASTER_V1','executable':False,'bounded_evidence_references':[r('actual_C0')]}
        review={'schema':'FULL_LABEL_PROJECTION_ROOT_REVIEW_V1','status':'ROOT_APPROVED_FULL_SOURCE_CACHE','reviewer':'root','reason':'actual scope',
          'master_reference':r('master'),'bounded_evidence_references':master['bounded_evidence_references'],
          'bounded_C0_parity_and_cost_accepted':True,'Sprime_reservations_released_or_fully_accounted':True,
          'storage_review_reference':r('storage'),'Sprime_reservation_closure_reference':r('Sprime'),'resource_authority_reference':r('authority'),
          'approved_whole_cache_cap_bytes':100,'approved_whole_cache_inode_cap':10,'quota_reserve_bytes':200000000000,
          'other_storage_scope_unwritten_cap_upper_bound_bytes':0,
          'final_common_D4_authorized':False,'final_masks_authorized':False}
        self.assertIs(review_contract(master,review,r('master')),review)
        bad=copy.deepcopy(review);bad['Sprime_reservations_released_or_fully_accounted']=False
        with self.assertRaisesRegex(ValueError,'SPRIME_STORAGE'):review_contract(master,bad,r('master'))
        bad=copy.deepcopy(review);bad['final_common_D4_authorized']=True
        with self.assertRaisesRegex(ValueError,'NORM_EXCEPTION'):review_contract(master,bad,r('master'))

    def test_sidecar_base_null_and_original_compact_axes_unchanged(self):
        provenance={'owner':{'record_ordinal':7,'new_role':'FULL'},'source_reference':{'file_id':3},'physical_row_ordinal':11}
        row={'record_ordinal':7,'task_code':255,'row_kind':'base','scientific_signature':'0'*64}
        out,role=sidecar_row(row,{'provenance':provenance},{});self.assertIsNone(out['candidate']);self.assertEqual((role,out['task_code']),('FULL',255))
        entry={'field_id':0,'values_float64':[0.0,-0.0],'source_value_mask':[True,True],'value_mask':[True,False],
          'source_reasons':[],'new_reasons':['PHYSICAL_DEFINITION_RANGE'],'review_reasons':['SUCCESS_WITH_CONVERGENCE_EVIDENCE_UNKNOWN']}
        candidate=compact.encode(7,2,[entry]);before=copy.deepcopy(candidate)
        payload={'provenance':provenance,'original_compact_candidate':candidate,'field_observations':[{'field_key':'a','payload_structural_failure':False}]}
        row=dict(row,task_code=2,row_kind='task');out,role=sidecar_row(row,payload,{'a':0})
        self.assertIs(out['candidate'],candidate);self.assertEqual(candidate,before)
        self.assertEqual(compact.unpack(out['candidate']['newly_masked_fields']),[0]);self.assertTrue(out['candidate']['review_groups'])
        from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import encode
        tree,pool=encode(dict(payload,cells=[{'unread_numeric_value':-0.0},{'unread_numeric_value':float('nan')}]))
        self.assertEqual(len(pool),2);self.assertEqual(metadata_only(tree),payload)
        tree,pool=encode({'provenance':{'illegal_float_metadata':1.0}})
        with self.assertRaisesRegex(ValueError,'UNEXPECTED_F64_POOL'):metadata_only(tree)
        # Actual Arrow file-like API seam, synthetic bytes only. This catches
        # close/tell/flush mismatches before any real cache/source is touched.
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'synthetic.parquet';sink=CappedOutput(p,4096)
            writer=pq.ParquetWriter(sink,pa.schema([('bits',pa.binary())]));writer.write_table(pa.table({'bits':[b'\x00\xff']}))
            writer.close();sink.finish();source=pq.ParquetFile(p)
            try:self.assertEqual(source.read(use_threads=False).to_pylist(),[{'bits':b'\x00\xff'}])
            finally:source.close()
            sink=CappedOutput(Path(tmp)/'cap.partial',1)
            try:
                with self.assertRaisesRegex(ValueError,'NO_TRUNCATION'):sink.write(b'xx')
                self.assertEqual(sink.tell(),0)
            finally:sink.abort()

if __name__=='__main__':unittest.main()
