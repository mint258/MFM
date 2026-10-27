"""Literal native symbols -> original composition/identity objects; no geometry."""
import collections,hashlib,json,re
from workflows.expansion.identity_v2.projection_v2 import native_composition,identity
from . import contract as C
NUMBER=re.compile(rb'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eEdD][+-]?[0-9]+)?\Z')


def canonical(value):return (json.dumps(value,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def read_frame(stream,ordinal,check):
    check();offset=stream.tell();raw=stream.readline(1024)
    if not raw:return None
    C.Q.need(raw.endswith(b'\n') and raw.strip().isdigit(),'ORIGINAL_BOUNDED_COUNT_LINE')
    count=int(raw.strip());C.Q.need(0<count<=512,'ORIGINAL_NATIVE_ATOM_BOUND')
    frame=hashlib.sha256();frame.update(raw);length=len(raw);comment=stream.readline(1<<20)
    C.Q.need(comment.endswith(b'\n'),'COMPLETE_BOUNDED_OPAQUE_COMMENT');frame.update(comment);length+=len(comment);symbols=collections.Counter()
    for _ in range(count):
        check();line=stream.readline(4096);C.Q.need(line.endswith(b'\n'),'COMPLETE_BOUNDED_ORIGINAL_ATOM_ROW')
        fields=line.split();C.Q.need(len(fields)==4 and re.fullmatch(rb'[A-Z][a-z]?',fields[0])
            and all(NUMBER.fullmatch(v) for v in fields[1:]),'SAME_NATIVE_SYMBOL_AND_THREE_OPAQUE_COORDINATE_TOKENS')
        symbol=fields[0].decode('ascii');C.Q.need(symbol in C.SYMBOL_Z,'SYMBOL_OUTSIDE_ACTUAL1897_SOURCE_UNIVERSE')
        symbols[symbol]+=1;frame.update(line);length+=len(line)
    return {'physical_frame_ordinal':ordinal,'source_offset':offset,'frame_bytes':length,'frame_sha256':frame.hexdigest(),
        'atoms':count,'native_symbol_counts':dict(symbols),'comment_bytes':len(comment),'comment_sha256':hashlib.sha256(comment).hexdigest(),
        'native_author_ID':None,'comment_values_or_coordinate_floats_decoded':False}


def project(source,source_reference):
    ordinal=source['physical_frame_ordinal'];C.Q.need(type(ordinal) is int and ordinal>=0 and source['native_author_ID'] is None,'PHYSICAL_ORDINAL_IS_NOT_AN_INVENTED_NATIVE_ID')
    counts=source['native_symbol_counts'];C.Q.need(counts and set(counts)<=set(C.SYMBOL_Z)
        and all(type(n) is int and n>0 for n in counts.values()) and sum(counts.values())==source['atoms'],'ACTUAL_NATIVE_ELEMENT_COUNT_CONSERVATION')
    native=collections.Counter({C.SYMBOL_Z[symbol]:n for symbol,n in counts.items()});composition=native_composition(native)
    locator=C.NAMESPACE+':physical_frame_ordinal:'+str(ordinal)
    row=identity('qm7b',locator,'all',[],[],composition=composition,reason=C.REASON,unresolved_variant=True)
    row.update(source_record_ordinal=ordinal,source_record_ID_basis=C.PARAMETERS['source_ID_basis'],native_author_ID=None,
        author_release_namespace=C.NAMESPACE,author_source_DOI=C.DOI,original_XYZ_reference=source_reference,
        native_frame_reference={k:source[k] for k in ('source_offset','frame_bytes','frame_sha256')},WP5_keys=[],
        full_key_graph_identity='UNKNOWN_NOT_INFERRED',conservative_composition_fallback=True,exact_MAT_row_mapping=False,
        charge_isotope_stereo_or_chemical_graph_inferred=False,global_pool_training_release=False)
    return row
