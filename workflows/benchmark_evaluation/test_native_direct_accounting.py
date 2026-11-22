"""Native read-only accounting uses the already-proven client, without changing mutations."""
import os,types,unittest
from unittest.mock import patch
from . import native_slurm_transport as transport
class NativeDirectAccountingTests(unittest.TestCase):
    def reader(self,path):
        return os.getuid(),0o600,"".join(k+"="+v+"\n" for k,v in transport.DIRECT_ACCOUNTING_FIELDS.items()),False
    def test_actual_cluster_override_only(self):
        env=transport.direct_accounting_environment(transport.DIRECT_ACCOUNTING_CONFIG,reader=self.reader)
        self.assertEqual(env["SLURM_CONF"],transport.DIRECT_ACCOUNTING_CONFIG)
        with self.assertRaises(ValueError):transport.direct_accounting_environment("/unregistered/cluster")
    def test_different_database_or_auth_refused(self):
        for key,value in (("AccountingStorageHost","elsewhere"),("AuthType","auth/none"),("ClusterName","other")):
            uid,mode,raw,link=self.reader("")
            raw=raw.replace(key+"="+transport.DIRECT_ACCOUNTING_FIELDS[key],key+"="+value)
            with self.subTest(key=key),self.assertRaises(ValueError):
                transport.direct_accounting_environment(transport.DIRECT_ACCOUNTING_CONFIG,reader=lambda p:(uid,mode,raw,link))
    def test_ownership_permissions_symlinks_refused(self):
        uid,mode,raw,link=self.reader("")
        for record in ((uid+1,mode,raw,False),(uid,0o666,raw,False),(uid,mode,raw,True)):
            with self.subTest(record=record[:2]),self.assertRaises(ValueError):
                transport.direct_accounting_environment(transport.DIRECT_ACCOUNTING_CONFIG,reader=lambda p:record)
    def test_native_sacct_uses_scoped_environment(self):
        calls=[]
        def runner(command,**kwargs):
            calls.append((command,kwargs));return types.SimpleNamespace(returncode=0,stdout="C0\n",stderr="")
        with patch.object(transport,"direct_accounting_environment",return_value={"SLURM_CONF":"proven"}):
            self.assertEqual(transport.native_control(["sacct","-j","123"],runner=runner,accounting_config=transport.DIRECT_ACCOUNTING_CONFIG),"C0")
        self.assertEqual(calls[0][0],["sacct","-j","123"])
        self.assertEqual(calls[0][1]["env"],{"SLURM_CONF":"proven"})
        self.assertEqual(len(calls),1)
    def test_mutation_stays_local_and_single_attempt(self):
        calls=[]
        def runner(command,**kwargs):
            calls.append((command,kwargs));return types.SimpleNamespace(returncode=0,stdout="123\n",stderr="")
        with patch.dict(os.environ,{"BENCHMARK_NATIVE_SLURM_ACCOUNTING_CONFIG":transport.DIRECT_ACCOUNTING_CONFIG}):
            transport.native_control(["sbatch","--parsable","--hold","script"],runner=runner)
        self.assertEqual(calls[0][0],["sbatch","--parsable","--hold","script"])
        self.assertNotIn("env",calls[0][1]);self.assertEqual(len(calls),1)
