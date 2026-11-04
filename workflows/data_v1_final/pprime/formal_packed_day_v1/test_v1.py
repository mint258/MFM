"""Three synthetic Source boundaries, executed in the production Parent before DATA."""
import hashlib,json,struct,tempfile,unittest,inspect,re
from . import contract as C,io as I,worker,prepare as P

class Boundaries(unittest.TestCase):
    def test_exact_user_floor_only_other_original_science_unchanged(self):
        self.assertTrue(C.fraction_ok(1989,2000));self.assertFalse(C.fraction_ok(1988,2000))
        self.assertTrue(C.fraction_ok(2000,2000))
        for args in ((True,2000),(1989,False),(-1,2000),(2001,2000),(0,0)):
            with self.assertRaises(ValueError):C.fraction_ok(*args)
        self.assertEqual(C.parameters('compute-0-18')['new_QA_calls'],0)
        with self.assertRaises(ValueError):C.parameters('compute-0-18','TIGHTER_ONLY_THREE_FIELDS')
        self.assertIs(C.record_once_key,C.Original.record_once_key)

    def test_entire_original_worker_context_isolation_and_fixed_first2(self):
        proof=worker.inverse();self.assertTrue(proof['entire_original_worker_code'])
        self.assertFalse(proof['shared_scientific_module_mutation'])
        rows=[{'sprime_conf_idx':i,'coordinates':[[float(i),0.,0.]],'status':'SUCCESS','converged':True} for i in (10,1,7)]
        actual=C.O.ordered_two(rows,'synthetic-mid',20261025)
        expected=sorted(rows,key=lambda r:(C.O.stable_key(20261025,'synthetic-mid','uff_sprime',r['sprime_conf_idx']),str(r['sprime_conf_idx'])))[:2]
        self.assertEqual(actual,expected)
        self.assertEqual(P.coordinate_sha([[-0.,1.0000000000000002,2.]]),hashlib.sha256(struct.pack('<ddd',-0.,1.0000000000000002,2.)).hexdigest())
        origin=C.meta(C.Q.pin(C.HERE/'source_origin.json'))['coordinate_source']
        from pathlib import Path
        text=Path(origin['path']).read_text()
        exact=re.search(r'(?ms)^def coordinate_sha\(.*?(?=^def |\Z)',text).group().strip()
        self.assertEqual(inspect.getsource(P.coordinate_sha).strip(),exact)
        pair={'molecule_id':'m','conformer':{'sprime_conf_idx':7},'uff_coordinate_sha256':'a'*64}
        old=C.record_once_key(pair,{'sha256':'b'*64})
        self.assertEqual(old,C.record_once_key(dict(pair,output='elsewhere',precision_mode='other'),{'sha256':'b'*64}))

    def test_actual_role_reservations_checkpoint_roundtrip_and_unknown_consumed(self):
        roles=I.Roles();start=roles.bound();self.assertEqual(start,C.PARENT_CAP)
        roles.start('one');roles.settle('one',100,True);self.assertEqual(roles.bound(),start+100)
        roles.start('unknown');roles.settle('unknown',0,False);self.assertEqual(roles.bound(),start+100+C.WORKER_CAP)
        with self.assertRaises(ValueError):roles.start('unknown')
        roles.add_export(1000);self.assertEqual(roles.bound(),start+1100+C.WORKER_CAP)
        with tempfile.TemporaryDirectory(prefix='formal_day_synthetic_') as d:
            from pathlib import Path
            store=I.Store(Path(d),4<<20);payload={'record_id':'synthetic','count':12,'unknown':True}
            ref=store.json(Path(d)/'checkpoint.json',payload)
            self.assertEqual(json.loads(Path(ref['path']).read_bytes()),payload)
            with self.assertRaises(Exception):store.json(Path(d)/'checkpoint.json',payload)
        self.assertEqual(P.claimed_identity('pprime:synthetic:colon-mid:7'),('synthetic:colon-mid',7))
        for rid in ('not-pprime:m:1','pprime:m:-1','pprime:m:01','pprime::1'):
            with self.assertRaises(ValueError):P.claimed_identity(rid)
        import duckdb
        with tempfile.TemporaryDirectory(prefix='formal_day_SQL_staging_') as d:
            from pathlib import Path
            path=Path(d)/'temp_only.duckdb';db=duckdb.connect(str(path))
            db.execute("CREATE TEMP TABLE eligible AS SELECT 'm'||lpad(CAST(i AS VARCHAR),5,'0') AS molecule_id FROM range(60005) t(i)")
            db.execute("CREATE TEMP TABLE pilot_mids AS SELECT 'm00000' AS molecule_id")
            db.execute("CREATE TEMP TABLE consumed_mid_ids AS SELECT 'm00001' AS molecule_id")
            db.execute(P.CHOSEN_SQL)
            self.assertEqual(db.execute('SELECT count(*),min(molecule_id),max(molecule_id) FROM chosen').fetchone(),(50000,'m00002','m50001'))
            self.assertEqual(db.execute("SELECT count(*) FROM chosen WHERE molecule_id='m00002'").fetchone()[0],1)
            # Partial once consumption is not a whole-MID deferral. After the
            # second physical once appears,next day starts beyond that MID.
            db.execute("INSERT INTO consumed_mid_ids VALUES ('m00002')");db.execute('DROP TABLE chosen');db.execute(P.CHOSEN_SQL)
            self.assertEqual(db.execute('SELECT count(*),min(molecule_id),max(molecule_id) FROM chosen').fetchone(),(50000,'m00003','m50002'))
            db.execute('CREATE TABLE pairs(rid VARCHAR PRIMARY KEY,pair BLOB,hashes BLOB)')
            # Actual runtime fetches TEMP chosen on the creating connection.
            self.assertEqual(len(db.execute('SELECT molecule_id FROM chosen ORDER BY molecule_id').fetchall()),50000)
            db.close()
            db=duckdb.connect(str(path),read_only=True)
            self.assertEqual([r[0] for r in db.execute('SHOW TABLES').fetchall()],['pairs']);db.close()
        self.assertEqual(C.MAX_RECORDS,100000);self.assertEqual(C.WALL,86400);self.assertEqual(C.CAP,64<<30)

if __name__=='__main__':unittest.main()
