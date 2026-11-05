"""Streaming PostgreSQL COPY text, retaining only explicitly selected fields.

Grammar authority: https://www.postgresql.org/docs/current/sql-copy.html
No downloaded statement is executed. NULL is matched before unescaping;
escaped physical tab/newline and chunk boundaries are handled explicitly.
"""
import hashlib,re

DELIMITER=re.compile(rb'[\t\r\n]')


def need(ok,code):
    if not ok:raise ValueError(code)


class Input:
    def __init__(self,stream,checkpoint,chunk=1024**2):
        self.stream,self.checkpoint,self.chunk=stream,checkpoint,chunk
        self.buffer=b'';self.index=0;self.read_bytes=self.consumed=0;self.eof=False
        self.sha=hashlib.sha256();self.tail=b'';self.prefix=bytearray()
        self.maximum_consumed=None

    def fill(self):
        if self.index<len(self.buffer):return True
        self.checkpoint();block=self.stream.read(self.chunk)
        self.buffer,self.index=block,0
        if not block:self.eof=True;return False
        self.sha.update(block);self.read_bytes+=len(block);self.tail=(self.tail+block)[-65536:]
        if len(self.prefix)<16*1024**2:self.prefix.extend(block[:16*1024**2-len(self.prefix)])
        return True

    def take(self,count):
        need(self.maximum_consumed is None or self.consumed+count<=self.maximum_consumed,'PROFILE_BOUNDARY_OVERSHOOT_STOP_NO_TRUNCATION')
        value=self.buffer[self.index:self.index+count];self.index+=len(value);self.consumed+=len(value);return value

    def line(self,cap=1024**2):
        chunks=[];size=0
        while self.fill():
            end=self.buffer.find(b'\n',self.index)
            value=self.take((end-self.index+1) if end>=0 else len(self.buffer)-self.index)
            chunks.append(value);size+=len(value);need(size<=cap,'SQL_METADATA_PHYSICAL_LINE_CAP_NO_TRUNCATION')
            if end>=0:break
        return b''.join(chunks)

    def segment(self):
        if not self.fill():return b'',None,True
        match=DELIMITER.search(self.buffer,self.index)
        if match is None:return self.take(len(self.buffer)-self.index),None,False
        end=match.start();value=self.take(end-self.index);delimiter=self.take(1)
        return value,delimiter,False

    def optional_LF(self):
        if self.fill() and self.buffer[self.index:self.index+1]==b'\n':return self.take(1)
        return b''


def decode(raw):
    if raw==b'\\N':return None
    out=bytearray();i=0;special={98:8,102:12,110:10,114:13,116:9,118:11}
    while i<len(raw):
        value=raw[i];i+=1
        if value!=92:out.append(value);continue
        need(i<len(raw),'DANGLING_COPY_ESCAPE')
        value=raw[i];i+=1
        if value in special:out.append(special[value])
        elif 48<=value<=55:
            digits=bytes([value])
            while i<len(raw) and len(digits)<3 and 48<=raw[i]<=55:digits+=bytes([raw[i]]);i+=1
            number=int(digits,8);need(number<=255,'COPY_OCTAL_BYTE_OUT_OF_RANGE');out.append(number)
        elif value==120 and i<len(raw) and raw[i] in b'0123456789abcdefABCDEF':
            digits=bytes([raw[i]]);i+=1
            if i<len(raw) and raw[i] in b'0123456789abcdefABCDEF':digits+=bytes([raw[i]]);i+=1
            out.append(int(digits,16))
        else:out.append(value)
    return out.decode('utf-8','strict')


def row(reader,width,wanted,field_cap=1024**2):
    start=reader.consumed;column=0;stored={};field=bytearray();size=0;slash=0;prefix=bytearray()
    digest=hashlib.sha256() if wanted else None
    def retain(value):
        nonlocal size,slash
        size+=len(value)
        if len(prefix)<3:prefix.extend(value[:3-len(prefix)])
        if digest is not None:digest.update(value)
        if column in wanted:
            need(len(field)+len(value)<=field_cap,'SELECTED_IDENTITY_FIELD_CAP_STOP_NO_TRUNCATION');field.extend(value)
    while True:
        piece,delimiter,eof=reader.segment()
        retain(piece)
        if piece:
            tail=len(piece)-len(piece.rstrip(b'\\'))
            slash=slash+tail if tail==len(piece) else tail
        if eof:
            need(reader.consumed==start,'COPY_ROW_TRUNCATED_AT_FILE_EOF')
            raise ValueError('COPY_BLOCK_HAS_NO_END_MARKER')
        if delimiter is None:continue
        escaped=slash%2==1
        if escaped:
            retain(delimiter);slash=0;continue
        if delimiter==b'\t':
            if digest is not None:digest.update(delimiter)
            if len(prefix)<3:prefix.extend(delimiter[:3-len(prefix)])
            if column in wanted:stored[column]=decode(bytes(field))
            column+=1;field=bytearray();size+=1;slash=0;continue
        ending=delimiter+(reader.optional_LF() if delimiter==b'\r' else b'')
        if digest is not None:digest.update(ending)
        terminal=column==0 and size==2 and bytes(prefix)==b'\\.'
        if terminal:return {'end':True,'bytes':reader.consumed-start,'ending':ending.decode()}
        need(column+1==width,'COPY_ROW_WIDTH_MISMATCH')
        if column in wanted:stored[column]=decode(bytes(field))
        return {'end':False,'fields':stored,'offset':start,'bytes':reader.consumed-start,
                'row_sha256':digest.hexdigest() if digest is not None else None,'ending':ending.decode()}


class Metadata:
    """Bounded SQL lexical statement boundaries; downloaded SQL is never run."""
    def __init__(self,cap=1024**2):
        self.cap=cap;self.parts=[];self.size=0;self.quote=None;self.dollar=None;self.block=0;self.has_sql=False

    def feed(self,line):
        text=line.decode('utf-8','strict');statements=[]
        # pg_dump psql guards and comments have no statement terminator.
        if not self.has_sql and not self.quote and not self.dollar and not self.block and (not text.strip() or text.lstrip().startswith(('\\','--'))):
            self.parts=[];self.size=0
            return statements
        self.parts.append(line);self.size+=len(line);need(self.size<=self.cap,'SQL_METADATA_STATEMENT_CAP_STOP_UNKNOWN')
        i=0;begin=0
        while i<len(text):
            if self.dollar:
                end=text.find(self.dollar,i)
                if end<0:return statements
                i=end+len(self.dollar);self.dollar=None;continue
            if self.block:
                if text.startswith('/*',i):self.block+=1;i+=2
                elif text.startswith('*/',i):self.block-=1;i+=2
                else:i+=1
                continue
            if self.quote:
                if text[i]==self.quote:
                    if i+1<len(text) and text[i+1]==self.quote:i+=2;continue
                    self.quote=None;i+=1;continue
                if self.quote=="'" and text[i]=='\\':i+=2;continue
                i+=1;continue
            if text.startswith('--',i):break
            if text.startswith('/*',i):self.block=1;i+=2;continue
            if not text[i].isspace():self.has_sql=True
            if text[i] in "'\"":self.quote=text[i];i+=1;continue
            if text[i]=='$' and (tag:=re.match(r'\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$',text[i:])):
                self.dollar=tag[0];i+=len(tag[0]);continue
            if text[i]==';':
                # Reject two statements on a COPY header physical line later.
                complete=b''.join(self.parts[:-1])+text[begin:i+1].encode()
                statements.append(complete);self.parts=[];self.size=0;begin=i+1;self.has_sql=False
            i+=1
        remainder=text[begin:].encode()
        if statements:
            self.parts=[remainder] if remainder.strip() else [];self.size=len(remainder) if self.parts else 0
        return statements

    def complete(self):return not self.quote and not self.dollar and not self.block and not self.has_sql
