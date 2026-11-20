"""Only new source-prefix and policy routing; original D3 program is mocked."""
import io
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
from rdkit import Chem

from .development_geometry import D3_NAMES, UnavailableD3, native_geometry, original_d3, structure
from workflows.data_v1_final.labels.common import D20_NAMES


class Prefix(io.BytesIO):
    def __init__(self, value):
        super().__init__(value)
        self.read_ends = []
    def read(self, size=-1):
        value = super().read(size)
        self.read_ends.append(self.tell())
        return value
    def __exit__(self, *args):
        return False


class DevelopmentGeometryTests(unittest.TestCase):
    def test_native_reader_never_reads_or_decodes_endpoint_label_bytes(self):
        n, offset = 2, 8
        geometry = struct.pack("<4I", n, 1, 3, 1) + struct.pack("<2H", 5, 7)
        geometry += np.array([[0., 0., 0.], [1.4, 0., 0.]], dtype="<f8").tobytes()
        boundary = offset + len(geometry)
        stream = Prefix(b"P1DS1\x00\x00\x00" + geometry + b"UNREAD_F32_COORDINATES_AND_ENDPOINT_LABELS")
        metadata = dict(member_uid="original-member", native_n_atoms=n, geometry_ready=True)
        store = SimpleNamespace(_path=Path("/original/native.bin"), _rows={("expansionrx", 4): dict(offset=offset)},
                                native_geometry_metadata=Mock(return_value=metadata), get=Mock())
        with patch.object(Path, "open", return_value=stream):
            result = native_geometry(store, "expansionrx", 4)
        self.assertLessEqual(max(stream.read_ends), boundary)
        self.assertEqual(result["atomic_numbers"].tolist(), [6, 8])
        self.assertEqual(result["source_atom_ids"], [0, 1])
        self.assertFalse(result["endpoint_label_bytes_read"])
        store.get.assert_not_called()

    def test_native_only_keeps_missing_H_explicit_and_never_calls_completion(self):
        complete = Mock()
        with self.assertRaisesRegex(UnavailableD3, "EXPLICIT_H"):
            structure("CO", [6, 8], [[0., 0., 0.], [1.4, 0., 0.]],
                      hydrogen_policy="native_only", complete=complete)
        complete.assert_not_called()
        with self.assertRaisesRegex(UnavailableD3, "GEOMETRY_UNAVAILABLE"):
            structure("CO", [6, 8], None, hydrogen_policy="B6_fixed_native_H", complete=complete)
        complete.assert_not_called()

    def test_existing_fixed_native_H_route_preserves_every_original_coordinate(self):
        xyz = [[0., 0., 0.], [1.4, .2, .1]]
        z = [atom.GetAtomicNum() for atom in Chem.AddHs(Chem.MolFromSmiles("CO")).GetAtoms()]
        def completion(value):
            self.assertEqual(value["coordinates_A"], xyz)
            return dict(value, atomic_numbers=z, coordinates_A=xyz + [[0., 0., 1.]] * (len(z) - 2),
                geometry_policy="H_COMPLETION_MMFF94_FIXED_ALL_EXISTING_NATIVE_ATOMS",
                xtb_source_atom_ids=[0, 1] + [None] * (len(z) - 2))
        result = structure("CO", [6, 8], xyz, hydrogen_policy="B6_fixed_native_H", complete=completion)
        self.assertEqual(result["coordinates_A"][:2], xyz)
        self.assertFalse(result["new_conformer_embedded"])
        self.assertEqual(result["xtb_source_atom_ids"][:2], [0, 1])
        def moved(value):
            result = completion(value)
            result["coordinates_A"][0] = [2., 0., 0.]
            return result
        with self.assertRaisesRegex(ValueError, "changed original"):
            structure("CO", [6, 8], xyz, hydrogen_policy="B6_fixed_native_H", complete=moved)

    def test_complete_native_geometry_reuses_original_D3_and_keeps_zero_missing_numeric_events(self):
        z = [atom.GetAtomicNum() for atom in Chem.AddHs(Chem.MolFromSmiles("CO")).GetAtoms()]
        xyz = np.zeros((len(z), 3))
        values = dict(zip(D3_NAMES, (0., None, float("inf"), float("nan"), 3., 4.)))
        atom_sasa = list(range(len(z)))
        values["SASA_atom_A2"] = atom_sasa
        calculator = Mock(return_value=(values, ["original-issue"]))
        complete = Mock()
        canonical = dict.fromkeys(D20_NAMES)
        result = original_d3("CO", z, xyz, canonical, hydrogen_policy="native_only",
                             calculator=calculator, complete=complete)
        complete.assert_not_called()
        calculator.assert_called_once()
        self.assertEqual(result["status"].tolist(), [1, 0, 2, 2, 1, 1])
        self.assertEqual(result["raw_values"][0], 0.)
        self.assertTrue(np.isinf(result["raw_values"][2]))
        self.assertIs(result["atomic_SASA_source_values"], atom_sasa)
        self.assertFalse(result["atomic_SASA_in_molecular_vector"])
        self.assertEqual(canonical, dict.fromkeys(D20_NAMES))
