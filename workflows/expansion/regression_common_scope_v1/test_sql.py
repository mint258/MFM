"""Small SQL parity, missing-ID, changed-decision and explanation boundaries."""
import unittest
from . import sql,source

FIELDS=['old_chemical_admit','new_graph_admit','old_final','conditional_new_final','native_rule_mismatch',
 'portable_flag_mismatch','unexplained','legacy_native_rule_mismatch','historical_unassigned_x1_coalesce',
 'raw_native_rule_mismatch','enriched_native_rule_mismatch','enrichment_metadata_mismatch']


class Source(unittest.TestCase):
    def fixture(self,drop=False,change=False,details=True):
        import duckdb
        db=duckdb.connect();db.execute('CREATE TABLE compact(record_id VARCHAR,molecule_id VARCHAR,source_family VARCHAR,decision_bits BIGINT,cause_bits BIGINT)')
        for rid,mid,selected in [('r1','a',True),('r2','a',True),('r3','b',True),('r4','outside',False),('r5','formal_outside',True)]:
            if drop and rid=='r3':continue
            values={key:False for key in FIELDS};values.update(old_chemical_admit=selected,new_graph_admit=selected,old_final=selected,conditional_new_final=selected)
            if rid=='r4':values['portable_flag_mismatch']=True
            if change and rid=='r2':values['conditional_new_final']=False
            bits=sum(1<<i for i,key in enumerate(FIELDS) if values[key]);db.execute('INSERT INTO compact VALUES(?,?,?,?,?)',[rid,mid,'test',bits,int(rid=='r4')])
        sql.decode_view(db,FIELDS,['ORIGINAL_SMILES_UNPARSEABLE'])
        db.execute("CREATE TABLE formal AS SELECT * FROM (VALUES ('r1','a'),('r2','a'),('r3','b'),('r5','formal_outside')) x(record_id,molecule_id)")
        db.execute("CREATE TABLE membership AS SELECT * FROM (VALUES ('a','TRAIN',2,TRUE),('b','VAL',1,TRUE)) x(molecule_id,effective_role,records,common_population)")
        db.execute('CREATE TABLE explanations(record_id VARCHAR,molecule_id VARCHAR,source_family VARCHAR,cause_bits BIGINT)')
        if details:db.execute("INSERT INTO explanations VALUES('r4','outside','test',1)")
        return db

    def test_actual_complete_scope_counts_not_just_global_agreement(self):
        db=self.fixture()
        try:
            result=sql.bind(db,FIELDS,{'molecules':2},True);self.assertTrue(result['passed'])
            self.assertEqual(result['metrics']['bound_selection']['old_records'],3)
            self.assertEqual(result['metrics']['formal_records'],4)
            self.assertEqual(result['metrics']['mismatch_explanations']['rows'],1)
        finally:db.close()

    def test_missing_Common_record_and_MID_fail_actual_anti_join(self):
        db=self.fixture(drop=True)
        try:
            result=sql.bind(db,FIELDS,{'molecules':2},True);self.assertFalse(result['passed'])
            self.assertEqual(result['metrics']['common_MIDs_absent_from_complete_decisions'],1)
            self.assertEqual(result['metrics']['old_final_formal_anti_join']['formal_not_selected'],1)
        finally:db.close()

    def test_changed_new_decision_is_observed_not_masked_by_same_predicate(self):
        db=self.fixture(change=True)
        try:
            result=sql.bind(db,FIELDS,{'molecules':2},True);self.assertFalse(result['passed'])
            self.assertEqual(result['metrics']['bound_selection']['changed_records'],1)
            self.assertEqual(result['metrics']['common_MIDs_with_different_native_record_counts'],1)
        finally:db.close()

    def test_missing_mismatch_explanation_cannot_disappear(self):
        db=self.fixture(details=False)
        try:
            result=sql.bind(db,FIELDS,{'molecules':2},True);self.assertFalse(result['passed'])
            self.assertEqual(result['metrics']['mismatch_explanations']['missing_details'],1)
        finally:db.close()

    def test_original_common_AND_and_bit_encoding_AST(self):
        v1='def evaluate(row):\n common=row.get("common_member",True)\n old_final=row["formal_member"] and common\n new_final=predicted_retained and assigned and common\n'
        v2='BOOL_FIELDS='+repr(tuple(FIELDS))
        v3='def compact_result(result):\n bits=sum(int(result[k]) << i for i,k in enumerate(BOOL_FIELDS))\n'
        self.assertTrue(source.prove(v1,v2,v3,FIELDS)['old_final_and_common'])
        with self.assertRaises(ValueError):source.prove(v1.replace('and common','or common'),v2,v3,FIELDS)


if __name__=='__main__':unittest.main()
