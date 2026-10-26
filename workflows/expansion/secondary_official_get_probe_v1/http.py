"""Bounded raw-entity HTTP seam; no requests import or network on module import."""
import hashlib,re,struct,time,zipfile
from urllib.parse import urljoin,urlsplit

def need(value,message):
    if not value:raise ValueError(message)

def host(url):
    parts=urlsplit(url);name=parts.hostname or ''
    need(parts.scheme=='https' and not parts.username and not parts.password and re.fullmatch('[A-Za-z0-9.-]{1,253}',name),
        'NORMAL_HTTPS_NO_USERINFO_REDIRECT_ONLY');return name.lower()

def safe_headers(headers):
    length=headers.get('Content-Length');valid=length is None or re.fullmatch('[0-9]{1,19}',str(length)) is not None
    mime=str(headers.get('Content-Type','')).split(';',1)[0].strip().lower()
    if not re.fullmatch('[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+',mime):mime=None
    value=headers.get('Content-Range');match=re.fullmatch(r'bytes ([0-9]{1,19})-([0-9]{1,19})/([0-9]{1,19}|\*)',str(value)) if value is not None else None
    cr={'first':int(match[1]),'last':int(match[2]),'total':None if match[3]=='*' else int(match[3])} if match else None
    return {'content_type':mime,'declared_content_length':int(length) if length is not None and valid else None,
        'content_length_syntax_valid':valid,'content_range':cr,'content_range_syntax_valid':value is None or match is not None}

def copy_response(response,path,cap,stop):
    need(type(cap) is int and cap>0,'POSITIVE_FINITE_RESPONSE_CAP');headers=safe_headers(response.headers)
    count=0;digest=hashlib.sha256();prefix=b'';eof=False;reason=None;error_type=None
    with path.open('xb') as out:
        while count<cap:
            if stop():reason='SOFT_STOP_NATURAL_RESPONSE_CLOSE';break
            requested=min(64<<10,cap-count)
            try:block=response.raw.read(requested,decode_content=False)
            except Exception as exc:reason='RESPONSE_READ_ERROR_PARTIAL_PRESERVED';error_type=type(exc).__name__;break
            if not block:eof=True;break
            need(type(block) is bytes and len(block)<=requested,'HTTP_RAW_SEAM_READ_SIZE_CONTRACT')
            out.write(block);digest.update(block);count+=len(block)
            if len(prefix)<4:prefix+=block[:4-len(prefix)]
        if not eof and reason is None:reason='SOURCE_BYTE_CAP_REACHED_NO_EOF_CLAIM'
        out.flush()
        import os
        os.fsync(out.fileno())
    length_ok=headers['content_length_syntax_valid'] and (headers['declared_content_length'] is None or count==headers['declared_content_length'])
    complete=eof and length_ok
    return {'status_code':int(response.status_code),'method':'GET',**headers,'bytes_saved':count,'body_sha256':digest.hexdigest(),
        'actual_eof_observed':eof,'declared_length_agrees_or_absent':length_ok,'response_entity_complete':complete,
        'whole_response_entity_sha256':digest.hexdigest() if complete else None,'partial_entity_sha256':None if complete else digest.hexdigest(),
        'stop_reason':reason,'read_error_type':error_type,'entity_encoding':'RAW_HTTP_ENTITY_NO_TRANSPARENT_CONTENT_DECODING',
        'zip_magic':prefix in (b'PK\x03\x04',b'PK\x05\x06',b'PK\x07\x08'),'archive_complete':False,'archive_whole_sha256':None}

def zip_inventory(path,observation,stop):
    if not (observation['status_code']==200 and observation['response_entity_complete'] and observation['zip_magic']):
        return {'status':'NOT_ELIGIBLE_FOR_WHOLE_ZIP_ACCEPTANCE','CSV_or_identity_decoded':False}
    try:
        # Reject oversized/ZIP64/split central directories before ZipFile eagerly
        # builds every ZipInfo. This is metadata only, at most65557 tail bytes.
        size=path.stat().st_size
        with path.open('rb') as f:f.seek(max(0,size-65557));tail=f.read(65557)
        position=tail.rfind(b'PK\x05\x06');need(position>=0 and len(tail)-position>=22,'STANDARD_ZIP_EOCD_REQUIRED')
        eocd=struct.unpack('<4s4H2LH',tail[position:position+22])
        need(eocd[1]==eocd[2]==0 and eocd[3]==eocd[4]<=256 and eocd[5]<=16<<20
            and eocd[6]+eocd[5]<=size and position+22+eocd[7]==len(tail),'FINITE_SINGLE_DISK_NONZIP64_CENTRAL_DIRECTORY')
        with zipfile.ZipFile(path,'r') as archive:
            entries=archive.infolist()
            need(len(entries)<=256 and sum(i.file_size for i in entries)<=1<<30
                and all(i.file_size<=128<<20 and len(i.filename.encode())<=4096 and not i.flag_bits&1 for i in entries),'ZIP_INVENTORY_OR_EXPANDED_SOFTWARE_BOUND')
            for info in entries:
                need(not stop(),'SOFT_STOP_BEFORE_NEXT_CRC_ENTRY')
                if info.is_dir():continue
                read=0
                with archive.open(info,'r') as stream:
                    while True:
                        need(not stop(),'SOFT_STOP_DURING_CRC_ENTRY');block=stream.read(64<<10)
                        if not block:break
                        read+=len(block);need(read<=info.file_size,'ZIP_ACTUAL_EXPANDED_LENGTH_BOUND')
                need(read==info.file_size,'ZIP_ACTUAL_EXPANDED_LENGTH_MISMATCH')
            return {'status':'COMPLETE_ZIP_ALL_ENTRIES_EOF_CRC_PASS','entries':[{'name':i.filename,'compressed_bytes':i.compress_size,
                'uncompressed_bytes':i.file_size,'CRC32':i.CRC,'directory':i.is_dir()} for i in entries],
                'expanded_bytes':sum(i.file_size for i in entries),'CSV_or_identity_decoded':False}
    except Exception as exc:return {'status':'ZIP_NOT_ACCEPTED','error_type':type(exc).__name__,'CSV_or_identity_decoded':False}

def fetch(spec,session,path,stop):
    """Follow normal HTTPS Location manually, closing unconsumed redirect bodies.

    requests automatic redirects can read their entire intermediate bodies.
    Manual standard redirects avoid that hidden unbounded transfer; no response
    cookie, Location query, arbitrary header value or exception URL is logged.
    """
    url=spec['url'];hops=[];original_host=host(url);headers={'Range':'bytes=0-1048575'} if spec['range_first_MiB'] else {}
    for index in range(6):
        if stop():return {'status':'NOT_STARTED_OR_STOPPED_BEFORE_NEXT_HTTP_HOP','method':'GET','redirect_hops':hops,'original_host':original_host,'archive_complete':False}
        session.cookies.clear()
        response=session.get(url,stream=True,verify=True,allow_redirects=False,timeout=(10,20),headers=headers)
        try:
            status=int(response.status_code);current=host(url)
            redirect_stop=None
            if status in (301,302,303,307,308):
                location=response.headers.get('Location')
                if location and index<5:
                    try:next_url=urljoin(url,location);next_host=host(next_url)
                    except ValueError:redirect_stop='NON_HTTPS_OR_USERINFO_REDIRECT_REJECTED_NO_BYPASS'
                    else:
                        hops.append({'status_code':status,'method':'GET','from_host':current,'to_host':next_host,
                            'redirect_body_not_downloaded':True});url=next_url;continue
                else:redirect_stop='NORMAL_REDIRECT_MISSING_OR_LIMIT_NO_BYPASS'
            observed=copy_response(response,path,spec['cap_bytes'],stop)
            observed.update(status='BOUNDED_RESPONSE_OBSERVED',original_host=original_host,final_host=current,redirect_hops=hops,
                original_source_id=spec['source_id'],Range_requested='bytes=0-1048575' if headers else None,
                Range_honored=(status==206 and observed['content_range'] is not None and observed['content_range']['first']==0) if headers else None,
                retry_attempts=0,confirmation_or_auth_bypass_attempted=False,redirect_response_bodies_preserved=False,redirect_stop=redirect_stop)
            if spec['source_id']=='tdc_admet_group_zip':
                inventory=zip_inventory(path,observed,stop);observed['ZIP_inventory']=inventory
                if inventory['status']=='COMPLETE_ZIP_ALL_ENTRIES_EOF_CRC_PASS':
                    observed['archive_complete']=True;observed['archive_whole_sha256']=observed['body_sha256']
            else:observed['archive_acceptance_permitted']=False
            return observed
        finally:response.close()
    raise ValueError('NORMAL_REDIRECT_LIMIT')
