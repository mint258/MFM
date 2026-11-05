"""Native filesystem checks for the transport ledger and exact stream hashing."""
import hashlib,io,os,tempfile,time,unittest
from pathlib import Path
from .main_rescue_score_transport import HashReader,Ledger,native_C0
class IOHelpers(unittest.TestCase):
    def test_incremental_ledger_counts_closed_mutable_partial_and_directories(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);ledger=Ledger(root)
            def actual():
                return sum(p.stat().st_blocks*512 for p in[root,*root.rglob('*')])
            closed=root/'closed';closed.write_bytes(b'x'*5001);ledger.partial=closed
            self.assertEqual(ledger.usage(),actual());self.assertEqual(ledger.credit(0),0)
            ledger.close(closed);self.assertEqual(ledger.usage(),actual())
            self.assertEqual(ledger.credit(time.time()+10),closed.stat().st_blocks*512)
            catalog=root/'mutable';catalog.write_bytes(b'm'*3_000_000);ledger.mutable.add(catalog)
            folder=root/'scores'/'0';folder.mkdir(parents=True)
            ledger.dirs.update([folder,folder.parent])
            partial=folder/'part.partial';partial.write_bytes(b'v'*3001);ledger.partial=partial
            self.assertEqual(ledger.usage(),actual())
            final=folder/'part'
            with ledger.lock:partial.rename(final);ledger.close(final)
            self.assertEqual(ledger.usage(),actual())
            ledger.close(catalog);self.assertEqual(ledger.usage(),actual())
    def test_hash_reader_full_EOF(self):
        data=b'exact original score bytes'*1000;reader=HashReader(io.BytesIO(data));result=b''
        while True:
            block=reader.read(719)
            if not block:break
            result+=block
        self.assertEqual(result,data);self.assertEqual(reader.n,len(data));self.assertEqual(reader.h.hexdigest(),hashlib.sha256(data).hexdigest())
    def test_metadata_fixture_requires_whole_parent_batch_and_steps_C0(self):
        # Synthetic metadata fixture. No actual scheduler allocation or C0 is claimed.
        with tempfile.TemporaryDirectory()as temp:
            path=Path(temp)/'fixture.txt';header='JobIDRaw|State|ExitCode|UID\n'
            parent='99|COMPLETED|0:0|1278\n';batch='99.batch|COMPLETED|0:0|\n';step='99.0|COMPLETED|0:0|\n'
            path.write_text(header+parent+batch+step);native_C0(dict(job_id='99'),path)
            path.write_text(header+parent+step)
            with self.assertRaises(ValueError):native_C0(dict(job_id='99'),path)
            path.write_text(header+parent+batch+'99.0|RUNNING|0:0|\n')
            with self.assertRaises(ValueError):native_C0(dict(job_id='99'),path)
if __name__=='__main__':unittest.main()
