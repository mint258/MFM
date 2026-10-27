"""Three synthetic raw/immutable/input-identity boundaries; no real data."""
import gzip,hashlib,json,pathlib,sqlite3,tempfile,unittest
from . import reader as D,contract as C


class Boundaries(unittest.TestCase):
    archive=None
    def test_original_bounded_gzip_EOF_CRC_and_size(self):
        fn=D.Parent.get.__globals__['bounded_gzip'];data=b'original-output-token\n';packed=gzip.compress(data,mtime=0)
        self.assertEqual(fn(packed,len(data)),data)
        with self.assertRaises(ValueError):fn(packed,len(data)-1)
        broken=bytearray(packed);broken[-8]^=1
        with self.assertRaises((OSError,EOFError)):fn(bytes(broken),len(data))
    def test_exact_original_get_on_immutable_synthetic_SQLite(self):
        with tempfile.TemporaryDirectory(prefix='pprime_readonly_fixture_') as folder:
            path=pathlib.Path(folder)/'synthetic.sqlite';data,manifest=self.archive.bundle([{'name':'process.out','data':b'finished\n'}])
            sha=hashlib.sha256(data).hexdigest();db=sqlite3.connect(path)
            db.execute('CREATE TABLE raw(record_id TEXT,calc_type TEXT,execution_id TEXT,metadata_json TEXT,raw_sha256 TEXT,raw_bytes INTEGER,frame BLOB)')
            db.execute('INSERT INTO raw VALUES(?,?,?,?,?,?,?)',('rid','task','execution',json.dumps({'output_file_manifest':manifest}),sha,len(data),gzip.compress(data,mtime=0)))
            db.commit();db.close();reader=D.ImmutableReader(path,self.archive,1<<20,1<<20)
            try:
                self.assertIs(D.ImmutableReader.get,D.Parent.get);self.assertEqual(reader.get('rid','task','execution',sha,len(data))['output_files'][0]['data'],b'finished\n')
                with self.assertRaises(sqlite3.OperationalError):reader.db.execute('DELETE FROM raw')
            finally:reader.close()
            self.assertFalse(pathlib.Path(str(path)+'-journal').exists())
    def test_exact_observed_frame_and_input_bytes_reject_mutation(self):
        from .run import inputs
        with tempfile.TemporaryDirectory(prefix='pprime_input_fixture_') as folder:
            root=pathlib.Path(folder);target=root/'target';actual=root/'actual';target.mkdir();actual.mkdir();refs=[];paths={}
            for name,data in (('input.xyz',b'1\ncomment\nH 0.000000000000 0.000000000000 0.000000000000\n'),('native.inp',b'$write\n json=true\n$end\n')):
                (target/name).write_bytes(data);(actual/name).write_bytes(data);refs.append(C.I.ref(target/name));paths[name]=actual/name
            bundle,_=self.archive.bundle([{'name':p.name,'data':p.read_bytes()} for p in target.iterdir()])
            intent={'input_file_sha256':[{'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(target.iterdir())],
                'input_bundle_sha256':hashlib.sha256(bundle).hexdigest()}
            self.assertEqual(len(inputs({'target_input_references':refs},intent,paths,self.archive)[0]),2)
            p=paths['input.xyz'];s=p.lstat();row=dict(zip(('dev','ino','bytes','mtime_ns','ctime_ns','uid','mode'),D.frame(s)),path=str(p))
            self.assertEqual(D.verify(row),p);p.write_bytes(b'changed')
            with self.assertRaises(ValueError):D.verify(row)
            with self.assertRaises(ValueError):inputs({'target_input_references':refs},intent,paths,self.archive)
