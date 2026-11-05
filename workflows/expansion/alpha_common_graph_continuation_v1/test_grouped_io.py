"""Stdlib-only byte parity and committed-prefix/dispatch boundary evidence."""
import concurrent.futures as cf,hashlib,json,pathlib,tempfile,unittest,sqlite3
from . import grouped_io as G,io as I


class Guard:
    def check(self,*args,**kwargs):pass


def policy():
    return dict(schema='ALPHA_COMMON_GROUPED_IO_POLICY_V1',mode=G.MODE,checkpoint_bytes=8<<20,checkpoint_seconds=2,
      maximum_pending_MIDs=32,final_close_flush_fsync=True,deferred_per_record_durable_requests=True,
      source_durable_before_real_worker_submit=True,full_readback_required=True,checkpoint_is_resume_authority=False,
      db_commit_requests_per_group=32,db_commit_seconds=2,deferred_SQLite_commit_requests=True,
      SQLite_synchronous_FULL_unchanged=True,SQLite_partial_is_resume_authority=False)


class Boundaries(unittest.TestCase):
    def test_original_and_grouped_bytes_rows_hash_equal_with_deferred_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);old=I.Writer(root/'old',Guard());budget=G.Budget(Guard(),policy(),clock=lambda:0);new=G.Writer(root/'grouped',budget)
            rows=[dict(ordinal=i,unicode='αβ',values=[i,None,True],text='line\nvalue') for i in range(71)]
            for i,row in enumerate(rows):old.write(row,i%3!=0);new.write(row,i%3!=0)
            self.assertEqual(new.committed_rows,0);old.close();new.close()
            self.assertEqual((root/'old').read_bytes(),(root/'grouped').read_bytes());self.assertEqual(old.rows,new.rows)
            self.assertEqual(old.reference()['sha256'],new.reference()['sha256']);self.assertEqual(new.checkpoints,1)
            self.assertEqual(new.requested_durable_rows,47);self.assertEqual(new.committed_rows,71)

    def test_partial_prefix_does_not_claim_uncommitted_tail_or_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            clock=[0];budget=G.Budget(Guard(),policy(),clock=lambda:clock[0]);writer=G.Writer(pathlib.Path(directory)/'partial',budget)
            writer.write(dict(row=1),True);writer.checkpoint('TEST_CONFIRMED_PREFIX')
            first=json.loads(writer.checkpoint_path.read_bytes());self.assertEqual(first['committed_rows'],1)
            class Pool:
                calls=0
                def submit(self,function,*args,**kwargs):
                    self.calls+=1;future=cf.Future();future.set_result(function(*args,**kwargs));return future
            real=Pool();proxy=G.SourceDurablePool(real,writer,budget)
            writer.write(dict(row=2),True);future=proxy.submit(lambda:'done');self.assertFalse(future.done());self.assertEqual(real.calls,0)
            # Simulate abrupt interruption without invoking the graceful close.
            writer.stream.flush();raw=writer.path.read_bytes();checkpoint=json.loads(writer.checkpoint_path.read_bytes())
            self.assertEqual(checkpoint,first);self.assertGreater(len(raw),checkpoint['committed_bytes'])
            self.assertEqual(hashlib.sha256(raw[:checkpoint['committed_bytes']]).hexdigest(),checkpoint['committed_prefix_sha256'])
            self.assertTrue(raw[:checkpoint['committed_bytes']].endswith(b'\n'))
            clock[0]=3;budget.check();self.assertEqual(future.result(),'done');self.assertEqual(real.calls,1)
            writer.close();self.assertEqual(writer.committed_rows,2)

    def test_SQLite_logical_parity_and_rollback_retains_only_confirmed_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);budget=G.Budget(Guard(),policy(),clock=lambda:0)
            old=sqlite3.connect(root/'old.db');base=sqlite3.connect(root/'new.db')
            for db in (old,base):db.executescript('PRAGMA journal_mode=DELETE;PRAGMA synchronous=FULL;CREATE TABLE rows(mid TEXT PRIMARY KEY,n INTEGER);')
            new=G.Connection(base,root/'new.db',budget)
            for i in range(12):
                row=('m%02d'%i,i);old.execute('INSERT INTO rows VALUES(?,?)',row);old.commit()
                new.execute('INSERT INTO rows VALUES(?,?)',row);new.commit()
                self.assertEqual(new.execute('SELECT count(*) FROM rows').fetchone()[0],i+1)
            self.assertEqual(new.actual_commits,0);new.checkpoint('TEST_CONFIRMED_LOGICAL_PREFIX')
            self.assertEqual(old.execute('SELECT * FROM rows ORDER BY mid').fetchall(),new.execute('SELECT * FROM rows ORDER BY mid').fetchall())
            observer=sqlite3.connect(root/'new.db');self.assertEqual(observer.execute('SELECT count(*) FROM rows').fetchone()[0],12)
            new.execute('INSERT INTO rows VALUES(?,?)',('unconfirmed_tail',99));new.commit()
            self.assertEqual(new.execute('SELECT count(*) FROM rows').fetchone()[0],13)
            self.assertEqual(observer.execute('SELECT count(*) FROM rows').fetchone()[0],12)
            base.rollback();base.close();new.closed=True
            checkpoint=json.loads(new.checkpoint_path.read_bytes())
            self.assertEqual(checkpoint['confirmed_commit_request_ordinal'],12)
            self.assertEqual(observer.execute('SELECT count(*) FROM rows').fetchone()[0],12)
            self.assertFalse(checkpoint['database_binary_equivalence_claimed']);observer.close();old.close()
