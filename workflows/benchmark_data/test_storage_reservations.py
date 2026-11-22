"""Shared-future reconciliation and system reserve boundaries."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from .storage_reservations import declared_concurrent,current_concurrent,local_reserve

POLICY={"schema":"benchmark-shared-storage-reservations-v1","updated_at":"2026-11-20T12:20:55Z","notice":"docs/interfaces/STATUS.md D shared-future reconciliation 20:20CST","owned_scopes":["/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119","/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119"],"components":{"model_P_NFS":25327352832,"private_environments":25769803776,"miscellaneous":1073741824,"S_full_study":68719476736,"D_joint_replaces_old_14GiB":36706053853,"benchmark_B1_C1":42949672960},"concurrent_total_bytes":200546101981,"quantum_future":"Added by original caller only while each scope access is not immutable/cross-node; committed bytes remain actual quota usage","old_114569896448_model_pool":"Lustre total; replaced by actual NFS model_P_NFS plus individually declared futures","no_own_training_or_foreign_jobs_changed":True,"node_local_tmp_peer_future_bytes":{"compute-0-7":8589934592,"compute-0-17":12884901888},"node_local_peer_notice":"docs/interfaces/STATUS.md D fixed diagnostics root budgets 2026-11-20T15:04:26UTC","node_local_peer_cache_path":"/tmp/d_recipe_20261120_D_R0_seed0_3M","node_local_claims_not_added_to_NFS_or_Lustre":True}
class StorageTests(unittest.TestCase):
    def test_components_counted_once_and_old_claim_replaced(self):
        self.assertEqual(declared_concurrent(POLICY),200546101981)
        changed=copy.deepcopy(POLICY);changed["components"]["old_D14GiB"]=15032385536
        with self.assertRaises(RuntimeError):declared_concurrent(changed)
    def test_mismatched_missing_or_unknown_bytes_refused(self):
        for mutation in (lambda p:p.update(concurrent_total_bytes=0),
                         lambda p:p["components"].pop("S_full_study"),
                         lambda p:p["components"].update(S_full_study=None)):
            item=copy.deepcopy(POLICY);mutation(item)
            with self.assertRaises(RuntimeError):declared_concurrent(item)
    def test_owned_only_and_stronger_caller_budget_preserved(self):
        with patch("pathlib.Path.read_text",return_value=__import__("json").dumps(POLICY)),patch("os.statvfs") as stat:
            stat.return_value=SimpleNamespace(f_blocks=100*1024**3,f_frsize=1,f_bavail=50*1024**3,f_favail=10000)
            self.assertEqual(current_concurrent(POLICY["owned_scopes"][0],1),200546101981)
            self.assertEqual(current_concurrent(POLICY["owned_scopes"][1],300000000000),300000000000)
            stat.assert_called()
        self.assertEqual(current_concurrent("/another/project",42,policy_path="/absent"),42)
    def test_unknown_policy_refuses_owned_write(self):
        with self.assertRaises(FileNotFoundError):current_concurrent(POLICY["owned_scopes"][0],1,policy_path="/absent")
    def test_actual_guard_rejects_quota_below_updated_shared_pool(self):
        from .acquire import guard,FLOOR
        import time
        stat=SimpleNamespace(f_favail=10000)
        with patch("workflows.benchmark_data.storage_reservations.current_concurrent",return_value=200546101981),patch(
            "subprocess.check_output",return_value="Avail\n1000000000000\n"),patch("os.statvfs",return_value=stat):
            with self.assertRaisesRegex(RuntimeError,"account quota"):
                guard(POLICY["owned_scopes"][0],1,FLOOR+200546101981-1,time.monotonic(),114569896448+40*1024**3)
    def test_guard_remains_callable_from_standalone_script_namespace(self):
        from .acquire import guard
        from . import storage_reservations
        import sys,time,types
        standalone=types.FunctionType(guard.__code__,dict(guard.__globals__,__package__=""))
        stat=SimpleNamespace(f_favail=10000)
        with patch.dict(sys.modules,{"storage_reservations":storage_reservations}),patch(
            "subprocess.check_output",return_value="Avail\n1000000000000\n"),patch("os.statvfs",return_value=stat):
            standalone("/another/project",1,1000000000000,time.monotonic(),42)
    def test_published_peer_root_budget_is_reserved_before_own_write(self):
        stat=SimpleNamespace(f_blocks=100*1024**3,f_frsize=1,f_bavail=22*1024**3+16*1024**2-1,f_favail=10000)
        with patch("pathlib.Path.read_text",return_value=__import__("json").dumps(POLICY)),patch(
            "socket.gethostname",return_value="compute-0-17"),patch("os.statvfs",return_value=stat),patch(
            "os.stat",return_value=SimpleNamespace(st_dev=1)):
            with self.assertRaisesRegex(RuntimeError,"root/tmp"):
                current_concurrent(POLICY["owned_scopes"][0],1)
            stat.f_bavail+=1
            self.assertEqual(current_concurrent(POLICY["owned_scopes"][0],1),200546101981)
    def test_unknown_peer_claim_and_changed_tmp_filesystem_refuse_owned_write(self):
        broken=copy.deepcopy(POLICY);broken.pop("node_local_tmp_peer_future_bytes")
        with patch("pathlib.Path.read_text",return_value=__import__("json").dumps(broken)):
            with self.assertRaisesRegex(RuntimeError,"node-local"):
                current_concurrent(POLICY["owned_scopes"][0],1)
        with patch("pathlib.Path.read_text",return_value=__import__("json").dumps(POLICY)),patch(
            "socket.gethostname",return_value="compute-0-7"),patch(
            "os.stat",side_effect=lambda path,*args,**kwargs:SimpleNamespace(st_dev=1 if str(path)=="/" else 2)):
            with self.assertRaisesRegex(RuntimeError,"split filesystems"):
                current_concurrent(POLICY["owned_scopes"][0],1)
    def test_root_tmp_exact_floor_and_inodes(self):
        stat=SimpleNamespace(f_blocks=100*1024**3,f_frsize=1,f_bavail=10*1024**3+16*1024**2,f_favail=2000)
        self.assertEqual(local_reserve(stat),10*1024**3)
        stat.f_bavail-=1
        with self.assertRaises(RuntimeError):local_reserve(stat)
        stat.f_bavail+=1;stat.f_favail=1999
        with self.assertRaises(RuntimeError):local_reserve(stat)

if __name__=="__main__":unittest.main()
