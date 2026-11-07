"""Original grammar method objects, independent source/header/summary seams."""
import collections,stat
from pathlib import PurePosixPath
from workflows.expansion.secondary_missing11_identity_format_probe_v1 import formats as F


class HeaderOnly(F.CSVProjection):
    def __init__(self,member):
        self.source_id='tdc_admet_group_zip:'+member  # No alias to a six-CSV source.
        self.header=None;self.names=[];self.selected={};self.stats={};self.counts=collections.Counter(
          physical_data_records=0,field_count_matches_header=0,field_count_below_header=0,field_count_above_header=0)
        self.field=0;self.fields=[];self.buffer=bytearray();self.field_start=True;self.quoted=False;self.after_quote=False
        self.pending_cr=False;self.started=False;self.row_bytes=0;self.decoded_bytes=0;self.complete=False
    def finish_record(self):
        self.finish_field()
        if self.header is None:
            self.header=[value.decode('utf-8-sig' if i==0 else 'utf-8') for i,value in enumerate(self.fields)]
            self.fields=[];self.names=list(self.header);self.selected={};self.stats={}
        else:
            self.counts['physical_data_records']+=1
            self.counts['field_count_matches_header']+=self.field==len(self.header)
            self.counts['field_count_below_header']+=self.field<len(self.header)
            self.counts['field_count_above_header']+=self.field>len(self.header)
        self.field=0;self.row_bytes=0;self.started=False
    def summary(self):
        header=self.header or []
        return {'literal_header':header,'header_columns':len(header),
            'duplicate_literal_header_names':{k:v for k,v in collections.Counter(header).items() if v>1},
            'record_counts':dict(self.counts),'CSV_EOF_complete':self.complete,'decoded_bytes_traversed':self.decoded_bytes,
            'selected_data_columns':0,'ID_and_SMILES_column_mapping':'UNKNOWN_PENDING_ACTUAL_HEADER_AND_LOADER_REVIEW',
            'data_fields_text_decoded':False,'identity_or_assay_values_persisted':False,'chemical_keys_computed':False,
            'physical_records_are_effective_molecules':False}


def method_proof():
    names=('feed','finish','finish_field','append')
    F.ensure(all(getattr(HeaderOnly,n) is getattr(F.CSVProjection,n) and n not in HeaderOnly.__dict__ for n in names),'ACTUAL_ORIGINAL_GRAMMAR_METHOD_OBJECTS')
    return {n:{'qualified_name':getattr(HeaderOnly,n).__module__+'.'+getattr(HeaderOnly,n).__qualname__,
        'filename':getattr(HeaderOnly,n).__code__.co_filename,'first_line':getattr(HeaderOnly,n).__code__.co_firstlineno} for n in names}


def checked_inventory(infos,expected):
    F.ensure(len(infos)==len(expected)==68,'EXACT68_ZIP_ENTRIES')
    seen=set()
    for info,row in zip(infos,expected):
        p=PurePosixPath(info.filename);F.ensure(info.filename not in seen and '\\' not in info.filename and not p.is_absolute()
            and '..' not in p.parts and not(info.flag_bits&1) and not stat.S_ISLNK(info.external_attr>>16),'DUPLICATE_UNSAFE_ENCRYPTED_OR_LINK_MEMBER_UNKNOWN')
        seen.add(info.filename)
        F.ensure({'name':info.filename,'directory':info.is_dir(),'CRC32':info.CRC,'compressed_bytes':info.compress_size,'uncompressed_bytes':info.file_size}==row,
            'ACTUAL_PHYSICAL_ZIP_ENTRY_DIFFERS_FROM_PRODUCER_METADATA')
        F.ensure(info.compress_type in (0,8),'UNSUPPORTED_ZIP_COMPRESSION_UNKNOWN')
    return True
