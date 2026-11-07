"""Three synthetic boundaries, same real allocation before any actual DATA."""
import copy,hashlib,json,os,sqlite3,tempfile,unittest
from pathlib import Path
from . import contracts as C,run as R
ROOT=None
class TinyBudget:
    stop=None
    def dispatch_check(self):pass
    def capacity(self,extra=0):assert type(extra) is int and extra>=0
def observation(table,identity,**changes):
    from secondary_coconut_identity_norm_profile_v1.run import FIELDS
    fields=dict.fromkeys(FIELDS[table]);fields.update(id=identity,**changes);names=('canonical_smiles',) if table=='molecules' else ('canonical_smiles','standardized_canonical_smiles','parent_canonical_smiles')
    src={'source_table':table,'copy_block':1,'source_row_ordinal':1,'source_offset':0,'source_bytes':4,'source_row_sha256':hashlib.sha256(b'syn\n').hexdigest(),'identity_fields_json':json.dumps(fields)}
    variants=[{'source_field':name,'state':'MISSING_OR_EMPTY','keys':[]} for name in names]
    return {'source':src,'variant_observations':variants,'source_full_keys_valid':[],'source_full_keys_invalid':[],'SMILES_derived_full_keys':[],
      'conservative_full_key_union':[],'has_any_valid_full_key':False,'unresolved_present_variants':0,'missing_variants':len(names),'stored_vs_computed_disagreement':False}
class Boundaries(unittest.TestCase):
    def test_sparse_norm_same_physical_row_and_SQL_opaque_offset_SHA(self):
        import pyarrow as pa,pyarrow.parquet as pq
        with tempfile.TemporaryDirectory(prefix='synthetic_sparse_',dir=ROOT) as folder:
            root=Path(folder);rows=[]
            for i in range(1,5):
                value=observation('entries','synthetic_'+str(i));value['source']['source_row_ordinal']=i
                rows.append({'source_table':'entries','copy_block':1,'source_row_ordinal':i,'observation_json':json.dumps(value)})
            pq.write_table(pa.Table.from_pylist(rows),root/'norm.parquet',row_group_size=2);ref=R.I.pin(root/'norm.parquet')
            got=list(R.selected_parquet(ref,{('entries',1,3)},TinyBudget(),norm=True));self.assertEqual([k for k,_ in got],[('entries',1,3)])
            with self.assertRaises(ValueError):list(R.selected_parquet(ref,{('entries',2,3)},TinyBudget(),norm=True))
            raw=b'head\noriginal\twhole\trow\n';(root/'source.sql').write_bytes(raw);data=raw[5:];source={'source_offset':5,'source_bytes':len(data),'source_row_sha256':hashlib.sha256(data).hexdigest()}
            fd=os.open(root/'source.sql',os.O_RDONLY)
            try:
                out=R.opaque_row(fd,source,TinyBudget(),root,0);self.assertEqual(Path(out['path']).read_bytes(),data)
                with self.assertRaises(ValueError):R.opaque_row(fd,dict(source,source_row_sha256='0'*64),TinyBudget(),root,1)
            finally:os.close(fd)
    def test_original_project_exact_FK_missing_and_whole_formula_not_partial(self):
        value=observation('entries','synthetic_e',molecule_id='synthetic_m');before=copy.deepcopy(value)
        orphan=R.K.project(value,[],None);self.assertEqual(orphan['FK_state'],'ORPHAN');self.assertFalse(orphan['covered'])
        parent={'molecule_id':'synthetic_m','keys':['AAAAAAAAAAAAAA-BBBBBBBBBB-C'],'compositions':[],'locator':{'synthetic_only':True}}
        matched=R.K.project(value,[],parent);self.assertEqual(matched['FK_state'],'MATCHED');self.assertTrue(matched['covered']);self.assertEqual(value,before)
        missing=R.K.project(observation('entries','synthetic_null'),[],None);self.assertEqual(missing['FK_state'],'NULL');self.assertFalse(missing['covered'])
        formula=R.K.formula('C2H6O');self.assertIsNotNone(formula['composition']);self.assertIsNone(R.K.formula('C2H6O_garbage')['composition'])
        replay=R.replay_batch([({'locator':{'source_table':'entries'},'FK_state':'ORPHAN','field_availability':{}},value,[],parent)])[0]
        self.assertTrue(replay['original_UNKNOWN_unchanged']);self.assertFalse(replay['strict5_written']);self.assertFalse(replay['new_authoritative_keys'])
    def test_large_fixed_SQLite_first_CPU_SHA_frame_and_sidecar_rejection(self):
        with tempfile.TemporaryDirectory(prefix='synthetic_bootstrap_',dir=ROOT) as folder:
            root=Path(folder);path=root/'identity_links.sqlite';db=sqlite3.connect(path);db.execute('CREATE TABLE x(value BLOB)');db.execute('INSERT INTO x VALUES(?)',(b'x'*(2*1024**2+8192),));db.commit();db.close()
            stat=path.stat();expected=dict(R.observed_frame(stat),device=stat.st_dev)
            authority={'fixed_index_path':str(path),'fixed_output_root':str(root),'actual_lstat':expected}
            with R.bootstrap_index(authority,TinyBudget()) as (db,ref,frame):
                self.assertGreater(ref['bytes'],2<<20);self.assertEqual(ref['sha256'],hashlib.sha256(path.read_bytes()).hexdigest());self.assertEqual(db.execute('SELECT count(*) FROM x').fetchone()[0],1);self.assertTrue(frame['first_hash_performed_in_this_CPU'])
            C.triple(ref)
            with self.assertRaises(ValueError):
                with R.bootstrap_index(dict(authority,actual_lstat=dict(expected,inode=expected['inode']+1)),TinyBudget()):pass
            Path(str(path)+'-journal').write_bytes(b'')
            with self.assertRaises(ValueError):
                with R.bootstrap_index(authority,TinyBudget()):pass
