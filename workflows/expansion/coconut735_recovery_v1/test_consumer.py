"""Actual SQL veto tests; neither an original UNKNOWN nor source scope is dropped."""
import json
import sqlite3
import unittest
from . import consumer as C


class ConsumerBoundaries(unittest.TestCase):
    def test_real_sql_keeps_exact_semantics_and_adds_only_sound_bounds(self):
        db = sqlite3.connect(':memory:')
        C.install_tables(db)
        key = 'AAAAAAAAAAAAAA-BBBBBBBBBB-C'
        db.execute('INSERT INTO excluded VALUES(?,?,?)', ('full', key, 'qm9'))
        binding = {'source_table': 'entries', 'copy_block': 3, 'source_row_ordinal': 7}
        rule = dict(rule_id='coconut735:physical7', kind='NON_H_ATOM_COUNT_LOWER_BOUND',
                    dataset='coconut', binding=binding, bound=[[6, 4], [8, 2]])
        C.insert_constraint(db, rule, expected_dataset='coconut', accepted_physical_bindings=[binding])
        def row(c, o, full='CCCCCCCCCCCCCC-DDDDDDDDDD-E'):
            composition = [[6, c], [8, o]]
            return dict(full_key=full, non_h_composition=json.dumps(composition, separators=(',', ':')), elements=[6, 8])
        self.assertEqual(C.contamination(row(3, 2), db), [])
        self.assertEqual(C.contamination(row(4, 2), db), [('composition_lower_bound:coconut735:physical7', 'coconut')])
        self.assertIn(('full', 'qm9'), C.contamination(row(3, 2, key), db))
        with self.assertRaises(ValueError):
            C.insert_constraint(db, rule, expected_dataset='coconut', accepted_physical_bindings=[])
        with self.assertRaises(ValueError):
            C.candidate_domain(dict(non_h_composition='[[11,1]]', elements=[11]))
        db.close()

    def test_metadata_does_not_pass_as_a_complete_all11_index(self):
        with self.assertRaises((ValueError, KeyError)):
            C.index_header(dict(schema=C.INDEX_SCHEMA, status='COMPLETE', sources={'coconut': {}},
                                all_physical_source_rows_covered=True, original_graph_unknowns_retained=True,
                                constraint_source_datasets=['coconut', 'moleculenet']))


if __name__ == '__main__':
    unittest.main()
