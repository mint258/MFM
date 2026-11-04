"""One standard-library proof boundary for full disjoint FP/MID allocation."""
import hashlib
import unittest
from .partition import assignment, cover, predicate


class Partition(unittest.TestCase):
    def test_full_disjoint_assignment_preserves_duplicate_FP_identities(self):
        left = list('0123456789a'); right = list('bcdef')
        self.assertEqual(cover([left, right]), list('0123456789abcdef'))
        rows = [(i, ('0' * 510 + format(i // 2, '02x'))) for i in range(256)]
        def selected(values):
            return [i for i, fp in rows if hashlib.md5(fp.encode('ascii')).hexdigest()[0] in values]
        a, b = selected(left), selected(right)
        self.assertEqual(sorted(a + b), list(range(256)))
        self.assertFalse(set(a).intersection(b))
        for i in range(0, 256, 2):
            self.assertEqual(i in a, i + 1 in a)
        self.assertEqual(assignment({'partition_id': 'cpu32', 'assigned_hash_buckets': left}), left)
        self.assertIn('md5(ecfp4_2048_hex)', predicate(left))
        for bad in ([left, list('abcdef')], [left, list('bcde')], [left, ['f', 'b', 'c', 'd', 'e']]):
            with self.assertRaises(ValueError):
                cover(bad)


if __name__ == '__main__':
    unittest.main()
