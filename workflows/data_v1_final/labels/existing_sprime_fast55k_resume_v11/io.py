"""Reuse five closed tables by exact original-row replay; new writes stay native."""
import hashlib,pathlib,stat
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v10 import io as OLD
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from workflows.data_v1_final.export.lossless_sqlite_io_v1.codec import encode_raw
from . import contract as C

COMPLETE=('geometries.parquet','atom_counts.parquet','roster.parquet',
          'diagnostic_base.parquet','diagnostic_targets.parquet')
PARTIAL='prior5481_unaccepted_program_input_views.parquet'
ACTIVE='actual_unperturbed_program_input_views.parquet'
REUSE_CONTEXT=None
writer_function=OLD.writer_function

def frame(path):
    s=path.lstat()
    C.need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and s.st_nlink==1,
      'OWNED_SINGLE_CLOSED_SERIALIZATION_TABLE')
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

class ReuseContext:
    def __init__(self,plan,root,budget):
        global REUSE_CONTEXT
        self.root=pathlib.Path(root);self.budget=budget;self.reports=[]
        review=C.meta(plan['metadata_recovery_reference'])
        C.need(review['old_job_id']=='4525481' and review['new_output_root']==str(self.root.parent),
          'ACTUAL_CLOSED5481_SERIALIZATION_ORIGIN')
        self.files={pathlib.Path(r['path']).name:r for r in review['staged_serialization_files']}
        C.need(set(self.files)==set(COMPLETE)|{PARTIAL},'FIVE_CLOSED_TABLES_AND_ONE_UNACCEPTED_PARTIAL')
        C.need(REUSE_CONTEXT is None,'ONE_SERIALIZATION_CONTEXT_PER_ACTUAL_PARENT')
        REUSE_CONTEXT=self
    def write_parquet(self,path,rows,schema,*,row_group_size=256):
        import pyarrow as pa,pyarrow.parquet as pq
        p=pathlib.Path(path)
        if p.name not in COMPLETE:
            C.need(p==self.root/ACTIVE and not p.exists(),'ONLY_NEW_FULL_INPUT_VIEWS_WRITTEN')
            return writer_function()(p,rows,schema,row_group_size=row_group_size)
        C.need(p==self.root/p.name and row_group_size==256
          and len(self.reports)<len(COMPLETE)
          and [r['name'] for r in self.reports]==list(COMPLETE[:len(self.reports)])
          and p.name==COMPLETE[len(self.reports)],'EXACT_ORIGINAL_CLOSED_TABLE_ORDER')
        source=self.files[p.name];before=frame(p)
        C.need(before[1:4]==(source['inode'],source['size'],source['mtime_ns'])
          and source['original_full_write_and_readback_passed'] is True,
          'EXACT_STAGED_COMPLETED5481_FILE_NOT_PARTIAL_ADOPTION')
        parquet=pq.ParquetFile(p,pre_buffer=False)
        expected=hashlib.sha256();actual=hashlib.sha256();count=0;actual_count=0;buffer=[]
        def digest_expected(values):
            for row in pa.Table.from_pylist(values,schema=schema).to_pylist():
                expected.update(encode_raw(row))
        try:
            C.need(parquet.schema_arrow.equals(schema,check_metadata=False),
              'ORIGINAL_CLOSED_TABLE_SCHEMA_EXACT')
            for row in rows:
                C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_BEFORE_NEXT_TYPED_ROW')
                buffer.append(row);count+=1
                if len(buffer)==row_group_size:
                    digest_expected(buffer);buffer=[];self.budget.check()
            if buffer:digest_expected(buffer)
            for batch in parquet.iter_batches(batch_size=256,use_threads=False):
                self.budget.check()
                for row in batch.to_pylist():actual.update(encode_raw(row));actual_count+=1
            C.need(count==actual_count==parquet.metadata.num_rows and actual.digest()==expected.digest(),
              'ORIGINAL_EXPECTED_ROWS_AND_FULL_CLOSED_F64_NONE_MASK_ORDER_EXACT_REPLAY')
        finally:parquet.close()
        C.need(frame(p)==before,'CLOSED_TABLE_STABLE_DURING_FULL_SEMANTIC_REPLAY')
        result=I.allow(I.pin(p));I.require(result)
        C.need(frame(p)==before,'CLOSED_TABLE_STABLE_THROUGH_WHOLE_FILE_REFERENCE')
        self.reports.append(dict(name=p.name,rows=count,reference=result,
          exact_original_row_semantic_sha256=actual.hexdigest(),original_F64_None_mask_order_exact=True,
          file_rewritten=False,old_partial_input_views_adopted=False))
        return result

def proof():
    value=OLD.proof()
    value.update(five_closed_tables_reused_only_after_original_full_semantic_replay=True,
      partial_input_views_never_scientifically_adopted=True,
      new_full_input_views_original_writer_and_defaults=True)
    return value
