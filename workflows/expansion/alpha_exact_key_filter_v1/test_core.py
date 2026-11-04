"""Meaningful exact-only/source-sharing boundaries; standard library only."""
import sqlite3
import unittest
from . import core as C

K = 'AAAAAAAAAAAAAA-BBBBBBBBBB-N'


def row(sid, keys, subdataset='', composition=None):
    return dict(source_id=sid, role='all', subdataset=subdataset,
                inchikeys=keys, non_h_composition=composition)


class ExactOnly(unittest.TestCase):
    def test_PDBbind_shared_key_survives_other_source_rebuild(self):
        db = sqlite3.connect(':memory:')
        try:
            db.execute('CREATE TABLE excluded(kind,key,dataset,PRIMARY KEY(kind,key,dataset))')
            entries = [('moleculenet', row('PDB physical', [K], 'PDBbind')),
                       ('moleculenet', row('HIV physical', [K], 'HIV')),
                       ('coconut', row('COCO physical', [K], 'molecules'))]
            for dataset, value in entries:
                _, keys = C.disposition(dataset, value)
                db.executemany('INSERT OR IGNORE INTO excluded VALUES(?,?,?)', keys)
            self.assertEqual(db.execute('SELECT kind,key,dataset FROM excluded ORDER BY kind,dataset').fetchall(),
                             [(kind, value, dataset) for kind, value in [('full', K), ('wp5', C.wp5(K))]
                              for dataset in ['coconut', 'moleculenet']])
            self.assertEqual(C.disposition(*entries[0]), ('PDBBIND_NOT_IN_DOWNSTREAM_PLAN', []))
        finally:
            db.close()

    def test_composition_is_never_a_veto_and_exact_audited_ID_only(self):
        self.assertEqual(C.disposition('qm7', row('unknown', [], composition=[[6, 100]]))[1], [])
        # Even malformed historical composition is not interpreted under the new rule.
        value = row('known', [K], composition={'not': 'an atom vector'})
        expected = [('full', K, 'qm7'), ('wp5', C.wp5(K), 'qm7')]
        self.assertEqual(C.disposition('qm7', value)[1], expected)
        self.assertEqual(C.disposition('qm7', value, {('qm7', 'known')})[1], [])
        self.assertEqual(C.disposition('qm7', value, {('qm7', 'know*')})[1], expected)

    def test_original_WP5_protonation_and_source_line_witness(self):
        other = 'AAAAAAAAAAAAAA-CCCCCCCCCC-N'
        changed = 'AAAAAAAAAAAAAA-CCCCCCCCCC-O'
        self.assertEqual(C.wp5(K), C.wp5(other))
        self.assertNotEqual(C.wp5(K), C.wp5(changed))
        value = row('physical', [], 'ClinTox')
        ref = dict(path='/original', bytes=100, sha256='a' * 64)
        witness = C.locator({'dataset': 'moleculenet'}, ref, ref, 5, 42, b'actual source line\n', value)
        self.assertEqual((witness['row_ordinal_1based'], witness['source_byte_offset'], witness['source_record_bytes']), (5, 42, 19))
        self.assertEqual(witness['source_record_sha256'], C.hashlib.sha256(b'actual source line\n').hexdigest())
        with self.assertRaises(ValueError):
            C.wp5('not a full key')


if __name__ == '__main__':
    unittest.main()
