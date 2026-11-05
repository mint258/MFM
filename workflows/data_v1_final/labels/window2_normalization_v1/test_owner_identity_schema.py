"""Closed SQLite job TEXT affinity must not change authoritative owner identity."""
import sqlite3,unittest
from .reader import effective_owner

class OwnerIdentitySchema(unittest.TestCase):
    def test_canonical_integer_job_and_closed_text_job_match_without_weakening_owner(self):
        db=sqlite3.connect(':memory:')
        try:
            db.execute('CREATE TABLE canonical(ordinal INTEGER,rid TEXT,mid TEXT,job_id INTEGER,role TEXT)')
            db.execute('CREATE TABLE eligibility(ordinal INTEGER,rid TEXT,mid TEXT,job TEXT,source_role TEXT,effective_role TEXT,common_population INTEGER,geometry_id TEXT,parent_geometry_id TEXT,fit INTEGER,reason TEXT)')
            original=(71,'opaque-native:key:9','molecule-exact',4513985,'TRAIN')
            db.execute('INSERT INTO canonical VALUES(?,?,?,?,?)',original)
            db.execute('INSERT INTO eligibility VALUES(?,?,?,?,?,?,?,?,?,?,?)',(*original,'TRAIN',1,None,None,1,'COMMON_TRAIN_NOT_D5'))
            row=db.execute('SELECT * FROM canonical').fetchone()
            owner=dict(zip(('record_ordinal','record_id','molecule_id','job_id','new_role'),row))
            side=db.execute('SELECT rid,mid,job,source_role,effective_role,common_population,geometry_id,parent_geometry_id,fit,reason FROM eligibility WHERE ordinal=?',(owner['record_ordinal'],)).fetchone()
            self.assertIs(type(owner['job_id']),int);self.assertIs(type(side[2]),str)
            result=effective_owner(owner,side)
            self.assertEqual(result['job_id'],4513985);self.assertIs(type(result['job_id']),int)
            self.assertTrue(result['fit_eligible']);self.assertEqual(result['record_id'],'opaque-native:key:9')
            # Preserve compatibility with older in-memory/direct integer sides.
            self.assertTrue(effective_owner(owner,(*side[:2],4513985,*side[3:]))['fit_eligible'])
            for index,replacement in [(0,'different-native'),(1,'different-mid'),(2,'4513986'),(2,'04513985'),(3,'VAL')]:
                wrong=list(side);wrong[index]=replacement
                with self.assertRaisesRegex(ValueError,'FINAL_ELIGIBILITY_OWNER_ALIGNMENT'):effective_owner(owner,tuple(wrong))
            with self.assertRaisesRegex(ValueError,'FINAL_ELIGIBILITY_OWNER_ALIGNMENT'):effective_owner(owner,None)
        finally:db.close()
