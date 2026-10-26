"""Observe the frozen CSV state machine without changing feed/finish or assays."""
import base64,hashlib,json
from secondary_cpu_queue_v1 import common as Q
from secondary_missing11_identity_format_probe_v1 import formats as original


def identity_field(name,index,raw):
    try:text=raw.decode('utf-8','strict');state='EMPTY' if text=='' else 'WHITESPACE_ONLY' if not text.strip() else 'PRESENT'
    except UnicodeDecodeError:text=None;state='INVALID_UTF8'
    return {'literal_column_name':name,'column_index':index,'state':state,'text':text,
        'original_field_bytes':len(raw),'original_field_sha256':hashlib.sha256(raw).hexdigest(),
        'invalid_UTF8_original_bytes_base64':base64.b64encode(raw).decode('ascii') if text is None else None}


class CallbackCSV(original.CSVProjection):
    """The wrapper calls the actual original feed; hooks only project identities.

    raw spans include CRLF as one terminator. A final CR at a chunk boundary delays
    publication until its possible LF is observed. No assay field is retained.
    """
    def __init__(self,source_id,callback):
        super().__init__(source_id);self.callback=callback;self._field_values={};self._data=b'';self._start=0;self._cursor=0
        self._digest=hashlib.sha256();self._bytes=0;self._offset=0;self._in_feed=False;self._pending=None;self.header_record=None
    def _consume(self,end):
        until=end-self._start;Q.need(self._cursor<=until<=len(self._data),'OBSERVATION_RAW_BOUNDARY_INSIDE_CURRENT_CHUNK')
        value=memoryview(self._data)[self._cursor:until];self._digest.update(value);self._bytes+=len(value);self._cursor=until
    def _publish(self):
        row=self._pending;Q.need(row is not None,'ONLY_COMPLETE_ORIGINAL_RECORD_CALLBACK')
        row.update(source_offset=self._offset,source_record_bytes=self._bytes,source_record_sha256=self._digest.hexdigest())
        self._offset+=self._bytes;self._digest=hashlib.sha256();self._bytes=0;self._pending=None
        if row.pop('_header',False):self.header_record=row
        else:self.callback(row)
    def feed(self,data):
        Q.need(isinstance(data,bytes) and not self._in_feed,'FINITE_ORIGINAL_BYTES_FEED')
        if not data:return
        self._data=data;self._start=self.decoded_bytes;self._cursor=0;self._in_feed=True
        try:
            if self._pending is not None:
                if data[:1]==b'\n':self._consume(self._start+1)
                self._publish()
            super().feed(data)  # The original byte grammar is never copied or edited.
            self._consume(self._start+len(data))
        finally:self._data=b'';self._in_feed=False
    def finish_field(self):
        if self.header is not None and self.field in self.selected:self._field_values[self.field]=bytes(self.buffer)
        super().finish_field()
    def finish_record(self):
        was_header=self.header is None
        if self._in_feed:self._consume(self.decoded_bytes)
        final_CR=self._in_feed and self._data[self.decoded_bytes-self._start-1]==13
        after=self.decoded_bytes-self._start
        if final_CR and after<len(self._data) and self._data[after]==10:self._consume(self.decoded_bytes+1)
        ordinal=self.counts['physical_data_records']+1;field_count=self.field+1
        super().finish_record()
        fields={str(index):identity_field(name,index,self._field_values[index]) if index in self._field_values else
            {'literal_column_name':name,'column_index':index,'state':'MISSING','text':None,'original_field_bytes':None,
             'original_field_sha256':None,'invalid_UTF8_original_bytes_base64':None} for index,name in self.selected.items()}
        self._field_values={}
        self._pending={'_header':was_header,'source_id':self.source_id,'source_row_ordinal':0 if was_header else ordinal,
            'role':'ALLSPLITS','field_count':field_count,'header_columns':len(self.header),'identity_fields':fields}
        if not(final_CR and after==len(self._data)):self._publish()
    def finish(self):
        if self._pending is not None:self._publish()
        result=super().finish()
        Q.need(self._pending is None and self._bytes==0 and self._offset==self.decoded_bytes,'ALL_DECODED_BYTES_ASSIGNED_TO_EXACT_HEADER_OR_PHYSICAL_ROWS')
        return result


def normalize(row,functions):
    Q.need(row['role']=='ALLSPLITS' and row['source_row_ordinal']>0,'EXACT_ORIGINAL_ALLSPLITS_PHYSICAL_ROW')
    values=[field for field in row['identity_fields'].values() if field['literal_column_name']=='smiles']
    Q.need(len(values)==1,'ONLY_SINGLE792_SMILES_COLUMN')
    value=values[0];text=value['text'];keys=[];errors=[]
    if value['state'] in ('MISSING','INVALID_UTF8') or text=='':
        state=value['state'];errors=[{'source_field':'smiles','exception_type':None,'message':state}]
    else:
        keys,errors=functions['source_smiles_keys']({'smiles':text});state='KEYS_DERIVED' if keys else 'UNKNOWN_ORIGINAL_SMILES'
    valid,invalid=functions['full_keys'](keys,strict=False)
    result={'source':row,'physical_identity':row['source_id']+':'+str(row['source_row_ordinal']),
        'source_ID_is_physical_ordinal':True,'opaque_source_ID_fields':[x for x in row['identity_fields'].values() if x['literal_column_name']!='smiles'],
        'stored_full_keys':[],'SMILES_derived_full_keys':valid,'invalid_computed_key_tokens':invalid,
        'WP5_keys':sorted({functions['wp5_key'](key) for key in valid}),'key_state':state,'identity_errors':errors,
        'missing_full_key':not valid,'X_or_features_called':False,'unknown_is_chemical_exclusion':False,
        'native_QM7b_SDF_MOL2_identity':'UNKNOWN_NOT_HANDLED_BY_CSV_STAGE'}
    Q.need(len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode())<=8<<20,'OBSERVATION_CONTAINER_STOP_NO_TRUNCATION')
    return result
