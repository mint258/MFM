"""One pure-mock quota publisher transport regression; zero file operations."""
import argparse,subprocess,unittest
from contextlib import ExitStack
from unittest.mock import Mock,patch
from . import lustre_non_native_writer_guard as G
from workflows.data_v1_final.export.v31_stream_v1 import quota_snapshot as Q

class LustreQuotaTransport(unittest.TestCase):
    def test_one_held_publisher_probe_failure_and_unchanged_capacity_transport(self):
        class StopLoop(BaseException):pass
        text='Disk quotas for usr zixiao (uid 1278):\nFilesystem kbytes quota limit grace files quota limit grace\n/lfshome 1098705652 0 2147483648 - 38481903 0 0 -\nuid 1278 is using default file quota setting\n'
        output='/share/synthetic-fresh-quota.json'
        profile={'quota_clock_safety_bias_seconds':1.25,'nodes':{'compute-0-19':{'reference':'synthetic-capacity.json'}}}
        values=[];sleeps=[];admit=[]
        class Publisher:
            def __init__(self,path,check):self.path=path;self.check=check;self.closed=False;self.close_calls=0
            def publish(self,value):self.check(value['available_bytes']);values.append(value)
            def close(self):self.close_calls+=1;self.closed=True
        publisher=[]
        def factory(path,check):
            instance=Publisher(path,check);publisher.append(instance);return instance
        def sleep(delay):
            sleeps.append(delay)
            if len(sleeps)==2:self.assertEqual([v['source_probe_time'] for v in values],[100.0])
            if len(sleeps)==3:raise StopLoop()
        with ExitStack() as stack:
            stack.enter_context(patch.object(G.os,'getuid',return_value=1278))
            stack.enter_context(patch.object(G,'load',return_value=profile))
            stack.enter_context(patch.object(G,'validate_profile'))
            stack.enter_context(patch.object(G,'control_admission',side_effect=lambda path:admit.append(path)))
            atomic=stack.enter_context(patch.object(G,'atomic'))
            stack.enter_context(patch('builtins.print'))
            construct=stack.enter_context(patch.object(Q,'AtomicPublisher',side_effect=factory))
            probe=stack.enter_context(patch.object(G.subprocess,'check_output',side_effect=[text,subprocess.CalledProcessError(1,['lfs']),text]))
            stack.enter_context(patch.object(G.time,'time',side_effect=[100.0,101.0,102.0]))
            stack.enter_context(patch.object(G.time,'monotonic',return_value=0))
            stack.enter_context(patch.object(G.time,'sleep',side_effect=sleep))
            args=argparse.Namespace(profile='synthetic-profile',mode='quota',output=output)
            with patch.object(argparse.ArgumentParser,'parse_args',return_value=args):
                with self.assertRaises(StopLoop):G.main()
            self.assertEqual(construct.call_count,1);self.assertEqual(len(publisher),1)
            self.assertEqual(publisher[0].path,output);self.assertTrue(publisher[0].closed);self.assertEqual(publisher[0].close_calls,1)
            self.assertEqual([v['source_probe_time'] for v in values],[100.0,102.0])
            self.assertEqual([v['observed_time'] for v in values],[98.75,100.75])
            self.assertEqual(admit,[output,output]);atomic.assert_not_called()
            self.assertEqual(probe.call_count,3)
            for call in probe.call_args_list:self.assertEqual(call.kwargs,{'text':True,'timeout':2})
        # Capacity retains its previous sampler -> atomic path and no held publisher.
        with ExitStack() as stack:
            stack.enter_context(patch.object(G.os,'getuid',return_value=1278));stack.enter_context(patch.object(G,'load',return_value=profile))
            stack.enter_context(patch.object(G,'validate_profile'));stack.enter_context(patch.object(G.socket,'gethostname',return_value='compute-0-19'))
            snapshot={'schema':'synthetic-capacity'};sampler=Mock();sampler.sample.return_value=snapshot
            stack.enter_context(patch.object(G,'CapacitySampler',return_value=sampler))
            construct=stack.enter_context(patch.object(Q,'AtomicPublisher'))
            atomic=stack.enter_context(patch.object(G,'atomic'))
            stack.enter_context(patch.object(G.time,'monotonic',return_value=0));stack.enter_context(patch.object(G.time,'sleep',side_effect=StopLoop()))
            args=argparse.Namespace(profile='synthetic-profile',mode='capacity',node='compute-0-19')
            with patch.object(argparse.ArgumentParser,'parse_args',return_value=args):
                with self.assertRaises(StopLoop):G.main()
            construct.assert_not_called();atomic.assert_called_once_with('synthetic-capacity.json',snapshot)
            sampler.sample.assert_called_once_with()