"""Four new source/soft-stop/bounded-order boundaries; no corpus, UFF or QM."""
import threading,time,unittest
from .verify_source_v1 import prove_edit_map
from .memory import soft_denial
from .controls import SoftDispatchStop,bounded_thread_map

class AutoMemoryAdapterBoundaries(unittest.TestCase):
    def test_declared_source_edit_replays_and_rejects_extra_science_change(self):
        old=b'def f():\n    old_guard()\n    return 9\n';new=old.replace(b'old_guard()',b'new_guard()')
        edits=[{'old':'old_guard()','new':'new_guard()'}]
        self.assertTrue(prove_edit_map(old,new,edits)['inverse_full_file_bytes_equal'])
        with self.assertRaisesRegex(ValueError,'UNDECLARED_SOURCE_EDIT'):prove_edit_map(old,new.replace(b'return 9',b'return 8'),edits)
    def test_actual_memory_soft_limits_do_not_assert_slurm_allocation(self):
        limits={'algorithm_rss_soft_cap_bytes':1000,'minimum_mem_available_bytes':200}
        row={'metrics_available':True,'owned_rss_sum_bytes':999,'MemAvailable_bytes':200}
        self.assertIsNone(soft_denial(row,limits))
        self.assertEqual(soft_denial(dict(row,owned_rss_sum_bytes=1001),limits),'ALGORITHM_OWNED_RSS_SOFT_CAP')
        self.assertEqual(soft_denial(dict(row,MemAvailable_bytes=199),limits),'ACTUAL_MEMAVAILABLE_LOW')
        self.assertEqual(soft_denial({'metrics_available':False},limits),'ACTUAL_MEMORY_OBSERVATION_UNAVAILABLE')
    def test_bounded_thread_map_preserves_original_input_order(self):
        def compute(i):time.sleep((9-i%10)*.00005);return i*i
        self.assertEqual(bounded_thread_map(compute,list(range(80)),lambda:True),[i*i for i in range(80)])
    def test_soft_stop_submits_no_more_work_and_drains_already_submitted(self):
        calls=[];lock=threading.Lock();budget=[0]
        def allow():
            budget[0]+=1;return budget[0]<=5
        def compute(i):
            time.sleep(.0001)
            with lock:calls.append(i)
            return i*i
        with self.assertRaises(SoftDispatchStop) as caught:bounded_thread_map(compute,list(range(25)),allow)
        self.assertEqual(sorted(calls),list(range(5)))
        self.assertEqual(caught.exception.completed,[i*i for i in range(5)])
        self.assertEqual(caught.exception.total,25)
if __name__=='__main__':unittest.main()
