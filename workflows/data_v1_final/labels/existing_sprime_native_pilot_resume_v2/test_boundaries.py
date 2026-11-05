"""Three new boundaries; plus original three, exactly six in the real Parent."""
import json,pathlib,sqlite3,tempfile,unittest
from . import contract as C,geometry as G

class Boundaries(unittest.TestCase):
    def test_real_technical_catalogue_copy_only_job_integer_and_strict_bad_ids(self):
        self.assertEqual(G.positive_job('42'),42);self.assertEqual(G.positive_job(42),42)
        for bad in (True,False,0,-1,1.0,'0','01','+1','-1','1.0',' 1','١'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):G.positive_job(bad)
        with tempfile.TemporaryDirectory()as directory:
            root=pathlib.Path(directory);source=root/'old.sqlite';target=root/'new.sqlite';db=sqlite3.connect(source)
            db.executescript('CREATE TABLE parts(file INTEGER,lo INTEGER,hi INTEGER,task INTEGER,kind TEXT,ref TEXT,window TEXT,parent TEXT,PRIMARY KEY(file,lo,task));'
              'CREATE TABLE base(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,numbers BLOB,meta TEXT,owner_sha BLOB,usable INTEGER);'
              'CREATE TABLE selected(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,mid TEXT,job TEXT,role TEXT,owner TEXT,seen INTEGER DEFAULT 0);')
            db.execute('INSERT INTO parts VALUES(1,0,1,255,?,?,?,?)',('base','exact_ref','exact_window','exact_parent'))
            db.execute('INSERT INTO base VALUES(?,?,?,?,?,?)',(7,'m:rid',b'\x00\x80\xff',b'original-bit-metadata',b'\x00'*32,1))
            db.execute('INSERT INTO selected VALUES(?,?,?,?,?,?,?)',(7,'m:rid','m',42,'TRAIN',json.dumps({'job_id':42,'bits':None}),32767));db.commit();db.close()
            class Budget:
                def check(self):pass
            report=G.convert_catalogue(source,target,Budget());old=G.sqlite_ro(source);new=G.sqlite_ro(target)
            try:
                self.assertEqual(old.execute('SELECT job,typeof(job)FROM selected').fetchone(),('42','text'))
                self.assertEqual(new.execute('SELECT job,typeof(job)FROM selected').fetchone(),(42,'integer'))
                self.assertEqual(G.catalogue_digest(old,True),G.catalogue_digest(new))
                self.assertEqual(old.execute('SELECT *FROM base').fetchall(),new.execute('SELECT *FROM base').fetchall())
                self.assertTrue(report['original_SQLite_unchanged'])
            finally:old.close();new.close()

    def test_real_new_eligibility_disk_original_lookup_and_child_selector_receive_int(self):
        with tempfile.TemporaryDirectory()as directory:
            db=sqlite3.connect(pathlib.Path(directory)/'eligibility.sqlite');wrapped=G.SchemaConnection(db)
            wrapped.executescript('CREATE TABLE eligibility(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,mid TEXT,job TEXT,source_role TEXT,effective_role TEXT,common_population INTEGER,geometry_id TEXT,parent_geometry_id TEXT,fit_eligible INTEGER,fit_reason TEXT);')
            db.execute('INSERT INTO eligibility VALUES(?,?,?,?,?,?,?,?,?,?,?)',(7,'m:rid','m','42','TRAIN','TRAIN',1,'real-g',None,1,'ELIGIBLE'))
            owner={'record_ordinal':7,'record_id':'m:rid','molecule_id':'m','job_id':42,'new_role':'TRAIN'}
            self.assertEqual(G.E.lookup(db,owner)['job_id'],42);self.assertEqual(db.execute('SELECT typeof(job)FROM eligibility').fetchone()[0],'integer')
            bad=dict(owner,job_id=43)
            with self.assertRaises(ValueError):G.E.lookup(db,bad)
            with self.assertRaises(ValueError):wrapped.executescript('CREATE TABLE wrong(job TEXT)')
            selected_jobs={row[0]for row in db.execute('SELECT DISTINCT job FROM eligibility')}
            self.assertEqual([s for s in [{'source_job_id':42},{'source_job_id':43}]if s['source_job_id']in selected_jobs],[{'source_job_id':42}]);db.close()

    def test_original_code_objects_full_inverse_and_truthful_new_scope(self):
        from . import source_inverse,run
        proof=source_inverse.proof();self.assertFalse(proof['old_shared_globals_patched']);self.assertFalse(proof['historical_parent_D4_complete_claimed'])
        self.assertEqual(proof['logical_groups'],171);self.assertTrue(proof['two_numeric_replays_required'])
        self.assertIs(G.metadata_children,G.N.metadata_children);self.assertIs(run.T.__dict__['B'],run.B)
        original=G.E.build;new=G.eligibility_function();self.assertIs(original.__code__,new.__code__)
        self.assertTrue(all(original.__globals__[k]is new.__globals__[k]for k in original.__globals__ if k!='sqlite3'))
        self.assertEqual(C.KEY,'existing_sprime_native_pilot_resume_v2');self.assertEqual(len(C.FILES),8)
        self.assertNotEqual(C.KEY,'existing_sprime_native_pilot_day_v1')
        self.assertEqual(C.RESUME_PARENT_KEYS,('request_reference','submission_reference','proof_reference','plan_reference','accounting_reference','raw_reference'))
        locators=C.deferred_stage_locators(pathlib.Path('/synthetic/actual-old-output'))
        self.assertEqual(locators['receipt'],'/synthetic/actual-old-output/receipt.json')
        self.assertEqual(set(locators),{'receipt','prefix','coverage_manifest','ordinary_root'})
        self.assertNotIn('receipt_reference',C.RESUME_PARENT_KEYS)
        self.assertTrue(proof['old_receipt_reference_established_on_CPU_after_Source6'])
        self.assertFalse(proof['metadata_old_receipt_body_or_SHA_read'])
        reader_memo_boundaries(self)

def reader_memo_boundaries(test):
    import hashlib,os
    memo=G.ReaderMemo(cap=4096,entries=2);memo.put(('one',),{'nested':[1]})
    value=memo.get(('one',));value['nested'].append(2);test.assertEqual(memo.get(('one',)),{'nested':[1]})
    memo.put(('too_large',),'x'*10000);test.assertIsNone(memo.get(('too_large',)))
    memo.put(('two',),2);memo.put(('three',),3);test.assertIsNone(memo.get(('three',)))
    test.assertLessEqual(memo.used,memo.cap);test.assertLessEqual(len(memo.values),memo.entry_cap)
    memo.reset(('changed_catalog_frame',));test.assertIsNone(memo.get(('one',)))
    with tempfile.TemporaryDirectory()as directory:
        root=pathlib.Path(directory);path=root/'verified-source-only-fixture.bin';path.write_bytes(b'original')
        ref={'path':str(path),'bytes':8,'sha256':hashlib.sha256(b'original').hexdigest()}
        original=G.I.require;private=G.private_reader_function(original,ALLOWED={str(path):ref})
        class CountIO:
            def __init__(self):self.whole=0
            def require(self,r,content=True):
                self.whole+=int(content);return private(r,content=content)
        counted=CountIO();memory=G.ReaderMemo();io=G.ReaderMemoIO(memory,counted)
        io.require(ref);io.require(ref);test.assertEqual(counted.whole,1)
        before=G.reader_frame(path);path.write_bytes(b'changed!');test.assertNotEqual(G.reader_frame(path),before)
        with test.assertRaises(ValueError):G.memo_group_end({'canonical':ref},{'canonical':before})
        with test.assertRaises(ValueError):io.require(ref)
        test.assertEqual(counted.whole,2)
        unknown=dict(ref,path=str(root/'unregistered.bin'));(root/'unregistered.bin').write_bytes(b'original')
        with test.assertRaises(ValueError):io.require(unknown)
        db=sqlite3.connect(root/'metadata_only.sqlite');db.executescript('CREATE TABLE base(ordinal INTEGER PRIMARY KEY,numbers BLOB,owner_sha BLOB,usable INTEGER,meta TEXT);')
        db.execute('INSERT INTO base VALUES(7,?,?,1,?)',(b'Z',b'owner','real fixture metadata'));db.commit()
        memory=G.ReaderMemo(cap=4096,entries=4);wrapped=G.MemoSQLite(db,'catalog',('exact_ref','frame'),memory)
        a=wrapped.execute(G.BASE_SQL,(7,)).fetchone();b=wrapped.execute(G.BASE_SQL,(7,)).fetchone()
        test.assertEqual(a,b);test.assertEqual(memory.metrics['SQL_result_hits'],1)
        test.assertEqual(wrapped.execute('SELECT count(*) FROM base').fetchone(),(1,))
        no_cache=G.ReaderMemo(cap=0,entries=1);uncached=G.MemoSQLite(db,'catalog',('exact_ref','frame'),no_cache)
        uncached.execute(G.BASE_SQL,(7,)).fetchone();uncached.execute(G.BASE_SQL,(7,)).fetchone()
        test.assertEqual(no_cache.metrics['original_SQL_queries'],2);test.assertEqual(len(no_cache.values),0)
        db.execute('UPDATE base SET usable=0');db.commit();memory.reset(('new_actual_frame',))
        test.assertEqual(wrapped.execute(G.BASE_SQL,(7,)).fetchone()[2],0);db.close()
        _,part,records,observations=G.reader_functions(G.ReaderMemo())
        test.assertIs(part.__code__,G.ORIGINAL_READER.one_part.__code__)
        test.assertIs(records.__code__,G.ORIGINAL_READER.records.__code__)
        test.assertIs(observations.__code__,G.ORIGINAL_READER.observations.__code__)
        test.assertIs(G.ORIGINAL_STATISTICS.observations,G.ORIGINAL_READER.observations)

if __name__=='__main__':unittest.main()
