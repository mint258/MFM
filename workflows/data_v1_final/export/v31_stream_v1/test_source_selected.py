"""One tiny D6 selected-row fixture, without production data or benchmarks."""
import json,pickle,sqlite3,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import pyarrow as pa
import pyarrow.parquet as pq
from workflows.data_v1_final.labels.window2_normalization_v1 import reader as R,selected as S,io as I
from workflows.data_v1_final.labels.window2_normalization_v1.r73 import ForwardRaw


def _signature(rows):
    return [(row['file_id'],row['physical_row'],row['record_ordinal'],struct.pack('<d',row['toy_value']))for row in rows]


class D6SelectedRowsCheck(unittest.TestCase):
    def test_d6_selected_rows_and_forward_raw_are_exact(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);tmp_path=Path(temporary.name)
        path=tmp_path/'raw.parquet'
        values=[dict(file_id=7,physical_row=i,record_ordinal=100+i,
                     toy_value=float('nan') if i==42 else -0.0 if i==11 else float(i))for i in range(53)]
        table=pa.Table.from_pylist(values);pq.write_table(table,path,row_group_size=11)
        before=path.read_bytes();reference=I.ref(path)
        ordinals=(111,142)
        expected=[row for row in R.one_part(reference,7,0,53)if row['record_ordinal']in ordinals]
        calls=[];original=pq.ParquetFile
        class Spy:
            def __init__(self,*a,**kw):self.inner=original(*a,**kw)
            def __getattr__(self,name):return getattr(self.inner,name)
            def iter_batches(self,*a,**kw):
                calls.append(kw.get('row_groups'));return self.inner.iter_batches(*a,**kw)
        with patch.object(pq,'ParquetFile',Spy):
            actual=list(S.one_part_selected(reference,7,0,53,ordinals))
        assert _signature(actual)==_signature(expected)
        assert calls==[[1,3]]
        no_stats=tmp_path/'no_stats.parquet';pq.write_table(table,no_stats,row_group_size=11,write_statistics=False)
        assert _signature(S.one_part_selected(I.ref(no_stats),7,0,53,ordinals))==_signature(expected)
        assert list(S.one_part_selected(reference,7,0,53,()))==[]
        with self.assertRaisesRegex(ValueError,'TYPED_PART_PHYSICAL_ORDER'):
            list(S.one_part_selected(reference,8,0,53,ordinals))
        old=ForwardRaw(path);new=S.RowGroupForwardRaw(path)
        try:
            for position in (0,11,22,42,52):
                assert _signature([new.get(position)])==_signature([old.get(position)])
            for value in (52,-1):
                with self.assertRaisesRegex(ValueError,'SOURCE_ROW_MUST_BE_FORWARD'):new.get(value)
            with self.assertRaises(StopIteration):new.get(53)
        finally:old.close();new.close()
        calls=[]
        with patch.object(pq,'ParquetFile',Spy):
            new=S.RowGroupForwardRaw(path)
            try:new.get(42)
            finally:new.close()
        assert calls==[[3]]
        assert path.read_bytes()==before

        # The original observations loop, real tiny SQLite joins and all 14 tasks.
        catalog=tmp_path/'catalog.sqlite';canonical=tmp_path/'canonical.sqlite';elig=tmp_path/'elig.sqlite'
        db=sqlite3.connect(catalog);db.executescript('CREATE TABLE base(ordinal INTEGER,numbers BLOB,owner_sha TEXT,usable INTEGER);CREATE TABLE parts(file INTEGER,kind TEXT,lo INTEGER,hi INTEGER,task TEXT,ref TEXT,parent TEXT);')
        index=sqlite3.connect(canonical)
        index.execute('CREATE TABLE records('+','.join(name+(' INTEGER' if name in ('record_ordinal','job_id','total_atoms')else ' TEXT')for name in R.RECORD_COLUMNS)+')')
        side=sqlite3.connect(elig);side.execute('CREATE TABLE eligibility(ordinal INTEGER,rid TEXT,mid TEXT,job TEXT,source_role TEXT,effective_role TEXT,common_population INTEGER,geometry_id TEXT,parent_geometry_id TEXT,fit_eligible INTEGER,fit_reason TEXT)')
        for i in range(4):
            mid='M0' if i<2 else 'M1';owner=dict(record_ordinal=100+i,record_id='rid'+str(i),molecule_id=mid,attempt_id='attempt',job_id=7,task_id='0',lane='0',total_atoms=1,new_role='TRAIN')
            index.execute('INSERT INTO records VALUES('+','.join('?'for _ in R.RECORD_COLUMNS)+')',tuple(owner[k]for k in R.RECORD_COLUMNS))
            side.execute('INSERT INTO eligibility VALUES(?,?,?,?,?,?,?,?,?,?,?)',(100+i,'rid'+str(i),mid,'7','TRAIN','TRAIN',1,'gid'+str(i),'gid'+str(i),1,'COMMON_TRAIN_NOT_D5'))
            db.execute('INSERT INTO base VALUES(?,?,?,?)',(100+i,struct.pack('<q',6),'owner'+str(i),1))
        for task,code in R.B.TASKS.items():
            part=tmp_path/('part_'+task+'.parquet')
            rows=[dict(file_id=7,physical_row=i*14+code,record_id='rid'+str(i),record_ordinal=100+i,role_code=0,owner_sha256='owner'+str(i),task_code=code,toy_value=float('nan')if i==3 and code==1 else -0.0 if i==2 and code==0 else float(i*14+code))for i in range(4)]
            pq.write_table(pa.Table.from_pylist(rows),part,row_group_size=1)
            db.execute('INSERT INTO parts VALUES(?,?,?,?,?,?,?)',(7,'task',0,56,task,json.dumps(I.ref(part)),'original'))
        db.commit();db.close();index.commit();index.close();side.commit();side.close()
        book=tmp_path/'book.json';I.save(book,{'files':[{'path':str(path),'file_id':7,'source_job_id':'7'}]})
        coverage=tmp_path/'coverage.json';I.save(coverage,{'parts_catalog':I.ref(catalog)})
        cfg=dict(coverage_reference=I.ref(coverage),canonical_index=I.ref(canonical),eligibility_reference=I.ref(elig),source_inventory_reference=I.ref(book),statistics_purpose='D6_export',emit_source=True,filter_mids={'M1'})
        group={'source_job_id':'7','group_index':0,'label_files':[I.ref(path)]}
        def unpack(row,fields):
            return [dict(field_id=1,field={'registry_id':1},values_float64=[row['toy_value']],value_mask=[True])]
        patcher=patch.object(R.K,'unpack_entries',unpack);patcher.start();self.addCleanup(patcher.stop)
        original_rows=list(R.observations(cfg,group,[{'field_id':1}]))
        selected_rows=list(R.observations(dict(cfg,d6_selected_row_groups=True),group,[{'field_id':1}]))
        assert len(original_rows)==len(selected_rows)==28
        assert _signature([r[3]for r in original_rows])==_signature([r[3]for r in selected_rows])
        for left,right in zip(original_rows,selected_rows):
            assert left[0]==right[0] and left[1]==right[1]==[6] and left[4]==right[4]
            assert left[2][0]['value_mask']==right[2][0]['value_mask']==[True]
            assert struct.pack('<d',left[2][0]['values_float64'][0])==struct.pack('<d',right[2][0]['values_float64'][0])
        with self.assertRaisesRegex(ValueError,'SELECTED_ROW_GROUPS_ARE_D6_ONLY'):
            list(R.observations(dict(cfg,d6_selected_row_groups=True,statistics_purpose='normalization_moments'),group,[{'field_id':1}]))
        # Removing a selected record remains a real original 14-task mass failure.
        db=sqlite3.connect(catalog);task,packed=db.execute('SELECT task,ref FROM parts ORDER BY task LIMIT 1').fetchone()
        ref=json.loads(packed);part=__import__('pathlib').Path(ref['path']);rows=pq.read_table(part).to_pylist()[:-1]
        pq.write_table(pa.Table.from_pylist(rows),part,row_group_size=1)
        db.execute('UPDATE parts SET ref=? WHERE task=?',(json.dumps(I.ref(part)),task));db.commit();db.close()
        for fast in (False,True):
            with self.assertRaisesRegex(ValueError,'ORIGINAL_14_TASK_RECORD_MASS'):
                list(R.observations(dict(cfg,d6_selected_row_groups=fast),group,[{'field_id':1}]))
