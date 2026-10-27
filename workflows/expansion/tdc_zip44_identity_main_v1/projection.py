"""Original RFC4180 byte grammar; independent real TDC field callback."""
import base64,collections
from workflows.expansion.secondary_missing11_identity_format_probe_v1 import formats as F


def text(raw):
    if raw is None:return {'state':'MISSING','text':None}
    try:return {'state':'EMPTY_PRESERVED' if raw==b'' else 'LITERAL_UTF8','text':raw.decode('utf-8'),'bytes':len(raw)}
    except UnicodeError:return {'state':'INVALID_UTF8_UNKNOWN','text':None,'base64':base64.b64encode(raw).decode('ascii'),'bytes':len(raw)}


class IdentityCSV(F.CSVProjection):
    def __init__(self,member,emit):
        self.source_id='tdc_admet_group_zip:'+member;self.member=member;self.emit=emit;self.values={}
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
            F.ensure(self.header==['Drug_ID','Drug','Y'],'ACTUAL_DECLARED_HEADER_CHANGED_UNKNOWN_HOLD')
            self.fields=[];self.names=list(self.header);self.selected={0:'Drug_ID',1:'Drug'}
        else:
            ordinal=self.counts['physical_data_records'];self.counts['physical_data_records']+=1
            self.counts['field_count_matches_header']+=self.field==3;self.counts['field_count_below_header']+=self.field<3;self.counts['field_count_above_header']+=self.field>3
            self.emit({'dataset':'tdc_admet_group_zip','member_name':self.member,'endpoint':self.member.split('/')[1],
                'original_split':self.member.rsplit('/',1)[-1][:-4],'physical_record_ordinal':ordinal,
                'original_Drug_ID':text(self.values.get(0)),'original_Drug':text(self.values.get(1)),
                'row_width':self.field,'source_identity_state':'EXACT_SOURCE_IDENTITY_COLUMNS' if self.field==3 else 'ROW_WIDTH_UNKNOWN',
                'assay_Y_decoded':False})
        self.values={};self.field=0;self.row_bytes=0;self.started=False
    def summary(self):return {'literal_header':self.header,'record_counts':dict(self.counts),'EOF_complete':self.complete,'decoded_bytes':self.decoded_bytes}


def grammar_proof():
    F.ensure(all(getattr(IdentityCSV,n) is getattr(F.CSVProjection,n) for n in ('feed','finish','append')),'ORIGINAL_GRAMMAR_FUNCTION_OBJECTS')
    return {n:{'filename':getattr(IdentityCSV,n).__code__.co_filename,'first_line':getattr(IdentityCSV,n).__code__.co_firstlineno} for n in ('feed','finish','append')}
