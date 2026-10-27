"""Opaque index grammar and exact old relation binding; no graph/target interpretation."""
import collections,gzip,hashlib,json,tarfile
from secondary_external_sources_acquisition_v1.run import StrictTarInfo,Expanded
from secondary_moleculenet_native4_identity_v1.native import token
from . import contracts as C
Q=C.Q;LINE_CAP=16<<20


def decode(raw):
    return json.loads(raw,object_pairs_hook=Q.pairs_unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


class Relations:
    def __init__(self,counts,missing):self.expected=counts;self.expected_missing=missing;self.counts=collections.Counter();self.missing=collections.Counter();self.selected={}
    def feed(self,value,segment):
        sid=value['source_id'];ordinal=value['original_index_ordinal']
        Q.need(sid in self.expected and type(ordinal) is int and ordinal==self.counts[sid] and ordinal<self.expected[sid],'ALL_RELATION_ORDINALS_EXACTLY_ONCE')
        Q.need(type(value['no_native_context_in_all_components']) is bool and value['same_ID_implies_same_graph'] is False
            and value['original_index_row_not_dropped'] is True and value['full_or_pool_release'] is False
            and value['relation_basis']=='ORIGINAL_ORDINAL_OR_EXACT_LITERAL_PDB_ID_ONLY_NOT_GRAPH_EQUIVALENCE','UNCHANGED_RELATION_NOT_GRAPH_EQUIVALENCE')
        Q.need(isinstance(value['matching_existing_native_entities'],list) and value['no_native_context_in_all_components']==(value['matching_existing_native_entities']==[]),'EXACT_RECORDED_MISSING_NATIVE_AXIS')
        self.counts[sid]+=1
        if value['no_native_context_in_all_components']:
            self.missing[sid]+=1;Q.need(sid=='pdbbind_general' and self.missing[sid]<=self.expected_missing[sid],'ONLY_ORIGINAL_GENERAL_GAP_SET')
            Q.need(value['graph_charge_stereo_if_no_native']=='UNKNOWN','ORIGINAL_GRAPH_UNKNOWN_RETAINED')
            self.selected[ordinal]={'relation':value,'relation_input_segment':segment}
            return self.selected[ordinal]
    def finish(self):
        Q.need({s:self.counts[s] for s in self.expected}==self.expected and {s:self.missing[s] for s in self.expected}==self.expected_missing,'WHOLE44510_RELATION_AND27_GAP_CENSUS')
        return self.selected


class Projection:
    def __init__(self,selected,counts):self.selected=selected;self.expected=counts;self.counts=collections.Counter();self.bound={};self.native_rows=0
    def feed(self,value,segment):
        if value['event']=='ORIGINAL_NATIVE_BYTES_AND_ROW_DURABLE_BEFORE_INDEX':self.native_rows+=1;return None
        Q.need(value['event']=='ORIGINAL_INDEX_ID_DURABLE_BEFORE_INDEX','ONLY_ORIGINAL_SOURCE_EVENT_TYPES')
        sid=value['source_id'];ordinal=value['ordinal']
        Q.need(sid in self.expected and type(ordinal) is int and ordinal==self.counts[sid] and ordinal<self.expected[sid],'ALL_ORIGINAL_PROJECTION_ORDINALS_EXACTLY_ONCE');self.counts[sid]+=1
        if sid!='pdbbind_general' or ordinal not in self.selected:return None
        relation=self.selected[ordinal]['relation'];Q.need(ordinal not in self.bound and value['ID']==relation['original_ID'] and value['details']==relation['original_details'],'EXACT_ORIGINAL_ID_DETAILS_TO_RECORDED_GAP')
        Q.need(value['details']['official_rule']=='NON_COMMENT_LINE_FIRST4_BYTES' and type(value['details']['line_bytes']) is int and value['details']['line_bytes']>0,'ORIGINAL_FIRST4_BYTE_RULE')
        self.bound[ordinal]={**self.selected[ordinal],'projection':value,'projection_input_segment':segment};return self.bound[ordinal]
    def finish(self):
        Q.need({s:self.counts[s] for s in self.expected}==self.expected and set(self.bound)==set(self.selected),'WHOLE_SOURCE_ID_CENSUS_AND_ALL27_PROJECTION_BINDINGS');return self.bound


class IndexLines:
    def __init__(self,bound,expected_rows,emit,comment):self.bound=bound;self.expected=expected_rows;self.emit=emit;self.comment=comment;self.n=0;self.comments=0;self.found=set();self.offset=0
    def feed(self,line):
        Q.need(0<len(line)<=1<<20,'BOUNDED_OPAQUE_INDEX_LINE')
        offset=self.offset;self.offset+=len(line)
        if line.startswith(b'#'):self.comment(line,offset);self.comments+=1;return
        ordinal=self.n;self.n+=1;Q.need(self.n<=self.expected,'NO_EXTRA_NONCOMMENT_INDEX_LINES')
        if ordinal not in self.bound:return
        row=self.bound[ordinal];details=row['projection']['details']
        Q.need(token(line[:4])==row['projection']['ID'] and len(line)==details['line_bytes'] and hashlib.sha256(line).hexdigest()==details['line_sha256'],'EXACT_UNMODIFIED_LINE_LENGTH_SHA_ID_AND_ORDINAL')
        Q.need(ordinal not in self.found,'NO_DUPLICATE_SELECTED_LINE');self.emit(line,ordinal,offset,row);self.found.add(ordinal)
    def finish(self):
        Q.need(self.n==self.expected and self.found==set(self.bound),'COMPLETE_ORIGINAL_INDEX_AND27_OPAQUE_LINES');return {'noncomment_rows':self.n,'comment_lines':self.comments,'selected_exact_rows':len(self.found),'member_bytes':self.offset}


def scan_tar(payload,inventory,expected,target,lines,check,progress):
    """Original TAR reader classes, every member compared to old inventory, gzip drained."""
    members=0;regular=0;targets=0;index_result=None
    with gzip.GzipFile(fileobj=payload,mode='rb') as gz:
        expanded=Expanded(gz,check,expected['decoded_bytes'])
        with tarfile.open(fileobj=expanded,mode='r|',ignore_zeros=True,tarinfo=StrictTarInfo,bufsize=10240) as archive:
            for member in archive:
                check();Q.need(members<expected['members'],'NO_ADDED_TAR_MEMBERS')
                old=next(inventory,None);Q.need(old is not None,'NO_MISSING_ORIGINAL_INVENTORY_ROW')
                got={'ordinal':members,'name':member.name,'type_hex':member.type.hex(),'declared_bytes':member.size,
                    'regular_member_bytes_read':0,'regular_member_sha256':None,'linkname':member.linkname if member.issym() or member.islnk() else None,
                    'extracted':False,'identity_or_target_rows_decoded':False}
                if member.isfile():
                    body=archive.extractfile(member);Q.need(body is not None,'ACTUAL_REGULAR_MEMBER_BODY');h=hashlib.sha256();n=0
                    with body:
                        if member.name==target:
                            targets+=1;Q.need(targets==1,'ONE_UNAMBIGUOUS_ORIGINAL_INDEX_MEMBER')
                            while True:
                                check();block=body.readline((1<<20)+1)
                                if not block:break
                                n+=len(block);h.update(block);lines.feed(block)
                            index_result=lines.finish()
                        else:
                            while True:
                                check();block=body.read(1<<20)
                                if not block:break
                                n+=len(block);h.update(block)
                    Q.need(n==member.size,'WHOLE_ORIGINAL_REGULAR_MEMBER_EOF');got['regular_member_bytes_read']=n;got['regular_member_sha256']=h.hexdigest();regular+=n
                Q.need(got==old,'EVERY_CURRENT_TAR_MEMBER_EXACT_ORIGINAL_INVENTORY')
                members+=1;progress.update(tar_members_verified=members,regular_bytes_verified=regular,decoded_bytes_seen=expanded.n)
        while expanded.read(1<<20):pass
        Q.need(next(inventory,None) is None and members==expected['members'] and regular==expected['regular_bytes'] and targets==1
            and expanded.n==expected['decoded_bytes'] and expanded.sha.hexdigest()==expected['decoded_sha256'],'COMPLETE_INVENTORY_GZIP_EOF_CRC_AND_DECODED_SHA')
        return {'all_members_verified':members,'all_regular_member_bytes':regular,'decoded_stream_bytes':expanded.n,'decoded_stream_sha256':expanded.sha.hexdigest(),
            'gzip_EOF_CRC_verified':True,'TAR_files_extracted':False,'original_index':index_result,'original_tar_reader_class_objects_reused':True}
