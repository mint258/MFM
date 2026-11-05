"""Meaningful minCID/aliases parity including replacement, duplicates and H-only row."""
import unittest
from .mincid_sql import reduce


class Native(unittest.TestCase):
    def test_full_accepted_oracle_equals_logical_delta(self):
        import duckdb
        db=duckdb.connect()
        try:
            old=[(10,'A',2,'6',10.75),(20,'B',3,'6',20.5),(30,'C',1,'8',30.25),(15,'A',2,'6',15.125)]
            delta=[(5,'A',2,'6',5.125),(25,'B',3,'6',25.5),(41,'D',4,'6,8',41.5),(40,'D',4,'6,8',40.5),(50,'H',0,'',2.016)]
            db.execute('CREATE TABLE accepted(cid BIGINT,full_key VARCHAR,heavy_atoms BIGINT,element_combination VARCHAR,mw DOUBLE)')
            db.executemany('INSERT INTO accepted VALUES (?,?,?,?,?)',old)
            db.execute('CREATE VIEW base AS SELECT * FROM accepted QUALIFY row_number() OVER(PARTITION BY full_key ORDER BY cid)=1')
            db.execute('CREATE VIEW old_aliases AS SELECT cid,full_key FROM accepted')
            db.execute('CREATE TABLE delta AS SELECT * FROM accepted WHERE false');db.executemany('INSERT INTO delta VALUES (?,?,?,?,?)',delta)
            stats=reduce(db);actual=db.execute('SELECT * FROM corrected_candidates ORDER BY full_key').fetchall()
            expected={}
            for row in old+delta:
                if row[1] not in expected or row[0]<expected[row[1]][0]:expected[row[1]]=row
            self.assertEqual(actual,[expected[k] for k in sorted(expected)])
            self.assertEqual(stats,dict(delta_rows=5,delta_unique_full_keys=4,new_full_keys=2,replaced_representatives=1,winning_delta_rows=3))
            self.assertEqual(db.execute('SELECT count(*) FROM old_aliases').fetchone()[0]+len(delta),9)
            self.assertEqual(actual[-1],(50,'H',0,'',2.016))
        finally:db.close()
