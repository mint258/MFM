"""Bounded HTTP bytes and ZIP members, kept opaque; never infer chemical structure."""
import hashlib,zlib,zipfile
from secondary_external_sources_acquisition_v1.run import NoRedirect,safe_headers
from . import contracts as C
Q=C.Q


def copy_response(response,output,check,maximum,expected):
    """One bounded body; even a bad status/length retains its actual opaque prefix."""
    n=0;h=hashlib.sha256();EOF=False
    while n<maximum:
        check();raw=response.read(min(1<<20,maximum-n))
        if not raw:EOF=True;break
        Q.need(len(raw)<=maximum-n,'FINITE_RESPONSE_READ_BOUND');check(len(raw));output.write(raw);h.update(raw);n+=len(raw)
    return {'observed_body_bytes':n,'sha256_of_observed_bytes':h.hexdigest(),'actual_body_EOF':EOF,
        'maximum_body_bytes':maximum,'body_length_matches_original_HEAD':n==expected,'bounded_prefix_only':not EOF}


def response_acceptable(status,headers,body,expected):
    declared=headers.get('Content-Length');kind=headers.get('Content-Type')
    return status==200 and isinstance(declared,str) and declared.isascii() and declared.isdecimal() and int(declared)==expected \
        and isinstance(kind,str) and kind.split(';',1)[0].strip().lower()=='application/zip' and headers.get('Content-Encoding') in (None,'identity') \
        and body['actual_body_EOF'] is True and body['observed_body_bytes']==expected and body['bounded_prefix_only'] is False


def inventory(archive_stream,raw_output,emit,check,maximum,members):
    count=0;total=0;directories=0;duplicates=0;seen=set();offset=0
    with zipfile.ZipFile(archive_stream,'r') as z:
        infos=z.infolist();Q.need(len(infos)<=members and sum(v.file_size for v in infos)<=maximum,'DECLARED_ZIP_CENSUS_WITHIN_EXPLICIT_BOUNDS_BEFORE_DECODE')
        for ordinal,info in enumerate(infos):
            check();Q.need(len(info.orig_filename.encode('utf-8'))<=4096 and info.file_size>=0 and info.compress_size>=0 and not(info.flag_bits&1),'BOUNDED_UNENCRYPTED_ORIGINAL_MEMBER_NO_PASSWORD_OR_NAME_REWRITE')
            duplicate=info.orig_filename in seen;duplicates+=duplicate;seen.add(info.orig_filename);h=hashlib.sha256();crc=0;n=0;start=offset
            with z.open(info,'r') as f:
                while True:
                    check();raw=f.read(1<<20)
                    if not raw:break
                    Q.need(total+len(raw)<=maximum and n+len(raw)<=info.file_size,'ACTUAL_ZIP_EXPANSION_BYTES_WITHIN_BOUND')
                    check(len(raw));raw_output.write(raw);n+=len(raw);total+=len(raw);offset+=len(raw);h.update(raw);crc=zlib.crc32(raw,crc)
            Q.need(n==info.file_size and crc&0xffffffff==info.CRC,'EVERY_ORIGINAL_MEMBER_COMPLETE_EOF_CRC')
            raw_output.flush()
            if hasattr(raw_output,'durable'):raw_output.durable()
            emit({'event':'OPAQUE_ORIGINAL_ZIP_MEMBER_DURABLE_BEFORE_INVENTORY','physical_member_ordinal':ordinal,'original_filename':info.orig_filename,
                'zipfile_filename':info.filename,'directory_flag':info.is_dir(),'duplicate_literal_filename':duplicate,'declared_uncompressed_bytes':info.file_size,
                'declared_compressed_bytes':info.compress_size,'compression_method':info.compress_type,'declared_CRC32':info.CRC,'actual_CRC32':crc&0xffffffff,
                'whole_member_SHA256':h.hexdigest(),'whole_member_EOF_CRC_verified':True,'original_uncompressed_blob_segment':{'offset':start,'bytes':n,'sha256':h.hexdigest()},
                'original_external_attr':info.external_attr,'original_flag_bits':info.flag_bits,'member_extra_bytes':len(info.extra),'member_extra_SHA256':hashlib.sha256(info.extra).hexdigest(),
                'member_comment_bytes':len(info.comment),'member_comment_SHA256':hashlib.sha256(info.comment).hexdigest(),'filesystem_extracted_or_executed':False,
                'coordinates_identity_SMILES_graph_or_rowmap_parsed':False,'filename_or_ordinal_is_MAT_mapping':False})
            count+=1;directories+=info.is_dir()
        Q.need(count==len(infos),'ALL_PHYSICAL_MEMBERS_PRESERVED_NO_DEDUP')
        return {'physical_members':count,'directory_flags':directories,'duplicate_literal_filenames_preserved':duplicates,'total_uncompressed_bytes':total,
            'archive_comment_bytes':len(z.comment),'archive_comment_SHA256':hashlib.sha256(z.comment).hexdigest(),'every_member_EOF_CRC_SHA_verified':True,
            'original_compressed_and_uncompressed_bytes_preserved':True,'member_files_extracted_or_executed':False,'original_graph_SMILES_MAT_row_mapping':'UNKNOWN'}
