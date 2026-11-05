"""Three synthetic closed-prefix/source/order boundaries; no Native/real DATA."""
import copy,hashlib,json,pathlib,struct,unittest
from . import metadata as M,hof_resume as H
WORKSPACE=None

class Context:
    def __init__(self,out,stop_after=None):
        self.out=pathlib.Path(out);self.out.mkdir();self.stop=None;self.calls=0;self.stop_after=stop_after
        self.plan={'hof_closed_prefix_reuse_review_reference':{'path':'/synthetic/Root_review','bytes':1,'sha256':'1'*64}}
        self.proof={'job_id':'4242000'};self.reserved={};self.copied_bytes=0
    def reserve(self,key,n):
        if key in self.reserved:raise ValueError('DUPLICATE_COPY_RESERVATION')
        self.reserved[key]=n
    def release(self,key):self.reserved.pop(key)
    def commit_closed_copy(self,path,n):self.copied_bytes+=n
    def check(self):
        if self.stop:raise ValueError(self.stop)
    def observe(self):
        self.calls+=1
        if self.stop_after is not None and self.calls>self.stop_after:self.stop='SYNTHETIC_FINITE_RESOURCE_STOP'
        return self.stop
    def write_json_new(self,path,value):return M.write(path,value)
    def reference(self,path):return M.pin(path)

class Boundaries(unittest.TestCase):
    def test_closed_database_copy_and_exact180_source_prefix(self):
        import duckdb
        root=pathlib.Path(WORKSPACE)/'synthetic_hof_copy';root.mkdir();source=root/'old.duckdb'
        db=duckdb.connect(str(source));db.execute('CREATE TABLE marker(value BIGINT)');db.execute('INSERT INTO marker VALUES (7)');db.execute('CHECKPOINT');db.close()
        ref=M.pin(source);ctx=Context(root/'new');copied=H.clone(ctx,ref,ctx.out/'work.duckdb')
        self.assertEqual((copied['bytes'],copied['sha256']),(ref['bytes'],ref['sha256']))
        db=duckdb.connect(copied['path'],read_only=True);self.assertEqual(db.execute('SELECT value FROM marker').fetchall(),[(7,)]);db.close()
        needed=[{'synthetic_source':i} for i in range(184)]
        notes=[{'source':r,'status':'ORIGINAL_SCALAR_READER_CLOSED'} for r in needed[:180]]
        self.assertEqual(H.ordered_prefix(needed,notes,180),needed[180:])
        metas=[{'molecule_id':'m'+str(i)} for i in range(5)];by={r['molecule_id']:[r] for r in metas}
        segments=H.scheduled_segments([{'molecules':5}],{0:2},{0:1})
        self.assertEqual([(r['phase'],r['molecules']) for r in segments],
          [('PILOT_PRIORITY',2),('DIAGNOSTIC_CANDIDATE_PRIORITY',1),('ORIGINAL_REMAINDER',2)])
        union=[]
        for segment in segments:
            selected,records=H.select_scheduled(metas,by,{'m0','m2'},{'m2','m3'},segment['phase'])
            union.extend(r['molecule_id'] for r in selected)
            for row in selected:self.assertIs(records[row['molecule_id']],by[row['molecule_id']])
        self.assertEqual(union,['m0','m2','m3','m1','m4']);self.assertEqual(len(set(union)),5)
        from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import contract as D4
        from workflows.data_v1_final.conformers.pm7_precache_day_v1 import io as old_io
        from . import io as new_io
        old,new=(D4.prefix_adapter({'scope_key':key,'execution_argv':[M.PY,'-B','-m',module]}) for key,module in
          (('pm7_precache_day_v1','workflows.data_v1_final.conformers.pm7_precache_day_v1.run'),(M.KEY,M.MODULE)))
        self.assertIs(old[1],old_io);self.assertIs(new[1],new_io);self.assertEqual(old_io.DAY_LEDGER,new_io.DAY_LEDGER)

    def test_duplicate_gap_contaminated_and_changed_closed_input_refused(self):
        needed=[{'synthetic_source':i} for i in range(184)]
        notes=[{'source':r,'status':'ORIGINAL_SCALAR_READER_CLOSED'} for r in needed[:180]]
        for transform in ('duplicate','gap','polluted','unclosed'):
            bad=copy.deepcopy(notes)
            if transform=='duplicate':bad[1]=copy.deepcopy(bad[0])
            if transform=='gap':bad[1]['source']=needed[2]
            if transform=='polluted':bad[1]['source']={'foreign':'not original source'}
            if transform=='unclosed':bad[1]['status']='SOURCE_HOF_PENDING_GEOMETRY_NOT_DROPPED'
            with self.assertRaises(ValueError):H.ordered_prefix(needed,bad,180)
        root=pathlib.Path(WORKSPACE)/'synthetic_bad_closed_hash';root.mkdir();source=root/'closed.bin';source.write_bytes(b'synthetic closed bytes')
        ref=dict(M.pin(source),sha256='0'*64)
        with self.assertRaises(ValueError):H.clone(Context(root/'new'),ref,root/'new'/'work.duckdb')
        with self.assertRaises(ValueError):H.scheduled_segments([{'molecules':5}],{0:2},{0:4})
        with self.assertRaises(ValueError):H.scheduled_segments([{'molecules':5}],{0:2},{1:1})

    def test_real_original_scalar_reader_four_sources_and_incomplete_boundary(self):
        import duckdb,pyarrow as pa,pyarrow.parquet as pq
        root=pathlib.Path(WORKSPACE)/'synthetic_hof_four';root.mkdir();sources=[];rows=[]
        schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('attempt_id',pa.int64()),
          ('job_id',pa.int64()),('task_id',pa.string()),('lane',pa.int64()),('total_atoms',pa.int64()),
          ('calc_type',pa.string()),('status',pa.string()),('numeric_issues',pa.list_(pa.int64())),('converged',pa.bool_()),
          ('values',pa.list_(pa.struct([('registry_id',pa.int64()),('kind',pa.int64()),('f64',pa.float64())])))])
        for i in range(4):
            row={'record_id':'r'+str(i),'molecule_id':'m'+str(i),'attempt_id':1,'job_id':100+i,'task_id':'t',
              'lane':0,'total_atoms':1,'calc_type':'pm7_B','status':'SUCCESS','numeric_issues':[],
              'converged':False if i==3 else True,'values':[{'registry_id':60,'kind':1,'f64':-0.0 if i==0 else -1.25-i}]}
            path=root/('source_%d.parquet'%i);pq.write_table(pa.Table.from_pylist([row],schema=schema),path)
            self.assertEqual(pq.read_table(path).to_pylist(),[row])
            sources.append(dict(M.pin(path),family='pm7_neutral',source_file_group=i,source_job_id=100+i,
              inherited_full_readback_verified=i!=2));rows.append(row)
        def database():
            db=duckdb.connect();db.execute('CREATE TABLE formal(record_id VARCHAR,molecule_id VARCHAR,total_atoms BIGINT,file_group BIGINT)')
            db.execute('CREATE TABLE hof_owners(molecule_id VARCHAR,attempt_id BIGINT,job_id BIGINT,task_id VARCHAR,lane BIGINT)')
            db.execute('CREATE TABLE hof(record_id VARCHAR PRIMARY KEY,value_json VARCHAR,duplicate BOOLEAN DEFAULT FALSE)')
            for i,row in enumerate(rows):
                db.execute('INSERT INTO formal VALUES(?,?,?,?)',[row['record_id'],row['molecule_id'],1,i])
                db.execute('INSERT INTO hof_owners VALUES(?,?,?,?,?)',[row['molecule_id'],1,100+i,'t',0])
            original=H.H.profile_common().decode_hof(rows[0])
            db.execute('INSERT INTO hof VALUES(?,?,FALSE)',['r0',H.C.canonical(original).decode()]);return db,original
        notes=[{'source':{'synthetic_closed_source':i},'status':'ORIGINAL_SCALAR_READER_CLOSED'} for i in range(180)]
        base={'hof_authority_review':{'path':'/synthetic/authority','bytes':1,'sha256':'2'*64}}
        db,original=database();ctx=Context(root/'complete');ref,complete=H.project_remaining(ctx,db,base,notes,sources)
        self.assertTrue(complete);evidence=M.meta(ref);self.assertEqual(evidence['actual_new_sources_processed'],4)
        self.assertEqual(evidence['actual_new_sources_reader_closed'],3)
        saved,duplicate=db.execute("SELECT value_json,duplicate FROM hof WHERE record_id='r0'").fetchone()
        self.assertTrue(duplicate);self.assertEqual(saved,H.C.canonical(original).decode())
        self.assertEqual(struct.pack('<d',json.loads(saved)['value_kcal_mol']),struct.pack('<d',-0.0))
        values=H.ORIGINAL_HOF.values(db,[{'record_id':r['record_id'],'molecule_id':r['molecule_id']} for r in rows])
        self.assertEqual(values['r0']['reason'],'DUPLICATE_CANONICAL_HOF_ACROSS_FILES')
        self.assertEqual(values['r2']['reason'],'CANONICAL_HOF_SOURCE_READ_OR_VALIDATION_FAILED')
        self.assertEqual(values['r3']['reason'],'SCF_NOT_CONVERGED');db.close()
        db,_=database();partial=Context(root/'partial',stop_after=2)
        ref,complete=H.project_remaining(partial,db,base,notes,sources)
        self.assertFalse(complete);self.assertFalse(M.meta(ref)['reader_complete'])
        self.assertEqual(M.meta(ref)['actual_new_sources_processed'],2);db.close()
