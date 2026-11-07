"""Three fast IO boundaries; original three math boundaries stay in same Parent."""
import hashlib,sqlite3,unittest
from . import fast_coverage as F,geometry as G,contract as C

class Boundaries(unittest.TestCase):
    def test_full_fixed32_digest_offset_null_and_arrow_selected_order_bits(self):
        import pyarrow as pa,pyarrow.compute as pc
        values=[bytes([k])*32 for k in range(5)];a=pa.array(values,type=pa.binary(32));h=hashlib.sha256();F.digest_array(h,a.slice(1,3))
        self.assertEqual(h.hexdigest(),hashlib.sha256(b''.join(values[1:4])).hexdigest())
        with self.assertRaises(ValueError):F.digest_array(hashlib.sha256(),pa.array([None],type=pa.binary(32)))
        table=pa.record_batch([pa.array(['a','b','a','c']),pa.array([b'\x00\x00\x00\x00\x00\x00\x00\x80',b'other',b'\x01\x00\x00\x00\x00\x00\xf8\x7f',None])],names=['record_id','data_f64'])
        selected=table.filter(pc.is_in(table.column(0),value_set=pa.array(['a'])))
        self.assertEqual(selected.to_pylist(),[table.to_pylist()[0],table.to_pylist()[2]])
        self.assertEqual(F.BATCH_ROWS,16)

    def test_original_all14_plus_base_mass_duplicate_gap_and_field_denominators(self):
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE selected(ordinal INTEGER PRIMARY KEY,seen INTEGER)');db.execute('INSERT INTO selected VALUES(7,0)')
        F.update_seen(db,[(7,k)for k in range(15)]);stats={str(k):{'records':1}for k in range(146)}
        F.complete_mass(db,1,1,14,stats)
        for items in ([(7,0)],[(8,1)],[(7,True)],[(7,15)]):
            with self.subTest(items=items),self.assertRaises(ValueError):F.update_seen(db,items)
        with self.assertRaises(ValueError):F.complete_mass(db,2,1,14,stats)
        bad=dict(stats);bad['0']={'records':0}
        with self.assertRaises(ValueError):F.complete_mass(db,1,1,14,bad)
        db.close()

    def test_exact_original_science_new_scope_private_reader_and_integer_IO(self):
        from . import source_inverse
        self.assertTrue(source_inverse.proof()['whole_old_SHA_stream_digest_and_mass_preserved'])
        self.assertIs(G.build,G.ORIGINAL.build);self.assertIs(G.metadata_children,G.ORIGINAL.metadata_children)
        self.assertIs(G.STATISTICS.original,G.MEMO.ORIGINAL_STATISTICS)
        self.assertNotEqual(C.KEY,'existing_sprime_native_pilot_day_v1');self.assertEqual(len(C.FILES),10)
        # Same actual Source method, including real small SHA/SQL/memo fixtures.
        reader_memo_boundaries(self)

def reader_memo_boundaries(test):
    import hashlib,os
    import pathlib,sqlite3,tempfile
    from . import reader_memo as G
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
