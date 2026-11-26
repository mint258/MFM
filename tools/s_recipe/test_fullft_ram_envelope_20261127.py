"""New resource safety tests; do not infer whole-tree demand from one RSS."""
import unittest
from fullft_ram_envelope_20261127 import estimate,GiB


class FullftRAMEnvelope(unittest.TestCase):
    def test_two_concurrent_forks_and_metadata_are_included(self):
        value=estimate(5*GiB,4*GiB)
        self.assertEqual(value['estimated_concurrent_host_peak_bytes'],16*GiB)
        self.assertFalse(value['measured_whole_process_tree_peak'])
        self.assertFalse(value['pretraining_reservations_changed'])

    def test_child_peak_can_raise_next_reservation_above_sixteen(self):
        self.assertGreater(estimate(4*GiB,6*GiB)['estimated_concurrent_host_peak_bytes'],16*GiB)
        with self.assertRaises(ValueError):estimate(4*GiB,0)


if __name__=='__main__':unittest.main()
