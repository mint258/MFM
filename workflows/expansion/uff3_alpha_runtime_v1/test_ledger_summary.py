"""Real tiny native files/SQLite: compact closed totals, no scientific DATA."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from ..uff3_candidate_v1.credit import ClosedLedger
from . import ledger_summary as L,prepare


class LedgerSummaryTests(unittest.TestCase):
    def example(self,root):
        molecules=root/'molecules';molecules.mkdir()
        nested=molecules/'closed';nested.mkdir();data=nested/'saved.bin';data.write_bytes(b'x'*18000)
        ledger=ClosedLedger(root/'output_accounting.sqlite');ledger.register(data);ledger.register_directory(nested)
        ledger.flush();totals=ledger.totals();maximum=ledger.maximum_native_ns;ledger.close()
        s=ledger.path.stat()
        closed=dict(path=str(ledger.path),schema_version=2,closed_totals=totals,
            maximum_recorded_native_ns=maximum,closed_at_unix_ns=max(time.time_ns(),s.st_ctime_ns),
            producer_frame=dict(uid=s.st_uid,size=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,nlink=s.st_nlink),
            mutable_paths=[str(root/'index.sqlite'),str(root/'deleted.sqlite-journal')],
            mutable_routing_directories=[str(root),str(molecules)],
            whole_tree_root_blocks_used_as_total=False,historical_peak_used_as_current=False)
        (root/'index.sqlite').write_bytes(b'metadata'*700)
        runtime={'job_id':'actual-small-fixture','uid':os.getuid()}
        plan={'path':'actual-plan','bytes':1,'sha256':'plan'};startup={'path':'actual-startup','bytes':1,'sha256':'startup'}
        receipt=dict(runtime=runtime,execution_metadata=dict(original_launcher_plan_reference=plan,original_startup_proof_reference=startup),
            status='COMPLETE_CANDIDATE_SHARD_NOT_TRAINING_RELEASE',expected_molecules=1,closed_family_export_molecules=1,
            closed_ledger=closed,last_resource_observation={'peak_actual_output_blocks_bytes':10**15})
        ref=L.Q.write(root/'receipt.json',receipt)
        binding=dict(scope='UFF',runtime=runtime,plan_reference=plan,startup_proof_reference=startup,generation_receipt_reference=ref)
        return binding,data,totals

    def test_real_closed_ledger_and_current_extras_without_tree_or_peak(self):
        with tempfile.TemporaryDirectory()as folder,patch.object(L.Q,'UID',os.getuid()):
            root=Path(folder);binding,data,totals=self.example(root)
            with patch.object(os,'walk',side_effect=AssertionError('No generation tree walk')):
                summary=L.summarize(binding,root)
            expected=totals['closed_allocated_bytes']+sum(p.stat().st_blocks*512 for p in
                (root,root/'molecules',root/'output_accounting.sqlite',root/'index.sqlite',root/'receipt.json'))
            self.assertEqual(summary['allocated_bytes'],expected)
            self.assertGreater(summary['allocated_bytes'],root.stat().st_blocks*512)
            self.assertFalse(summary['historical_peak_used_as_current'])
            self.assertGreaterEqual(summary['maximum_eligible_ns'],Path(binding['generation_receipt_reference']['path']).stat().st_ctime_ns)
            # The full finalizer independently verifies DATA; this summary is
            # explicitly not a fresh whole-tree integrity/whole-body audit.
            self.assertFalse(summary['whole_tree_enumerated'])
            self.assertFalse(summary['unrecorded_tree_files_credited'])
            p=prepare.partition_for({'private_caps_bytes':{'generation':10**8,'quality':10**7,'finalizer':10**7},
                'global_UFF_scope_root':str(root.parent),'routing_overhead_reserved_bytes':1000},
                {'scope_total_caps_bytes':{'UFF':10**9},'other_future_reserved_bytes_for_each_scope':{'UFF':1000},'closed_census_reference':{}},
                {'records':[],'generation_summaries':[summary]},'quality',root.parent/'qa',root.parent/'qa'/'new',root)
            self.assertEqual(p['closed_legacy_allocated_bytes'],0)
            self.assertEqual(p['peer_remaining_reserved_bytes'],110000000-summary['allocated_bytes'])

    def test_changed_ledger_or_unregistered_hardlink_rejected(self):
        with tempfile.TemporaryDirectory()as folder,patch.object(L.Q,'UID',os.getuid()):
            root=Path(folder);binding,data,_=self.example(root)
            os.link(data,root/'ambiguous-hardlink')
            with self.assertRaisesRegex(ValueError,'hardlink'):L.summarize(binding,root)
            (root/'ambiguous-hardlink').unlink()
            with(root/'output_accounting.sqlite').open('ab')as out:out.write(b'changed')
            with self.assertRaisesRegex(ValueError,'frame changed'):L.summarize(binding,root)


if __name__=='__main__':unittest.main()