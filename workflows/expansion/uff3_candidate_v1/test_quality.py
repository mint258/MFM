"""Native SQL regression: record mask reports and separate source-NA counts."""
import unittest
from .quality import RECORD_GATE_SQL


class OriginalQualityReportTests(unittest.TestCase):
    def test_atom_component_denominator_cannot_hide_bad_records(self):
        import duckdb
        db=duckdb.connect()
        try:
            db.execute('CREATE TABLE masks(field_id VARCHAR,field_key VARCHAR,source_path VARCHAR,stream VARCHAR,molecule_id VARCHAR,source_value_mask BOOLEAN[],value_mask BOOLEAN[])')
            for mid,source,valid in (('M1',[True]*100,[False]+[True]*99),('M2',[True]*100,[True]*100),('M3',[],[])):
                db.execute("INSERT INTO masks VALUES('24','D3.SASA','SASA_atom_A2','R',?,?,?)",[mid,source,valid])
            row=db.execute(RECORD_GATE_SQL).fetchone()
            self.assertEqual(row[4:7],(3,3,1));self.assertEqual(row[7:],(1,1))
            self.assertGreater(row[6]/row[4],.01)
            self.assertLess(1/200,.01)
        finally:db.close()

    def test_source_missing_and_NA_are_not_newly_masked(self):
        import duckdb
        db=duckdb.connect()
        try:
            db.execute('CREATE TABLE masks(field_id VARCHAR,field_key VARCHAR,source_path VARCHAR,stream VARCHAR,molecule_id VARCHAR,source_value_mask BOOLEAN[],value_mask BOOLEAN[])')
            for mid,source,valid in (('M1',[False],[False]),('M2',[],[]),('M3',[True],[True])):
                db.execute("INSERT INTO masks VALUES('20','D3.PBF','PBF_A','N',?,?,?)",[mid,source,valid])
            row=db.execute(RECORD_GATE_SQL).fetchone();self.assertEqual(row[4:7],(3,3,0));self.assertEqual(row[7:],(1,2))
        finally:db.close()


if __name__=='__main__':unittest.main()
