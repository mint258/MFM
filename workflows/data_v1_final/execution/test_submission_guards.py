"""Small boundary tests for preventing unauthorized or duplicate CPU submissions."""
import copy, importlib.util, tempfile, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("submit_reviewed",Path(__file__).with_name("submit_reviewed.py"))
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class Guards(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="dv1_guard_")
        self.script=Path(self.tmp.name)/"pilot.sbatch"
        self.script.write_text("#!/bin/bash\n#SBATCH --job-name=dv1_test\n#SBATCH --partition=cpu\n#SBATCH --nodelist=compute-0-14\n#SBATCH --nodes=1\n#SBATCH --ntasks=1\n#SBATCH --cpus-per-task=16\n#SBATCH --mem=32G\n#SBATCH --time=01:00:00\ntrue\n")
        self.request={"kind":"conformer","node":"compute-0-14","cpus":16,"memory_gib":32,
                      "wall_seconds":3600,"estimated_peak_output_bytes":1024**3,"pilot":True,
                      "root_review":{"status":"APPROVED"},"source_references":[],
                      "script_reference":mod.file_ref(self.script)}
    def tearDown(self): self.tmp.cleanup()
    def test_valid(self):
        self.assertEqual(mod.validate_request(self.request),"dv1_test")
    def test_quota_zero_soft_is_not_zero_capacity(self):
        self.assertEqual(mod.quota_available_bytes("  /dev/sda1 10 0 100 0 2 0 0\n"),90*1024)
        with self.assertRaises(ValueError): mod.quota_available_bytes("/dev/sda1 10 0 0 0 2 0 0")
    def test_memory_units_and_wall(self):
        self.assertEqual(mod.memory_mib("32G"),32768)
        self.assertEqual(mod.memory_mib("1024K"),1)
        self.assertEqual(mod.wall_seconds("2-00:00:00"),172800)
        with self.assertRaises(ValueError): mod.wall_seconds("01:61:00")
    def test_unauthorized_nodes(self):
        for node in ("compute-0-20","compute-0-13","202.38.252.202"):
            with self.subTest(node=node):
                req=copy.deepcopy(self.request);req["node"]=node
                with self.assertRaises(AssertionError): mod.validate_request(req)
    def test_cpu_wall_budget_boundaries(self):
        for key,value in (("cpus",15),("wall_seconds",172801),("estimated_peak_output_bytes",-1)):
            with self.subTest(key=key):
                req=copy.deepcopy(self.request);req[key]=value
                with self.assertRaises(AssertionError): mod.validate_request(req)
    def test_unreviewed_request(self):
        req=copy.deepcopy(self.request);req["root_review"]["status"]="PENDING"
        with self.assertRaises(AssertionError): mod.validate_request(req)
    def test_modified_pinned_source(self):
        self.script.write_text(self.script.read_text()+"echo changed\n")
        with self.assertRaises(AssertionError): mod.validate_request(self.request)
    def test_sbatch_directives_must_match_request(self):
        self.script.write_text(self.script.read_text().replace("--mem=32G","--mem=64G"))
        self.request["script_reference"]=mod.file_ref(self.script)
        with self.assertRaises(AssertionError): mod.validate_request(self.request)
    def test_crlf_and_gpu_directives_refused(self):
        original=self.script.read_bytes()
        for data in (original.replace(b"\n",b"\r\n"), original+b"#SBATCH --gres=gpu:1\n"):
            with self.subTest(data=data[-30:]):
                self.script.write_bytes(data);self.request["script_reference"]=mod.file_ref(self.script)
                with self.assertRaises(AssertionError): mod.validate_request(self.request)
    def test_large_formal_request_requires_accepted_pilot(self):
        req=copy.deepcopy(self.request);req.update(pilot=False,estimated_total_core_hours=501)
        with self.assertRaises(KeyError): mod.validate_request(req)
    def test_job_id_survives_controller_readback_failure_and_prevents_retry(self):
        import json, sys
        from unittest import mock
        run_root=Path(self.tmp.name)/"run"
        request_path=Path(self.tmp.name)/"request.json"
        request_path.write_text(json.dumps(self.request))
        def fake_query(argv):
            if argv[:2]==["quota","-v"]: return "/dev/sda1 10 0 1000000000 0 2 0 0\n"
            if argv[0]=="squeue": return ""
            if argv[0]=="sinfo": return "compute-0-14|cpu|idle|0/96/0/96|375000\n"
            if argv[:3]==["scontrol","show","node"]:
                return "NodeName=compute-0-14 CPUTot=96 CPUAlloc=0 RealMemory=375000 AllocMem=0"
            if argv[:3]==["scontrol","show","job"]: raise RuntimeError("Controller readback unavailable")
            raise AssertionError(argv)
        completed=mod.subprocess.CompletedProcess([],0,stdout="12345\n",stderr="")
        with mock.patch.object(mod,"ROOT",run_root), \
             mock.patch.object(mod,"PROJECT",Path(self.tmp.name)), \
             mock.patch.object(mod.os,"getuid",return_value=1278), \
             mock.patch.object(mod.socket,"gethostname",return_value="sonmi"), \
             mock.patch.object(mod,"query",side_effect=fake_query), \
             mock.patch.object(mod.subprocess,"run",return_value=completed) as submit, \
             mock.patch.object(sys,"argv",["submit_reviewed.py","--request",str(request_path)]):
            with self.assertRaisesRegex(RuntimeError,"Controller readback"): mod.main()
            receipt=json.loads((run_root/"control/submissions/dv1_test.json").read_text())
            self.assertEqual(receipt["job_id"],"12345")
            with self.assertRaisesRegex(AssertionError,"already registered"): mod.main()
            self.assertEqual(submit.call_count,1)

if __name__=="__main__": unittest.main(verbosity=2)
