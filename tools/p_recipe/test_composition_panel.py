"""Only new panel order/prefix and byte-accounting logic."""
import unittest
import numpy as np
from composition_panel import append_molecule, arrays_from_state, cache_footprint


class PanelTests(unittest.TestCase):
    def test_order_and_partial_prefix(self):
        state=dict(indices=[13,4],basis=[1,6,8],molecules=[])
        append_molecule(state,13,[6,1,8],[7,2],[1,6,8])
        prefix=arrays_from_state(state)
        self.assertEqual(prefix["rows"].tolist(),[[13,7],[13,2]])
        append_molecule(state,4,[1,6],[9],[1,6,8])
        arrays=arrays_from_state(state)
        np.testing.assert_array_equal(arrays["rows"][:2],prefix["rows"])
        self.assertEqual(arrays["owners"].tolist(),[0,0,1])
        self.assertEqual(arrays["first"].tolist(),[0,2])
        self.assertEqual(arrays["record_atom_offsets"].tolist(),[0,3,6,8])
        self.assertEqual(arrays["molecule_atom_offsets"].tolist(),[0,3,5])
        self.assertEqual(arrays["X"].tolist(),[[1,1,1,3,2],[1,1,0,2,1]])
        self.assertEqual(arrays["X"].dtype,np.float64)

    def test_invalid_choices_rejected(self):
        for choices in [[],[2,2],list(range(11))]:
            with self.assertRaises(ValueError):
                append_molecule(dict(molecules=[]),1,[6,1],choices,[1,6])

    def test_cache_byte_accounting(self):
        result=cache_footprint(3,8,dimensions=2,source_count=12)
        self.assertEqual(result["mean_float32_bytes"],24)
        self.assertEqual(result["atom_float32_bytes"],64)
        self.assertEqual(result["all_sources_cache_peak_bytes"],12*(88+2**20))


if __name__=="__main__":unittest.main()
