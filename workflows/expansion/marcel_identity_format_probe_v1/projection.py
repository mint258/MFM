"""Byte-preserving Drugs selected-field projection; no molecule or assay parser."""
import base64,collections,hashlib,json,re
from workflows.expansion.secondary_missing11_identity_format_probe_v1 import formats as F


def encoded(raw):
    if raw is None:return {'state':'MISSING','bytes':None}
    try:text=raw.decode('utf-8')
    except UnicodeDecodeError:return {'state':'INVALID_UTF8_UNKNOWN','base64':base64.b64encode(raw).decode('ascii'),'bytes':len(raw)}
    return {'state':'EMPTY_PRESERVED' if raw==b'' else 'LITERAL_UTF8','text':text,'bytes':len(raw)}


class NameCSV(F.CSVProjection):
    def __init__(self,emit):
        self.source_id='marcel_drugs_zip:Drugs.csv';self.emit=emit;self.values={}
        self.header=None;self.names=[];self.selected={};self.stats={};self.counts=collections.Counter(
            physical_data_records=0,field_count_matches_header=0,field_count_below_header=0,field_count_above_header=0)
        self.field=0;self.fields=[];self.buffer=bytearray();self.field_start=True;self.quoted=False;self.after_quote=False
        self.pending_cr=False;self.started=False;self.row_bytes=0;self.decoded_bytes=0;self.complete=False
    def finish_field(self):
        if self.header is None:self.fields.append(bytes(self.buffer))
        elif self.field in self.selected:self.values[self.field]=bytes(self.buffer)
        self.field+=1;self.buffer.clear();self.field_start=True;self.after_quote=False
    def finish_record(self):
        self.finish_field()
        if self.header is None:
            self.header=[v.decode('utf-8-sig' if i==0 else 'utf-8') for i,v in enumerate(self.fields)]
            self.fields=[];self.names=list(self.header);self.selected={i:n for i,n in enumerate(self.header) if n=='name'}
        else:
            ordinal=self.counts['physical_data_records'];self.counts['physical_data_records']+=1
            self.counts['field_count_matches_header']+=self.field==len(self.header)
            self.counts['field_count_below_header']+=self.field<len(self.header)
            self.counts['field_count_above_header']+=self.field>len(self.header)
            names=[self.values.get(i) for i in self.selected]
            state='EXACT_LITERAL_NAME_COLUMN' if len(names)==1 and self.field==len(self.header) else 'MISSING_AMBIGUOUS_OR_WIDTH_UNKNOWN'
            self.emit(ordinal,names[0] if len(names)==1 else None,{'name_fields':[encoded(n) for n in names],
                'mapping_state':state,'physical_fields':self.field,'header_fields':len(self.header)})
        self.values={};self.field=0;self.row_bytes=0;self.started=False
    def summary(self):
        return {'literal_header':self.header,'name_column_indices':list(self.selected),'counts':dict(self.counts),
            'EOF_complete':self.complete,'decoded_bytes':self.decoded_bytes,'assay_values_decoded':False}


def grammar_proof():
    names=('feed','finish','append')
    F.ensure(all(getattr(NameCSV,n) is getattr(F.CSVProjection,n) and n not in NameCSV.__dict__ for n in names),'ORIGINAL_CSV_GRAMMAR_METHOD_OBJECTS')
    return {n:{'filename':getattr(NameCSV,n).__code__.co_filename,'first_line':getattr(NameCSV,n).__code__.co_firstlineno} for n in names}


def sdf_record(raw,terminated):
    F.ensure(len(raw)<=16<<20,'SDF_RECORD_BOUND_UNKNOWN');lines=raw.splitlines(keepends=True)
    def value(line):
        return line[:-2] if line.endswith(b'\r\n') else line[:-1] if line.endswith((b'\r',b'\n')) else line
    lines=[value(v) for v in lines];title=lines[0] if lines else None;seen_end=False;current=None;parts=[]
    fields={'ID':[],'smiles':[],'_Name':[]}
    def close():
        if current in fields:
            data=b'\n'.join(parts);F.ensure(len(data)<=1<<20,'SDF_IDENTITY_FIELD_BOUND_UNKNOWN');fields[current].append(data)
    for line in lines[1:]:
        if not seen_end:
            if line==b'M  END':seen_end=True
            continue
        m=re.match(br'^>[^<]*<([^<>]+)>',line)
        if m:
            close();name=m.group(1);current=name.decode('ascii') if name in (b'ID',b'smiles',b'_Name') else None;parts=[]
        elif line==b'':close();current=None;parts=[]
        elif line==b'$$$$':close();current=None;parts=[]
        elif current is not None:
            parts.append(line);F.ensure(sum(map(len,parts))+len(parts)<=1<<20,'SDF_SELECTED_MULTILINE_BOUND_UNKNOWN')
    close();issues=[]
    if not terminated:issues.append('UNTERMINATED_PHYSICAL_RECORD_UNKNOWN')
    if not seen_end:issues.append('M_END_NOT_OBSERVED_GRAPH_UNKNOWN')
    for name in ('ID','smiles'):
        if len(fields[name])!=1:issues.append(name+'_MISSING_OR_DUPLICATE_UNKNOWN')
    if fields['_Name']:issues.append('EXPLICIT_NAME_PROPERTY_VERSUS_TITLE_UNKNOWN')
    row={'title_name':encoded(title),'properties':{k:[encoded(v) for v in vs] for k,vs in fields.items()},
        'record_sha256':hashlib.sha256(raw).hexdigest(),'record_bytes':len(raw),'terminated':terminated,
        'M_END_observed':seen_end,'format_state':'SELECTED_SOURCE_FIELDS_OBSERVED' if not issues else 'UNKNOWN',
        'issues':issues,'graph_and_stereo_verified':False}
    return title,fields,row


def sdf_rows(stream,emit,check):
    record=bytearray();ordinal=0
    while True:
        check();line=stream.readline((1<<20)+1)
        if not line:break
        F.ensure(len(line)<=1<<20,'SDF_NATIVE_LINE_BOUND_UNKNOWN');record.extend(line)
        F.ensure(len(record)<=16<<20,'SDF_RECORD_BOUND_UNKNOWN')
        if line.rstrip(b'\r\n')==b'$$$$':
            name,fields,row=sdf_record(bytes(record),True);emit(ordinal,name,fields,row);ordinal+=1;record.clear()
    if record:
        name,fields,row=sdf_record(bytes(record),False);emit(ordinal,name,fields,row);ordinal+=1
    return ordinal
