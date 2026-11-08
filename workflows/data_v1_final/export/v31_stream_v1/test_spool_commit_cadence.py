"""One tiny real-SQLite transaction-cadence fixture; no production data/timing."""
import pathlib,sqlite3,tempfile,unittest
import numpy as np
from . import source_bridge as S


class SpoolCommitCadenceCheck(unittest.TestCase):
    def test_batched_molecules_match_bytes_visibility_and_rollback(self):
        mids=['mid_%03d'%i for i in reversed(range(35))]
        payloads=[{'mid':mid,'record_ids':['record-2','record-1'],
                   'values':np.asarray([np.nan,-0.,float(i)],dtype='<f4'),'mask':np.asarray([0,1,1],dtype='u1')}for i,mid in enumerate(mids)]
        blobs=[S.spool_dumps(value,None if i%2==0 else 'zlib1')for i,value in enumerate(payloads)]
        original=list(zip(mids,blobs));events={}
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)
            def seed(path):
                db=sqlite3.connect(path)
                try:
                    db.executescript('CREATE TABLE pieces(mid TEXT,row BLOB); CREATE INDEX pieces_mid ON pieces(mid); CREATE TABLE molecules(mid TEXT PRIMARY KEY,row BLOB);')
                    db.executemany('INSERT INTO pieces VALUES(?,?)',original);db.commit()
                finally:db.close()
            def ordered(path,table):
                db=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)
                try:return list(db.execute('SELECT mid,row FROM '+table+' ORDER BY rowid'))
                finally:db.close()
            def write(path,batched,fail_at=None):
                db=sqlite3.connect(path);reader=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)
                state=events[path]={'commits':[],'visible':{}}
                try:
                    for completed,(mid,blob) in enumerate(original,1):
                        db.execute('INSERT INTO molecules VALUES(?,?)',(mid,blob));db.execute('DELETE FROM pieces WHERE mid=?',(mid,))
                        if not batched or S.molecule_commit_due(completed,len(mids)):
                            db.commit();state['commits'].append(completed)
                        if completed in (1,15,16,17,19,31,32,33,35):
                            state['visible'][completed]=(list(reader.execute('SELECT mid,row FROM molecules ORDER BY rowid')),
                                                         list(reader.execute('SELECT mid,row FROM pieces ORDER BY rowid')))
                        if completed==fail_at:raise RuntimeError('synthetic uncommitted molecule tail')
                finally:reader.close();db.close()
            reference=root/'per_mid.sqlite';batched=root/'batched.sqlite';seed(reference);seed(batched)
            write(reference,False);write(batched,True)
            self.assertEqual(events[reference]['commits'],list(range(1,36)))
            self.assertEqual(events[batched]['commits'],[16,32,35])
            self.assertEqual(ordered(reference,'molecules'),original);self.assertEqual(ordered(batched,'molecules'),original)
            self.assertEqual(ordered(reference,'pieces'),[]);self.assertEqual(ordered(batched,'pieces'),[])
            for completed,visible in events[batched]['visible'].items():
                committed=completed if completed==35 else completed//16*16
                self.assertEqual(visible,(original[:committed],original[committed:]))
            for i,(mid,blob) in enumerate(ordered(batched,'molecules')):
                item=S.spool_loads(blob);self.assertEqual(item['mid'],mid);self.assertEqual(item['record_ids'],payloads[i]['record_ids'])
                self.assertEqual(item['values'].tobytes(),payloads[i]['values'].tobytes())
                self.assertEqual(item['mask'].tobytes(),payloads[i]['mask'].tobytes())
                self.assertEqual(blob.startswith(S.SPOOL_ZLIB1_MAGIC),bool(i%2))
            interrupted=root/'interrupted.sqlite';seed(interrupted)
            with self.assertRaisesRegex(RuntimeError,'synthetic uncommitted molecule tail'):write(interrupted,True,19)
            self.assertEqual(events[interrupted]['commits'],[16])
            self.assertEqual(events[interrupted]['visible'][19],(original[:16],original[16:]))
            self.assertEqual(ordered(interrupted,'molecules'),original[:16])
            self.assertEqual(ordered(interrupted,'pieces'),original[16:])
            for total,expected in ((1,[1]),(16,[16]),(32,[16,32]),(35,[16,32,35])):
                self.assertEqual([i for i in range(1,total+1)if S.molecule_commit_due(i,total)],expected)


if __name__=='__main__':unittest.main()
