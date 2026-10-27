"""Exactly three meaningful pure boundaries; no fixture opens any input body."""
import copy,unittest
from . import contract as C


class TimeoutInventoryBoundaries(unittest.TestCase):
    def test_timeout_zero_exit_never_old_C0_and_forged_parent_rejected(self):
        cfgref={'path':str(C.RUN/'control/original_config.json'),'bytes':1,'sha256':'a'*64}
        argv=[C.PY,'-B','-m','workflows.data_v1_final.labels.full_projection_v1.run','--config',cfgref['path'],
          '--startup-proof',str(C.RUN/'control/queue_startup/old.json'),'--output',str(C.OLD)]
        request={'execution_argv':argv,'startup_proof_path':argv[7],'source_references':[cfgref]}
        cfg={'schema':'FULL_LABEL_PROJECTION_BATCH_CONFIG_V1','dispatch_book_path':str(C.BOOK),'batch_name':'full_batch0000'}
        proof={'schema':'FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1','uid':1278,'node':'compute-0-17','job_id':'4521904','request':request}
        submission={'schema':'CPU_AUTO_MEMORY_SUBMISSION_V1','uid':1278,'job_id':'4521904','sbatch_returncode':0,'request':request}
        account={'schema':'DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1','status':'ACTUAL_PARENT_ACCOUNTING_CLOSED',
          'query_returncode':0,'endpoint':'202.38.247.57:22','uid':1278,'allocated_core_seconds':230592,
          'parents':[{'job_id':'4521904','state':'TIMEOUT','exit_code':'0:0','alloc_cpus':16,'elapsed_raw_seconds':14412,'node':'compute-0-17'}]}
        raw='JobIDRaw|State|ExitCode|ElapsedRaw|AllocCPUS|NodeList|UID\n4521904|TIMEOUT|0:0|14412|16|compute-0-17|1278\n'
        self.assertIs(C.parent_chain(account,raw,request,proof,submission,cfg,cfgref)['original_parent_c0'],False)
        for field,value in [('state','COMPLETED'),('job_id','4521905'),('alloc_cpus',1)]:
            bad=copy.deepcopy(account);bad['parents'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):C.parent_chain(bad,raw,request,proof,submission,cfg,cfgref)
        with self.assertRaises(ValueError):C.parent_chain(account,raw.replace('|1278','|1264'),request,proof,submission,cfg,cfgref)
        badproof=dict(proof,uid=1264)
        with self.assertRaises(ValueError):C.parent_chain(account,raw,request,badproof,submission,cfg,cfgref)

    def test_commit_receipt_cursor_conservation_conflict_and_missing_part(self):
        ref={'path':str(C.OLD/'parts/window_t.json'),'bytes':1,'sha256':'b'*64}
        expected=[{'range_id':'r','physical_row_lo':0,'physical_row_hi':4}]
        ranges=[{'range_id':'r','cursor':2,'stop':4}]
        tickets=[{'ticket':'t','range_id':'r','lo':0,'status':'CLOSED','receipt':ref,'amount':10,'inodes':2},
          {'ticket':'u','range_id':'r','lo':2,'status':'RESERVED','receipt':None,'amount':20,'inodes':2}]
        windows=[{'range_id':'r','lo':0,'hi':2,'receipt':ref}]
        self.assertEqual(C.cursor_chain(ranges,tickets,windows,expected)['unpublished_tickets'],1)
        bad=copy.deepcopy(ranges);bad[0]['cursor']=3
        with self.assertRaises(ValueError):C.cursor_chain(bad,tickets,windows,expected)
        bad=copy.deepcopy(tickets);bad[0]['receipt']['sha256']='c'*64
        with self.assertRaises(ValueError):C.cursor_chain(ranges,bad,windows,expected)
        with self.assertRaises(ValueError):C.cursor_chain(ranges,tickets,windows+windows,expected)
        body={'schema':'BOUNDED_TYPED_PHYSICAL_WINDOW_V1','range_id':'r','physical_row_lo':0,'physical_row_hi':2,
          'all_part_reopen_bits_verified':True,'physical_classifications':{'CANONICAL':2},'parts':[{'reference':ref}]}
        self.assertTrue(C.completed_window(body,windows[0],[{'status':'VERIFIED_TYPED_PART','rows':2}]))
        for parts in ([],[{'status':'UNKNOWN_SHA_MISMATCH','rows':2}],[{'status':'VERIFIED_TYPED_PART','rows':1}]):
            with self.subTest(parts=parts),self.assertRaises(ValueError):C.completed_window(body,windows[0],parts)

    def test_uncommitted_partial_orphan_never_completed(self):
        self.assertEqual(C.file_class('parts/a.parquet.partial',set()),'UNCOMMITTED_PARTIAL_NEVER_COMPLETED')
        self.assertEqual(C.file_class('parts/a.parquet',set()),'UNCOMMITTED_ORPHAN_NEVER_COMPLETED')
        self.assertEqual(C.file_class('parts/window_u.json',set()),'UNCOMMITTED_ORPHAN_NEVER_COMPLETED')
        self.assertEqual(C.file_class('parts/a.parquet',{'parts/a.parquet'}),'COMMITTED_REFERENCE_REQUIRES_CPU_VERIFICATION')
        self.assertNotIn('VERIFIED',C.file_class('worker_04.json',set()))
        self.assertEqual(C.STATUS,'PARTIAL_TIMEOUT_EVIDENCE_NOT_OLD_C0')