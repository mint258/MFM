"""One bounded actual-footer member per selected source; no Parquet body IO."""
from __future__ import annotations
import gzip,hashlib,json,os
from pathlib import Path
from .control import need
from workflows.data_v1_final.labels.bounded_projection_v1.materialize import footer_inputs,load,require,triple
from workflows.data_v1_final.labels.bounded_projection_v1.parts import slices
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity


def select_groups(groups,cursor,stop,limit):
    need(type(cursor) is int and type(stop) is int and 0<=cursor<stop and type(limit) is int and limit>0,'FINITE_ACTUAL_CURSOR_TILE')
    selected=[]
    for g in groups:
        if g['physical_row_hi']<=cursor:continue
        if g['physical_row_lo']>=stop:break
        selected.append(g)
        if len(selected)==limit:break
    need(selected,'NONEMPTY_ACTUAL_RG_TILE')
    hi=min(stop,selected[-1]['physical_row_hi']);list(slices(selected,cursor,hi))
    return selected,hi


def resolve(cfg):
    """Whole-stream producer SHA is lineage; exact selected member SHA is read.

    Rehashing a multi-source gzip stream on every continuation is unnecessary:
    this path verifies its current same-fd stable frame and the exact compressed
    and uncompressed member hashes from the actual C0 footer index. It does
    not claim a fresh whole-stream or a fresh original-Parquet whole-file SHA.
    """
    footer=load(require(cfg['footer_manifest_reference']));book,index,_,_,_=footer_inputs(footer)
    byid={r['file_id']:r for r in book['files']};selectors=load(require(cfg['selector_reference']))['sources']
    ranges=[];member_observations=[]
    for selector in selectors:
        fid=selector['file_id'];observed=index[fid];reference=observed['inventory_reference'];p=Path(reference['path'])
        before=identity(p);need(before[2]==reference['bytes'],'METADATA_STREAM_SIZE_CHANGED')
        lo,hi=observed['gzip_member_byte_lo'],observed['gzip_member_byte_hi'];need(0<=lo<hi<=reference['bytes'] and hi-lo<=128<<20,'BOUNDED_ACTUAL_MEMBER')
        with p.open('rb') as f:
            initial=os.fstat(f.fileno())
            need([initial.st_dev,initial.st_ino,initial.st_size,initial.st_mtime_ns,initial.st_ctime_ns]==before,'SAME_FD_METADATA_SOURCE')
            f.seek(lo);compressed=f.read(hi-lo)
            after=os.fstat(f.fileno())
            need([after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns]==before==identity(p),'METADATA_MEMBER_STABLE_FRAME')
        need(len(compressed)==hi-lo and hashlib.sha256(compressed).hexdigest()==observed['gzip_member_sha256'],'EXACT_SELECTED_COMPRESSED_MEMBER_SHA')
        raw=gzip.decompress(compressed);del compressed
        need(len(raw)==observed['uncompressed_member_bytes'] and len(raw)<=64<<20
          and hashlib.sha256(raw).hexdigest()==observed['uncompressed_member_sha256'],'EXACT_SELECTED_RAW_MEMBER_SHA')
        head=schema=None;groups=[]
        for line in raw.splitlines():
            if b'"type":"column_chunk"' in line:continue
            row=json.loads(line)
            if row['type']=='source':head=row
            elif row['type']=='schema':schema=row
            elif row['type']=='row_group':groups.append(row)
        del raw
        source=byid[fid];need(head is not None and schema is not None and head['source']==source
          and schema['physical_rows']==source['rows'] and len(groups)==schema['row_groups'],'ACTUAL_C0_SOURCE_DIRECTORY')
        groups,stop=select_groups(groups,selector['physical_row_lo'],selector['physical_row_hi'],cfg['max_actual_RGs_per_source'])
        start=selector['physical_row_lo'];key=hashlib.sha256(json.dumps([triple(source),start,stop],sort_keys=True,separators=(',',':')).encode()).hexdigest()[:24]
        ranges.append({'range_id':key,'file_id':fid,'source':source,'physical_row_lo':start,'physical_row_hi':stop,
          'groups':groups,'file_row_groups':schema['row_groups'],'expected_footer_sha256':observed['actual_footer_sha256'],
          'footer_observed_source_frame':observed['source_frame_before_after'],'metadata_member_reference':reference})
        member_observations.append({'file_id':fid,'whole_stream_reference_inherited':reference,'stable_current_stream_frame':before,
          'compressed_member_bytes_read':hi-lo,'compressed_member_sha256':observed['gzip_member_sha256'],
          'raw_member_bytes_read':observed['uncompressed_member_bytes'],'raw_member_sha256':observed['uncompressed_member_sha256']})
    return {'schema':'FULL_LABEL_BATCH_ACTUAL_RANGE_PLAN_V1','ranges':ranges,'source_metadata_member_observations':member_observations,
      'original_Parquet_wholebody_SHA':'INHERITED_PRODUCER_NOT_REHASHED_THIS_JOB','label_bodies_read':False,
      'actual_selected_physical_rows':sum(r['physical_row_hi']-r['physical_row_lo'] for r in ranges),
      'actual_selected_row_groups':sum(len(r['groups']) for r in ranges)}
