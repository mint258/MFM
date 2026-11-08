"""D6-only selected row groups; exact rows and forward raw access."""
import bisect
from . import io as I


def one_part_selected(reference,expected_file,lo,hi,ordinals):
    """Yield the same ordered subset without converting unrelated label rows."""
    if not ordinals:return
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    table=pq.ParquetFile(I.require(reference),pre_buffer=False);last=-1
    try:
        metadata=table.metadata;groups=[]
        column=next((i for i in range(metadata.num_columns)
                     if metadata.num_row_groups and metadata.row_group(0).column(i).path_in_schema=='record_ordinal'),None)
        for number in range(metadata.num_row_groups):
            stats=metadata.row_group(number).column(column).statistics if column is not None else None
            keep=True
            if stats is not None and stats.has_min_max:
                low,high=stats.min,stats.max
                if isinstance(low,int) and isinstance(high,int):
                    at=bisect.bisect_left(ordinals,low)
                    keep=at<len(ordinals) and ordinals[at]<=high
            if keep:groups.append(number)
        wanted=pa.array(ordinals,type=table.schema_arrow.field('record_ordinal').type)
        for batch in table.iter_batches(batch_size=256,row_groups=groups,use_threads=False):
            mask=pc.is_in(batch.column(batch.schema.get_field_index('record_ordinal')),value_set=wanted)
            for row in batch.filter(mask).to_pylist():
                if not (row['file_id']==expected_file and lo<=row['physical_row']<hi and row['physical_row']>last):
                    raise ValueError('TYPED_PART_PHYSICAL_ORDER')
                last=row['physical_row'];yield row
    finally:table.close()


class RowGroupForwardRaw:
    """Original ForwardRaw.get semantics while skipping unused leading groups."""
    def __init__(self,path,columns=None):
        import pyarrow.parquet as pq
        self.file=pq.ParquetFile(path,pre_buffer=False);self.columns=columns
        self.starts=[];self.ends=[];offset=0
        for number in range(self.file.metadata.num_row_groups):
            self.starts.append(offset);offset+=self.file.metadata.row_group(number).num_rows;self.ends.append(offset)
        self.group=None;self.iterator=None;self.batch=None;self.lo=0;self.hi=0;self.last=-1
    def get(self,index):
        if index<=self.last:raise ValueError('SOURCE_ROW_MUST_BE_FORWARD')
        group=bisect.bisect_right(self.ends,index)
        if group==len(self.ends):raise StopIteration
        if group!=self.group:
            self.group=group;self.iterator=self.file.iter_batches(batch_size=16,columns=self.columns,row_groups=[group],use_threads=False)
            self.batch=None;self.lo=self.hi=self.starts[group]
        while self.batch is None or index>=self.hi:
            self.batch=next(self.iterator);self.lo=self.hi;self.hi+=self.batch.num_rows
        self.last=index;return self.batch.slice(index-self.lo,1).to_pylist()[0]
    def close(self):self.file.close()
