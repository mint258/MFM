"""Three incremental resource checks; no corpus, science guard, or Slurm calls."""
import concurrent.futures, threading, unittest
from types import SimpleNamespace
from unittest.mock import patch
from .materialize import rebind
from .resource_runtime import SourceStatusSoftStop,drain_submit,soft_worker_rss

class ResourceSemantics(unittest.TestCase):
    def test_pressure_stops_dispatch_and_drains_sixteen_running_files(self):
        started=[];receipts=[];failures=[];lock=threading.Lock();all_started=threading.Event()
        pressure=threading.Event();release=threading.Event();peer_stop=threading.Event()
        def work(value):
            with lock:
                started.append(value)
                if len(started)==16:all_started.set()
            if not release.wait(5):raise RuntimeError('FIXTURE_RELEASE_TIMEOUT')
            return {'file_id':value}
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            def driver():
                try:drain_submit(list(range(48)),executor,work,receipts,pressure.is_set,peer_stop)
                except BaseException as exc:failures.append(exc)
            thread=threading.Thread(target=driver);thread.start()
            self.assertTrue(all_started.wait(5));pressure.set();release.set();thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(started),16);self.assertEqual(len(receipts),16)
        self.assertEqual(len(failures),1);self.assertIsInstance(failures[0],SourceStatusSoftStop)
        self.assertFalse(peer_stop.is_set())

    def test_complete_final_wave_with_late_pressure_keeps_full_file_set(self):
        receipts=[];peer=threading.Event();active=0;maximum=0;lock=threading.Lock()
        def work(value):
            nonlocal active,maximum
            with lock:active+=1;maximum=max(maximum,active)
            with lock:active-=1
            return value
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            drain_submit(list(range(48)),executor,work,receipts,lambda:len(receipts)==48,peer)
        self.assertEqual(sorted(receipts),list(range(48)));self.assertLessEqual(maximum,16);self.assertFalse(peer.is_set())

    def test_worker_soft_cap_and_resource_only_argv_rebinding(self):
        cap=3<<30;high=cap+1024
        with patch('resource.getrusage',return_value=SimpleNamespace(ru_maxrss=high//1024)), \
             patch('workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime.process_observation',return_value={'rss_bytes':cap,'pid':4}), \
             patch('workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime.mark_stop') as stop:
            self.assertEqual(soft_worker_rss(cap),high)
            self.assertEqual(stop.call_args.args[0],'SCAN_WORKER_SOFTWARE_RSS_CAP')
            self.assertEqual(stop.call_args.args[1]['software_cap_bytes'],cap)
        argv=['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B','-m',
          'workflows.data_v1_final.labels.source_status_v1.prepare','--config','/old/exact_config.json',
          '--output','/old/output','--startup-proof','/old/proof.json']
        old={'kind':'analysis','pilot':False,'execution_argv':argv[:]}
        stage,config,new=rebind(old,'/new/auto_memory/prepared')
        self.assertEqual(stage,'prepare');self.assertEqual(str(config),'/old/exact_config.json')
        self.assertEqual(old['execution_argv'],argv);self.assertEqual(new[new.index('--config')+1],'/old/exact_config.json')
        self.assertIn('__ROOT_STARTUP_PROOF__',new)

if __name__=='__main__':unittest.main()