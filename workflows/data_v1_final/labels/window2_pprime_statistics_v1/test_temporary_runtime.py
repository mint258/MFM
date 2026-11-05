"""One toy fixture for plan-time env, SQLite checks and explicit DuckDB spill."""
import os,sqlite3,struct,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from . import temporary as T

class TemporaryRuntime(unittest.TestCase):
    def test_safe_environment_spill_settings_runtime_stop_and_root_refusal(self):
        import duckdb
        from workflows.data_v1_final.export.v31_stream_v1 import disk_guard as D
        original_temp=tempfile.tempdir
        class Guard:
            poll=0.01
            def __init__(self):self.fail=False;self.waited=[]
            def target(self,path):return {'facts':{'root_filesystem':False},'budget':{'peak_additional_bytes':16*1024**2}}
            def wait(self,path,**unused):self.waited.append(str(path))
            def check(self,path,**unused):
                if self.fail:raise D.DiskUnavailable('TOY_RUNTIME_RESERVE_REACHED')
        try:
            with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,clear=False):
                root=Path(directory)/"safe's-temp";guard=Guard()
                plan={'temporary_root':str(root),'temporary_spill_limit_bytes':1024**2,'disk_protection':{'targets':['toy']}}
                with patch.object(D,'from_plan',return_value=guard):runtime=T.activate(plan)
                for name in ('TMPDIR','TMP','TEMP','SQLITE_TMPDIR'):self.assertEqual(os.environ[name],str(root))
                self.assertEqual(tempfile.gettempdir(),str(root))
                connection=runtime.sqlite(sqlite3.connect(':memory:'),root/'toy.sqlite')
                try:
                    self.assertEqual(connection.execute('WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<2000) SELECT sum(x) FROM n').fetchone()[0],2001000)
                    self.assertGreater(len(guard.waited),2)
                finally:connection.close()
                db=duckdb.connect();value=1.0000000000000002
                try:
                    with runtime.duckdb(db):
                        self.assertTrue(Path(db.execute("SELECT current_setting('temp_directory')").fetchone()[0]).is_relative_to(root))
                        self.assertEqual(struct.pack('<d',db.execute('SELECT ?::DOUBLE',[value]).fetchone()[0]),struct.pack('<d',value))
                finally:db.close()
                interrupted=threading.Event()
                class Database:
                    def execute(self,sql):
                        if sql.startswith('SET max_temp_directory_size='):self.assertion=sql
                        return self
                    def interrupt(self):interrupted.set()
                fake=Database()
                with self.assertRaisesRegex(D.DiskUnavailable,'TOY_RUNTIME_RESERVE_REACHED'):
                    with runtime.duckdb(fake):
                        guard.fail=True;self.assertTrue(interrupted.wait(1))
                self.assertEqual(fake.assertion,"SET max_temp_directory_size='1048576B'")
                with self.assertRaisesRegex(D.DiskUnavailable,'ROOT_TMP_TEMPORARY_PATH_FORBIDDEN'):
                    T.activate(dict(plan,temporary_root='/tmp/must-not-create'))
        finally:tempfile.tempdir=original_temp
