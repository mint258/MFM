"""Pending native new-backend/original-oracle fixtures; never auto-build a binary."""
import copy
import json
import os
from pathlib import Path
import random
import struct
import tempfile
import unittest
from unittest.mock import patch
from ..exact_nn_cached_v1 import engine as oracle
from . import backend
from ..exact_nn_popcount_cpp_v1 import backend as previous_backend
from concurrent.futures import ThreadPoolExecutor
from .artifacts import reference, write_new

CAP = 3 << 30


def raw(bits):
    result = bytearray(256)
    for bit in bits: result[bit // 8] |= 1 << (bit % 8)
    return bytes(result)


class NativeOracleParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get('EXACT_INVERTED_BUILD_MANIFEST')
        if not path:
            raise RuntimeError('Root must explicitly build in an admitted Linux allocation and set EXACT_INVERTED_BUILD_MANIFEST; no skipped pass')
        cls.build = reference(path)
        cls.kernel, cls.manifest = backend.load_kernel(cls.build)
        previous = os.environ.get('EXACT_POPCOUNT_BUILD_MANIFEST')
        if not previous: raise RuntimeError('Explicit independently built old popcount oracle required; no skipped parity')
        cls.previous_build = reference(previous)

    def compiled(self, references):
        result = backend.CompiledReference(iter(references), worker_rss_cap_bytes=CAP, build_manifest_reference=self.build)
        self.addCleanup(result.close)
        return result

    def compare(self, queries, references, all_orders=False):
        original = oracle.CachedReference(references, worker_rss_cap_bytes=CAP)
        native = self.compiled(references)
        previous = previous_backend.CompiledReference(iter(references), worker_rss_cap_bytes=CAP, build_manifest_reference=self.previous_build)
        self.addCleanup(previous.close)
        for query in queries:
            expected, observed = original.nearest(query), native.nearest(query)
            previous_value = previous.nearest(query)
            self.assertEqual(previous_value, expected)
            self.assertEqual(struct.pack('<d', previous_value['score']), struct.pack('<d', expected['score']))
            self.assertEqual(set(expected), set(observed))
            self.assertEqual(observed, expected)  # Includes exact un-reduced ints and debug group sequence.
            self.assertEqual(struct.pack('<d', observed['score']), struct.pack('<d', expected['score']))
        if all_orders:
            # Exhausts q-popcounts, forces >64 LRU insertions and revisits evicted qbits.
            for qbits in [*range(2049), 0, 2048, 11, 1]:
                self.assertEqual(native.order(qbits), original.order(qbits))
                self.assertEqual(previous.order(qbits), original.order(qbits))
        self.assertEqual(native.reference_records_loaded, len(references))
        self.assertFalse(hasattr(native, 'decode_calls'))  # Packed load is not RDKit decoding.
        return native

    def test_exhaustive_six_bit_space_duplicate_reference_and_all_group_orders(self):
        values = [raw(i for i in range(6) if mask & (1 << i)) for mask in range(64)]
        shuffled = list(values); random.Random(7103).shuffle(shuffled)
        for refs in (values, values[::3], shuffled[:29], shuffled + shuffled[:7]):
            self.compare(values, refs, all_orders=True)

    def test_zero_scores_preserve_unreduced_winner_and_zero_zero(self):
        value = self.compare([raw([])], [raw(range(10)), raw([]), raw([1])]).nearest(raw([]))
        self.assertEqual((value['score_numerator'], value['score_denominator'], value['reference_ordinal']), (0, 10, 0))
        empty = self.compare([raw([])], [raw([])]).nearest(raw([]))
        self.assertEqual((empty['score_numerator'], empty['score_denominator']), (0, 1))
        self.assertEqual(empty['score'], 0.)

    def test_equal_bounds_point_one_earliest_tie_and_strict_pruning_accounting(self):
        q = raw(range(11)); refs = [raw(range(110)), raw([0, 1, *range(200, 209)])]
        value = self.compare([q], refs).nearest(q)
        self.assertEqual((value['score_numerator'], value['score_denominator'], value['reference_ordinal']), (11, 110, 0))
        self.assertIn(110, value['searched_popcount_groups'])
        q = raw([0, 1]); value = self.compare([q], [q, raw([0]), raw(range(10)), q]).nearest(q)
        self.assertEqual((value['evaluated_references'], value['strictly_bound_pruned_references']), (2, 2))
        self.compare([q], [raw(range(6)), raw([0, 7])])

    def test_all_2048_positions_extreme_popcounts_and_random_dense_queries(self):
        counts = (0, 1, 2, 3, 10, 11, 32, 64, 128, 256, 512, 1024, 1536, 2047, 2048)
        generator = random.Random(20261104)
        references = [raw(generator.sample(range(2048), k)) for k in counts for repeat in range(2)]
        queries = [raw(range(k)) for k in counts] + [raw([i]) for i in range(2048)]
        self.compare(queries, references)

    def test_file_loader_same_fd_fullN_and_private_copy_survives_source_deletion(self):
        refs = [raw([3]), raw(range(128)), raw([])]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'references.bin'; path.write_bytes(b''.join(refs))
            expected_frame = oracle.file_frame(path)
            native = backend.load_reference(path, expected_frame, len(refs), CAP, build_manifest_reference=self.build)
            self.addCleanup(native.close)
            path.write_bytes(b''); path.unlink()  # Native storage must never be mmap-backed.
            original = oracle.CachedReference(refs, worker_rss_cap_bytes=CAP)
            for query in refs: self.assertEqual(native.nearest(query), original.nearest(query))

    def test_loader_rejects_inflight_inode_replacement_and_wrong_cardinality(self):
        refs = [raw([2]), raw([0, 3])]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'references.bin'; path.write_bytes(b''.join(refs))
            expected = oracle.file_frame(path)
            with self.assertRaises(ValueError):
                backend.load_reference(path, expected, 3, CAP, build_manifest_reference=self.build)
            constructor = backend.CompiledReference
            def replace_after_copy(rows, **kwargs):
                result = constructor(rows, **kwargs); self.addCleanup(result.close)
                replacement = path.with_name('new.bin'); replacement.write_bytes(b''.join(refs))
                os.replace(replacement, path)
                return result
            with patch.object(backend, 'CompiledReference', side_effect=replace_after_copy):
                with self.assertRaises(ValueError):
                    backend.load_reference(path, expected, len(refs), CAP, build_manifest_reference=self.build)

    def test_invalid_width_empty_mutable_input_cap_and_sealed_reference(self):
        for refs in ([], [b'x'], [bytearray(256)]):
            with self.assertRaises(ValueError): self.compiled(refs)
        with self.assertRaises(RuntimeError):
            backend.CompiledReference([raw([0])], worker_rss_cap_bytes=1, build_manifest_reference=self.build)
        value = self.compiled([raw([0])])
        for query in (b'x', bytearray(256)):
            with self.assertRaises(ValueError): value.nearest(query)
        with self.assertRaises(ValueError): value.kernel.append(value.handle, raw([1]))
        for pop in (-1, 2049, True):
            with self.assertRaises(ValueError): value.order(pop)

    def test_explicit_build_binary_pin_abi_and_source_binding(self):
        for key in ('binary_reference', 'oracle_source_reference'):
            with tempfile.TemporaryDirectory() as directory:
                altered = copy.deepcopy(self.manifest); altered[key]['sha256'] = '0' * 64
                ref = write_new(Path(directory) / 'wrong_build.json', altered)
                with self.assertRaises(ValueError): backend.load_kernel(ref)
        with tempfile.TemporaryDirectory() as directory:
            altered = copy.deepcopy(self.manifest); altered['python']['soabi'] = 'wrong-ABI'
            ref = write_new(Path(directory) / 'wrong_abi.json', altered)
            with self.assertRaises(ValueError): backend.load_kernel(ref)

    def test_physical_posting_work_is_not_logical_group_pruning(self):
        q=raw([0,1]);refs=[q,raw([0]),raw(range(10)),q]
        value=self.compare([q],refs);result,work=value.nearest_with_work(q)
        self.assertEqual((result['evaluated_references'],result['strictly_bound_pruned_references']),(2,2))
        self.assertEqual(work['posting_entries_visited'],7)
        self.assertEqual(work['intersection_counter_increments'],7)
        self.assertEqual(work['intersection_counters_zeroed'],4)
        self.assertEqual(work['winner_scan_rows'],2)
        self.assertTrue(work['logically_pruned_rows_may_have_posting_work'])
        stats=value.native_statistics
        self.assertEqual(stats['posting_entries'],15)
        self.assertEqual(stats['posting_buffer_bytes'],60)
        self.assertEqual(stats['query_workspace_bytes_per_call'],8)
        self.assertEqual(stats['raw_fingerprint_bytes_retained'],0)
        zero,zero_work=value.nearest_with_work(raw([]))
        self.assertEqual(zero,value.nearest(raw([])))
        self.assertEqual(zero_work['posting_entries_visited'],0)
        self.assertEqual(zero_work['intersection_counters_zeroed'],4)
        dense=self.compiled([raw(range(2048))])
        self.assertEqual(dense.nearest(raw(range(2048)))['score_numerator'],2048)

    def test_concurrent_queries_own_workspaces_and_preserve_all_results(self):
        refs=[raw(i for i in range(8)if mask & (1<<i))for mask in range(256)]
        native=self.compiled(refs);queries=[refs[i%256]for i in range(100)]
        expected=[native.nearest(q)for q in queries]
        with ThreadPoolExecutor(max_workers=4)as pool:
            observed=list(pool.map(native.nearest_with_work,queries))
        self.assertEqual([r for r,w in observed],expected)
        for q,(result,work)in zip(queries,observed):
            exact_visits=sum((int.from_bytes(q,'little')&int.from_bytes(r,'little')).bit_count()for r in refs)
            self.assertEqual(work['posting_entries_visited'],exact_visits)
            self.assertEqual(work['winner_scan_rows'],result['evaluated_references'])

if __name__ == '__main__':
    unittest.main()
