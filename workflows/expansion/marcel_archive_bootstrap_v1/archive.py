"""Bounded single-disk ZIP/ZIP64 directory preflight and opaque member streaming."""
import hashlib,stat,struct,zipfile,zlib
from pathlib import PurePosixPath


def need(value,label):
    if not value:raise ValueError(label)


def preflight(stream,size):
    need(size>=22,'NO_COMPLETE_EOCD');start=max(0,size-65557);stream.seek(start);tail=stream.read(size-start)
    offset=tail.rfind(b'PK\x05\x06');need(offset>=0 and offset+22<=len(tail),'EOCD_NOT_OBSERVED_WITHIN_COMMENT_BOUND')
    _,disk,cdisk,n_disk,n,csize,coffset,comment=struct.unpack('<4s4H2LH',tail[offset:offset+22]);eocd=start+offset
    need(offset+22+comment==len(tail) and disk==cdisk==0,'TRAILING_BYTES_OR_MULTIDISK_UNKNOWN')
    zip64=n in (65535,) or n_disk==65535 or csize==0xffffffff or coffset==0xffffffff
    boundary=eocd
    if zip64:
        need(eocd>=20,'ZIP64_LOCATOR_MISSING');stream.seek(eocd-20);locator=stream.read(20)
        sig,ldisk,zoffset,disks=struct.unpack('<4sLQL',locator);need(sig==b'PK\x06\x07' and ldisk==0 and disks==1 and 0<=zoffset<=eocd-76,'BOUNDED_SINGLE_DISK_ZIP64_LOCATOR')
        stream.seek(zoffset);record=stream.read(56);need(len(record)==56,'ZIP64_EOCD_TRUNCATED')
        sig,record_size,_,_,disk,cdisk,n_disk,n,csize,coffset=struct.unpack('<4sQ2H2L4Q',record)
        need(sig==b'PK\x06\x06' and 44<=record_size<=1<<20 and zoffset+12+record_size==eocd-20 and disk==cdisk==0,'BOUNDED_ZIP64_EOCD_RECORD')
        boundary=zoffset
    need(n==n_disk and 0<=n<=4096 and 0<=csize<=16<<20 and 0<=coffset<=boundary and coffset+csize<=boundary,'CENTRAL_DIRECTORY_ENTRY_SIZE_OR_OFFSET_BOUND')
    return {'ZIP64':zip64,'entries_declared':n,'central_directory_bytes':csize,'central_directory_offset':coffset,'EOCD_offset':eocd,'comment_bytes':comment}


def directory(archive,pre,expanded_cap):
    infos=archive.infolist();need(len(infos)==pre['entries_declared']<=4096,'ACTUAL_DIRECTORY_ENTRY_COUNT')
    seen=set();total=0
    for i in infos:
        p=PurePosixPath(i.filename);need(i.filename not in seen and not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename
            and len(i.filename.encode('utf-8'))<=1024 and not stat.S_ISLNK(i.external_attr>>16) and not(i.flag_bits&1),'DUPLICATE_UNSAFE_LINK_OR_ENCRYPTED_MEMBER_UNKNOWN')
        seen.add(i.filename);need(i.compress_type in (0,8),'UNSUPPORTED_COMPRESSION_UNKNOWN');total+=i.file_size
        need(i.file_size>=0 and total<=expanded_cap,'DECLARED_EXPANDED_BYTES_EXCEED_ROOT_CAP')
    return infos,total


def member(archive,info,check,remaining):
    digest=hashlib.sha256();crc=0;n=0
    with archive.open(info,'r') as stream:
        while True:
            check();block=stream.read(1<<20)
            if not block:break
            n+=len(block);need(n<=info.file_size and n<=remaining,'ACTUAL_MEMBER_BYTES_EXCEED_DECLARED_OR_ROOT_CAP')
            crc=zlib.crc32(block,crc);digest.update(block)
    need(n==info.file_size and (crc&0xffffffff)==info.CRC,'MEMBER_EOF_CRC_LENGTH_CONTRADICTION')
    base=PurePosixPath(info.filename).name;hint='DIRECTORY_NO_IDENTITY' if info.is_dir() else 'PICKLE_FILENAME_ONLY_NO_LOAD' if base.lower().endswith(('.pickle','.pkl')) else 'SDF_FILENAME_ONLY_NO_PARSE' if base.lower().endswith('.sdf') else 'CSV_FILENAME_ONLY_NO_DECODE' if base.lower().endswith('.csv') else 'OTHER_REGULAR_UNKNOWN_SEMANTICS'
    return {'name':info.filename,'directory':False,'compressed_bytes':info.compress_size,'decoded_bytes':n,
        'decoded_sha256':digest.hexdigest(),'CRC32_observed':crc&0xffffffff,'EOF_CRC_passed':True,'format_hint':hint,
        'identity_fields_or_pickle_or_assay_decoded':False}
