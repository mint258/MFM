"""Native D transport contracts and a real owned CPU process handoff; no GPU work."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.d_recipe.gpu_native import (native_payload, request_once, require_transport,
    gpu_facts, require_readout_window, ReadoutDeferred)
from tools.d_recipe.gpu_takeover import continuation, load_waiter
from tools.d_recipe.training import prepare_runtime
from tools.d_recipe.shared_admission import atomic_json

REPO = Path(__file__).resolve().parents[1]


class NativeGPUContracts(unittest.TestCase):
    def setUp(self):
        self.original = json.loads((REPO / "configs/d_recipe/continuations/L1_from2090752_GPU20_20261126.json").read_text())
        execution = "ssh:P_D_contract_fixture"
        receipt = ("/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/exit_control/"
            + self.original["run"] + "/P_D_contract_fixture/receipt.json")
        self.c = native_payload(self.original, execution, receipt)
        self.c.update(cores=list(range(5)), cleanup_seconds=900, expected_readout_seconds=7200,
                      native_hard_end_epoch=10000)

    def test_scientific_binding_and_actual_native_routing(self):
        self.assertEqual(prepare_runtime(self.original)["d_recipe"]["scientific_binding"],
                         prepare_runtime(self.c)["d_recipe"]["scientific_binding"])
        require_transport(self.c, "compute-0-20", self.c["gpu_uuid"], range(5))
        for node, cores in (("compute-0-21", range(5)), ("compute-0-20", range(3))):
            with self.assertRaises(ValueError):
                require_transport(self.c, node, self.c["gpu_uuid"], cores)

    def test_gpu_threshold_and_unknown_capacity_refuse(self):
        self.assertEqual(gpu_facts(self.c, [self.c["gpu_uuid"], "fixture", "30000", "100000"])["used_MiB"], 30000)
        for value in ("30001", "nan", "-1"):
            with self.assertRaises(ValueError):
                gpu_facts(self.c, [self.c["gpu_uuid"], "fixture", value, "100000"])

    def test_stop_request_is_idempotent_and_uses_real_ssh_handle(self):
        with tempfile.TemporaryDirectory() as directory:
            c = dict(self.c, handoff_request=str(Path(directory) / "request.json"))
            check = Mock()
            first = request_once(c, check, atomic_json)
            self.assertEqual(first, request_once(c, check, atomic_json))
            self.assertEqual(first["job_id"], c["ssh_execution_id"])
            check.assert_called_once()

    def test_readout_defers_before_encoder_when_work_window_is_insufficient(self):
        with tempfile.TemporaryDirectory() as directory:
            c = dict(self.c, handoff_request=str(Path(directory) / "request.json"))
            require_readout_window(c, now=100)
            with self.assertRaises(ReadoutDeferred):
                require_readout_window(c, now=2000)
            Path(c["handoff_request"]).write_text("{}")
            with self.assertRaises(ReadoutDeferred):
                require_readout_window(c, now=100)

    def test_saved_ack_resumes_same_run_and_finished_source_is_not_repeated(self):
        c = self.c
        bound = dict(pid=99999999, start_ticks=1, uids=[1278]*4, cgroup="fixture")
        record = dict(execution_id=c["ssh_execution_id"], node=c["node"], gpu_uuid=c["gpu_uuid"],
            status="CURSOR_SAVED_NOT_COMPLETE", returncode=75, owned_tree_reaped=True,
            remaining_children=[], supervisor=bound, parent=bound, launcher=bound)
        phase = dict(status="HANDOFF_SAVED", execution_id=c["ssh_execution_id"], run=c["run"],
            request_id="original", scientific_binding=prepare_runtime(c)["d_recipe"]["scientific_binding"])
        request = dict(run=c["run"], action="SAVE_AND_EXIT", execution_id=c["ssh_execution_id"], request_id="original")
        checkpoint = Path(c["output"]) / "samples_2090784.pt"
        ack = dict(run=c["run"], job_id=c["ssh_execution_id"], request_id="original",
                   checkpoint=str(checkpoint), clock=dict(samples_consumed=2090784))
        table = {c["native_phase_state"]: phase, c["handoff_request"]: request, c["handoff_ack"]: ack}
        stat = Mock()
        resumed = continuation(c, record, reader=lambda p: table[str(p)], identity=lambda p: None, checkpoint_stat=stat)
        self.assertEqual((resumed["run"], resumed["output"]), (c["run"], c["output"]))
        self.assertEqual(resumed["resume"], str(checkpoint))
        self.assertEqual(resumed["execution"], "Slurm")
        self.assertNotIn("ssh_execution_id", resumed)
        self.assertNotIn("safe_exit_control", resumed)
        stat.assert_called_once_with(checkpoint)
        with self.assertRaisesRegex(ValueError, "still exists"):
            continuation(c, record, reader=lambda p: table[str(p)],
                identity=lambda p: SimpleNamespace(pid=p, start_ticks=1, uids=(1278,)*4, cgroup="fixture"),
                checkpoint_stat=stat)
        record.update(status="COMPLETE", returncode=0)
        phase["status"] = "GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS"
        self.assertIsNone(continuation(c, record, reader=lambda p: table[str(p)],
                                       identity=lambda p: None, checkpoint_stat=Mock(side_effect=AssertionError("No repeat"))))

    def test_completed_training_continues_original_readouts_without_retraining(self):
        from tools.d_recipe import train
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            c = dict(self.c, output=str(output))
            prepared = prepare_runtime(c)
            summary = dict(status="TRAINING_COMPLETE_EVALUATION_PENDING", run=c["run"], samples=c["samples"])
            (output / "summary.json").write_text(json.dumps(summary))
            (output / "configuration.json").write_text(json.dumps(prepared))
            phase = dict(status="TRAINING_COMPLETE_READOUT_DEFERRED", samples=c["samples"],
                run=c["run"], execution_id=c["ssh_execution_id"], scientific_binding=prepared["d_recipe"]["scientific_binding"])
            bound = dict(pid=99999999, start_ticks=1, uids=[1278]*4, cgroup="fixture")
            record = dict(execution_id=c["ssh_execution_id"], node=c["node"], gpu_uuid=c["gpu_uuid"],
                status="CURSOR_SAVED_NOT_COMPLETE", returncode=75, owned_tree_reaped=True,
                remaining_children=[], supervisor=bound, parent=bound, launcher=bound)
            table = {c["native_phase_state"]: phase, str(output / "summary.json"): summary}
            selected = continuation(c, record, reader=lambda p: table[str(p)],
                identity=lambda pid: None, checkpoint_stat=Mock())
            trainer = Mock(side_effect=AssertionError("Closed training must not repeat"))
            evaluator = Mock(return_value={})
            checkpoint = output / "samples_3000000.pt"
            with patch.dict(sys.modules, torch=SimpleNamespace(cuda=SimpleNamespace(empty_cache=Mock()))):
                result = train.run(selected, trainer=trainer, evaluator=evaluator,
                    checkpoint_resolver=lambda cfg, samples: checkpoint, publish=Mock())
            trainer.assert_not_called()
            evaluator.assert_called_once()
            self.assertEqual(evaluator.call_args.args[0]["checkpoint"], str(checkpoint))
            self.assertEqual(result["status"], "GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS")


CHILD = r'''import json,os,signal,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from tools.d_recipe.gpu_native import request_once
from tools.d_recipe.shared_admission import atomic_json
root=Path(sys.argv[2]);receipt=root/"receipt.json"
c=dict(run="owned_control_fixture",ssh_execution_id="ssh:P_D_owned_control_fixture",handoff_request=str(root/"request.json"))
def identity():
 p=Path("/proc")/str(os.getpid());raw=(p/"stat").read_text();f=raw[raw.rfind(")")+2:].split()
 return dict(pid=os.getpid(),start_ticks=int(f[19]),uids=[int(x) for x in next(l for l in (p/"status").read_text().splitlines() if l.startswith("Uid:")).split()[1:]],cgroup=(p/"cgroup").read_text())
me=identity();r=dict(execution_id=c["ssh_execution_id"],node=os.uname().nodename,gpu_uuid="NO_GPU_FIXTURE",supervisor=me,launcher=me,status="RUNNING")
def stop(sig,frame):
 value=request_once(c,lambda path:None,atomic_json)
 atomic_json(root/"ack.json",dict(request_id=value["request_id"],job_id=value["job_id"],synthetic_state=dict(optimizer=7,clock=37,RNG="retained")))
 r.update(status="CURSOR_SAVED_NOT_COMPLETE",returncode=75,owned_tree_reaped=True,remaining_children=[])
 atomic_json(receipt,r);raise SystemExit(75)
signal.signal(signal.SIGUSR1,stop)
atomic_json(receipt,r);print("READY",flush=True)
time.sleep(30)
'''


class RealOwnedControlHandoff(unittest.TestCase):
    def test_existing_waiter_requests_our_original_protocol_then_observes_actual_exit(self):
        waiter = load_waiter()
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.Popen([sys.executable, "-B", "-c", CHILD, str(REPO), directory],
                stdout=subprocess.PIPE, text=True, start_new_session=True)
            try:
                self.assertEqual(process.stdout.readline().strip(), "READY")
                c = dict(ssh_runtime_receipt=str(Path(directory) / "receipt.json"),
                    ssh_execution_id="ssh:P_D_owned_control_fixture", node=os.uname().nodename,
                    gpu_uuid="NO_GPU_FIXTURE", work_unit_seconds=1)
                def identity(pid):
                    process.poll()
                    return waiter.lifecycle.identity(pid)
                with patch.dict(os.environ, P_MANAGED_STOP_NEW_UNITS_AT=str(time.time()+60)):
                    self.assertEqual(waiter.wait_for_source(c, SimpleNamespace(requested=False),
                                     identity=identity, poll=.01), "RESUME_READY")
                self.assertEqual(process.wait(timeout=3), 75)
                self.assertIsNone(waiter.lifecycle.identity(process.pid))
                ack = json.loads((Path(directory) / "ack.json").read_text())
                self.assertEqual(ack["job_id"], c["ssh_execution_id"])
                self.assertEqual(ack["synthetic_state"], dict(optimizer=7, clock=37, RNG="retained"))
            finally:
                if process.poll() is None:
                    bound = waiter.lifecycle.identity(process.pid)
                    scope = next(x for x in bound.cgroup.splitlines() if x.startswith("0::"))
                    waiter.lifecycle.signal_owned(bound, signal.SIGTERM, uid=os.getuid(), scope=scope)
                    process.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
