"""Physical bytes only: exact gzip inventory, bounded row locators and ordinal parts."""
import gzip,hashlib,heapq,json,os,random
from pathlib import Path
from . import contracts as C
from .runtime import frame
from secondary_cpu_queue_v1 import common as Q

def pin(path,budget=None):
    path=Q.literal(path);before=frame(path);h=hashlib.sha256();total=0
    with path.open('rb') as stream:
        while total<=before[2]:
            if budget:budget.check()
            piece=stream.read(min(4<<20,before[2]+1-total))
            if not piece:break
            total+=len(piece);h.update(piece)
    Q.need(total==before[2] and frame(path)==before,'BOUNDED_FILE_SHA_FRAME_OR_BYTES_CHANGED')
    return {'path':str(path),'bytes':total,'sha256':h.hexdigest()}

def verify(reference,budget=None):
    Q.need(pin(reference['path'],budget)==reference,'ACTUAL_DATA_SHA_OR_BYTES_DIFFER');return Path(reference['path'])

def line(value,cap=C.INDEX_CAP):
    raw=Q.canonical(value)+b'\n';Q.need(len(raw)<=cap,'FINITE_METADATA_RECORD_CAP_NO_TRUNCATION');return raw

def write_json(path,value,budget=None):
    raw=Q.canonical(value)+b'\n'
    if budget:budget.check(len(raw))
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return pin(path,budget=None)

def sample(n=C.N,k=C.COUNT):return sorted(random.Random(C.SEED).sample(range(1,n+1),k))

def index_rows(reference,budget=None):
    path=verify(reference,budget)
    with path.open('rb') as stream:
        for raw in iter(lambda:stream.readline(C.INDEX_CAP+1),b''):
            if budget:budget.check()
            Q.need(len(raw)<=C.INDEX_CAP and raw.endswith(b'\n'),'INDEX_LINE_MALFORMED_OR_TRUNCATED')
            yield json.loads(raw,object_pairs_hook=Q.pairs_unique)

def cid_summary(token):
    canonical=token.lstrip(b'0');Q.need(token.isascii() and token.isdigit() and canonical,'POSITIVE_ORIGINAL_DECIMAL_CID_REQUIRED')
    return {'decimal_digits':len(canonical),'decimal_prefix':canonical[:32].decode('ascii'),
        'complete_decimal':canonical.decode('ascii') if len(canonical)<=32 else None,'decimal_sha256':hashlib.sha256(canonical).hexdigest()}

def row_fact(raw,ordinal,part_index,offset):
    Q.need(0<len(raw)<=C.MAX_LINE and raw.count(b'\t')==1,'ORIGINAL_SNAPSHOT_ROW_FRAMING_OR_MAXLINE_DIFFERS')
    raw.decode('utf-8','strict');cid,payload=raw.split(b'\t');cid_summary(cid)
    terminator=2 if payload.endswith(b'\r\n') else (1 if payload.endswith(b'\n') else 0)
    smiles=payload[:-terminator] if terminator else payload
    return {'ordinal':ordinal,'part_index':part_index,'offset_bytes':offset,'source_row_bytes':len(raw),
        'smiles_bytes':len(smiles),'source_row_sha256':hashlib.sha256(raw).hexdigest()}

def record(raw,fact,reference):
    actual=row_fact(raw,fact['ordinal'],fact['part_index'],fact['offset_bytes'])
    Q.need(actual=={k:fact[k] for k in actual},'EXACT_PHYSICAL_ROW_LOCATOR_OR_SHA_DIFFERS')
    cid,payload=raw.split(b'\t');end=2 if payload.endswith(b'\r\n') else (1 if payload.endswith(b'\n') else 0)
    smiles=payload[:-end] if end else payload
    return {**actual,'cid_source_ascii':cid.decode('ascii'),'source_smiles':smiles.decode('utf-8','strict'),
        'source_smiles_sha256':hashlib.sha256(smiles).hexdigest(),'source_terminator_hex':raw[-end:].hex() if end else '',
        'source_part':reference}

def validate_index(rows,root):
    first=1;total=0
    for index,row in enumerate(rows):
        Q.need(set(row)=={'index','first_ordinal','last_ordinal','records','bytes','first_cid','last_cid','reference'}
            and row['index']==index and row['first_ordinal']==first and row['last_ordinal']==first+row['records']-1
            and row['reference']['bytes']==row['bytes'] and row['reference']['path']==str(Path(root)/('source_%06d.tsv'%index)),
            'EXACT_CANONICAL_PART_SEQUENCE_SCHEMA_AND_ORDINALS_REQUIRED')
        first=row['last_ordinal']+1;total+=row['bytes']
    Q.need(len(rows)==C.PARTS and first==C.N+1 and total==C.UNCOMPRESSED_BYTES,'FULL500_ROW_BYTE_ORDINAL_CONSERVATION_REQUIRED')
    return rows

def inventory(plan,out,budget):
    verify(plan['raw_reference'],budget);main=list(index_rows(plan['main_index_reference'],budget))
    Q.need(len(main)==C.PARTS,'ACTUAL_MAIN500_INDEX_REQUIRED')
    uniform=set(sample());uniform_facts=[];longest=[];parts=[];total=rows=maximum=0;previous=None;current=None
    mathematical=C.UNCOMPRESSED_BYTES+2*((C.UNCOMPRESSED_BYTES+1)//3//C.PART_ROWS+C.UNCOMPRESSED_BYTES//C.PART_BYTES+1)*C.INDEX_CAP+(C.COUNT+C.LONGEST)*C.INDEX_CAP+(256<<20)
    Q.need(mathematical<=plan['output_cap_bytes'],'EXACT_SOURCE_PLUS_BOUNDED_METADATA_INVENTORY_OUTPUT_BOUND')
    def begin():
        index=len(parts);path=out/('source_%06d.partial.tsv'%index)
        return {'index':index,'partial':path,'stream':path.open('xb'),'hash':hashlib.sha256(),'bytes':0,'records':0,
            'first_ordinal':rows+1,'first_cid':None,'last_cid':None}
    def close_part():
        nonlocal current
        current['stream'].flush();os.fsync(current['stream'].fileno());current['stream'].close()
        path=out/('source_%06d.tsv'%current['index']);Q.need(not path.exists(),'NEW_PART_ONLY');os.rename(current['partial'],path)
        row={key:current[key] for key in ('index','first_ordinal','records','bytes','first_cid','last_cid')}
        row.update(last_ordinal=rows,reference={'path':str(path),'bytes':current['bytes'],'sha256':current['hash'].hexdigest()})
        Q.need(pin(path,budget)==row['reference'],'ACTUAL_PART_FULL_DISK_SHA_AND_FSTAT_MUST_MATCH_WRITTEN_SOURCE_BYTES')
        Q.need(len(parts)<len(main),'PART_COUNT_EXCEEDS_ACTUAL_MAIN500');expected=main[len(parts)]
        Q.need(all(row[key]==expected[key] for key in row if key!='reference')
            and all(row['reference'][key]==expected['reference'][key] for key in ('bytes','sha256')),'ALPHA_PART_DIFFERS_FROM_MAIN_ORIGINAL_BYTES_ORDINALS_OR_CIDS')
        write_json(out/('source_%06d.receipt.json'%row['index']),row,budget);parts.append(row);current=None
    raw_frame=frame(plan['raw_reference']['path'])
    try:
        with gzip.open(plan['raw_reference']['path'],'rb') as stream:
            while True:
                budget.check();raw=stream.readline(C.MAX_LINE+1)
                if not raw:break
                Q.need(len(raw)<=C.MAX_LINE,'ORIGINAL_COMPLETE_SNAPSHOT_MAXLINE_DIFFERS_NOT_CHEMICAL_EXCLUSION')
                if current is None:current=begin()
                fact=row_fact(raw,rows+1,current['index'],current['bytes']);token=raw.split(b'\t',1)[0].lstrip(b'0');key=(len(token),token)
                Q.need(previous is None or key>previous,'ORIGINAL_GLOBAL_CID_ORDER_OR_UNIQUENESS_DIFFERS');previous=key
                info=cid_summary(raw.split(b'\t',1)[0]);current['first_cid']=info if current['first_cid'] is None else current['first_cid'];current['last_cid']=info
                Q.need(current['stream'].write(raw)==len(raw),'SHORT_PHYSICAL_SOURCE_WRITE');current['hash'].update(raw);current['bytes']+=len(raw);current['records']+=1
                total+=len(raw);rows+=1;maximum=max(maximum,len(raw))
                if rows in uniform:uniform_facts.append(fact)
                item=(fact['smiles_bytes'],-fact['ordinal'],fact)
                if len(longest)<C.LONGEST:heapq.heappush(longest,item)
                elif item[:2]>longest[0][:2]:heapq.heapreplace(longest,item)
                if current['records']>=C.PART_ROWS or current['bytes']>=C.PART_BYTES:close_part()
        if current is not None:close_part()
    finally:
        if current is not None and not current['stream'].closed:current['stream'].flush();os.fsync(current['stream'].fileno());current['stream'].close()
    Q.need(frame(plan['raw_reference']['path'])==raw_frame and rows==C.N and total==C.UNCOMPRESSED_BYTES and maximum==C.MAX_LINE,
        'COMPLETE_GZIP_EOF_CRC_BYTES_ROWS_AND_MAXLINE_REQUIRED')
    validate_index(parts,out);index=out/'source_index.jsonl'
    with index.open('xb') as stream:
        for part in parts:stream.write(line(part))
        stream.flush();os.fsync(stream.fileno())
    refs={}
    for name,facts in (('uniform',uniform_facts),('longest',[v[2] for v in sorted(longest,key=lambda x:(-x[0],-x[1]))])):
        path=out/(name+'_locators.jsonl')
        with path.open('xb') as stream:
            for fact in facts:stream.write(line(fact))
            stream.flush();os.fsync(stream.fileno())
        refs[name]=pin(path)
    Q.need(len(uniform_facts)==C.COUNT and len(longest)==C.LONGEST,'FIXED_SELECTED_LOCATOR_COUNTS')
    return {'source_index':pin(index),'part_count':len(parts),'uniform_locators':refs['uniform'],'longest_locators':refs['longest'],
        'records':rows,'uncompressed_bytes':total,'maximum_source_line_bytes':maximum,'raw_complete_SHA_verified':True,
        'gzip_EOF_CRC_revalidated':True,'global_unique_cids_proven':True,'cid_uniqueness_basis':'Observed strictly increasing positive decimal CID sequence',
        'all500_parts_equal_Main_SHA_rows_bytes':True,'mathematical_output_upper_bytes':mathematical,
        'chemical_screening_performed':False,'pool_release_authorized':False}

def load_inventory(plan,budget):
    receipt=Q.load_ref(plan['alpha_inventory_receipt_reference']);Q.need(receipt['status']=='ALPHA_PHYSICAL500_COMPLETE_NO_CHEMISTRY','ACTUAL_ALPHA_COMPLETE_INVENTORY_REQUIRED')
    data=receipt['inventory'];parts=list(index_rows(data['source_index'],budget));validate_index(parts,Path(data['source_index']['path']).parent)
    return receipt,parts

def read_selected(parts,locator_reference,budget):
    facts=list(index_rows(locator_reference,budget));groups={}
    for fact in facts:groups.setdefault(fact['part_index'],[]).append(fact)
    for index,locators in sorted(groups.items()):
        part=parts[index];path=verify(part['reference'],budget);before=frame(path)
        with path.open('rb') as stream:
            for fact in sorted(locators,key=lambda x:x['offset_bytes']):
                budget.check();Q.need(part['first_ordinal']<=fact['ordinal']<=part['last_ordinal'],'SELECTED_ORDINAL_IN_EXACT_PART')
                stream.seek(fact['offset_bytes']);raw=stream.read(fact['source_row_bytes']);yield record(raw,fact,part['reference'])
        Q.need(frame(path)==before,'SELECTED_PART_CHANGED_AFTER_READ')

def iter_part(part,budget):
    path=verify(part['reference'],budget);before=frame(path);ordinal=part['first_ordinal'];offset=0
    with path.open('rb') as stream:
        for raw in iter(lambda:stream.readline(C.MAX_LINE+1),b''):
            budget.check();fact=row_fact(raw,ordinal,part['index'],offset);yield record(raw,fact,part['reference'])
            ordinal+=1;offset+=len(raw)
    Q.need(frame(path)==before and ordinal==part['last_ordinal']+1 and offset==part['bytes'],'FULL_PART_ORDINAL_BYTE_FRAME_CONSERVATION')
