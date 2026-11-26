"""Only new atomic element grouping, original-order streaming and resource sizing."""
import unittest
import numpy as np
from composition_descriptive import element_layout,accumulate_records,additional_output_peak


class DescriptiveTests(unittest.TestCase):
    def panel(self):
        return dict(Z=np.array([6,1,1,8,1]),molecule_atom_offsets=np.array([0,3,5]),
            owners=np.array([0,0,1]),record_atom_offsets=np.array([0,3,6,8]))

    def test_original_element_population_and_record_weights(self):
        layout=element_layout(self.panel())
        self.assertEqual(layout["elements"].tolist(),[1,6,1,8])
        self.assertEqual(layout["owners"].tolist(),[0,0,1,1])
        self.assertEqual(layout["counts"].tolist(),[4,2,1,1])

    def test_exact_stream_prefix_continuation(self):
        p=self.panel();layout=element_layout(p);h=np.arange(24,dtype=np.float32).reshape(8,3)
        full=np.zeros((4,3));square=np.zeros(4)
        accumulate_records(full,square,h,p,layout,0,3)
        partial=np.zeros((4,3));part_square=np.zeros(4)
        self.assertEqual(accumulate_records(partial,part_square,h,p,layout,0,1),1)
        resumed=partial.copy();resumed_square=part_square.copy()
        accumulate_records(resumed,resumed_square,h,p,layout,1,3)
        np.testing.assert_array_equal(resumed,full)
        np.testing.assert_array_equal(resumed_square,square)
        np.testing.assert_array_equal(full[0],h[[1,2,4,5]].astype(np.float64).sum(0))
        self.assertEqual(square[0],np.square(h[[1,2,4,5]].astype(np.float64)).sum())

    def test_shape_guard_and_peak_includes_all_closed_arrays(self):
        p=self.panel();layout=element_layout(p)
        with self.assertRaises(ValueError):
            accumulate_records(np.zeros((4,3)),np.zeros(4),np.zeros((8,2)),p,layout,0,3)
        raw=8*(4*(512*8+8)+5000*512*8)+68*2**20
        self.assertGreaterEqual(additional_output_peak(4),raw)
        self.assertLess(additional_output_peak(4)-raw,2**20)


if __name__=="__main__":unittest.main()
