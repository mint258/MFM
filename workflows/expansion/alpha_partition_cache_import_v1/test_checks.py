"""Reject scientific counter/key/bit changes while preserving true overlap once."""
import copy,hashlib,unittest
import duckdb,pyarrow as pa
from . import checks
class Checks(unittest.TestCase):
    def setUp(self):
        self.db=duckdb.connect();checks.install(self.db)
        self.rows=[]
        for i in range(3):
            fp=('%0512x'%(i+1));self.rows.append(dict(ecfp4_2048_hex=fp,nearest_v1_key='KEY'+str(i),nearest_v1_tanimoto=2/6,reference_ordinal=i,score_numerator=2,score_denominator=6,evaluated_references=1,strictly_bound_pruned_references=2,reference_molecules=3))
        self.db.execute("CREATE TABLE ref_keys AS SELECT *FROM(VALUES(0,'KEY0'),(1,'KEY1'),(2,'KEY2'))t(ordinal,full_key)")
        self.prefixes=sorted({hashlib.md5(r['ecfp4_2048_hex'].encode()).hexdigest()[0]for r in self.rows})
    def tearDown(self):self.db.close()
    def view(self,name,rows):
        table=pa.Table.from_pylist(rows);checks.schema(table.schema);self.db.register('_'+name,table);self.db.execute('CREATE OR REPLACE VIEW '+name+' AS SELECT *FROM _'+name)
    def test_matching_overlap_and_new_mass(self):
        self.view('incoming',self.rows);self.view('existing',self.rows[:1])
        checks.validate(self.db,'incoming',self.prefixes,3,3);checks.validate(self.db,'existing',self.prefixes,3)
        self.assertEqual(checks.overlap_and_new(self.db),(1,2))
    def test_equal_fraction_with_changed_unreduced_counts_is_not_equivalent(self):
        self.view('incoming',self.rows);bad=copy.deepcopy(self.rows[:1]);bad[0].update(score_numerator=1,score_denominator=3);self.view('existing',bad)
        checks.validate(self.db,'existing',self.prefixes,3)
        with self.assertRaisesRegex(ValueError,'all9'):checks.overlap_and_new(self.db)
    def test_invalid_reference_key_mass_and_partition_fail(self):
        for field,value in [('nearest_v1_key','WRONG'),('reference_molecules',2),('evaluated_references',2),('nearest_v1_tanimoto',0.334)]:
            with self.subTest(field=field):
                bad=copy.deepcopy(self.rows);bad[0][field]=value;self.view('incoming',bad)
                with self.assertRaises(ValueError):checks.validate(self.db,'incoming',self.prefixes,3,3)
        self.view('incoming',self.rows+[self.rows[0]])
        with self.assertRaisesRegex(ValueError,'unique'):checks.validate(self.db,'incoming',self.prefixes,3)
        self.view('incoming',self.rows)
        excluded=next(x for x in '0123456789abcdef'if x not in self.prefixes)
        with self.assertRaises(ValueError):checks.validate(self.db,'incoming',[excluded],3)
    def test_binary32_score_schema_rejected(self):
        table=pa.Table.from_pylist(self.rows);index=table.schema.get_field_index('nearest_v1_tanimoto');table=table.set_column(index,'nearest_v1_tanimoto',pa.array([2/6]*3,type=pa.float32()))
        with self.assertRaisesRegex(ValueError,'binary64'):checks.schema(table.schema)
if __name__=='__main__':unittest.main()