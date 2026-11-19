import json
import sqlite3
import unittest
import zlib
from workflows.benchmark_data.geometry_queue import schema,claim,recover_intents,finish


class OnceOnlyTests(unittest.TestCase):
    def test_kernel_deadline_terminates_a_blocked_native_call(self):
        import signal,subprocess,sys
        code='from workflows.benchmark_data.geometry_queue import arm_deadline; import ctypes; arm_deadline(.05); ctypes.PyDLL(None).sleep(5)'
        result=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,-signal.SIGALRM)

    def test_interrupted_native_intent_cannot_be_reclaimed(self):
        db=sqlite3.connect(':memory:');schema(db)
        db.execute("INSERT INTO tasks(mid,model_smiles) VALUES ('one','CCO')");db.commit()
        claim(db,'one',123)
        recover_intents(db)
        with self.assertRaises(RuntimeError):claim(db,'one',456)
        self.assertEqual(db.execute('SELECT state FROM tasks').fetchone()[0],'UNKNOWN_INTERRUPTED_NO_RETRY')

    def test_one_result_preserves_valid_f64_and_missing_masks(self):
        db=sqlite3.connect(':memory:');schema(db)
        db.execute("INSERT INTO tasks(mid,model_smiles) VALUES ('one','CCO')");db.commit();claim(db,'one',123)
        finish(db,'one',{'state':'DONE','D20':{'values':[1.2345678901234567,float('nan')],'valid_mask':[True,False]}})
        result=json.loads(zlib.decompress(db.execute('SELECT result FROM tasks').fetchone()[0]))
        self.assertEqual(result['D20']['values'],[1.2345678901234567,None])
        self.assertEqual(result['D20']['valid_mask'],[True,False])
        with self.assertRaises(RuntimeError):finish(db,'one',{'state':'DONE'})

if __name__=='__main__':unittest.main()
