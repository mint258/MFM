"""Bounded ZIP/CSV structural profile, streaming EOF CRC; no chemistry or extraction."""
from __future__ import annotations
import collections,csv,hashlib,io,pathlib,stat,time,zipfile
from contracts import need


class CountedRaw(io.RawIOBase):
    def __init__(self,source,total,limit,deadline,checkpoint=None):
        self.source=source;self.total=total;self.limit=limit;self.deadline=deadline;self.count=0;self.sha=hashlib.sha256();self.eof=False;self.checkpoint=checkpoint
    def readable(self):return True
    def readinto(self,buffer):
        if self.checkpoint is not None:self.checkpoint()
        need(time.monotonic()<self.deadline,'CSV_PROFILE_FINITE_WALL_BUDGET_STOP')
        block=self.source.read(len(buffer))
        if not block:self.eof=True;return 0
        self.count+=len(block);self.total[0]+=len(block)
        need(self.total[0]<=self.limit,'TOTAL_ZIP_INFLATED_READ_CAP_EXCEEDED')
        self.sha.update(block);buffer[:len(block)]=block;return len(block)


class LimitedLines:
    def __init__(self,text,limits):self.text=text;self.limits=limits;self.lines=0;self.characters=0
    def begin(self):self.lines=0;self.characters=0
    def __iter__(self):return self
    def __next__(self):
        line=self.text.readline(self.limits['max_physical_line_characters']+1)
        if line=='':raise StopIteration
        self.lines+=1;self.characters+=len(line)
        need(len(line)<=self.limits['max_physical_line_characters'] and self.lines<=self.limits['max_physical_lines_per_record']
            and self.characters<=self.limits['max_logical_record_characters'],'BOUNDED_CSV_LOGICAL_RECORD_LIMIT')
        return line


def profile_csv(raw,limits):
    csv.field_size_limit(limits['max_field_characters'])
    buffered=io.BufferedReader(raw,buffer_size=64*1024);text=io.TextIOWrapper(buffered,encoding='utf-8-sig',errors='strict',newline='')
    lines=LimitedLines(text,limits);reader=csv.reader(lines,delimiter=',',quotechar='"',doublequote=True,strict=True)
    lines.begin()
    try:header=next(reader)
    except StopIteration:raise ValueError('CSV_HEADER_MISSING')
    need(0<len(header)<=limits['max_columns'] and all(len(name)<=limits['max_header_name_characters'] for name in header),'CSV_HEADER_BOUNDARY_EXCEEDED')
    widths=collections.Counter();records=0;blank=0;mismatched=0;examples=[]
    status_columns=[(i,name) for i,name in enumerate(header) if name.strip().lower() in {'status','active','is_active','deleted','is_deleted','deleted_at'}]
    literals={str(i):collections.Counter() for i,_ in status_columns};value_truncated={str(i):False for i,_ in status_columns}
    while True:
        lines.begin()
        try:row=next(reader)
        except StopIteration:break
        records+=1;widths[len(row)]+=1
        need(len(row)<=limits['max_columns'],'CSV_COLUMN_CAP_EXCEEDED')
        if not row:blank+=1
        if len(row)!=len(header):
            mismatched+=1
            if len(examples)<20:examples.append({'logical_data_record_ordinal':records,'observed_columns':len(row)})
        for index,name in status_columns:
            if index>=len(row):continue
            value=row[index]
            if len(value)>128:value_truncated[str(index)]=True;continue
            counter=literals[str(index)]
            if value in counter or len(counter)<32:counter[value]+=1
            else:value_truncated[str(index)]=True
    need(raw.eof,'CSV_ZIP_MEMBER_NOT_READ_TO_EOF')
    return {'header':header,'header_count':len(header),'duplicate_header_names':[name for name,n in collections.Counter(header).items() if n>1],
        'logical_data_records_including_blank':records,'blank_logical_records':blank,'nonblank_logical_data_records':records-blank,
        'row_width_histogram':dict(sorted(widths.items())),'row_width_mismatch_records':mismatched,'first20_width_mismatches':examples,
        'status_column_literal_observations':[{'column_index':i,'column_name':name,'literal_counts':dict(literals[str(i)]),
           'values_omitted_or_truncated':value_truncated[str(i)]} for i,name in status_columns],
        'inactive_or_soft_deleted_coverage_proven':False,'logical_molecule_count_claimed':False,
        'encoding':'utf-8-sig strict','delimiter':',','normalized_identity_or_chemistry_performed':False}


def profile_zip(path,limits,deadline,checkpoint=None):
    total=[0];members=[];csv_count=0
    with zipfile.ZipFile(path,'r') as archive:
        infos=archive.infolist();need(0<len(infos)<=limits['max_zip_members'],'BOUNDED_ZIP_MEMBER_COUNT_REQUIRED')
        declared=sum(info.file_size for info in infos)
        need(declared<=limits['max_total_inflated_bytes'],'DECLARED_ZIP_INFLATED_CAP_EXCEEDED')
        for info in infos:
            name=pathlib.PurePosixPath(info.filename)
            need(len(info.filename)<=1024 and not name.is_absolute() and '..' not in name.parts
                and not stat.S_ISLNK(info.external_attr>>16),'UNSUPPORTED_OR_UNSAFE_ZIP_MEMBER_NAME')
            need(not info.flag_bits&1 and info.compress_type in {zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED},'UNSUPPORTED_ENCRYPTED_OR_NON_DEFLATE_ZIP_MEMBER')
            if info.is_dir():
                need(info.file_size==0,'DIRECTORY_ZIP_MEMBER_HAS_BODY');members.append({'name':info.filename,'directory':True});continue
            need(info.compress_size>0 or info.file_size==0,'INVALID_ZIP_COMPRESSED_SIZE')
            with archive.open(info,'r') as member:
                counted=CountedRaw(member,total,limits['max_total_inflated_bytes'],deadline,checkpoint)
                item={'name':info.filename,'declared_uncompressed_bytes':info.file_size,'compressed_bytes':info.compress_size,
                    'zip_crc32_metadata':format(info.CRC,'08x'),'compression_method':info.compress_type}
                if name.suffix.lower()=='.csv':
                    csv_count+=1;need(csv_count<=limits['max_csv_members'],'CSV_MEMBER_COUNT_CAP_EXCEEDED')
                    item['csv']=profile_csv(counted,limits)
                else:
                    buffered=io.BufferedReader(counted,buffer_size=64*1024)
                    while buffered.read(1024**2):pass
                need(counted.eof and counted.count==info.file_size,'FULL_ZIP_MEMBER_LENGTH_OR_EOF_CRC_INCOMPLETE')
                item.update(actual_uncompressed_bytes=counted.count,uncompressed_sha256=counted.sha.hexdigest(),
                    zipfile_crc_verified_by_complete_EOF=True);members.append(item)
    need(csv_count>0,'NO_CSV_MEMBER_IN_OFFICIAL_CSV_ARCHIVE')
    return {'schema':'SECONDARY_COCONUT_ZIP_CSV_PROFILE_V1','status':'ZIP_EOF_CRC_AND_BOUNDED_CSV_STRUCTURE_PROFILE_COMPLETE',
        'members':members,'csv_members':csv_count,'actual_total_inflated_bytes':total[0],
        'csv_files_extracted_to_disk':False,'all_member_EOF_CRC_observed':True,
        'inactive_or_deleted_coverage_proven':False,'release_version_from_month_proven':False,
        'identity_normalization_or_candidate_release_performed':False}
