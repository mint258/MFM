"""Column-pruned exact FP partition SQL and bounded sorted Parquet export."""
import hashlib
import json
import os
from pathlib import Path
import stat
import time

HEX='0123456789abcdef'
TARGETS=['8','9','a','e','f']


def need(value,message):
    if not value:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'


def predicate(prefixes):
    need(prefixes==TARGETS,'Exactly the authorized MD5 canonical-hex-text far-tail8,9,a,e,f')
    return "substr(md5(ecfp4_2048_hex),1,1) IN ('8','9','a','e','f')"


def validation_sql(bucket):
    need(type(bucket)is str and len(bucket)==1 and bucket in HEX,'One physical raw-FP first nibble')
    return """SELECT count(*),count(*) FILTER(WHERE ecfp4_2048_hex IS NULL
        OR NOT regexp_full_match(ecfp4_2048_hex,'[0-9a-f]{512}')
        OR substr(ecfp4_2048_hex,1,1)<>'"""+bucket+"') FROM incoming_fp"


def selected_sql(prefixes):
    # Multiplicity gives selected original-candidate counts without another
    # MD5 scan. GROUP BY is exactly FP DISTINCT, not a change of molecule scope.
    return 'SELECT ecfp4_2048_hex,count(*) AS multiplicity FROM incoming_fp WHERE '+predicate(prefixes)+' GROUP BY ecfp4_2048_hex ORDER BY ecfp4_2048_hex'


def frame(path):
    value=Path(path).lstat()
    need(stat.S_ISREG(value.st_mode)and value.st_uid==os.getuid(),'Own native regular artifact')
    return (value.st_dev,value.st_ino,value.st_uid,value.st_size,value.st_mtime_ns,value.st_ctime_ns)


def export_bucket(db,paths,bucket,expected_rows,out,reference,parts,journal,check=lambda:None,
                  *,prefixes=TARGETS,max_rows=200000,max_file_bytes=256<<20):
    """Real SQL/Arrow only; caller separately admits actual Alpha allocation."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    need(paths and 0<max_rows<=200000,'Bounded source and <=200k output rows per file')
    db.read_parquet([str(path)for path in paths],union_by_name=False).project('ecfp4_2048_hex').create_view('incoming_fp',replace=True)
    total,invalid=db.execute(validation_sql(bucket)).fetchone()
    need(total==expected_rows and invalid==0,'Full physical candidate bucket row/FP width/domain census')
    folder=Path(out)/('physical_'+bucket);folder.mkdir()
    selected=unique=part_count=0;previous=None;schema=pa.schema([('ecfp4_2048_hex',pa.string())])
    reader=db.execute(selected_sql(prefixes)).fetch_record_batch(max_rows)
    for batch in reader:
        check();values=batch.column(0).cast(pa.string());n=len(values)
        need(0<n<=max_rows and values.null_count==0,'Bounded complete exported FP batch')
        first,last=values[0].as_py(),values[-1].as_py()
        need(previous is None or previous<first,'Strict sorted unique FP order across output parts')
        if n>1:need(pc.all(pc.greater(values.slice(1),values.slice(0,n-1))).as_py(),'Strict sorted unique FPs inside output part')
        need(first[0]==last[0]==bucket,'Every selected FP retains its original physical bucket')
        multiplicity=pc.sum(batch.column(1)).as_py();need(type(multiplicity)is int and multiplicity>=n,'Actual selected-candidate multiplicities')
        selected+=multiplicity;unique+=n;previous=last
        partial=folder/('part_%06d.parquet.partial'%part_count);final=partial.with_suffix('')
        need(not partial.exists()and not final.exists(),'Fresh immutable output shard')
        pq.write_table(pa.Table.from_arrays([values],schema=schema),partial,compression='zstd',row_group_size=min(65536,max_rows))
        with partial.open('rb')as stream:os.fsync(stream.fileno())
        need(partial.stat().st_size<=max_file_bytes,'Single FP-only shard exceeds256MiB')
        os.rename(partial,final);before=frame(final);ref=reference(final)
        footer=pq.ParquetFile(final)
        need(frame(final)==before and footer.metadata.num_rows==n and footer.schema_arrow==schema,'Closed single-column FP Parquet footer/frame/schema')
        item=dict(ref,rows=n,physical_fp_bucket=bucket)
        parts.write(canonical(item));parts.flush();os.fsync(parts.fileno())
        journal.write(canonical(dict(reference=item,current_frame=list(before),closed_at_unix_seconds=time.time(),immutable_after_close=True)))
        journal.flush();os.fsync(journal.fileno());part_count+=1;check()
    need(0<=unique<=selected<=total,'Input/selected-candidate/distinct-FP mass conservation')
    return dict(input_candidate_rows=total,selected_candidate_rows=selected,distinct_fingerprints=unique,part_count=part_count)
