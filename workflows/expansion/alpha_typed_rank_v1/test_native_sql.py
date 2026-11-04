"""Root Alpha DuckDB-only fixtures, separate from standard-library metadata tests."""
from pathlib import Path
import tempfile
import unittest
from ..common import stable_hash
from .closed_N_audit import summary,stamp


def fill(db):
    db.execute('CREATE TABLE n_candidates(cid BIGINT,full_key VARCHAR,heavy_stratum VARCHAR,element_combination VARCHAR,v1_scaffold_count BIGINT,v1_ring_system_count BIGINT,nearest_v1_tanimoto DOUBLE)')
    db.executemany('INSERT INTO n_candidates VALUES(?,?,?,?,?,?,?)',[
      (1,'key-a','10','6',1,2,.5),(2,'key-b','10','6',1,2,.5),(3,'key-c','10','6',2,2,.5),(4,'key-d','20','6',1,2,.5)])


class Source(unittest.TestCase):
    def test_complete_tuple_collision_is_not_hidden_by_unique_identity_or_other_strata(self):
        import duckdb
        db=duckdb.connect()
        try:
            fill(db);db.create_function('n_hash',lambda key:'deliberately-colliding-fixture',['VARCHAR'],'VARCHAR')
            result=summary(db)
            self.assertEqual((result['grouped_mass'],result['duplicate_tuple_groups'],result['rows_in_duplicate_tuples']),(4,1,2))
            self.assertFalse(result['strict_N_order_independent_of_query_row_order'])
        finally:db.close()

    def test_actual_closed_read_only_connection_registers_original_hash_without_source_mutation(self):
        import duckdb
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'ranking.duckdb';db=duckdb.connect(str(path));fill(db);db.execute('CHECKPOINT');db.close()
            before=stamp(path.stat());db=duckdb.connect(str(path),read_only=True)
            try:
                db.create_function('n_hash',lambda key:stable_hash('N-tie',20261025,key),['VARCHAR'],'VARCHAR')
                result=summary(db);self.assertTrue(result['strict_N_order_independent_of_query_row_order'])
                self.assertEqual(result['n_candidate_rows'],4)
            finally:db.close()
            self.assertEqual(stamp(path.stat()),before)


if __name__=='__main__':unittest.main()
