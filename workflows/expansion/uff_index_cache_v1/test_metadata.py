"""Metadata-only SQLite cache regression; never calls UFF/D."""
import hashlib,pathlib,sqlite3,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[3]
OLD='c0ab32e28f47cbc1d0696cee3e92bf813ab08664cf75e73259c33c59160bee54'
ADDED="    db.execute('PRAGMA cache_size=-4194304')\n    db.execute('PRAGMA temp_store=MEMORY')\n"
class CacheTests(unittest.TestCase):
    def test_only_cache_statements_change(self):
        raw=(ROOT/'workflows/expansion/uff3_candidate_v1/run.py').read_text()
        self.assertEqual(raw.count(ADDED),1)
        self.assertEqual(hashlib.sha256(raw.replace(ADDED,'').encode()).hexdigest(),OLD)
    def test_cache_and_persistent_transaction_semantics(self):
        with tempfile.TemporaryDirectory()as folder:
            path=pathlib.Path(folder)/'index.sqlite';db=sqlite3.connect(path)
            db.execute('PRAGMA cache_size=-4194304');db.execute('PRAGMA temp_store=MEMORY')
            self.assertEqual(db.execute('PRAGMA cache_size').fetchone()[0],-4194304)
            self.assertEqual(db.execute('PRAGMA temp_store').fetchone()[0],2)
            self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0],'delete')
            self.assertEqual(db.execute('PRAGMA synchronous').fetchone()[0],2)
            db.execute('CREATE TABLE source(ordinal INTEGER PRIMARY KEY, full_key TEXT UNIQUE,stream TEXT,stream_rank INTEGER,UNIQUE(stream,stream_rank))')
            db.executemany('INSERT INTO source VALUES(?,?,?,?)',[(0,'A','R',1),(1,'B','N',1)])
            db.commit()
            with self.assertRaises(sqlite3.IntegrityError):db.execute("INSERT INTO source VALUES(2,'A','N',2)")
            db.rollback();db.execute("INSERT INTO source VALUES(2,'C','N',2)");db.rollback();db.close()
            db=sqlite3.connect(path);self.assertEqual(db.execute('SELECT * FROM source ORDER BY ordinal').fetchall(),[(0,'A','R',1),(1,'B','N',1)])
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok');db.close()
if __name__=='__main__':unittest.main()
