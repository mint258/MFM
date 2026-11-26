import unittest
from fullft_physical_ram_20261127 import estimate_physical
from fullft_ram_envelope_20261127 import GiB


class PhysicalEnvelope(unittest.TestCase):
    def test_two_post_exec_families_and_transient_allowance_are_retained(self):
        value=estimate_physical(5*GiB,32*1024**2,verified_shared_address_spawn=True)
        self.assertEqual(value['estimated_physical_host_peak_bytes'],6.5*GiB)
        self.assertFalse(value['measured_whole_tree_peak'])

    def test_unknown_spawn_or_large_metadata_cannot_use_smaller_estimate(self):
        with self.assertRaises(ValueError):
            estimate_physical(5*GiB,32*1024**2,verified_shared_address_spawn=False)
        with self.assertRaises(ValueError):
            estimate_physical(5*GiB,257*1024**2,verified_shared_address_spawn=True)


if __name__=='__main__':unittest.main()
