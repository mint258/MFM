"""Three pure boundaries; no scientific bodies, imports of old main, or mocks."""
import unittest
from . import contract as C
class Boundaries(unittest.TestCase):
    def test_exact_ordinals_partition_without_gaps_or_pilot_assumption(self):
        pieces=C.ranges(11231854);self.assertEqual(len(pieces),16);self.assertEqual(pieces[0][0],0);self.assertEqual(pieces[-1][1],11231854)
        self.assertTrue(all(a<b for a,b in pieces));self.assertTrue(all(pieces[i][1]==pieces[i+1][0] for i in range(15)))
        with self.assertRaises(ValueError):C.ranges(True)
    def test_source_job_order_file_order_roles_and_full_counts(self):
        jobs=list(range(16,0,-1));labels=[{'source_job_id':j,'path':str(j)+'b'} for j in jobs]+[{'source_job_id':j,'path':str(j)+'a'} for j in jobs]
        base={j:[{'path':'base'+str(j)}] for j in jobs};counts={str(j):{'TRAIN':{'records':1,'molecules':1}} for j in jobs}
        counts['1']['TRAIN']={'records':11231839,'molecules':1220451};authority={'TRAIN':{'records':11231854,'molecules':1220466}}
        groups,roles,mols=C.groups(labels,base,counts,authority);self.assertEqual([g['source_job_id'] for g in groups],list(range(1,17)))
        self.assertEqual([r['path'] for r in groups[0]['label_files']],['1b','1a']);self.assertIsNone(groups[0]['owner_index']);self.assertEqual(roles['TRAIN'],11231854)
        with self.assertRaises(ValueError):C.groups(labels,{**base,99:[{}]},counts,authority)
        with self.assertRaises(ValueError):C.groups(labels,base,counts,{'TRAIN':{'records':11231853,'molecules':1220466}})
    def test_root_review_cannot_promote_null_timeout_or_skip_storage(self):
        ref={'path':str(C.RUN/'control/synthetic.json'),'bytes':1,'sha256':'0'*64}
        cfg={'baseline512_config_reference':ref,'footer_parent':{'manifest':ref},'canonical_preparation_reference':ref,'formal_record_index_reference':ref,
          'source_mapping_evidence_references':[ref],'other_output_cap_bytes':123}
        review={'schema':'ROOT_FULL_LOGICAL_OWNER_PLAN_BUILD_REVIEW_V1','status':'ROOT_APPROVED_NEW_FULL_LOGICAL_PLAN_BUILD','reviewer':'root','reason':'synthetic boundary only',
          'baseline512_config_reference':ref,'footer_manifest_reference':ref,'canonical_preparation_reference':ref,'formal_record_index_reference':ref,
          'source_mapping_evidence_references':[ref],'old_full_logical_plan_was_null':True,'old1904_remains_TIMEOUT':True,'old_books_or_HOLD_modified':False,
          'current_CPU_full_SHA_current_frame_binding_approved':True,'freeze_requires_actual_C0':True,'all_other_future_caps_reviewed':True,
          'other_output_cap_bytes':123,'new_output_cap_bytes':C.CAP,'quota_headroom_bytes':200000000000}
        self.assertIs(C.review(cfg,review),review)
        for field,bad in (('old1904_remains_TIMEOUT',False),('old_full_logical_plan_was_null',False),('freeze_requires_actual_C0',False),
          ('all_other_future_caps_reviewed',False),('other_output_cap_bytes',0),('old_books_or_HOLD_modified',True)):
            with self.assertRaises(ValueError):C.review(cfg,dict(review,**{field:bad}))
        self.assertEqual(C.PARAMETERS['TSQR_chunk'],256);self.assertEqual(C.PARAMETERS['QR_reduction'],'ORIGINAL_ORDERED_LEFT_FOLD')
