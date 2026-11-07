"""Native SQL permutation, identity preservation and complete-source boundaries."""
import json
from pathlib import Path
import tempfile
import unittest
from . import core


def row(n,fp='01',heavy=1):
    return dict(cid=n,full_key='A'*13+chr(65+n)+'-'+'B'*10+'-N',heavy_atoms=heavy,
      element_combination='6' if heavy else '',generic_murcko='',generic_ring_systems=[],ecfp4_2048_hex=fp*256)


def database(rows):
    import duckdb
    db=duckdb.connect();db.execute('CREATE TABLE candidates('+','.join(k+' '+v for k,v in core.TYPES.items())+')')
    db.executemany('INSERT INTO candidates VALUES('+','.join('?' for _ in core.FIELDS)+')',[[r[k] for k in core.FIELDS] for r in rows])
    return db


class Source(unittest.TestCase):
    def test_duplicate_FP_keeps_every_distinct_identity_and_all_fields(self):
        rows=[row(3,'02'),row(2),row(1)];db=database(rows)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'query.jsonl';ref,order=core.write_projection(db,path,3,lambda:None)
                proof=core.prove(db,path,3,lambda:None);actual=[json.loads(l) for l in path.read_text().splitlines()]
                self.assertEqual([r['cid'] for r in actual],[1,2,3]);self.assertEqual(ref['rows'],3)
                self.assertEqual(actual,sorted(rows,key=lambda r:(r['ecfp4_2048_hex'],r['full_key'],r['cid'])))
                self.assertEqual(len({r['ecfp4_2048_hex'] for r in actual}),2)
                self.assertTrue(proof['FP_duplicate_identity_rows_preserved']);self.assertEqual(order['strict_adjacent_order_checks'],2)
        finally:db.close()

    def test_H_only_heavy_zero_empty_element_and_zero_FP_are_preserved(self):
        rows=[row(2),row(1,'00',heavy=0)];db=database(rows)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'query.jsonl';core.write_projection(db,path,2,lambda:None)
                core.prove(db,path,2,lambda:None)
                self.assertEqual(json.loads(path.read_text().splitlines()[0]),rows[1])
        finally:db.close()

    def test_missing_duplicate_or_changed_feature_rows_fail_complete_multiset_proof(self):
        rows=[row(1),row(2),row(3)];db=database(rows)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'query.jsonl'
                variants=[rows[:-1],[rows[0],rows[0],rows[2]],[rows[0],{**rows[1],'generic_ring_systems':['changed']},rows[2]]]
                for changed in variants:
                    db.execute('DROP VIEW IF EXISTS observed');path.write_text(''.join(json.dumps(r)+'\n' for r in changed))
                    with self.subTest(changed=changed),self.assertRaises(ValueError):core.prove(db,path,3,lambda:None)
        finally:db.close()

    def test_wrong_order_types_fields_FP_encoding_or_partial_baseline_scope_fail(self):
        audit=core.Audit();audit.add(row(2),b'a\n')
        with self.assertRaises(ValueError):audit.add(row(1),b'b\n')
        for bad in ({**row(1),'sample_ordinal':0},{**row(1),'heavy_atoms':1.0},{**row(1),'ecfp4_2048_hex':'AA'*256},
                    {**row(1),'generic_ring_systems':'not-a-list'}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):core.row_contract(bad)
        pool={'population_version':'synthetic','unique_full_keys':109875599}
        valid=dict(schema='expansion_filtered_columnar_pool_v1',status='COMPLETE',population_version='synthetic',
          counts=dict(input_unique_molecules=109875599,eligible_molecules=10000000,excluded_molecules=99875599))
        core.population_scope(valid,pool)
        for bad in ({**valid,'schema':'EXPANSION_PUBCHEM_PREDECON_BASELINE_V1'},
                    {**valid,'counts':dict(input_unique_molecules=52000,eligible_molecules=40000,excluded_molecules=12000)},
                    {**valid,'counts':dict(input_unique_molecules=109875599,eligible_molecules=9999999,excluded_molecules=99875600)}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):core.population_scope(bad,pool)


if __name__=='__main__':unittest.main()
