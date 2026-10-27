"""Four pure resource boundaries; no filesystem, scheduler or real subprocess."""
from contextlib import contextmanager
import unittest
from . import capacity_gate as G


class CapacityBoundaries(unittest.TestCase):
    def run_case(self,raw,action=None,busy=False):
        events=[]
        @contextmanager
        def lock():
            if busy:raise BlockingIOError(11,'busy')
            events.append('acquired')
            try:yield 91
            finally:events.append('released')
        def read():events.append('read');return raw
        def transition(fd):
            self.assertEqual(fd,91);self.assertNotIn('released',events);events.append('intent-and-submit')
            if action:action()
        return G.guarded_transition(read,transition,lock),events

    def test_free14_waits_without_transition_intent_or_submission(self):
        result,events=self.run_case('NodeName=compute-0-13 Partitions=cpu CPUTot=96 CPUAlloc=82')
        self.assertEqual(result['action'],'WAIT_EXISTING_JOBS_OR_CAPACITY');self.assertEqual(result['observation']['free_cpus'],14)
        self.assertEqual(events,['acquired','read','released'])

    def test_exact16_calls_original_path_once_while_locked(self):
        result,events=self.run_case('NodeName=compute-0-13 Partitions=cpu CPUTot=96 CPUAlloc=80')
        self.assertEqual(result['action'],'TRANSITION_FINISHED');self.assertEqual(events.count('intent-and-submit'),1)
        self.assertEqual(events,['acquired','read','intent-and-submit','released'])

    def test_busy_outer_lock_never_queries_or_creates_intent(self):
        result,events=self.run_case('unused',busy=True)
        self.assertEqual(result['reason'],'OUTER_SUBMISSION_SERIALIZATION_LOCK_BUSY');self.assertEqual(events,[])

    def test_malformed_node_or_inner_EAGAIN_still_propagates_to_HOLD(self):
        for raw in ('NodeName=compute-0-19 Partitions=cpu CPUTot=96 CPUAlloc=80',
                    'NodeName=compute-0-13 Partitions=cpu CPUTot=96 CPUAlloc=100'):
            with self.assertRaises(ValueError):self.run_case(raw)
        def error():raise BlockingIOError(11,'inner activation failed')
        with self.assertRaises(BlockingIOError):self.run_case('NodeName=compute-0-13 Partitions=cpu CPUTot=96 CPUAlloc=80',error)
