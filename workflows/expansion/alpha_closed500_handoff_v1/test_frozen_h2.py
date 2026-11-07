"""Actual Alpha frozen scientific-kernel fixture; Root runs on allocated CPU."""
import importlib
from pathlib import Path
import sqlite3
import sys
import unittest
from .plan import ORIGINAL_ROOT, original_science
from . import science_v3
from .empty_domain import candidate_domain, contamination


class ActualFrozenH2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ORIGINAL_ROOT / 'code/pubchem_science_frozen_v1/screen.py').is_file():
            raise unittest.SkipTest('Requires actual Alpha original frozen science files; source-only Main checks do not claim this fixture passed')
        cls.actual_pins = original_science()
        code = str(ORIGINAL_ROOT / 'code'); sys.path.insert(0, code)
        try:cls.kernel = importlib.import_module('pubchem_science_frozen_v1.features_legacy_compatible_v2')
        finally:sys.path.remove(code)
        cls.features = cls.kernel.features_candidate(1, '[H][H]', 1)

    def test_actual_frozen_X_rules_accept_H2_without_a_heavy_cutoff(self):
        mol, flags = self.kernel.chemical_flags('[H][H]')
        self.assertIsNotNone(mol); self.assertEqual(flags, {name: False for name in ('X01', 'X02', 'X03', 'X04', 'X05')})
        self.assertEqual(self.features['reasons'], []); self.assertEqual(self.features['heavy_atoms'], 0)
        self.assertEqual(self.features['non_h_composition'], '[]'); self.assertEqual(self.features['elements'], [])
        self.assertEqual(candidate_domain(self.features), {})

    def test_empty_candidate_matches_no_positive_bound_but_full_and_WP5_still_apply(self):
        db = sqlite3.connect(':memory:')
        db.executescript('CREATE TABLE excluded(kind TEXT,key TEXT,dataset TEXT);CREATE TABLE constraints(rule_id TEXT,dataset TEXT,binding TEXT);CREATE TABLE constraint_atoms(rule_id TEXT,z INTEGER,n INTEGER);')
        db.execute('INSERT INTO constraints VALUES(?,?,?)', ('positive_C_fixture', 'coconut', '{}')); db.execute('INSERT INTO constraint_atoms VALUES(?,?,?)', ('positive_C_fixture', 6, 1))
        self.assertEqual(contamination(self.features, db), [])
        db.execute('INSERT INTO excluded VALUES(?,?,?)', ('full', self.features['full_key'], 'qm9'))
        db.execute('INSERT INTO excluded VALUES(?,?,?)', ('wp5', science_v3.wp5_key(self.features['full_key']), 'som_cyp'))
        self.assertEqual(contamination(self.features, db), [('full', 'qm9'), ('wp5', 'som_cyp')]); db.close()
        with self.assertRaises(ValueError):science_v3.vector([])


if __name__ == '__main__':unittest.main()
