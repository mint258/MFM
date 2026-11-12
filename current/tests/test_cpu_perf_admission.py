"""Resource admission checks, without GPU work or scheduler mutations."""
import importlib.util
from pathlib import Path
import unittest
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


if __name__=='__main__': unittest.main()
