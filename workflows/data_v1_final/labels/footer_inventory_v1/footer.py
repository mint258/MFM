"""Bounded original-footer reads; no Parquet data-page or value APIs."""
from __future__ import annotations
import hashlib,json,struct


def need(value,message):
    if not value:raise ValueError(message)


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def footer_only(stream,size,footer_cap=128<<20):
    """Never ask Arrow to prefetch the tail of the original scientific file.

    Only header4, trailer8 and the exact serialized footer region are read.
    Arrow receives a metadata-only in-memory file with no original data pages.
    Original column offsets are retained in the footer and refer to original
    source, not this deliberately short synthetic metadata file.
    """
    need(type(size) is int and size>=12,'SOURCE_TOO_SHORT_FOR_PARQUET')
    intervals=[]
    def fetch(start,count):
        stream.seek(start);raw=stream.read(count)
        need(len(raw)==count,'SHORT_FOOTER_ENVELOPE_READ');intervals.append([start,start+count]);return raw
    header=fetch(0,4);trailer=fetch(size-8,8)
    need(header==b'PAR1' and trailer[4:]==b'PAR1','UNSUPPORTED_PARQUET_MAGIC_OR_ENCRYPTED_FOOTER')
    length=struct.unpack('<I',trailer[:4])[0]
    need(0<length<=size-12,'INVALID_OR_OVERLAPPING_FOOTER_LENGTH')
    need(length<=footer_cap,'FOOTER_SOFTWARE_CAP_PENDING_NOT_LABEL_FAILURE')
    start=size-8-length;body=fetch(start,length)
    return {'metadata_file':b'PAR1'+body+trailer,'footer_start':start,'footer_bytes':length,
      'actual_footer_sha256':hashlib.sha256(body).hexdigest(),'actual_source_read_intervals':intervals,
      'actual_source_metadata_bytes_read':length+12,'original_data_pages_read':False,
      'current_wholebody_SHA_verified':False}


def parse_metadata(only):
    import pyarrow as pa
    import pyarrow.parquet as pq
    # read_metadata never has access to the original source or any data pages.
    return pq.read_metadata(pa.BufferReader(only['metadata_file']))


def records(metadata,expected_rows):
    """Explicit metadata allowlist. Never access statistics/min/max/to_dict."""
    need(metadata.num_rows==expected_rows,'CURRENT_FOOTER_PRODUCER_PHYSICAL_ROWS_DIFFER')
    columns=[]
    for i in range(metadata.num_columns):
        col=metadata.schema.column(i)
        columns.append({'column':i,'path':col.path,'physical_type':col.physical_type,
          'logical_type':str(col.logical_type),'converted_type':str(col.converted_type),
          'max_definition_level':col.max_definition_level,'max_repetition_level':col.max_repetition_level})
    yield {'type':'schema','physical_rows':metadata.num_rows,'row_groups':metadata.num_row_groups,
      'physical_columns':metadata.num_columns,'format_version':str(metadata.format_version),
      'created_by':metadata.created_by,'created_by_is_writer_not_QM_program':True,
      'arrow_schema':str(metadata.schema.to_arrow_schema().remove_metadata()),'columns':columns}
    physical=0;chunks=0;compressed=0;uncompressed=0;external=0
    for rg in range(metadata.num_row_groups):
        group=metadata.row_group(rg);n=group.num_rows
        need(n>=0 and group.num_columns==metadata.num_columns,'ROW_GROUP_PHYSICAL_LAYOUT_INVALID')
        yield {'type':'row_group','row_group':rg,'physical_row_lo':physical,'physical_row_hi':physical+n,
               'rows':n,'columns':group.num_columns,'parquet_total_byte_size':group.total_byte_size}
        for i in range(group.num_columns):
            col=group.column(i);c=col.total_compressed_size;u=col.total_uncompressed_size
            need(c>=0 and u>=0 and col.num_values>=0,'COLUMN_METADATA_SIZE_UNAVAILABLE')
            path=col.file_path;external+=bool(path);compressed+=c;uncompressed+=u;chunks+=1
            yield {'type':'column_chunk','row_group':rg,'column':i,'num_values':col.num_values,
              'compressed_bytes':c,'uncompressed_bytes':u,'file_offset':col.file_offset,
              'data_page_offset':col.data_page_offset,'dictionary_page_offset':col.dictionary_page_offset,
              'external_file_path':path,'compression':col.compression,'encodings':list(col.encodings)}
        physical+=n
    need(physical==metadata.num_rows,'ROW_GROUP_INTERVALS_NOT_EXACT_FULL_FILE')
    yield {'type':'file_end','physical_rows':physical,'row_groups':metadata.num_row_groups,
      'column_chunks':chunks,'compressed_column_bytes':compressed,'uncompressed_column_bytes':uncompressed,
      'external_column_chunks':external,'statistics_min_max_accessed':False,
      'payload_values_or_actual_array_lengths_observed':False}


def pack_records(items,raw_cap=64<<20):
    """One independently complete gzip member per source, bounded before write."""
    raw=bytearray();last=None;count=0
    for item in items:
        body=canonical(item)+b'\n';limit=256<<10 if item['type'] in ('source','schema') else 4096
        need(len(body)<=limit,'SINGLE_FOOTER_RECORD_CAP_PENDING')
        need(len(raw)+len(body)<=raw_cap,'ONE_SOURCE_METADATA_BUFFER_CAP_PENDING')
        raw.extend(body);last=item;count+=1
    need(last is not None and last['type']=='file_end','COMPLETE_SOURCE_METADATA_MEMBER_REQUIRED')
    return bytes(raw),last,count


def static_scenario(sources):
    """Frozen writer32768 scenario only, not actual RG evidence or a forecast."""
    rg=chunks=0
    for row in sources:
        groups=(row['rows']+32767)//32768
        cols={'D20':10,'D3':14,'base_geometry':24}.get(row['family'],34)
        rg+=groups;chunks+=groups*cols
    return {'writer_default_row_group_size_scenario':32768,'actual_row_groups_known':False,
      'scenario_row_groups':rg,'scenario_column_chunks':chunks,
      'scenario_uncompressed_output_allowance_bytes':len(sources)*65536+rg*512+chunks*1024+(80<<20),
      'scenario_is_not_current_wholebody_or_actual_compressed_output_measurement':True,
      'if_actual_metadata_exceeds_cap':'STOP_PENDING_PRESERVE_CLOSED_MEMBERS_NOT_FALSE_FULL'}
