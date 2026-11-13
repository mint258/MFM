"""Resource admission checks, without GPU work or scheduler mutations."""
import importlib.util
from pathlib import Path
import unittest
import tempfile
import sys,json
from types import SimpleNamespace
from unittest.mock import patch
path=Path(__file__).parents[2]/'tools/model_v3/cpu_perf_wait.py'
spec=importlib.util.spec_from_file_location('cpu_wait',path)
wait=importlib.util.module_from_spec(spec);spec.loader.exec_module(wait)


class AdmissionTests(unittest.TestCase):
    def test_cpu_sdk_and_held_job_do_not_reserve_gpu_and_eight_cores_are_admitted(self):
        def command(argv):
            if argv[0]=='squeue':
                return '11|PENDING|Dependency|v3-sdk-A2-P\n12|PENDING|JobHeldUser|old\n13|RUNNING|None|v3-T1-A2-P'
            if argv[:3]==['scontrol','show','job']:
                self.assertEqual(argv[3],'13')
                return 'ReqNodeList=compute-0-0 NodeList=compute-0-0'
            if argv[:3]==['scontrol','show','hostnames']:
                return argv[3]
            if argv[:3]==['scontrol','show','node']:
                return 'CPUTot=104 CPUAlloc=96 State=MIXED'
            if argv[0]=='ssh':
                return 'GPU-test, NVIDIA GeForce RTX 4090'
            self.fail(argv)
        with patch.object(wait,'command',side_effect=command), patch.object(wait,'NODES',('compute-0-20',)):
            plan,_=wait.choose()
        self.assertEqual((plan['node'],plan['gpu'],plan['cores']),('compute-0-20','GPU-test',8))
        self.assertEqual(plan['python'],wait.PYTHON128)

    def test_model_chain_is_skipped_and_low_cpu_falls_back_to_free_3090(self):
        def command(argv):
            if argv[0]=='squeue': return '13|PENDING|Dependency|v3-T1-A2-P'
            if argv[:3]==['scontrol','show','job']: return 'ReqNodeList=compute-0-0'
            if argv[:3]==['scontrol','show','hostnames']: return argv[3]
            if argv[:3]==['scontrol','show','node']:
                return 'CPUTot=48 CPUAlloc=45 State=MIXED' if argv[3]=='compute-0-20' else 'CPUTot=48 CPUAlloc=44 State=MIXED'
            if argv[0]=='ssh':
                self.assertEqual(argv[-2],'compute-0-4')
                return 'GPU-test, NVIDIA GeForce RTX 3090'
            self.fail(argv)
        with patch.object(wait,'command',side_effect=command), patch.object(wait,'NODES',('compute-0-0','compute-0-20','compute-0-4')):
            plan,observations=wait.choose()
        self.assertEqual(plan['cores'],4)
        self.assertEqual(plan['python'],wait.PYTHON118)
        self.assertEqual(observations[0]['status'],'MODEL_LINE_RESERVED')
        self.assertEqual(observations[1]['status'],'CPU_UNAVAILABLE')

    def test_busy_gpu_is_not_admitted(self):
        def command(argv):
            if argv[0]=='squeue': return ''
            if argv[0]=='scontrol': return 'CPUTot=104 CPUAlloc=96 State=MIXED'
            return 'GPU-test, NVIDIA GeForce RTX 4090\nGPU-test, 1234'
        with patch.object(wait,'command',side_effect=command), patch.object(wait,'NODES',('compute-0-20',)):
            plan,_=wait.choose()
        self.assertIsNone(plan)


    def test_known_binding_reserves_only_one_card_on_a_dual_gpu_node(self):
        a='GPU-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        b='GPU-22222222-2222-2222-2222-222222222222'
        def command(argv):
            if argv[0]=='squeue':return '13|PENDING|Dependency|v3-H2-P'
            if argv[:3]==['scontrol','show','job']:
                return 'ReqNodeList=compute-0-21 Command=runner config.json '+a.upper()
            if argv[:3]==['scontrol','show','node']:return 'CPUTot=104 CPUAlloc=16 State=MIXED'
            if argv[0]=='ssh':return a+', NVIDIA GeForce RTX 5090\n'+b+', NVIDIA GeForce RTX 5090'
            self.fail(argv)
        with patch.object(wait,'command',side_effect=command),patch.object(wait,'NODES',('compute-0-21',)):
            plan,observations=wait.choose()
        self.assertEqual(plan['gpu'],b)
        self.assertEqual(observations[0]['reserved_gpus'],[a])

    def test_pending_bound_card_is_not_taken_when_other_card_is_busy(self):
        a='GPU-11111111-1111-1111-1111-111111111111'
        b='GPU-22222222-2222-2222-2222-222222222222'
        def command(argv):
            if argv[0]=='squeue':return '13|PENDING|Dependency|v3-H2-P'
            if argv[:3]==['scontrol','show','job']:
                return 'ReqNodeList=compute-0-21 Command=runner config.json '+a
            if argv[:3]==['scontrol','show','node']:return 'CPUTot=104 CPUAlloc=16 State=MIXED'
            if argv[0]=='ssh':return a+', NVIDIA GeForce RTX 5090\n'+b+', NVIDIA GeForce RTX 5090\n'+b+', 999'
            self.fail(argv)
        with patch.object(wait,'command',side_effect=command),patch.object(wait,'NODES',('compute-0-21',)):
            plan,_=wait.choose()
        self.assertIsNone(plan)

class SamplerReadinessTests(unittest.TestCase):
    def test_native_sampler_waits_for_post_warmup_data_row(self):
        runner_path=Path(__file__).parents[2]/'tools/model_v3/cpu_bottleneck_step1.py'
        spec=importlib.util.spec_from_file_location('cpu_step1',runner_path)
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'segments.csv'
            self.assertFalse(runner.measured_updates_available(path))
            path.write_text('step,forward,total\n')
            self.assertFalse(runner.measured_updates_available(path))
            with path.open('a') as file:
                file.write('101,0.2,0.3\n')
            self.assertTrue(runner.measured_updates_available(path))


class CapacityDebitTests(unittest.TestCase):
    def test_allocated_model_and_own_files_are_not_charged_twice(self):
        runner_path=Path(__file__).parents[2]/'tools/model_v3/cpu_bottleneck_step1.py'
        spec=importlib.util.spec_from_file_location('cpu_step1_budget',runner_path)
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        model=[30_000_000_000,70_000_000_000]
        used=[100_000_000]
        guard=SimpleNamespace(model_growth_forecast=lambda:tuple(model),remaining_d6=lambda:0)
        loader=SimpleNamespace(exec_module=lambda module:None)
        disk=SimpleNamespace(filesystem_status=lambda path:{}, require_capacity=lambda *args:None)
        quota=json.dumps(dict(schema='XFS_USER_QUOTA_AVAILABLE_V1',uid=runner.os.getuid(),
            filesystem='/share',observed_time=1000.,available_bytes=200_000_000_000))
        with tempfile.TemporaryDirectory() as directory:
            scratch=Path(directory)
            with patch.object(runner,'SCRATCH',scratch),patch.object(runner.time,'time',return_value=1000.), \
                 patch.dict(sys.modules,{'phychem_mfm.phase1.v2_disk':disk}), \
                 patch.object(runner,'query',side_effect=lambda *args:f'/lfshome {used[0]} 0 300000000 -'), \
                 patch.object(Path,'read_text',return_value=quota), \
                 patch.object(runner.importlib.util,'spec_from_file_location',return_value=SimpleNamespace(loader=loader)), \
                 patch.object(runner.importlib.util,'module_from_spec',return_value=guard):
                first=runner.capacity()
                path=scratch/'retained_checkpoint'
                path.write_bytes(b'x'*(1024**2))
                allocated=path.stat().st_blocks*512
                model[0]+=1024**2;model[1]-=1024**2
                used[0]+=(allocated+1024**2)//1024
                second=runner.capacity()
            self.assertEqual(second['own_allocated_bytes'],allocated)
            self.assertEqual(first['available_bytes']-first['required_bytes'],
                             second['available_bytes']-second['required_bytes'])

if __name__=='__main__': unittest.main()
