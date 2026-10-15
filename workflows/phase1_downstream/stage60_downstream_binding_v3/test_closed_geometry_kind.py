"""One stdlib kind-vocabulary oracle; no geometry, annotations or model."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).absolute().parent))
from downstream_binding_data import DownstreamBindingError
from materialize_downstream_bindings import closed_geometry_kind


class ClosedGeometryKindTest(unittest.TestCase):
    def test_exact_three_pairs_and_reject_other_status_basis_or_type(self):
        # Historical vocabulary is explicit; case-folding/alias inference is forbidden.
        allowed = (("GEOMETRY_READY", "ORIGINAL_SOURCE_3D", "original_source_3d"),
                   ("GEOMETRY_READY", "SAVED_GENERATED_CANDIDATE", "cached_generated"),
                   ("NOT_READY", "SAVED_GENERATED_CANDIDATE", "not_ready"))
        for status, basis, expected in allowed:
            with self.subTest(status=status, basis=basis):
                self.assertEqual(closed_geometry_kind(status=status, basis=basis), expected)
        forbidden = (("NOT_READY", "ORIGINAL_SOURCE_3D"),
                     ("GENERATION_FAILED", "SAVED_GENERATED_CANDIDATE"),
                     ("GEOMETRY_READY", "original_source_3d"),
                     ("GEOMETRY_READY", "cached_generated"),
                     ("not_ready", "SAVED_GENERATED_CANDIDATE"),
                     ("GEOMETRY_READY", "UNKNOWN"),
                     ("UNKNOWN", "SAVED_GENERATED_CANDIDATE"),
                     ("", ""), (None, "ORIGINAL_SOURCE_3D"),
                     (True, "ORIGINAL_SOURCE_3D"),
                     ("GEOMETRY_READY", None), ("GEOMETRY_READY", []),
                     (["GEOMETRY_READY"], "ORIGINAL_SOURCE_3D"),
                     (b"GEOMETRY_READY", "ORIGINAL_SOURCE_3D"))
        for status, basis in forbidden:
            with self.subTest(status=repr(status), basis=repr(basis)):
                with self.assertRaises(DownstreamBindingError):
                    closed_geometry_kind(status=status, basis=basis)


if __name__ == "__main__":
    unittest.main()
