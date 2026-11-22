"""Actual GPU protect remains the original peer-aware GPU path, never the CPU producer gate."""
import copy,json,os,time,types,unittest
from pathlib import Path
from unittest.mock import patch
from .idle_gpu_confirmation import prepare_script,PLACEMENTS,select_pending_rows
from .gpu_runtime import GpuRuntime,MODEL_RESERVE,GIB
from workflows.benchmark_data import acquire,storage_reservations,admission
class IdleGpuTailTests(unittest.TestCase):
    def row_script(self):
        task=dict(feature_group="Pprime_plus_D",learner="TabPFN",primary_source_job="4537316",confirmation_seed="20261026",primary_seed="20261025",fold_and_statistics_seed="20261025",reason="FINAL_SIGNIFICANT_IMPROVEMENT",frozen_B1_role="RETAIN",task_roster_reselection="False",original_labels_or_masks_changed="False",dataset="Joung2020",producer_task="emi FWHM (nm)")
        env={"BENCHMARK_MODEL":"C1-TabPFN-Pprime_plus_D","BENCHMARK_TASK_INDEX":"8","LOKY_MAX_CPU_COUNT":"2","TABPFN_ALLOW_CPU_LARGE_DATASET":"1"}
        group=dict(primary_job="4537316",feature_group="Pprime_plus_D",learner="TabPFN",array=False,required_tasks=[task],environment=env,node="compute-0-7",uuid="GPU-original")
        row=dict(replaced_CPU_job=4538359,group_index=29,group=group,execution_environment=env)
        script="#SBATCH --cpus-per-task=2\n#SBATCH --nodelist=compute-0-7\n#SBATCH --output=old\n"
        script+="".join("export "+k+"="+v+"\n" for k,v in env.items())
        script+="_gpu_runtime=module.GpuRuntime(root,snapshot,gpu_uuid='GPU-original',expected_node='compute-0-7')\nprogram=Path('original.py').read_text()\nORIGINAL_GPU_PROTECT_AND_SHARED_RESERVATIONS\n"
        return row,script
    def test_only_registered_card_placements(self):
        self.assertEqual(set(PLACEMENTS),{4538349,4538350,4538352,4538353,4538359,4538360})
        self.assertEqual({v[1] for v in PLACEMENTS.values()},{"compute-0-5","compute-0-6"})
    def test_unknown_tail_refused(self):
        with self.assertRaises(ValueError):prepare_script({"replaced_CPU_job":1},"original")
    def test_original_gpu_guard_and_body_loading_preserved(self):
        row,script=self.row_script();result=prepare_script(row,script)
        self.assertIn("ORIGINAL_GPU_PROTECT_AND_SHARED_RESERVATIONS",result)
        self.assertIn("program=Path('original.py').read_text()",result)
        self.assertNotIn("_shared_storage_protect",result)
        self.assertNotIn("module.GpuRuntime.protect=",result)
        self.assertIn("expected_node='compute-0-5'",result)
    def test_changed_selector_refused(self):
        row,script=self.row_script();row=copy.deepcopy(row);row["execution_environment"]["BENCHMARK_TASK_INDEX"]="7"
        with self.assertRaises(ValueError):prepare_script(row,script)
    def runtime(self):
        runtime=GpuRuntime.__new__(GpuRuntime);runtime.root=storage_reservations.OWNED_SCOPES[0]
        runtime.local_capacity=lambda:{"actual_GPU_node":"compute-0-5"}
        runtime.quantum_future=lambda:0
        return runtime
    def test_actual_gpu_protect_does_not_call_cpu_only_admission(self):
        r=self.runtime();snapshot=Path("/unit/quota.json");q=dict(uid=os.getuid(),generation="benchmarkB020261119",returncode=0,observed_epoch=time.time(),raw="native")
        with patch.object(admission,"protect",side_effect=AssertionError("CPU-only gate")),patch("workflows.benchmark_evaluation.gpu_runtime.quota_observation",return_value=10**12),patch("workflows.benchmark_evaluation.gpu_runtime.guard") as gate,patch.object(Path,"read_text",return_value=json.dumps(q)):
            r.protect(r.root,123,snapshot,own_concurrent_bytes=40*GIB)
        self.assertEqual(gate.call_args.args[0],r.root)
        self.assertEqual(gate.call_args.args[-1],MODEL_RESERVE+40*GIB)
    def policy(self,peer=0):
        components={k:0 for k in storage_reservations.COMPONENTS};components["model_P_NFS"]=200*GIB;components["benchmark_B1_C1"]=40*GIB
        return dict(schema="benchmark-shared-storage-reservations-v1",components=components,owned_scopes=[str(p) for p in storage_reservations.OWNED_SCOPES],concurrent_total_bytes=sum(components.values()),node_local_tmp_peer_future_bytes={"compute-0-7":16*GIB,"compute-0-17":0,"compute-0-5":peer})
    def stat(self,available=100*GIB):
        return types.SimpleNamespace(f_blocks=100*GIB,f_frsize=1,f_bavail=available,f_favail=100000)
    def test_original_native_guard_applies_current_peer_pool_on_gpu(self):
        policy=self.policy()
        with patch.object(Path,"read_text",return_value=json.dumps(policy)),patch.object(storage_reservations.socket,"gethostname",return_value="compute-0-5"),patch.object(os,"statvfs",return_value=self.stat()),patch.object(acquire.subprocess,"check_output",return_value="Avail\n1000000000000\n"):
            with self.assertRaisesRegex(RuntimeError,"quota reserve"):
                acquire.guard(storage_reservations.OWNED_SCOPES[0],1,acquire.FLOOR+policy["concurrent_total_bytes"],time.monotonic(),MODEL_RESERVE+40*GIB)
    def test_original_native_guard_applies_gpu_local_peer_future(self):
        policy=self.policy(peer=16*GIB);available=10*GIB+16*GIB+16*1024**2-1
        with patch.object(Path,"read_text",return_value=json.dumps(policy)),patch.object(storage_reservations.socket,"gethostname",return_value="compute-0-5"),patch.object(os,"statvfs",return_value=self.stat(available)),patch.object(os,"stat",return_value=types.SimpleNamespace(st_dev=1)):
            with self.assertRaisesRegex(RuntimeError,"root/tmp"):
                storage_reservations.current_concurrent(storage_reservations.OWNED_SCOPES[0],MODEL_RESERVE+40*GIB)
    def test_original_gpu_quota_freshness_remains_required(self):
        r=self.runtime();q=dict(uid=os.getuid(),generation="benchmarkB020261119",returncode=0,observed_epoch=time.time()-1000,raw="native")
        with patch.object(Path,"read_text",return_value=json.dumps(q)):
            with self.assertRaisesRegex(RuntimeError,"quota observation"):r.protect(r.root,1,Path("/unit/quota.json"))

class PendingGpuQueueSelectionTests(unittest.TestCase):
    def test_running_and_closed_candidates_never_create_a_second_fit(self):
        rows=[{"replaced_CPU_job":j} for j in [4538349,4538350,4538352,4538353]]
        actual={4538349:{"state":"PENDING","exit_code":"0:0"},4538350:{"state":"RUNNING","exit_code":"0:0"},4538352:{"state":"COMPLETED","exit_code":"0:0"},4538353:{"state":"PENDING","exit_code":"0:0"}}
        self.assertEqual([r["replaced_CPU_job"] for r in select_pending_rows(rows,actual)],[4538349,4538353])
        self.assertEqual(actual[4538350]["state"],"RUNNING")
    def test_actual_source_failures_cannot_be_hidden_as_unstarted_queues(self):
        for state,exit_code in [("FAILED","1:0"),("TIMEOUT","0:0"),("CANCELLED","0:0"),("COMPLETED","1:0")]:
            with self.subTest(state=state),self.assertRaises(ValueError):
                select_pending_rows([{"replaced_CPU_job":4538349}],{4538349:{"state":state,"exit_code":exit_code}})
