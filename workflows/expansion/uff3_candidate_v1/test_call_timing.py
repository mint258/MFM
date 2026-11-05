"""Actual tiny journal and identity-preserving per-call instrumentation."""
from pathlib import Path
import tempfile
import unittest
from .call_timing import CallTimings,TimedKernel
from .store import Journal,read_events


class TimingTests(unittest.TestCase):
    def test_same_objects_order_exception_and_existing_event_count(self):
        result=object();row={'conformer_id':0};calls=[]
        class Original:
            sentinel=result
            def prepare(self,source):calls.append(('prepare',source));return result
            def embed(self,seed,count):
                calls.append(('embed',seed,count));raise ValueError('original failure')
            def optimize(self,candidate):calls.append(('optimize',candidate));return result
            def d3(self,value):calls.append(('d3',value));return result
        wall=iter(range(0,80,10));cpu=iter(range(0,24,3))
        timing=CallTimings(lambda:next(wall),lambda:next(cpu));kernel=TimedKernel(Original(),timing)
        self.assertIs(kernel.sentinel,result)
        with tempfile.TemporaryDirectory()as folder:
            path=Path(folder)/'events.jsonl';journal=Journal(path);journal.timing=timing
            self.assertIs(kernel.prepare(row),result);journal.emit({'phase':'graph_return'})
            with self.assertRaisesRegex(ValueError,'original failure'):kernel.embed(7,30)
            journal.emit({'phase':'cache_closed'})
            self.assertIs(kernel.optimize(4),result);journal.emit({'phase':'optimizer_return','candidate_id':4})
            self.assertIs(kernel.d3(row),result);journal.emit({'phase':'descriptor_return','conformer':row})
            journal.close();events=read_events(path)
            self.assertEqual(len(events),4)
            self.assertEqual(events[1]['native_call_timings_without_matching_return'][0]['error_type'],'ValueError')
            self.assertEqual([e['native_call_timing']['operation']for e in events if 'native_call_timing'in e],['prepare','optimize','d3'])
            self.assertEqual(events[0]['native_call_timing']['wall_nanoseconds'],10)
            self.assertEqual(events[0]['native_call_timing']['process_CPU_nanoseconds'],3)
        self.assertEqual(calls,[('prepare',row),('embed',7,30),('optimize',4),('d3',row)])
        self.assertEqual(timing.pending,{})


if __name__=='__main__':unittest.main()
